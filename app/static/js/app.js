let currentPromptsList = [];
let currentPromptId = null;
let currentPromptDetail = null;
let formState = {};
let currentSlideIndex = 0;
let currentTag = 'all';
let currentTab = 'featured';
let currentNavTab = 'image'; // 'image' | 'video' | 'content'
let currentSampleContentIndex = 0;
let usePromptProvider = 'openai';
let searchDebounceTimer = null;
let tagAutocompleteDebounce = null;
let activeDropdownIndex = -1;
let currentAutocompleteItems = [];
let tagRequestSeq = 0;
let createModalCategory = 'image'; // Category selected in create modal
let videoScenes = [{dialogue:'', action:'', camera:''}];
let newVideoUploadedFile = null;

// ==========================================
// Browser Router Functions (HTML5 History API - No '#')
// ==========================================

function parseCurrentRoute() {
    const pathname = window.location.pathname.replace(/\/+$/, '');
    const parts = pathname.split('/').filter(Boolean);

    let tab = null;
    let promptId = null;

    // 1. Check pathname: /image, /video, /content, /character, /image/:id, etc.
    if (parts.length > 0 && (parts[0] === 'image' || parts[0] === 'video' || parts[0] === 'character' || parts[0] === 'content')) {
        tab = parts[0] === 'character' ? 'image' : parts[0];
        if (parts.length > 1 && parts[1]) {
            promptId = decodeURIComponent(parts[1]);
        }
    }

    // 2. Check fallback hash (if user had old hash URL e.g. #content_100, #/content/100, #video/prompt_35)
    if (!tab && window.location.hash) {
        const rawHash = window.location.hash.replace(/^#\/?/, '').trim();
        const hashParts = rawHash.split('/').filter(Boolean);
        if (hashParts.length > 0) {
            if (hashParts[0] === 'image' || hashParts[0] === 'video' || hashParts[0] === 'character' || hashParts[0] === 'content') {
                tab = hashParts[0] === 'character' ? 'image' : hashParts[0];
                if (hashParts[1]) promptId = decodeURIComponent(hashParts[1]);
            } else if (rawHash.startsWith('content_')) {
                tab = 'content';
                promptId = rawHash;
            } else if (rawHash.startsWith('prompt_')) {
                tab = 'image';
                promptId = rawHash;
            }
        }
    }

    // 3. Fallback to localStorage if no route was in the URL bar
    if (!tab) {
        let savedTab = localStorage.getItem('last_active_tab');
        if (savedTab === 'character') savedTab = 'image';
        if (savedTab === 'image' || savedTab === 'video' || savedTab === 'content') {
            tab = savedTab;
            promptId = localStorage.getItem('last_active_prompt_' + tab) || null;
        }
    }

    // 4. Default fallback
    if (!tab) {
        tab = 'image';
    }

    return { tab, promptId };
}

function updateBrowserRoute(tab, promptId = null, replace = true) {
    if (!tab) tab = currentNavTab || 'image';
    if (tab === 'character') tab = 'image';
    const targetPath = promptId ? `/${tab}/${encodeURIComponent(promptId)}` : `/${tab}`;

    if (window.location.pathname !== targetPath || window.location.hash) {
        try {
            if (replace) {
                history.replaceState({ tab, promptId }, '', targetPath);
            } else {
                history.pushState({ tab, promptId }, '', targetPath);
            }
        } catch (e) {
            console.warn('History router error:', e);
        }
    }

    // Persist to localStorage for F5 & tab restore
    try {
        localStorage.setItem('last_active_tab', tab);
        if (promptId) {
            localStorage.setItem('last_active_prompt_' + tab, promptId);
        }
    } catch (e) {}
}

// ==========================================
// AI Connection & Ping State Management
// ==========================================
async function pingAiConnection(manual = false) {
    const dot = document.getElementById('aiStatusDot');
    const text = document.getElementById('aiStatusText');
    const btn = document.getElementById('aiConnectionStatusBtn');
    const icon = document.getElementById('aiStatusIcon');

    if (dot) dot.className = 'w-2 h-2 rounded-full bg-amber-400 animate-ping';
    if (text) text.innerText = manual ? 'AI: Đang ping-pong...' : 'AI: Đang kiểm tra...';
    if (btn) {
        btn.className = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-dark-700/80 hover:bg-dark-700 text-slate-300 border border-dark-600 transition shadow-sm active:scale-95 cursor-pointer';
        btn.title = 'Đang gọi ping-pong thử nghiệm tới AI...';
    }

    try {
        const res = await fetch('/api/ai/ping');
        const data = await res.json();

        if (res.ok && data.status === 'connected') {
            if (dot) dot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-pulse';
            if (text) {
                text.innerHTML = `<span class="text-emerald-300 font-semibold font-mono">${escapeHtml(data.model)}</span> <span class="text-slate-400">• Sẵn sàng</span> <span class="text-slate-500 font-mono text-[10px]">(${data.latency_ms}ms)</span>`;
            }
            if (btn) {
                btn.className = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 transition shadow-sm active:scale-95 cursor-pointer';
                const replyText = data.reply ? ` | Phản hồi ping: "${data.reply}"` : '';
                btn.title = `Mô hình AI: ${data.model} | Ảnh: ${data.image_model} | Độ trễ phản hồi: ${data.latency_ms}ms${replyText}\nURL: ${data.base_url}\n(Nhấp để gọi ping-pong kiểm tra lại)`;
            }
            if (manual) {
                const replySnippet = data.reply ? ` (Reply: "${data.reply}")` : '';
                showToast(`Ping-pong AI thành công! Độ trễ phản hồi thực tế: ${data.latency_ms}ms${replySnippet}`);
            }
        } else {
            const errMsg = data.message || 'Mất kết nối tới AI';
            if (dot) dot.className = 'w-2 h-2 rounded-full bg-rose-500';
            if (text) text.innerText = 'AI: Mất kết nối';
            if (btn) {
                btn.className = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 transition shadow-sm active:scale-95 cursor-pointer';
                btn.title = `${errMsg}\n(Nhấp để thử lại)`;
            }
            if (manual) {
                showToast(`Lỗi kết nối AI: ${errMsg}`);
            }
        }
    } catch (err) {
        if (dot) dot.className = 'w-2 h-2 rounded-full bg-rose-500';
        if (text) text.innerText = 'AI: Lỗi mạng';
        if (btn) {
            btn.className = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 transition shadow-sm active:scale-95 cursor-pointer';
            btn.title = `Lỗi mạng khi ping AI: ${err.message}\n(Nhấp để thử lại)`;
        }
        if (manual) {
            showToast(`Không thể kết nối server để kiểm tra AI: ${err.message}`);
        }
    }
}

// ==========================================
// AI Background Task Definitions & Queue System
// ==========================================
const AI_TASK_DEFINITIONS = {
    suggest_primary: {
        id: 'suggest_primary',
        label: 'Gợi ý thuộc tính',
        cardRunningLabel: 'Đang gợi ý thuộc tính...',
        cardQueuedLabel: 'Chờ gợi ý thuộc tính...',
        buttonId: 'btnSuggestPrimary',
        defaultTitle: 'Dùng AI phân tích ngữ cảnh câu lệnh để tự động chọn & đánh dấu các thuộc tính quan trọng cần nhập hoặc lựa chọn',
        idleHtml: '<i class="fa-solid fa-wand-magic-sparkles text-amber-400 text-[11px]"></i> <span>AI Gợi ý thuộc tính</span>',
        runningHtml: '<i class="fa-solid fa-spinner fa-spin text-amber-400 text-[11px]"></i> <span>Đang gợi ý ngầm...</span>',
        queuedHtml: '<i class="fa-solid fa-clock text-amber-400 text-[11px]"></i> <span>Đang trong hàng đợi...</span>'
    },
    convert_json: {
        id: 'convert_json',
        label: 'Chuyển sang JSON',
        cardRunningLabel: 'Đang chuyển JSON...',
        cardQueuedLabel: 'Chờ chuyển JSON...',
        buttonId: 'convertJsonBtn',
        defaultTitle: 'Chuyển đổi câu lệnh dạng text sang cấu trúc JSON phân cấp',
        idleHtml: '<i class="fa-solid fa-code text-indigo-200"></i> <span>Chuyển sang JSON</span>',
        runningHtml: '<i class="fa-solid fa-spinner fa-spin text-indigo-300"></i> <span>Đang chuyển JSON ngầm...</span>',
        queuedHtml: '<i class="fa-solid fa-clock text-indigo-300"></i> <span>Đang trong hàng đợi...</span>'
    },
    analyze_script: {
        id: 'analyze_script',
        label: 'Phân tích kịch bản',
        cardRunningLabel: 'Đang phân tích kịch bản...',
        cardQueuedLabel: 'Chờ phân tích kịch bản...',
        buttonId: 'analyzeScriptBtn',
        defaultTitle: 'Dùng AI phân tích văn bản gốc thành kịch bản phân cảnh chuẩn điện ảnh',
        idleHtml: '<i class="fa-solid fa-clapperboard text-rose-200"></i> <span>Phân tích kịch bản</span>',
        runningHtml: '<i class="fa-solid fa-spinner fa-spin text-rose-300"></i> <span>Đang phân tích ngầm...</span>',
        queuedHtml: '<i class="fa-solid fa-clock text-rose-300"></i> <span>Đang trong hàng đợi...</span>'
    },
    improve_prompt: {
        id: 'improve_prompt',
        label: 'Cải tiến prompt',
        cardRunningLabel: 'Đang cải tiến...',
        cardQueuedLabel: 'Chờ cải tiến...',
        buttonId: 'improvePromptBtn',
        defaultTitle: 'Cải tiến câu lệnh bằng AI',
        idleHtml: '<i class="fa-solid fa-wand-magic-sparkles text-amber-300"></i> <span>Cải tiến prompt</span>',
        runningHtml: '<i class="fa-solid fa-spinner fa-spin text-emerald-300"></i> <span>Đang cải tiến ngầm...</span>',
        queuedHtml: '<i class="fa-solid fa-clock text-emerald-300"></i> <span>Đang trong hàng đợi...</span>'
    },
    suggest_title: {
        id: 'suggest_title',
        label: 'AI Đặt tên',
        cardRunningLabel: 'Đang đặt tên...',
        cardQueuedLabel: 'Chờ đặt tên...',
        buttonId: 'btnGenerateTitleAI',
        defaultTitle: 'Nhấp để AI tự động đặt lại tiêu đề ngắn gọn, bắt mắt theo nội dung prompt',
        idleHtml: '<i class="fa-solid fa-wand-magic-sparkles text-[11px] text-amber-300 group-hover/btn:rotate-12 transition-transform"></i> <span>AI Đặt tên</span>',
        runningHtml: '<i class="fa-solid fa-circle-notch fa-spin text-[11px] text-amber-300"></i> <span>Đang đặt tên...</span>',
        queuedHtml: '<i class="fa-solid fa-clock text-[11px] text-amber-300"></i> <span>Chờ đặt tên...</span>'
    },
    extract_json_image: {
        id: 'extract_json_image',
        label: 'Trích xuất JSON ảnh',
        cardRunningLabel: 'Đang đọc JSON ảnh...',
        cardQueuedLabel: 'Chờ đọc JSON ảnh...',
        buttonId: 'btnExtractJsonFromImg',
        defaultTitle: 'Gọi AI phân tích ảnh này để lấy JSON gốc và tạo prompt mới',
        idleHtml: '<i class="fa-solid fa-code text-[11px] text-indigo-200"></i> <span>Lấy json từ ảnh này</span>',
        runningHtml: '<i class="fa-solid fa-circle-notch fa-spin text-indigo-200"></i> <span>Đang phân tích...</span>',
        queuedHtml: '<i class="fa-solid fa-clock text-indigo-200"></i> <span>Chờ phân tích...</span>'
    },
    compact_prompt: {
        id: 'compact_prompt',
        label: 'Tối giản Prompt',
        cardRunningLabel: 'Đang tối giản...',
        cardQueuedLabel: 'Chờ tối giản...',
        buttonId: 'btnRegenCompact',
        defaultTitle: 'Tạo lại phiên bản prompt tối giản (≤ 1000 ký tự) bằng AI',
        idleHtml: '<i class="fa-solid fa-arrows-rotate text-[11px] text-amber-300"></i> <span>Tạo lại</span>',
        runningHtml: '<i class="fa-solid fa-spinner fa-spin text-[11px] text-amber-300"></i> <span>Đang tạo...</span>',
        queuedHtml: '<i class="fa-solid fa-clock text-[11px] text-amber-300"></i> <span>Chờ tạo...</span>'
    }
};

const MAX_CONCURRENT_AI_TASKS = 1;
const aiTaskQueue = [];
let isProcessingAiQueue = false;

// Synchronize all buttons in the detail pane strictly according to the specified prompt's state
function syncDetailPaneButtonStates(promptId) {
    for (const [taskType, def] of Object.entries(AI_TASK_DEFINITIONS)) {
        const btn = document.getElementById(def.buttonId);
        if (!btn) continue;

        if (!promptId) {
            btn.disabled = false;
            btn.innerHTML = def.idleHtml;
            if (def.defaultTitle) btn.title = def.defaultTitle;
            continue;
        }

        const task = aiTaskQueue.find(t => t.promptId === promptId && t.taskType === taskType);
        if (task) {
            btn.disabled = true;
            if (task.status === 'running') {
                btn.innerHTML = def.runningHtml;
                btn.title = `${def.label}: Đang xử lý trong nền...`;
            } else if (task.status === 'queued') {
                btn.innerHTML = def.queuedHtml;
                btn.title = `${def.label}: Đang chờ trong hàng đợi...`;
            }
        } else {
            btn.disabled = false;
            btn.innerHTML = def.idleHtml;
            if (def.defaultTitle) btn.title = def.defaultTitle;
        }
    }
}

function updateSidebarCardIndicator(promptId) {
    const card = document.getElementById(`prompt-card-${promptId}`);
    if (!card) return;

    let indicator = card.querySelector('.prompt-card-bg-indicator');
    const runningTask = aiTaskQueue.find(t => t.promptId === promptId && t.status === 'running');
    const queuedTask = aiTaskQueue.find(t => t.promptId === promptId && t.status === 'queued');

    if (runningTask) {
        if (!indicator) {
            indicator = document.createElement('div');
            card.appendChild(indicator);
        }
        indicator.className = 'prompt-card-bg-indicator flex items-center gap-1.5 text-[10px] text-amber-400 font-medium animate-pulse mt-1.5 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 w-fit';
        const def = AI_TASK_DEFINITIONS[runningTask.taskType];
        const label = def ? def.cardRunningLabel : 'Đang xử lý ngầm...';
        indicator.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-[10px]"></i> <span>${label}</span>`;
    } else if (queuedTask) {
        if (!indicator) {
            indicator = document.createElement('div');
            card.appendChild(indicator);
        }
        indicator.className = 'prompt-card-bg-indicator flex items-center gap-1.5 text-[10px] text-cyan-400 font-medium mt-1.5 px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20 w-fit';
        const def = AI_TASK_DEFINITIONS[queuedTask.taskType];
        const label = def ? def.cardQueuedLabel : 'Đang trong hàng đợi...';
        indicator.innerHTML = `<i class="fa-solid fa-clock text-[10px]"></i> <span>${label}</span>`;
    } else {
        if (indicator) {
            indicator.remove();
        }
    }
}

function updateTaskUI(promptId) {
    if (currentPromptId === promptId) {
        syncDetailPaneButtonStates(promptId);
    }
    updateSidebarCardIndicator(promptId);
}

function getPromptCardIndicatorHtml(promptId) {
    const runningTask = aiTaskQueue.find(t => t.promptId === promptId && t.status === 'running');
    if (runningTask) {
        const def = AI_TASK_DEFINITIONS[runningTask.taskType];
        const label = def ? def.cardRunningLabel : 'Đang xử lý ngầm...';
        return `<div class="prompt-card-bg-indicator flex items-center gap-1.5 text-[10px] text-amber-400 font-medium animate-pulse mt-1.5 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 w-fit"><i class="fa-solid fa-spinner fa-spin text-[10px]"></i> <span>${label}</span></div>`;
    }
    const queuedTask = aiTaskQueue.find(t => t.promptId === promptId && t.status === 'queued');
    if (queuedTask) {
        const def = AI_TASK_DEFINITIONS[queuedTask.taskType];
        const label = def ? def.cardQueuedLabel : 'Đang trong hàng đợi...';
        return `<div class="prompt-card-bg-indicator flex items-center gap-1.5 text-[10px] text-cyan-400 font-medium mt-1.5 px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20 w-fit"><i class="fa-solid fa-clock text-[10px]"></i> <span>${label}</span></div>`;
    }
    return '';
}

function updateGlobalBackgroundBadge() {
    const badge = document.getElementById('globalBgTaskBadge');
    const text = document.getElementById('globalBgTaskText');
    if (!badge || !text) return;

    const runningTasks = aiTaskQueue.filter(t => t.status === 'running');
    const queuedTasks = aiTaskQueue.filter(t => t.status === 'queued');
    const total = runningTasks.length + queuedTasks.length;

    if (total > 0) {
        if (runningTasks.length > 0 && queuedTasks.length > 0) {
            text.innerText = `${runningTasks.length} đang chạy (${queuedTasks.length} chờ)`;
        } else if (runningTasks.length > 0) {
            text.innerText = `${runningTasks.length} tác vụ ngầm`;
        } else {
            text.innerText = `${queuedTasks.length} trong hàng đợi`;
        }

        const tooltipList = [
            ...runningTasks.map(t => `[Đang chạy] ${t.promptTitle}: ${AI_TASK_DEFINITIONS[t.taskType]?.label || t.taskType}`),
            ...queuedTasks.map((t, idx) => `[Chờ #${idx + 1}] ${t.promptTitle}: ${AI_TASK_DEFINITIONS[t.taskType]?.label || t.taskType}`)
        ].join('\n');
        badge.title = tooltipList;

        badge.classList.remove('hidden');
        badge.classList.add('inline-flex');
    } else {
        badge.removeAttribute('title');
        badge.classList.add('hidden');
        badge.classList.remove('inline-flex');
    }
}

function hasActiveOrQueuedTask(promptId, taskType = null) {
    if (!taskType) {
        return aiTaskQueue.some(t => t.promptId === promptId);
    }
    return aiTaskQueue.some(t => t.promptId === promptId && t.taskType === taskType);
}

// Legacy alias
function hasBackgroundTask(promptId, taskType = null) {
    return hasActiveOrQueuedTask(promptId, taskType);
}

function enqueueAiTask(promptId, taskType, promptTitle, executeFn) {
    const existing = aiTaskQueue.find(t => t.promptId === promptId && t.taskType === taskType);
    if (existing) {
        showToast(`Tác vụ "${existing.promptTitle}" đã có trong hàng đợi hoặc đang chạy.`);
        return;
    }

    const runningCount = aiTaskQueue.filter(t => t.status === 'running').length;

    const task = {
        id: `${promptId}_${taskType}_${Date.now()}`,
        promptId,
        taskType,
        promptTitle,
        fn: executeFn,
        status: 'queued',
        createdAt: Date.now()
    };

    aiTaskQueue.push(task);
    updateTaskUI(promptId);
    updateGlobalBackgroundBadge();

    const queuedCount = aiTaskQueue.filter(t => t.status === 'queued').length;
    const taskLabel = AI_TASK_DEFINITIONS[taskType]?.label || 'Tác vụ AI';

    if (runningCount === 0) {
        showToast(`Đang thực hiện ${taskLabel} cho "${promptTitle}"... Bạn có thể tiếp tục thao tác item khác.`);
    } else {
        showToast(`Đã xếp ${taskLabel} cho "${promptTitle}" vào hàng đợi (vị trí #${queuedCount})... Bạn có thể tiếp tục thao tác item khác.`);
    }

    processAiTaskQueue();
}

async function processAiTaskQueue() {
    if (isProcessingAiQueue) return;

    const runningCount = aiTaskQueue.filter(t => t.status === 'running').length;
    if (runningCount >= MAX_CONCURRENT_AI_TASKS) return;

    const nextTask = aiTaskQueue.find(t => t.status === 'queued');
    if (!nextTask) return;

    nextTask.status = 'running';
    updateTaskUI(nextTask.promptId);
    updateGlobalBackgroundBadge();

    isProcessingAiQueue = true;
    try {
        await nextTask.fn();
    } catch (err) {
        console.error(`AI Task Error [${nextTask.taskType}] for ${nextTask.promptId}:`, err);
        showToast(`Lỗi tác vụ "${nextTask.promptTitle}": ${err.message || err}`);
    } finally {
        const idx = aiTaskQueue.findIndex(t => t.id === nextTask.id);
        if (idx !== -1) {
            aiTaskQueue.splice(idx, 1);
        }
        updateTaskUI(nextTask.promptId);
        updateGlobalBackgroundBadge();
        isProcessingAiQueue = false;
        setTimeout(processAiTaskQueue, 50);
    }
}

// Backward compatibility helpers
function registerBackgroundTask(promptId, taskType, promptTitle) {
    if (!hasActiveOrQueuedTask(promptId, taskType)) {
        aiTaskQueue.push({
            id: `${promptId}_${taskType}_${Date.now()}`,
            promptId,
            taskType,
            promptTitle,
            fn: () => Promise.resolve(),
            status: 'running',
            createdAt: Date.now()
        });
        updateTaskUI(promptId);
        updateGlobalBackgroundBadge();
    }
}

function unregisterBackgroundTask(promptId, taskType) {
    const idx = aiTaskQueue.findIndex(t => t.promptId === promptId && t.taskType === taskType);
    if (idx !== -1) {
        aiTaskQueue.splice(idx, 1);
        updateTaskUI(promptId);
        updateGlobalBackgroundBadge();
    }
}

function updateBackgroundTaskUI(promptId, taskType, isRunning) {
    updateTaskUI(promptId);
}

// Initialize app on DOM ready with browser router
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    fetchStats();
    pingAiConnection(false); // Ping AI on startup

    // Parse current route from browser URL (Clean path, NO '#')
    const route = parseCurrentRoute();
    if (route.tab !== currentNavTab) {
        switchNavTab(route.tab, route.promptId, false);
        updateBrowserRoute(route.tab, route.promptId, true);
    } else {
        updateBrowserRoute(currentNavTab, route.promptId, true);
        loadPrompts(route.promptId);
    }
});

function initEventListeners() {
    // Search input with debounce
    const searchInput = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearSearchBtn');

    searchInput.addEventListener('input', (e) => {
        const val = e.target.value;
        if (val) {
            clearBtn.classList.remove('hidden');
        } else {
            clearBtn.classList.add('hidden');
        }
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            loadPrompts();
        }, 250);
    });

    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        clearBtn.classList.add('hidden');
        loadPrompts();
    });

    // Mobile sidebar toggle
    const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    if (toggleSidebarBtn && sidebar && sidebarOverlay) {
        toggleSidebarBtn.addEventListener('click', () => {
            sidebar.classList.toggle('-translate-x-full');
            sidebarOverlay.classList.toggle('hidden');
        });
        sidebarOverlay.addEventListener('click', () => {
            sidebar.classList.add('-translate-x-full');
            sidebarOverlay.classList.add('hidden');
        });
    }

    // Inline editable title handling
    const titleEl = document.getElementById('currentPromptTitle');
    if (titleEl) {
        titleEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                titleEl.blur();
            } else if (e.key === 'Escape') {
                if (currentPromptDetail) {
                    titleEl.innerText = currentPromptDetail.title || '';
                }
                titleEl.blur();
            }
        });

        titleEl.addEventListener('blur', async () => {
            if (!currentPromptId || !currentPromptDetail) return;
            const newTitle = titleEl.innerText.trim();
            if (!newTitle) {
                titleEl.innerText = currentPromptDetail.title || '';
                return;
            }
            if (newTitle !== currentPromptDetail.title) {
                try {
                    const res = await fetch(`/api/prompts/${currentPromptId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ title: newTitle })
                    });
                    if (res.ok) {
                        currentPromptDetail.title = newTitle;
                        // Update in local prompts list
                        const found = currentPromptsList.find(p => p.id === currentPromptId);
                        if (found) found.title = newTitle;
                        // Update sidebar card text
                        const cardTitle = document.querySelector(`#prompt-card-${currentPromptId} h4`);
                        if (cardTitle) {
                            cardTitle.innerText = newTitle;
                        }
                        showToast(`Đã lưu tiêu đề: "${newTitle}"`);
                    } else {
                        showToast('Lỗi khi lưu tiêu đề.');
                    }
                } catch (err) {
                    console.error('Error saving title:', err);
                    showToast('Không thể kết nối đến máy chủ.');
                }
            }
        });
    }

    // Initialize lightbox zoom & pan handlers
    initLightboxEvents();

    // Lightbox & Modal keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        const lightboxModal = document.getElementById('lightboxModal');
        const isLightboxOpen = lightboxModal && !lightboxModal.classList.contains('hidden');

        if (e.key === 'Escape') {
            closeLightbox();
            closeCreateModal();
            closeGenerateImageModal();
            closeGenerateVideoModal();
            closeImproveModal();
            closeAddMediaModal();
            closeUsePromptModal();
            closeAddSampleModal();
            closeAiChat();
        } else if (isLightboxOpen) {
            if (e.key === '+' || e.key === '=' || e.code === 'NumpadAdd') {
                e.preventDefault();
                lightboxZoomIn();
            } else if (e.key === '-' || e.key === '_' || e.code === 'NumpadSubtract') {
                e.preventDefault();
                lightboxZoomOut();
            } else if (e.key === '0' || e.code === 'Numpad0') {
                e.preventDefault();
                lightboxResetZoom();
            }
        }
    });

    // Reference image drag & drop setup
    const dropzone = document.getElementById('genRefDropzone');
    if (dropzone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add('border-purple-500', 'bg-purple-500/10');
            });
        });
        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove('border-purple-500', 'bg-purple-500/10');
            });
        });
        dropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt && dt.files;
            if (files && files.length > 0) {
                processRefImageFile(files[0]);
            }
        });
    }

    // Create Modal Image Dropzone setup
    const createDropzone = document.getElementById('createImageDropzone');
    if (createDropzone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            createDropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                createDropzone.classList.add('border-brand-500', 'bg-brand-500/10');
            });
        });
        ['dragleave', 'drop'].forEach(eventName => {
            createDropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                createDropzone.classList.remove('border-brand-500', 'bg-brand-500/10');
            });
        });
        createDropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt && dt.files;
            if (files && files.length > 0) {
                processNewPromptFiles(files);
            }
        });
    }

    // Add Media Modal Dropzone setup
    const addMediaDropzone = document.getElementById('addMediaDropzone');
    if (addMediaDropzone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            addMediaDropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                addMediaDropzone.classList.add('border-brand-500', 'bg-brand-500/10');
            });
        });
        ['dragleave'].forEach(eventName => {
            addMediaDropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                addMediaDropzone.classList.remove('border-brand-500', 'bg-brand-500/10');
            });
        });
        addMediaDropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            addMediaDropzone.classList.remove('border-brand-500', 'bg-brand-500/10');
            const dt = e.dataTransfer;
            const files = dt && dt.files;
            if (files && files.length > 0) {
                processAddMediaFiles(files);
            }
        });
    }

    // Tag input events (Select2-style with Autocomplete)
    const tagInput = document.getElementById('tagInput');
    if (tagInput) {
        tagInput.addEventListener('input', (e) => {
            clearTimeout(tagAutocompleteDebounce);
            const val = e.target.value;
            tagAutocompleteDebounce = setTimeout(() => {
                fetchTagSuggestions(val);
            }, 150);
        });

        tagInput.addEventListener('focus', () => {
            fetchTagSuggestions(tagInput.value);
        });

        tagInput.addEventListener('keydown', (e) => {
            const dropdown = document.getElementById('tagAutocompleteDropdown');
            const isDropdownOpen = dropdown && !dropdown.classList.contains('hidden');

            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                if (isDropdownOpen && activeDropdownIndex >= 0 && currentAutocompleteItems[activeDropdownIndex]) {
                    addPromptTag(currentAutocompleteItems[activeDropdownIndex].tag);
                } else if (tagInput.value.trim()) {
                    addPromptTag(tagInput.value.trim());
                }
            } else if (e.key === 'Backspace') {
                if (!tagInput.value && currentPromptDetail && currentPromptDetail.tags && currentPromptDetail.tags.length > 0) {
                    const lastTag = currentPromptDetail.tags[currentPromptDetail.tags.length - 1];
                    removePromptTag(lastTag);
                }
            } else if (e.key === 'ArrowDown') {
                if (isDropdownOpen && currentAutocompleteItems.length > 0) {
                    e.preventDefault();
                    activeDropdownIndex = (activeDropdownIndex + 1) % currentAutocompleteItems.length;
                    highlightDropdownItem(activeDropdownIndex);
                }
            } else if (e.key === 'ArrowUp') {
                if (isDropdownOpen && currentAutocompleteItems.length > 0) {
                    e.preventDefault();
                    activeDropdownIndex = (activeDropdownIndex - 1 + currentAutocompleteItems.length) % currentAutocompleteItems.length;
                    highlightDropdownItem(activeDropdownIndex);
                }
            } else if (e.key === 'Escape') {
                closeTagAutocomplete();
            }
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            const wrapper = document.getElementById('select2TagsWrapper');
            if (wrapper && !wrapper.contains(e.target)) {
                closeTagAutocomplete();
            }
        });
    }

    // Browser router popstate listener (Back / Forward buttons, URL path changes)
    window.addEventListener('popstate', (event) => {
        const route = parseCurrentRoute();
        if (route.tab !== currentNavTab) {
            switchNavTab(route.tab, route.promptId, false);
        } else if (route.promptId && route.promptId !== currentPromptId) {
            selectPrompt(route.promptId, false);
        }
    });

    // Initialize AI Search Assistant Chat events
    initAiChatListeners();
}

// Fetch stats from backend
async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        if (res.ok) {
            const stats = await res.json();
            const total = stats.total_prompts || 0;
            const byCat = stats.by_category || {};
            const imgCount = byCat.image !== undefined ? byCat.image : 0;
            const vidCount = byCat.video !== undefined ? byCat.video : 0;
            const contCount = byCat.content !== undefined ? byCat.content : 0;

            // Cập nhật Slogan với tổng số câu lệnh
            const sloganCount = document.getElementById('sloganPromptCount');
            if (sloganCount) {
                sloganCount.innerText = total;
            }
            const headerSlogan = document.getElementById('headerSlogan');
            if (headerSlogan && !sloganCount) {
                headerSlogan.innerText = `Quản lý & Tùy biến câu lệnh (${total} prompts)`;
            }

            // Cập nhật số lượng trên các tab Image, Video, Content
            const tabImgText = document.getElementById('navTabImageText');
            if (tabImgText) {
                tabImgText.innerText = `Image (${imgCount})`;
            }

            const tabVidText = document.getElementById('navTabVideoText');
            if (tabVidText) {
                tabVidText.innerText = `Video (${vidCount})`;
            }

            const tabContText = document.getElementById('navTabContentText');
            if (tabContText) {
                tabContText.innerText = `Content (${contCount})`;
            }

            const badge = document.getElementById('promptCountBadge');
            if (badge) {
                badge.innerText = `${total} Câu lệnh`;
            }
        }
    } catch (err) {
        console.error('Failed to fetch stats:', err);
    }
}

// Load prompts list
async function loadPrompts(selectedIdToKeep = null) {
    const q = document.getElementById('searchInput').value.trim();
    const url = new URL('/api/prompts', window.location.origin);
    if (q) url.searchParams.set('q', q);
    if (currentTag && currentTag !== 'all') url.searchParams.set('tag', currentTag);
    url.searchParams.set('category', currentNavTab);

    const listEl = document.getElementById('promptList');
    listEl.innerHTML = `
        <div class="p-8 text-center text-slate-500 text-sm">
            <i class="fa-solid fa-circle-notch fa-spin text-brand-500 text-2xl mb-2"></i>
            <p>Đang tải danh sách...</p>
        </div>
    `;

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('Network error');
        const data = await res.json();
        currentPromptsList = data.items || [];

        renderPromptList(currentPromptsList);

        // Update count display
        const displayCountText = document.getElementById('displayCountText');
        if (displayCountText) {
            displayCountText.innerText = `Hiển thị ${currentPromptsList.length} câu lệnh`;
        }

        let targetId = null;
        if (selectedIdToKeep && currentPromptsList.some(p => p.id === selectedIdToKeep)) {
            targetId = selectedIdToKeep;
        } else {
            const route = parseCurrentRoute();
            if (route.tab === currentNavTab && route.promptId && currentPromptsList.some(p => p.id === route.promptId)) {
                targetId = route.promptId;
            } else {
                const savedPrompt = localStorage.getItem('last_active_prompt_' + currentNavTab);
                if (savedPrompt && currentPromptsList.some(p => p.id === savedPrompt)) {
                    targetId = savedPrompt;
                } else if (currentPromptsList.length > 0) {
                    targetId = currentPromptsList[0].id;
                }
            }
        }

        if (targetId) {
            selectPrompt(targetId, true);
        } else {
            renderEmptyDetail();
        }
    } catch (err) {
        console.error('Error loading prompts:', err);
        listEl.innerHTML = `
            <div class="p-6 text-center text-red-400 text-xs">
                <i class="fa-solid fa-triangle-exclamation text-xl mb-2"></i>
                <p>Không thể tải dữ liệu từ máy chủ.</p>
            </div>
        `;
    }
}

function renderPromptList(items) {
    const listEl = document.getElementById('promptList');
    if (!items || items.length === 0) {
        listEl.innerHTML = `
            <div class="p-8 text-center text-slate-500 text-sm">
                <i class="fa-regular fa-folder-open text-2xl mb-2"></i>
                <p>Không tìm thấy câu lệnh phù hợp</p>
            </div>
        `;
        return;
    }

    listEl.innerHTML = items.map((item, idx) => {
        const isJson = item.prompt_type === 'json' || item.parsed_json;
        const imgCount = item.image_count || (item.images ? item.images.length : 0);
        const sampleCount = item.sample_count || 0;
        const bgIndicator = getPromptCardIndicatorHtml(item.id);

        const rawContent = item.original_raw_content || item.raw_content || item.prompt_code || '';
        const rawChars = rawContent.length;

        const isDifferentCategory = item.category && item.category !== currentNavTab;
        const categoryBadgeHtml = isDifferentCategory ? `
            <span class="text-[9px] px-1.5 py-0.5 rounded font-bold font-mono ${
                item.category === 'video' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' :
                item.category === 'content' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30' :
                'bg-purple-500/20 text-purple-300 border border-purple-500/30'
            }" title="Câu lệnh này đã được chuyển sang danh mục: ${item.category}">
                ${item.category === 'video' ? '🎬 Video' : (item.category === 'content' ? '📝 Bài viết' : '📸 Ảnh')}
            </span>
        ` : '';

        return `
            <div onclick="selectPrompt('${item.id}')" id="prompt-card-${item.id}"
                 class="prompt-card group p-3 rounded-xl cursor-pointer transition-all duration-200 hover:bg-dark-700/70 border border-transparent hover:border-dark-600">
                <div class="flex items-start justify-between gap-2 mb-1.5">
                    <span class="text-[11px] font-mono font-semibold px-2 py-0.5 rounded bg-dark-900 text-slate-400 border border-dark-700 group-hover:border-slate-600">
                        #${idx + 1}
                    </span>
                    <div class="flex items-center gap-1.5 flex-wrap justify-end">
                        ${categoryBadgeHtml}
                        ${imgCount > 0 ? `
                            <span class="text-[10px] px-1.5 py-0.5 rounded bg-dark-900/90 text-amber-400/90 border border-amber-500/20 flex items-center gap-1 font-mono">
                                <i class="fa-solid fa-image text-[9px]"></i> ${imgCount}
                            </span>
                        ` : ''}
                        ${sampleCount > 0 ? `
                            <span class="text-[10px] px-1.5 py-0.5 rounded bg-dark-900/90 text-cyan-400 border border-cyan-500/20 flex items-center gap-1 font-mono">
                                <i class="fa-solid fa-file-lines text-[9px]"></i> ${sampleCount} Mẫu
                            </span>
                        ` : ''}
                        <span class="text-[10px] px-1.5 py-0.5 rounded font-medium ${isJson ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'bg-slate-700/50 text-slate-300'}">
                            ${isJson ? 'JSON' : 'TEXT'}
                        </span>
                    </div>
                </div>
                <h4 class="text-xs font-medium text-slate-200 group-hover:text-white line-clamp-2 leading-relaxed">
                    ${escapeHtml(item.title)}
                </h4>
                ${bgIndicator}
                ${item.note ? `
                    <p class="text-[11px] text-slate-400 mt-1 line-clamp-2 leading-tight flex items-start gap-1">
                        <i class="fa-solid fa-note-sticky text-amber-400/80 text-[10px] mt-0.5 flex-shrink-0"></i>
                        <span>${escapeHtml(item.note)}</span>
                    </p>
                ` : ''}
                <div class="flex items-center justify-between gap-1.5 mt-2 pt-1 border-t border-dark-750/50 text-[10px]">
                    <div class="sidebar-card-tags flex items-center gap-1 flex-wrap min-w-0">
                        ${item.tags && item.tags.length > 0 ? `
                            ${item.tags.slice(0, 2).map(t => `<span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-dark-900/80 text-brand-400 border border-brand-500/20 truncate max-w-[85px]">#${escapeHtml(t)}</span>`).join('')}
                            ${item.tags.length > 2 ? `<span class="text-[9px] font-mono text-slate-500">+${item.tags.length - 2}</span>` : ''}
                        ` : '<span class="text-[10px] text-slate-600/70">--</span>'}
                    </div>
                    <span class="text-[10px] font-mono text-slate-400 flex items-center gap-1 ml-auto shrink-0 group-hover:text-emerald-400 transition-colors" title="Độ dài văn bản gốc (Raw / Gốc): ${rawChars} ký tự">
                        <i class="fa-solid fa-align-left text-[9px] text-slate-500"></i>
                        <span>${rawChars.toLocaleString()} chars</span>
                    </span>
                </div>
            </div>
        `;
    }).join('');
}

// ==========================================
// Detail Pane Loading Backdrop Helpers
// ==========================================
let detailLoadingStartTime = 0;

function showDetailLoading() {
    const backdrop = document.getElementById('detailLoadingBackdrop');
    const card = document.getElementById('detailLoadingCard');
    if (!backdrop) return;
    detailLoadingStartTime = Date.now();
    backdrop.classList.remove('hidden', 'pointer-events-none');
    requestAnimationFrame(() => {
        backdrop.classList.remove('opacity-0');
        backdrop.classList.add('opacity-100');
        if (card) {
            card.classList.remove('scale-95');
            card.classList.add('scale-100');
        }
    });
}

function hideDetailLoading(minDuration = 120) {
    const backdrop = document.getElementById('detailLoadingBackdrop');
    const card = document.getElementById('detailLoadingCard');
    if (!backdrop) return;

    const elapsed = Date.now() - detailLoadingStartTime;
    const remaining = Math.max(0, minDuration - elapsed);

    setTimeout(() => {
        backdrop.classList.remove('opacity-100');
        backdrop.classList.add('opacity-0');
        if (card) {
            card.classList.remove('scale-100');
            card.classList.add('scale-95');
        }
        setTimeout(() => {
            if (backdrop.classList.contains('opacity-0')) {
                backdrop.classList.add('hidden', 'pointer-events-none');
            }
        }, 200);
    }, remaining);
}

function highlightActivePromptCard(promptId, scrollIntoView = false) {
    if (!promptId) return;
    document.querySelectorAll('.prompt-card').forEach(el => {
        el.classList.remove('bg-dark-700', 'border-brand-500/50', 'ring-1', 'ring-brand-500/30', 'bg-gradient-to-r', 'from-brand-950/40', 'to-dark-700');
    });
    const activeEl = document.getElementById(`prompt-card-${promptId}`);
    if (activeEl) {
        activeEl.classList.add('bg-dark-700', 'border-brand-500/50', 'ring-1', 'ring-brand-500/30');
        if (scrollIntoView) {
            activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
}

async function selectPrompt(promptId, updateRoute = true) {
    if (!promptId) return;
    currentPromptId = promptId;

    // Immediately synchronize detail button states for the newly selected prompt
    syncDetailPaneButtonStates(promptId);

    // Update browser URL (clean path, NO '#')
    if (updateRoute) {
        updateBrowserRoute(currentNavTab, promptId, true);
    }

    // Highlight active in sidebar and scroll card into view
    highlightActivePromptCard(promptId, true);

    // Close mobile sidebar if open
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    if (sidebar && !sidebar.classList.contains('-translate-x-full')) {
        sidebar.classList.add('-translate-x-full');
        if (sidebarOverlay) sidebarOverlay.classList.add('hidden');
    }

    // Hiển thị loading có backdrop ở khung bên phải
    showDetailLoading();

    try {
        const res = await fetch(`/api/prompts/${promptId}`);
        if (!res.ok) throw new Error('Failed to fetch prompt detail');
        currentPromptDetail = await res.json();
        renderDetail(currentPromptDetail);
    } catch (err) {
        console.error('Error fetching prompt detail:', err);
        showToast('Lỗi khi tải chi tiết câu lệnh');
    } finally {
        hideDetailLoading();
    }
}

function renderDetail(prompt) {
    if (!prompt) return;
    currentPromptDetail = prompt;
    if (prompt.id) currentPromptId = prompt.id;

    // Header info
    const isJson = prompt.prompt_type === 'json' || prompt.parsed_json;

    // Show AI convert button only for image category raw text
    const promptCat = prompt.category || 'image';
    const convertBtn = document.getElementById('convertJsonBtn');
    if (convertBtn) {
        if (!isJson && promptCat === 'image') {
            convertBtn.classList.remove('hidden');
        } else {
            convertBtn.classList.add('hidden');
        }
    }

    // Show "Phân tích kịch bản" button only for video category
    const analyzeBtn = document.getElementById('analyzeScriptBtn');
    if (analyzeBtn) {
        if (promptCat === 'video') {
            analyzeBtn.classList.remove('hidden');
        } else {
            analyzeBtn.classList.add('hidden');
        }
    }

    // Hide compact tab & button for video and content
    const btnViewCompact = document.getElementById('btnViewCompact');
    const btnRegenCompact = document.getElementById('btnRegenCompact');
    const btnExtractJson = document.getElementById('btnExtractJsonFromImg');
    if (promptCat === 'video' || promptCat === 'content') {
        if (btnViewCompact) btnViewCompact.classList.add('hidden');
        if (btnRegenCompact) {
            btnRegenCompact.classList.add('hidden');
            btnRegenCompact.classList.remove('flex');
        }
        if (btnExtractJson) btnExtractJson.classList.add('hidden');
    } else {
        if (btnViewCompact) btnViewCompact.classList.remove('hidden');
        if (btnExtractJson) btnExtractJson.classList.remove('hidden');
    }

    const images = prompt.images || [];
    const samples = prompt.sample_contents || [];
    const hasImages = (images && images.length > 0);
    const hasSamples = (samples && samples.length > 0);

    let isContent = false;
    if (currentNavTab === 'content') {
        isContent = true;
    } else if (currentNavTab === 'video') {
        isContent = !hasImages && hasSamples;
    } else {
        isContent = (prompt.category === 'content' && !hasImages);
    }

    document.getElementById('currentPromptTitle').innerText = prompt.title || 'Không có tiêu đề';

    // Render Select2-style Tags
    renderPromptTags(prompt.tags || []);
    closeTagAutocomplete();
    const tagInputEl = document.getElementById('tagInput');
    if (tagInputEl) tagInputEl.value = '';

    // Initialize Form State
    formState = {};
    if (prompt.fields && prompt.fields.length > 0) {
        prompt.fields.forEach(f => {
            formState[f.path] = f.value !== undefined ? f.value : '';
        });
    }

    // Toggle Content vs Character view elements
    const genImageBtn = document.getElementById('generateImageBtn');
    const genImageActionSection = document.getElementById('genImageActionSection');
    const imageSliderContainer = document.getElementById('imageSliderContainer');
    const sampleContentContainer = document.getElementById('sampleContentContainer');
    const usePromptActionSection = document.getElementById('usePromptActionSection');

    if (isContent) {
        if (genImageBtn) genImageBtn.classList.add('hidden');
        if (genImageActionSection) genImageActionSection.classList.add('hidden');
        if (imageSliderContainer) imageSliderContainer.classList.add('hidden');
        if (sampleContentContainer) sampleContentContainer.classList.remove('hidden');
        if (usePromptActionSection) usePromptActionSection.classList.remove('hidden');

        currentSampleContentIndex = 0;
        renderSampleContent(samples);
    } else {
        if (genImageBtn) genImageBtn.classList.remove('hidden');
        if (genImageActionSection) genImageActionSection.classList.remove('hidden');
        if (imageSliderContainer) imageSliderContainer.classList.remove('hidden');
        if (sampleContentContainer) sampleContentContainer.classList.add('hidden');
        if (usePromptActionSection) usePromptActionSection.classList.add('hidden');

        // Toggle "Tạo ảnh với AI" vs "Tạo Video với AI"
        const genImageBtnText = document.getElementById('genImageBtnText');
        const genImageBtnIcon = document.getElementById('genImageBtnIcon');
        if (promptCat === 'video') {
            if (genImageBtn) {
                genImageBtn.className = "w-full py-3 px-4 rounded-xl bg-gradient-to-r from-rose-600 via-pink-600 to-purple-600 hover:from-rose-500 hover:via-pink-500 hover:to-purple-500 text-white font-bold text-sm shadow-xl shadow-rose-600/25 flex items-center justify-center gap-2.5 transition transform active:scale-[0.98]";
            }
            if (genImageBtnText) genImageBtnText.textContent = "Tạo Video với AI";
            if (genImageBtnIcon) genImageBtnIcon.className = "fa-solid fa-film text-amber-300 text-sm";
        } else {
            if (genImageBtn) {
                genImageBtn.className = "w-full py-3 px-4 rounded-xl bg-gradient-to-r from-purple-600 via-pink-600 to-indigo-600 hover:from-purple-500 hover:via-pink-500 hover:to-indigo-500 text-white font-bold text-sm shadow-xl shadow-purple-600/25 flex items-center justify-center gap-2.5 transition transform active:scale-[0.98]";
            }
            if (genImageBtnText) genImageBtnText.textContent = "Tạo ảnh với AI";
            if (genImageBtnIcon) genImageBtnIcon.className = "fa-solid fa-wand-magic-sparkles text-amber-300 text-sm animate-pulse";
        }

        // Render Image/Video Slider
        currentSlideIndex = 0;
        renderSlider(images);
    }

    // Render Dynamic Form
    renderDynamicForm(prompt.fields || []);

    // Render Code Display and Tab Sync (luôn mặc định là tab 'live' - Prompt tùy biến khi vào item mới)
    setCodeViewMode('live');

    // Sync background and queued task state on the buttons for this prompt
    syncDetailPaneButtonStates(prompt.id);
}

function renderSlider(images) {
    const sliderImg = document.getElementById('currentSliderImg');
    const sliderVideo = document.getElementById('currentSliderVideo');
    const noImgPlaceholder = document.getElementById('noImgPlaceholder');
    const sliderCounter = document.getElementById('sliderCounter');
    const thumbnailsContainer = document.getElementById('sliderThumbnails');
    const prevBtn = document.getElementById('sliderPrevBtn');
    const nextBtn = document.getElementById('sliderNextBtn');
    const expandBtn = document.getElementById('sliderExpandBtn');

    if (!images || images.length === 0) {
        sliderImg.classList.add('hidden');
        if (sliderVideo) {
            sliderVideo.classList.add('hidden');
            sliderVideo.pause();
        }
        noImgPlaceholder.classList.remove('hidden');
        noImgPlaceholder.classList.add('flex');
        sliderCounter.innerText = '0 / 0';
        thumbnailsContainer.innerHTML = '';
        prevBtn.classList.add('hidden');
        nextBtn.classList.add('hidden');
        expandBtn.classList.add('hidden');
        return;
    }

    noImgPlaceholder.classList.add('hidden');
    noImgPlaceholder.classList.remove('flex');
    expandBtn.classList.remove('hidden');

    if (images.length > 1) {
        prevBtn.classList.remove('hidden');
        nextBtn.classList.remove('hidden');
    } else {
        prevBtn.classList.add('hidden');
        nextBtn.classList.add('hidden');
    }

    updateSlideImage(images, currentSlideIndex);

    // Thumbnails
    if (images.length > 1) {
        thumbnailsContainer.innerHTML = images.map((img, idx) => {
            const imgSrc = getImageSource(img);
            return `
                <button onclick="goToSlide(${idx})" id="thumb-${idx}"
                        class="w-14 h-14 rounded-lg overflow-hidden border-2 flex-shrink-0 transition-all ${idx === currentSlideIndex ? 'border-brand-500 scale-105 shadow-md shadow-brand-500/30' : 'border-dark-700 opacity-60 hover:opacity-100'}">
                    <img src="${imgSrc}" class="w-full h-full object-cover" onerror="handleThumbError(this)">
                </button>
            `;
        }).join('');
    } else {
        thumbnailsContainer.innerHTML = '';
    }
}

function getImageSource(img) {
    if (typeof img === 'string') return img;
    if (img.status === 'downloaded' && img.filename) {
        return `/media/${img.filename}`;
    }
    return img.url || '';
}

function updateSlideImage(images, index) {
    if (!images || images.length === 0) return;
    const imgObj = images[index];
    const src = getImageSource(imgObj);
    const sliderImg = document.getElementById('currentSliderImg');
    const sliderVideo = document.getElementById('currentSliderVideo');
    const isVideo = !!(src && src.match(/\.(mp4|webm|mov|avi)(\?.*)?$/i));

    if (isVideo && sliderVideo) {
        if (sliderImg) sliderImg.classList.add('hidden');
        sliderVideo.classList.remove('hidden');
        if (sliderVideo.src !== src) {
            sliderVideo.src = src;
        }
    } else {
        if (sliderVideo) {
            sliderVideo.classList.add('hidden');
            sliderVideo.pause();
        }
        if (sliderImg) {
            sliderImg.classList.remove('hidden');
            sliderImg.src = src;
            sliderImg.dataset.remoteUrl = typeof imgObj === 'object' ? imgObj.url : imgObj;
        }
    }

    document.getElementById('sliderCounter').innerText = `${index + 1} / ${images.length}`;

    // Update thumbnail border
    images.forEach((_, idx) => {
        const thumb = document.getElementById(`thumb-${idx}`);
        if (thumb) {
            if (idx === index) {
                thumb.className = "w-14 h-14 rounded-lg overflow-hidden border-2 border-brand-500 scale-105 shadow-md shadow-brand-500/30 flex-shrink-0 transition-all";
            } else {
                thumb.className = "w-14 h-14 rounded-lg overflow-hidden border-2 border-dark-700 opacity-60 hover:opacity-100 flex-shrink-0 transition-all";
            }
        }
    });
}

function prevSlide() {
    const images = currentPromptDetail?.images || [];
    if (images.length <= 1) return;
    currentSlideIndex = (currentSlideIndex - 1 + images.length) % images.length;
    updateSlideImage(images, currentSlideIndex);
}

function nextSlide() {
    const images = currentPromptDetail?.images || [];
    if (images.length <= 1) return;
    currentSlideIndex = (currentSlideIndex + 1) % images.length;
    updateSlideImage(images, currentSlideIndex);
}

function goToSlide(index) {
    const images = currentPromptDetail?.images || [];
    currentSlideIndex = index;
    updateSlideImage(images, currentSlideIndex);
}

function handleImgError(img) {
    // If local image fails, fallback to remote URL
    if (img.dataset.remoteUrl && img.src !== img.dataset.remoteUrl) {
        img.src = img.dataset.remoteUrl;
    } else {
        img.src = "https://placehold.co/600x600/1e293b/64748b?text=Image+Unavailable";
    }
}

function handleThumbError(img) {
    img.src = "https://placehold.co/100x100/1e293b/64748b?text=Img";
}

// Render dynamic parameter form
function renderDynamicForm(fields) {
    const formEl = document.getElementById('dynamicParamForm');
    const allCountBadge = document.getElementById('allFieldsCount');
    const featuredCountBadge = document.getElementById('featuredFieldsCount');

    const primaryFields = (fields || []).filter(f => f.is_primary);
    if (allCountBadge) allCountBadge.innerText = (fields || []).length;
    if (featuredCountBadge) featuredCountBadge.innerText = primaryFields.length;

    const promptCat = (currentPromptDetail && currentPromptDetail.category) || 'image';
    const isImagePrompt = (promptCat === 'image' || promptCat === 'character');
    const needsRef = currentPromptDetail && !!currentPromptDetail.requires_reference;

    // 1. Configuration header for 'all' tab (Chuyển đổi Category & Toggle yêu cầu ảnh tham chiếu)
    const allTabConfigHtml = `
        <div class="p-3.5 rounded-xl bg-gradient-to-r from-dark-900 via-dark-850 to-dark-900 border border-dark-700/80 hover:border-dark-600 transition space-y-3 mb-3 shadow-md">
            <!-- 1.1 Category Switcher -->
            <div class="flex items-center justify-between gap-2.5 flex-wrap">
                <div class="flex items-center gap-2 min-w-0">
                    <div class="w-7 h-7 rounded-lg bg-brand-500/15 text-brand-400 flex items-center justify-center flex-shrink-0 border border-brand-500/20">
                        <i class="fa-solid fa-shapes text-xs"></i>
                    </div>
                    <div>
                        <div class="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                            <span>Danh mục (Category)</span>
                            <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-dark-800 text-slate-400 border border-dark-700">Phân loại</span>
                        </div>
                        <p class="text-[11px] text-slate-400">Chọn danh mục phù hợp cho câu lệnh này</p>
                    </div>
                </div>

                <div class="flex items-center bg-dark-950 p-1 rounded-lg border border-dark-700 text-xs gap-1">
                    <button type="button" onclick="updateCurrentPromptCategory('image')"
                            class="px-2.5 py-1 rounded-md font-medium transition flex items-center gap-1.5 ${promptCat === 'image' || promptCat === 'character' ? 'bg-purple-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'}"
                            title="Chuyển sang danh mục Hình ảnh">
                        <i class="fa-solid fa-image text-[10px]"></i>
                        <span>Hình ảnh</span>
                    </button>
                    <button type="button" onclick="updateCurrentPromptCategory('video')"
                            class="px-2.5 py-1 rounded-md font-medium transition flex items-center gap-1.5 ${promptCat === 'video' ? 'bg-gradient-to-r from-rose-600 to-pink-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'}"
                            title="Chuyển sang danh mục Video">
                        <i class="fa-solid fa-clapperboard text-[10px]"></i>
                        <span>Video</span>
                    </button>
                    <button type="button" onclick="updateCurrentPromptCategory('content')"
                            class="px-2.5 py-1 rounded-md font-medium transition flex items-center gap-1.5 ${promptCat === 'content' ? 'bg-cyan-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'}"
                            title="Chuyển sang danh mục Bài viết">
                        <i class="fa-solid fa-file-lines text-[10px]"></i>
                        <span>Bài viết</span>
                    </button>
                </div>
            </div>

            <!-- Divider -->
            <div class="border-t border-dark-750/70"></div>

            <!-- 1.2 Reference Toggle -->
            <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-2 min-w-0">
                    <div class="w-7 h-7 rounded-lg bg-purple-500/15 text-purple-400 flex items-center justify-center flex-shrink-0 border border-purple-500/20">
                        <i class="fa-solid fa-camera-retro text-xs"></i>
                    </div>
                    <div class="min-w-0">
                        <div class="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                            <span>Cần ảnh tham chiếu</span>
                            <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-purple-500/15 text-purple-300 border border-purple-500/25">Reference Image</span>
                        </div>
                        <p class="text-[11px] text-slate-400 truncate">Bật nếu câu lệnh cần có ảnh mẫu đối chiếu khi tạo ảnh / video</p>
                    </div>
                </div>
                <label class="relative inline-flex items-center cursor-pointer flex-shrink-0" title="Bật/tắt yêu cầu ảnh tham chiếu">
                    <input type="checkbox" id="toggleRequiresReferenceInput" onchange="togglePromptRequiresReference(this.checked)" class="sr-only peer" ${needsRef ? 'checked' : ''}>
                    <div class="w-9 h-5 bg-dark-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
                </label>
            </div>
        </div>
    `;

    // 2. Reference notice banner for 'featured' tab (displayed when requires_reference is ON)
    const refBannerHtml = (needsRef) ? `
        <div class="p-3 rounded-xl bg-gradient-to-r from-purple-950/40 via-purple-900/20 to-dark-900/60 border border-purple-500/35 text-purple-200 text-xs flex items-start gap-2.5 shadow-sm mb-2">
            <div class="w-6 h-6 rounded-lg bg-purple-500/20 text-purple-300 flex items-center justify-center flex-shrink-0 mt-0.5 border border-purple-500/30">
                <i class="fa-solid fa-camera-retro text-[11px]"></i>
            </div>
            <div class="flex-1 min-w-0">
                <div class="font-bold text-purple-300 flex items-center gap-1.5">
                    <span>Yêu cầu ảnh tham chiếu (Reference Image)</span>
                    <span class="text-[9px] font-mono font-medium px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-200 border border-purple-500/30">Bắt buộc</span>
                </div>
                <p class="text-slate-300 text-[11px] mt-0.5 leading-relaxed">
                    Prompt này yêu cầu có ảnh mẫu tham chiếu. Hãy chuẩn bị hoặc sử dụng ảnh mẫu đi kèm khi tạo ảnh với AI.
                </p>
            </div>
        </div>
    ` : '';

    if (!fields || fields.length === 0) {
        formEl.innerHTML = `
            ${currentTab === 'all' ? allTabConfigHtml : refBannerHtml}
            <div class="p-6 text-center text-slate-500 text-xs">
                <i class="fa-solid fa-list-check text-xl mb-1 text-slate-600"></i>
                <p>Không có trường tham số động cho câu lệnh này.</p>
            </div>
        `;
        return;
    }

    let displayedFields = fields;
    if (currentTab === 'featured') {
        displayedFields = primaryFields;
        if (displayedFields.length === 0) {
            formEl.innerHTML = `
                ${refBannerHtml}
                <div class="p-8 text-center text-slate-400 text-xs space-y-3">
                    <i class="fa-regular fa-star text-2xl text-amber-400/80 mb-1"></i>
                    <p class="font-semibold text-slate-200">Chưa có thuộc tính chính nào được đánh dấu</p>
                    <p class="text-slate-400 max-w-sm mx-auto leading-relaxed">Hệ thống có thể tự động phân tích những trường cần truyền nội dung hoặc lựa chọn giá trị để đánh dấu cho bạn.</p>
                    <div class="flex items-center justify-center gap-2 pt-1 flex-wrap">
                        <button type="button" onclick="suggestAndMarkPrimaryFields()"
                                class="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white text-xs font-semibold shadow-md shadow-amber-600/20 transition flex items-center gap-1.5 active:scale-95">
                            <i class="fa-solid fa-wand-magic-sparkles text-xs"></i>
                            <span>Gợi ý thuộc tính chính ngay</span>
                        </button>
                        <button type="button" onclick="setFormTab('all')" class="px-3.5 py-1.5 rounded-lg bg-dark-700 hover:bg-dark-600 text-slate-300 text-xs font-medium transition">
                            Xem toàn bộ trường (${fields.length})
                        </button>
                    </div>
                </div>
            `;
            return;
        }
    }

    function renderSingleFieldHtml(field) {
        const val = formState[field.path] !== undefined ? formState[field.path] : field.value;
        const isTextarea = field.type === 'textarea' || (val && val.length > 50);
        const isPrimary = !!field.is_primary;

        return `
            <div class="space-y-1.5 p-3 rounded-xl bg-dark-900/60 border ${isPrimary ? 'border-amber-500/25' : 'border-dark-700/70'} hover:border-dark-600 transition">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-1.5 min-w-0">
                        <button type="button" onclick="toggleFieldPrimary(${field.id}, ${!isPrimary})"
                                class="p-1 rounded hover:bg-dark-750 transition flex items-center justify-center flex-shrink-0 group/star"
                                title="${isPrimary ? 'Bỏ thuộc tính chính' : 'Đánh dấu là thuộc tính chính'}">
                            <i class="${isPrimary ? 'fa-solid fa-star text-amber-400 scale-110' : 'fa-regular fa-star text-slate-500 group-hover/star:text-amber-400'} text-xs transition-transform"></i>
                        </button>
                        <label class="text-xs font-semibold text-slate-300 flex items-center gap-1.5 truncate">
                            <i class="fa-solid fa-pen-to-square text-brand-500 text-[10px] flex-shrink-0"></i>
                            <span class="truncate">${escapeHtml(field.label || field.key)}</span>
                        </label>
                    </div>
                    <div class="flex items-center gap-1.5">
                        ${isPrimary ? `<span class="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">Chính</span>` : ''}
                        <span class="text-[10px] font-mono text-slate-500 truncate max-w-[130px]" title="${escapeHtml(field.path)}">${escapeHtml(field.path)}</span>
                    </div>
                </div>
                ${isTextarea ? `
                    <textarea rows="3" oninput="onFieldChange('${escapeHtml(field.path)}', this.value)"
                              class="w-full px-3 py-2 bg-dark-850 text-slate-100 text-xs font-mono rounded-lg border border-dark-700 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition leading-relaxed">${escapeHtml(val)}</textarea>
                ` : `
                    <input type="text" value="${escapeHtml(val)}" oninput="onFieldChange('${escapeHtml(field.path)}', this.value)"
                           class="w-full px-3 py-2 bg-dark-850 text-slate-100 text-xs font-mono rounded-lg border border-dark-700 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition">
                `}
            </div>
        `;
    }

    let fieldsHtml = '';
    const hasSceneFields = displayedFields.some(f => /scenes\[\d+\]/.test(f.path));
    if (promptCat === 'video' && hasSceneFields) {
        // Group by scene index for video
        const sceneGroups = {};
        const nonSceneFields = [];
        const parsedScenes = currentPromptDetail?.parsed_json?.scenes || [];

        displayedFields.forEach(field => {
            const m = field.path.match(/scenes\[(\d+)\]/);
            if (m) {
                const sIdx = parseInt(m[1]);
                if (!sceneGroups[sIdx]) {
                    const sData = parsedScenes[sIdx] || {};
                    const sTitle = sData.title || `Cảnh ${sIdx + 1}`;
                    sceneGroups[sIdx] = { index: sIdx, title: sTitle, fields: [] };
                }
                sceneGroups[sIdx].fields.push(field);
            } else {
                nonSceneFields.push(field);
            }
        });

        const nonSceneHtml = nonSceneFields.map(renderSingleFieldHtml).join('');

        const sortedSceneIndices = Object.keys(sceneGroups).map(Number).sort((a, b) => a - b);
        const sceneCardsHtml = sortedSceneIndices.map(sIdx => {
            const grp = sceneGroups[sIdx];
            const sNum = sIdx + 1;
            const innerHtml = grp.fields.map(renderSingleFieldHtml).join('');
            return `
                <div class="rounded-2xl border-2 border-rose-500/30 bg-dark-900/50 p-4 space-y-3 shadow-md mb-4 hover:border-rose-500/50 transition">
                    <div class="flex items-center justify-between pb-2.5 border-b border-dark-700/80">
                        <div class="flex items-center gap-2">
                            <div class="w-6 h-6 rounded-lg bg-rose-500/20 text-rose-300 font-bold flex items-center justify-center text-xs border border-rose-500/30">
                                ${sNum}
                            </div>
                            <h4 class="text-xs font-bold text-slate-100 flex items-center gap-1.5">
                                <i class="fa-solid fa-clapperboard text-rose-400 text-xs"></i>
                                <span>Cảnh ${sNum}${grp.title ? ': ' + escapeHtml(grp.title) : ''}</span>
                            </h4>
                        </div>
                        <span class="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/25">Scene ${sNum}</span>
                    </div>
                    <div class="space-y-3">
                        ${innerHtml}
                    </div>
                </div>
            `;
        }).join('');

        fieldsHtml = nonSceneHtml + sceneCardsHtml;
    } else {
        fieldsHtml = displayedFields.map(renderSingleFieldHtml).join('');
    }

    const topHeader = currentTab === 'all' ? allTabConfigHtml : refBannerHtml;
    formEl.innerHTML = topHeader + fieldsHtml;
}

async function updateCurrentPromptCategory(newCategory) {
    if (!currentPromptId || !newCategory) return;
    if (currentPromptDetail && currentPromptDetail.category === newCategory) return;

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/category`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category: newCategory })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Không thể cập nhật danh mục');
        }
        const data = await res.json();

        if (currentPromptDetail) {
            currentPromptDetail.category = newCategory;
        }

        const found = currentPromptsList.find(p => p.id === currentPromptId);
        if (found) {
            found.category = newCategory;
        }

        fetchStats();

        const catNames = {
            image: 'Hình ảnh 📸',
            video: 'Video 🎬',
            content: 'Bài viết 📝'
        };
        showToast(data.message || `Đã chuyển sang danh mục ${catNames[newCategory] || newCategory}!`);

        // Re-render layout adapting to new category
        renderDetail(currentPromptDetail);

        // Keep active form tab on 'all'
        setFormTab('all');

        // Re-render prompt list and preserve card highlight
        renderPromptList(currentPromptsList);
        highlightActivePromptCard(currentPromptId);

    } catch (err) {
        console.error('Error updating prompt category:', err);
        showToast(`Lỗi: ${err.message}`);
    }
}

async function togglePromptRequiresReference(newStatus) {
    if (!currentPromptId) return;
    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/toggle-reference`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ requires_reference: !!newStatus })
        });
        if (!res.ok) throw new Error('Không thể cập nhật yêu cầu ảnh tham chiếu');
        const data = await res.json();
        if (currentPromptDetail) {
            currentPromptDetail.requires_reference = data.requires_reference;
            renderDynamicForm(currentPromptDetail.fields || []);
        }
        showToast(data.message || (newStatus ? 'Đã bật yêu cầu ảnh tham chiếu 📸' : 'Đã tắt yêu cầu ảnh tham chiếu'));
    } catch (err) {
        console.error('Error toggling requires_reference:', err);
        showToast('Lỗi khi cập nhật yêu cầu ảnh tham chiếu');
        const toggleEl = document.getElementById('toggleRequiresReferenceInput');
        if (toggleEl && currentPromptDetail) {
            toggleEl.checked = !!currentPromptDetail.requires_reference;
        }
    }
}

async function toggleFieldPrimary(fieldId, newStatus) {
    if (!currentPromptId || !fieldId) return;
    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/fields/${fieldId}/primary`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_primary: !!newStatus })
        });
        if (!res.ok) throw new Error('Không thể cập nhật thuộc tính');
        
        if (currentPromptDetail && currentPromptDetail.fields) {
            const field = currentPromptDetail.fields.find(f => f.id === fieldId);
            if (field) {
                field.is_primary = newStatus ? 1 : 0;
            }
            renderDynamicForm(currentPromptDetail.fields);
        }
        showToast(newStatus ? 'Đã ghim vào Thuộc tính chính ⭐' : 'Đã bỏ khỏi Thuộc tính chính');
    } catch (err) {
        console.error('Error toggling primary:', err);
        showToast('Lỗi khi cập nhật thuộc tính chính');
    }
}

async function suggestAndMarkPrimaryFields() {
    if (!currentPromptId) {
        showToast('Vui lòng chọn một câu lệnh trước');
        return;
    }

    const targetPromptId = currentPromptId;
    const targetTitle = (currentPromptDetail && currentPromptDetail.title) || `#${targetPromptId}`;

    if (hasActiveOrQueuedTask(targetPromptId, 'suggest_primary')) {
        showToast('Tác vụ gợi ý thuộc tính cho câu lệnh này đã có trong hàng đợi hoặc đang chạy.');
        return;
    }

    enqueueAiTask(targetPromptId, 'suggest_primary', targetTitle, async () => {
        const res = await fetch(`/api/prompts/${targetPromptId}/suggest-primary-fields`, {
            method: 'POST'
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi gợi ý thuộc tính chính');
        }

        const data = await res.json();
        const newFields = data.fields || (data.prompt ? data.prompt.fields : []);

        // Update in local prompts list
        const found = currentPromptsList.find(p => p.id === targetPromptId);
        if (found) {
            found.fields = newFields;
        }

        // If user is currently looking at this prompt, update detail form
        if (currentPromptId === targetPromptId) {
            if (currentPromptDetail) {
                currentPromptDetail.fields = newFields;
            }
            currentTab = 'featured';
            const btnFeatured = document.getElementById('tabBtnFeatured');
            const btnAll = document.getElementById('tabBtnAll');
            if (btnFeatured) btnFeatured.className = 'px-3 py-1 rounded-md bg-dark-700 text-white font-medium transition flex items-center gap-1.5';
            if (btnAll) btnAll.className = 'px-3 py-1 rounded-md text-slate-400 hover:text-white transition flex items-center gap-1.5';

            renderDynamicForm(newFields);
            showToast(data.message || `Đã gợi ý & đánh dấu ${data.suggested_count || 0} thuộc tính chính! ⭐`);
        } else {
            showToast(`✓ Đã gợi ý thuộc tính chính cho "${targetTitle}" và tự động lưu vào dữ liệu! ⭐`);
        }
    });
}

function setFormTab(tab) {
    currentTab = tab;
    const btnFeatured = document.getElementById('tabBtnFeatured');
    const btnAll = document.getElementById('tabBtnAll');

    if (tab === 'featured') {
        if (btnFeatured) {
            btnFeatured.className = 'px-3 py-1 rounded-md bg-dark-700 text-white font-medium transition flex items-center gap-1.5';
        }
        if (btnAll) {
            btnAll.className = 'px-3 py-1 rounded-md text-slate-400 hover:text-white transition flex items-center gap-1.5';
        }
    } else {
        if (btnAll) {
            btnAll.className = 'px-3 py-1 rounded-md bg-dark-700 text-white font-medium transition flex items-center gap-1.5';
        }
        if (btnFeatured) {
            btnFeatured.className = 'px-3 py-1 rounded-md text-slate-400 hover:text-white transition flex items-center gap-1.5';
        }
    }

    if (currentPromptDetail) {
        renderDynamicForm(currentPromptDetail.fields || []);
    }
}

let codeViewMode = 'live';

function setCodeViewMode(mode) {
    const detailCat = (currentPromptDetail && currentPromptDetail.category) || 'image';
    if ((detailCat === 'video' || detailCat === 'content') && mode === 'compact') {
        mode = 'live';
    }
    codeViewMode = mode;
    const btnLive = document.getElementById('btnViewLive');
    const btnCompact = document.getElementById('btnViewCompact');
    const btnRaw = document.getElementById('btnViewRaw');
    const btnRegenCompact = document.getElementById('btnRegenCompact');
    const title = document.getElementById('codeBoxTitle');

    const activeCls = 'px-3 py-1 rounded-md bg-dark-700 text-white font-medium transition';
    const inactiveCls = 'px-3 py-1 rounded-md text-slate-400 hover:text-white transition';

    if (btnLive) btnLive.className = (mode === 'live' ? activeCls : inactiveCls);
    if (btnCompact) {
        if (detailCat === 'video' || detailCat === 'content') {
            btnCompact.classList.add('hidden');
        } else {
            btnCompact.classList.remove('hidden');
            btnCompact.className = (mode === 'compact' ? activeCls : (inactiveCls + ' flex items-center gap-1.5'));
        }
    }
    if (btnRaw) btnRaw.className = (mode === 'raw' ? activeCls : inactiveCls);

    if (btnRegenCompact) {
        // Only show compact button for image category
        if (mode === 'compact' && detailCat === 'image') {
            btnRegenCompact.classList.remove('hidden');
            btnRegenCompact.classList.add('flex');
        } else {
            btnRegenCompact.classList.add('hidden');
            btnRegenCompact.classList.remove('flex');
        }
    }

    if (title) {
        if (mode === 'live') {
            title.innerHTML = '<i class="fa-solid fa-terminal text-emerald-400 text-xs"></i> <span>CÂU LỆNH PROMPT TÙY BIẾN</span>';
        } else if (mode === 'compact') {
            title.innerHTML = '<i class="fa-solid fa-compress text-cyan-400 text-xs"></i> <span>CÂU LỆNH PROMPT TỐI GIẢN (≤ 1000 KÝ TỰ)</span>';
        } else {
            title.innerHTML = '<i class="fa-solid fa-file-lines text-slate-400 text-xs"></i> <span>VĂN BẢN GỐC (RAW PROMPT)</span>';
        }
    }
    updatePromptCodeDisplay();
}

function onFieldChange(path, newValue) {
    formState[path] = newValue;
    updatePromptCodeDisplay();
}

function updatePromptCodeDisplay() {
    if (!currentPromptDetail) return;

    const codeEl = document.getElementById('promptCodeDisplay');
    const badgeEl = document.getElementById('charCountBadge');
    if (!codeEl) return;

    if (codeViewMode === 'compact') {
        let compactText = (currentPromptDetail.compact_prompt || '').trim();
        const reqRef = !!(currentPromptDetail.requires_reference || currentPromptDetail.category === 'image');

        // Nếu đã có compactText nhưng prompt yêu cầu ảnh tham chiếu mà thiếu [ATTACHED_PHOTO], chuẩn hóa lại
        if (compactText && reqRef && !compactText.includes('[ATTACHED_PHOTO]')) {
            compactText = '';
        }

        // Nếu prompt gốc đang < 1000 ký tự (và không phải JSON thô), sử dụng luôn và đảm bảo ảnh tham chiếu
        if (!compactText) {
            const rawSource = (currentPromptDetail.original_raw_content || currentPromptDetail.prompt_code || currentPromptDetail.raw_content || '').trim();
            if (rawSource && rawSource.length < 1000 && !rawSource.startsWith('{')) {
                let candidate = rawSource;
                if (reqRef) {
                    candidate = candidate.replace(/<image[\s_]*\d+>/gi, '[ATTACHED_PHOTO]');
                    candidate = candidate.replace(/\b(?:image|img|photo)[\s_]*\d+\.(?:png|jpg|jpeg|webp)\b/gi, '[ATTACHED_PHOTO]');
                    candidate = candidate.replace(/ảnh\s*tham\s*chiếu(?:\s*tải\s*lên)?/gi, '[ATTACHED_PHOTO]');
                    if (!candidate.includes('[ATTACHED_PHOTO]')) {
                        if (candidate.includes('--ar') || candidate.includes('--v')) {
                            candidate = `${candidate} --cref [ATTACHED_PHOTO]`;
                        } else {
                            candidate = `${candidate} Reference: Strict consistency matching [ATTACHED_PHOTO].`;
                        }
                    }
                }
                if (candidate.length <= 1000) {
                    compactText = candidate;
                    currentPromptDetail.compact_prompt = candidate;
                    const found = currentPromptsList.find(p => p.id === currentPromptDetail.id);
                    if (found) found.compact_prompt = candidate;
                    fetch(`/api/prompts/${currentPromptDetail.id}/compact`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ force_refresh: false })
                    }).catch(() => {});
                }
            }
        }

        if (compactText) {
            codeEl.innerText = compactText;
            if (badgeEl) badgeEl.innerText = `${compactText.length} / 1000 chars`;
        } else {
            const isProcessing = hasActiveOrQueuedTask(currentPromptDetail.id, 'compact_prompt');
            if (isProcessing) {
                codeEl.innerText = '⚡ Đang dùng AI tối giản prompt dưới 1000 ký tự... Vui lòng đợi trong giây lát.';
                if (badgeEl) badgeEl.innerText = 'Đang tạo...';
            } else {
                codeEl.innerText = '⚡ Đang kích hoạt tối giản prompt dưới 1000 ký tự...';
                if (badgeEl) badgeEl.innerText = 'Đang tạo...';
                generateCompactPromptForCurrent(false);
            }
        }
        return;
    }

    let generatedCode = "";

    if (codeViewMode === 'raw') {
        generatedCode = currentPromptDetail.original_raw_content || currentPromptDetail.raw_content || currentPromptDetail.prompt_code || "";
    } else {
        if (currentPromptDetail.parsed_json) {
            // Clone json object and deep update with formState
            const jsonObj = JSON.parse(JSON.stringify(currentPromptDetail.parsed_json));
            for (const [path, val] of Object.entries(formState)) {
                setValueByPath(jsonObj, path, val);
            }
            generatedCode = JSON.stringify(jsonObj, null, 2);
        } else {
            if (formState['prompt_content']) {
                generatedCode = formState['prompt_content'];
            } else {
                let text = currentPromptDetail.prompt_code || currentPromptDetail.raw_content || "";
                if (currentPromptDetail.fields && currentPromptDetail.fields.length > 0) {
                    for (const f of currentPromptDetail.fields) {
                        const path = f.path;
                        const val = formState[path];
                        if (val !== undefined && val !== null && String(val).trim() !== '') {
                            text = text.split(path).join(String(val).trim());
                        }
                    }
                }
                generatedCode = text;
            }
        }
    }

    codeEl.innerText = generatedCode;
    if (badgeEl) badgeEl.innerText = `${generatedCode.length} chars`;
}

function regenerateCompactPrompt() {
    if (!currentPromptDetail || !currentPromptDetail.id) {
        showToast('Vui lòng chọn một câu lệnh trước');
        return;
    }
    generateCompactPromptForCurrent(true);
}

function generateCompactPromptForCurrent(force = false) {
    if (!currentPromptDetail || !currentPromptDetail.id) return;

    const targetPromptId = currentPromptDetail.id;
    const targetTitle = currentPromptDetail.title || `#${targetPromptId}`;

    // Nếu không force và prompt gốc < 1000 ký tự (và không phải JSON thô), dùng luôn và chuẩn hóa tham chiếu
    if (!force) {
        const rawSource = (currentPromptDetail.original_raw_content || currentPromptDetail.prompt_code || currentPromptDetail.raw_content || '').trim();
        const reqRef = !!(currentPromptDetail.requires_reference || currentPromptDetail.category === 'image');
        if (rawSource && rawSource.length < 1000 && !rawSource.startsWith('{')) {
            let candidate = rawSource;
            if (reqRef) {
                candidate = candidate.replace(/<image[\s_]*\d+>/gi, '[ATTACHED_PHOTO]');
                candidate = candidate.replace(/\b(?:image|img|photo)[\s_]*\d+\.(?:png|jpg|jpeg|webp)\b/gi, '[ATTACHED_PHOTO]');
                candidate = candidate.replace(/ảnh\s*tham\s*chiếu(?:\s*tải\s*lên)?/gi, '[ATTACHED_PHOTO]');
                if (!candidate.includes('[ATTACHED_PHOTO]')) {
                    if (candidate.includes('--ar') || candidate.includes('--v')) {
                        candidate = `${candidate} --cref [ATTACHED_PHOTO]`;
                    } else {
                        candidate = `${candidate} Reference: Strict consistency matching [ATTACHED_PHOTO].`;
                    }
                }
            }
            if (candidate.length <= 1000) {
                currentPromptDetail.compact_prompt = candidate;
                const found = currentPromptsList.find(p => p.id === targetPromptId);
                if (found) found.compact_prompt = candidate;
                if (currentPromptId === targetPromptId && codeViewMode === 'compact') {
                    const codeEl = document.getElementById('promptCodeDisplay');
                    const badgeEl = document.getElementById('charCountBadge');
                    if (codeEl) codeEl.innerText = candidate;
                    if (badgeEl) badgeEl.innerText = `${candidate.length} / 1000 chars`;
                }
                fetch(`/api/prompts/${targetPromptId}/compact`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ force_refresh: false })
                }).catch(() => {});
                return;
            }
        }
    }

    if (hasActiveOrQueuedTask(targetPromptId, 'compact_prompt')) {
        if (force) {
            showToast('Tác vụ tối giản prompt cho câu lệnh này đã có trong hàng đợi hoặc đang chạy.');
        }
        return;
    }

    enqueueAiTask(targetPromptId, 'compact_prompt', targetTitle, async () => {
        if (currentPromptId === targetPromptId && codeViewMode === 'compact') {
            const codeEl = document.getElementById('promptCodeDisplay');
            if (codeEl) codeEl.innerText = '⚡ AI đang phân tích và cô đọng câu lệnh dưới 1000 ký tự... Vui lòng đợi trong giây lát.';
            const badgeEl = document.getElementById('charCountBadge');
            if (badgeEl) badgeEl.innerText = 'Đang xử lý...';
        }

        try {
            const res = await fetch(`/api/prompts/${targetPromptId}/compact`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    force_refresh: force
                })
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || 'Lỗi khi tạo prompt tối giản');
            }

            const data = await res.json();
            const compactResult = data.compact_prompt || '';

            // Update in currentPromptDetail if still points to targetPromptId
            if (currentPromptDetail && currentPromptDetail.id === targetPromptId) {
                currentPromptDetail.compact_prompt = compactResult;
            }

            // Update in currentPromptsList
            const found = currentPromptsList.find(p => p.id === targetPromptId);
            if (found) {
                found.compact_prompt = compactResult;
            }

            // If user is currently viewing this prompt in compact mode, render it
            if (currentPromptId === targetPromptId && codeViewMode === 'compact') {
                const codeEl = document.getElementById('promptCodeDisplay');
                const badgeEl = document.getElementById('charCountBadge');
                if (codeEl) codeEl.innerText = compactResult;
                if (badgeEl) badgeEl.innerText = `${compactResult.length} / 1000 chars`;
            }

            if (force) {
                showToast('✓ Đã tạo lại và lưu prompt tối giản thành công! (≤ 1000 chars)');
            } else {
                showToast('✓ Đã tự động tạo và lưu prompt tối giản thành công! (≤ 1000 chars)');
            }
        } catch (err) {
            if (currentPromptId === targetPromptId && codeViewMode === 'compact') {
                const codeEl = document.getElementById('promptCodeDisplay');
                const badgeEl = document.getElementById('charCountBadge');
                if (codeEl) codeEl.innerText = `⚠️ Lỗi khi tạo prompt tối giản: ${err.message || err}`;
                if (badgeEl) badgeEl.innerText = 'Lỗi';
            }
            throw err;
        }
    });
}

function setValueByPath(obj, path, value) {
    const parts = path.replace(/\[(\w+)\]/g, '.$1').replace(/^\./, '').split('.');
    let current = obj;
    for (let i = 0; i < parts.length - 1; i++) {
        const p = parts[i];
        if (!(p in current)) return;
        current = current[p];
    }
    const lastKey = parts[parts.length - 1];
    if (lastKey in current) {
        if (Array.isArray(current[lastKey])) {
            current[lastKey] = value.split(',').map(s => s.trim()).filter(Boolean);
        } else if (typeof current[lastKey] === 'number') {
            current[lastKey] = Number(value) || value;
        } else if (typeof current[lastKey] === 'boolean') {
            current[lastKey] = value === 'true' || value === true;
        } else {
            current[lastKey] = value;
        }
    }
}


async function convertPromptToJsonAI() {
    if (!currentPromptId || !currentPromptDetail) return;
    const targetPromptId = currentPromptId;
    const targetTitle = currentPromptDetail.title || `#${targetPromptId}`;

    if (hasActiveOrQueuedTask(targetPromptId, 'convert_json')) {
        showToast('Tác vụ chuyển JSON cho câu lệnh này đã có trong hàng đợi hoặc đang chạy.');
        return;
    }

    enqueueAiTask(targetPromptId, 'convert_json', targetTitle, async () => {
        const res = await fetch(`/api/prompts/${targetPromptId}/convert-json`, {
            method: 'POST'
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Lỗi khi gọi AI chuyển JSON');
        }

        const updatedPrompt = await res.json();

        // Update in local prompts list
        const found = currentPromptsList.find(p => p.id === targetPromptId);
        if (found) {
            found.prompt_type = 'json';
            found.parsed_json = updatedPrompt.parsed_json;
            found.fields = updatedPrompt.fields;
            found.prompt_code = updatedPrompt.prompt_code;
            found.requires_reference = updatedPrompt.requires_reference;
        }

        renderPromptList(currentPromptsList);
        highlightActivePromptCard(currentPromptId);

        // If user is currently looking at this prompt, update detail view
        if (currentPromptId === targetPromptId) {
            currentPromptDetail = updatedPrompt;
            renderDetail(currentPromptDetail);
            showToast(`Đã chuyển đổi "${targetTitle}" sang cấu trúc JSON thành công!`);
        } else {
            showToast(`✓ "${targetTitle}" đã chuyển sang JSON thành công và tự động cập nhật vào dữ liệu!`);
        }
    });
}

async function analyzeScriptAI() {
    if (!currentPromptId || !currentPromptDetail) return;
    const targetPromptId = currentPromptId;
    const targetTitle = currentPromptDetail.title || `#${targetPromptId}`;

    if (hasActiveOrQueuedTask(targetPromptId, 'analyze_script')) {
        showToast('Tác vụ phân tích kịch bản cho câu lệnh này đã có trong hàng đợi hoặc đang chạy.');
        return;
    }

    enqueueAiTask(targetPromptId, 'analyze_script', targetTitle, async () => {
        const res = await fetch(`/api/prompts/${targetPromptId}/analyze-script`, {
            method: 'POST'
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Lỗi khi gọi AI phân tích kịch bản');
        }

        const updatedPrompt = await res.json();

        // Update in local prompts list
        const found = currentPromptsList.find(p => p.id === targetPromptId);
        if (found) {
            found.prompt_type = 'video';
            found.parsed_json = updatedPrompt.parsed_json;
            found.fields = updatedPrompt.fields;
            found.prompt_code = updatedPrompt.prompt_code;
        }

        renderPromptList(currentPromptsList);
        highlightActivePromptCard(currentPromptId);

        // If user is currently looking at this prompt, update detail view
        if (currentPromptId === targetPromptId) {
            currentPromptDetail = updatedPrompt;
            renderDetail(currentPromptDetail);
            showToast(`Đã phân tích kịch bản cho "${targetTitle}" thành công!`);
        } else {
            showToast(`✓ "${targetTitle}" đã phân tích kịch bản thành công!`);
        }
    });
}

async function extractJsonFromCurrentImage() {
    if (!currentPromptId || !currentPromptDetail) return;
    const targetPromptId = currentPromptId;
    const targetTitle = currentPromptDetail.title || `#${targetPromptId}`;

    const sliderImg = document.getElementById('currentSliderImg');
    if (!sliderImg || sliderImg.classList.contains('hidden') || !sliderImg.src) {
        showToast('Không tìm thấy ảnh hiện tại để phân tích.');
        return;
    }

    const imgUrl = sliderImg.src;

    if (hasActiveOrQueuedTask(targetPromptId, 'extract_json_image')) {
        showToast('Tác vụ phân tích ảnh này đã có trong hàng đợi hoặc đang chạy.');
        return;
    }

    enqueueAiTask(targetPromptId, 'extract_json_image', targetTitle, async () => {
        const res = await fetch(`/api/prompts/${targetPromptId}/extract-json-from-image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imgUrl })
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'Lỗi khi trích xuất JSON từ ảnh');
        }

        showToast(data.message || 'Tạo prompt mới thành công!');

        // Refresh stats & list, select newly created prompt
        await fetchStats();
        await loadPrompts(data.prompt.id);
    });
}

async function deleteCurrentPrompt() {
    if (!currentPromptId || !currentPromptDetail) return;

    const confirmMsg = `Bạn có chắc chắn muốn xóa câu lệnh "${currentPromptDetail.title || currentPromptId}" không?`;
    if (!confirm(confirmMsg)) return;

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}`, {
            method: 'DELETE'
        });

        if (!res.ok) {
            throw new Error('Lỗi khi xóa câu lệnh');
        }

        showToast('Đã xóa câu lệnh thành công!');

        const deletedId = currentPromptId;
        // Determine next prompt to select
        const currentIdx = currentPromptsList.findIndex(p => p.id === deletedId);
        let nextTargetId = null;
        if (currentPromptsList.length > 1) {
            if (currentIdx < currentPromptsList.length - 1) {
                nextTargetId = currentPromptsList[currentIdx + 1].id;
            } else if (currentIdx > 0) {
                nextTargetId = currentPromptsList[currentIdx - 1].id;
            }
        }

        // Refresh stats & list
        await fetchStats();
        await loadPrompts(nextTargetId);
    } catch (err) {
        console.error('Delete error:', err);
        showToast('Lỗi: Không thể xóa câu lệnh.');
    }
}

function resetCurrentForm() {
    if (!currentPromptDetail) return;
    formState = {};
    if (currentPromptDetail.fields) {
        currentPromptDetail.fields.forEach(f => {
            formState[f.path] = f.value || '';
        });
    }
    renderDynamicForm(currentPromptDetail.fields || []);
    updatePromptCodeDisplay();
    showToast('Đã khôi phục giá trị mặc định');
}

function copyCurrentPrompt() {
    const text = document.getElementById('promptCodeDisplay').innerText;
    if (!text) return;

    navigator.clipboard.writeText(text).then(() => {
        showToast('Đã sao chép câu lệnh vào bộ nhớ tạm!');
        const btn = document.getElementById('copyTopBtn');
        if (btn) {
            btn.classList.add('copied-anim');
            setTimeout(() => btn.classList.remove('copied-anim'), 400);
        }
    }).catch(() => {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showToast('Đã sao chép câu lệnh!');
    });
}

// ==========================================
// AI Generate Title Helper
// ==========================================
async function generateTitleAI() {
    if (!currentPromptId) {
        showToast('Vui lòng chọn một câu lệnh trước');
        return;
    }

    const targetPromptId = currentPromptId;
    const targetTitle = (currentPromptDetail && currentPromptDetail.title) || `#${targetPromptId}`;

    if (hasActiveOrQueuedTask(targetPromptId, 'suggest_title')) {
        showToast('Tác vụ đặt tên cho câu lệnh này đã có trong hàng đợi hoặc đang chạy.');
        return;
    }

    enqueueAiTask(targetPromptId, 'suggest_title', targetTitle, async () => {
        const res = await fetch(`/api/prompts/${targetPromptId}/suggest-title`, {
            method: 'POST'
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi gọi AI gợi ý tiêu đề');
        }

        const data = await res.json();
        const newTitle = data.title;

        if (newTitle) {
            // Update in memory states
            const found = currentPromptsList.find(p => p.id === targetPromptId);
            if (found) {
                found.title = newTitle;
            }

            // Update sidebar card text
            const cardTitle = document.querySelector(`#prompt-card-${targetPromptId} h4`);
            if (cardTitle) {
                cardTitle.innerText = newTitle;
            }

            // If user is currently looking at this prompt, update title in detail view
            if (currentPromptId === targetPromptId) {
                const titleEl = document.getElementById('currentPromptTitle');
                if (titleEl) {
                    titleEl.innerText = newTitle;
                }
                if (currentPromptDetail) {
                    currentPromptDetail.title = newTitle;
                }
                showToast(`AI đã áp dụng tiêu đề mới: "${newTitle}"`);
            } else {
                showToast(`✓ AI đã cập nhật tiêu đề mới cho "${targetTitle}": "${newTitle}"`);
            }
        }
    });
}


// ==========================================
// Create Prompt: File Upload & Link Helpers
// ==========================================
let newPromptUploadedFiles = []; // Array of { name: str, size: number, dataUrl: str }
let currentCreateMediaTab = 'upload';

function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function setCreateMediaTab(tab) {
    currentCreateMediaTab = tab;
    const btnUpload = document.getElementById('btnCreateTabUpload');
    const btnUrl = document.getElementById('btnCreateTabUrl');
    const uploadSec = document.getElementById('createUploadSection');
    const urlSec = document.getElementById('createUrlSection');

    if (tab === 'upload') {
        if (btnUpload) btnUpload.className = 'px-2.5 py-1 rounded-md bg-dark-700 text-brand-400 font-medium transition flex items-center gap-1.5';
        if (btnUrl) btnUrl.className = 'px-2.5 py-1 rounded-md text-slate-400 hover:text-white transition flex items-center gap-1.5';
        if (uploadSec) uploadSec.classList.remove('hidden');
        if (urlSec) urlSec.classList.add('hidden');
    } else {
        if (btnUrl) btnUrl.className = 'px-2.5 py-1 rounded-md bg-dark-700 text-brand-400 font-medium transition flex items-center gap-1.5';
        if (btnUpload) btnUpload.className = 'px-2.5 py-1 rounded-md text-slate-400 hover:text-white transition flex items-center gap-1.5';
        if (urlSec) urlSec.classList.remove('hidden');
        if (uploadSec) uploadSec.classList.add('hidden');
    }
}

function handleNewPromptFiles(event) {
    const files = event.target.files;
    if (files && files.length > 0) {
        processNewPromptFiles(files);
    }
    event.target.value = '';
}

function processNewPromptFiles(files) {
    const validImageTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/svg+xml'];
    let errorMsg = null;

    Array.from(files).forEach(file => {
        if (!validImageTypes.includes(file.type) && !file.name.match(/\.(jpg|jpeg|png|webp|gif|svg)$/i)) {
            errorMsg = `Tệp "${file.name}" không phải định dạng ảnh hợp lệ (PNG, JPG, WEBP, GIF).`;
            return;
        }
        if (file.size > 15 * 1024 * 1024) {
            errorMsg = `Ảnh "${file.name}" quá lớn (vượt quá 15MB).`;
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            newPromptUploadedFiles.push({
                name: file.name,
                size: file.size,
                dataUrl: e.target.result
            });
            renderNewPromptFilesPreview();
        };
        reader.readAsDataURL(file);
    });

    if (errorMsg) {
        showToast(errorMsg);
    }
}

function syncExtractJsonButtonVisibility() {
    const btn = document.getElementById('btnExtractJsonFromUpload');
    const notice = document.getElementById('promptJsonNotice');
    const hasImg = newPromptUploadedFiles && newPromptUploadedFiles.length > 0;
    if (btn) {
        if (createModalCategory === 'image' && hasImg) {
            btn.classList.remove('hidden');
            if (notice) notice.classList.add('hidden');
        } else {
            btn.classList.add('hidden');
            if (notice) notice.classList.remove('hidden');
        }
    }
}

async function extractJsonFromNewUploadedImage() {
    if (!newPromptUploadedFiles || newPromptUploadedFiles.length === 0) {
        showToast('Vui lòng chọn hoặc tải ảnh lên trước');
        return;
    }
    const btn = document.getElementById('btnExtractJsonFromUpload');
    const promptInput = document.getElementById('newPromptInput');
    const titleInput = document.getElementById('newPromptTitleInput');
    if (!btn) return;

    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-[10px]"></i> <span>Đang đọc JSON từ ảnh...</span>';

    try {
        const firstImg = newPromptUploadedFiles[0];
        const res = await fetch('/api/prompts/extract-json-from-uploaded-image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: firstImg.dataUrl })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Lỗi khi trích xuất JSON từ ảnh');
        }

        const data = await res.json();
        if (promptInput && data.json_code) {
            promptInput.value = data.json_code;
        }
        if (titleInput && !titleInput.value.trim() && data.suggested_title) {
            titleInput.value = data.suggested_title;
        }
        showToast('Đã trích xuất JSON từ ảnh và điền sẵn vào ô câu lệnh thành công!');
    } catch (err) {
        console.error('Error extracting JSON from uploaded image:', err);
        showToast(`Lỗi: ${err.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

function renderNewPromptFilesPreview() {
    const previewBox = document.getElementById('createUploadedPreviewContainer');
    const thumbnails = document.getElementById('createUploadedThumbnails');
    const countEl = document.getElementById('createUploadedCount');
    const tabLabel = document.getElementById('labelTabUpload');

    if (!previewBox || !thumbnails) return;

    if (tabLabel) {
        tabLabel.innerText = newPromptUploadedFiles.length > 0 ? `Tải ảnh lên (${newPromptUploadedFiles.length})` : 'Tải ảnh lên';
    }

    syncExtractJsonButtonVisibility();

    if (newPromptUploadedFiles.length === 0) {
        previewBox.classList.add('hidden');
        thumbnails.innerHTML = '';
        return;
    }

    previewBox.classList.remove('hidden');
    if (countEl) {
        countEl.innerText = `${newPromptUploadedFiles.length} ảnh đã chọn`;
    }

    thumbnails.innerHTML = newPromptUploadedFiles.map((fileObj, idx) => `
        <div class="relative group/thumb flex-shrink-0 w-16 h-16 rounded-xl overflow-hidden border border-dark-700 bg-dark-900 shadow">
            <img src="${fileObj.dataUrl}" alt="${escapeHtml(fileObj.name)}" class="w-full h-full object-cover">
            <button type="button" onclick="removeNewPromptFile(${idx})"
                    title="Gỡ ảnh này"
                    class="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/80 hover:bg-rose-600 text-white text-[10px] flex items-center justify-center transition shadow">
                <i class="fa-solid fa-xmark"></i>
            </button>
            <div class="absolute bottom-0 inset-x-0 bg-dark-900/80 px-1 py-0.5 text-[9px] text-slate-300 font-mono truncate text-center pointer-events-none">
                ${formatFileSize(fileObj.size)}
            </div>
        </div>
    `).join('');
}

function removeNewPromptFile(index) {
    if (index >= 0 && index < newPromptUploadedFiles.length) {
        newPromptUploadedFiles.splice(index, 1);
        renderNewPromptFilesPreview();
        syncExtractJsonButtonVisibility();
    }
}

function clearAllNewPromptFiles() {
    newPromptUploadedFiles = [];
    const fileInput = document.getElementById('newImageFileInput');
    if (fileInput) fileInput.value = '';
    renderNewPromptFilesPreview();
    syncExtractJsonButtonVisibility();
}

function openCreateModal() {
    const modal = document.getElementById('createModal');
    if (modal) {
        modal.classList.remove('hidden');
        clearAllNewPromptFiles();
        clearVideoFile();
        setCreateMediaTab('upload');
        setCreateVideoMediaTab('upload');

        const mediaInput = document.getElementById('newMediaInput');
        if (mediaInput) mediaInput.value = '';
        const videoUrlInput = document.getElementById('newVideoUrlInput');
        if (videoUrlInput) videoUrlInput.value = '';
        const titleInput = document.getElementById('newPromptTitleInput');
        if (titleInput) titleInput.value = '';
        const reqRefInput = document.getElementById('newPromptRequiresRefInput');
        if (reqRefInput) reqRefInput.checked = true;
        const noteInput = document.getElementById('newNoteInput');
        if (noteInput) noteInput.value = '';
        const sampleInput = document.getElementById('newSampleContentInput');
        if (sampleInput) sampleInput.value = '';
        const promptInput = document.getElementById('newPromptInput');
        if (promptInput) promptInput.value = '';

        videoScenes = [{dialogue:'', action:'', camera:''}];
        setCreateCategory(currentNavTab);

        if (titleInput) titleInput.focus();
    }
}

function closeCreateModal() {
    const modal = document.getElementById('createModal');
    if (modal) {
        modal.classList.add('hidden');
    }
    clearAllNewPromptFiles();
    clearVideoFile();
    const videoUrlInput = document.getElementById('newVideoUrlInput');
    if (videoUrlInput) videoUrlInput.value = '';
}

function setCreateCategory(cat) {
    createModalCategory = cat;
    const charWrapper = document.getElementById('createCharacterMediaWrapper');
    const videoWrapper = document.getElementById('createVideoWrapper');
    const contentWrapper = document.getElementById('createContentWrapper');
    const promptSection = document.getElementById('createPromptSection');
    const titleInput = document.getElementById('newPromptTitleInput');
    const titleIcon = document.getElementById('createTitleIcon');
    const titleLabel = document.getElementById('createTitleLabel');
    const btnImage = document.getElementById('createCatBtnImage');
    const btnVideo = document.getElementById('createCatBtnVideo');
    const btnContent = document.getElementById('createCatBtnContent');

    const activeImageCls = 'flex-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 flex items-center justify-center gap-1.5 bg-gradient-to-r from-brand-600 to-emerald-600 text-white shadow-md shadow-brand-600/20';
    const activeVideoCls = 'flex-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 flex items-center justify-center gap-1.5 bg-gradient-to-r from-rose-600 to-pink-600 text-white shadow-md shadow-rose-600/20';
    const activeContentCls = 'flex-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 flex items-center justify-center gap-1.5 bg-gradient-to-r from-cyan-600 to-teal-600 text-white shadow-md shadow-cyan-600/20';
    const inactiveCls = 'flex-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 flex items-center justify-center gap-1.5 text-slate-400 hover:text-white hover:bg-dark-750';

    if (btnImage) btnImage.className = (cat === 'image' ? activeImageCls : inactiveCls);
    if (btnVideo) btnVideo.className = (cat === 'video' ? activeVideoCls : inactiveCls);
    if (btnContent) btnContent.className = (cat === 'content' ? activeContentCls : inactiveCls);

    if (titleInput) {
        if (cat === 'video') {
            titleInput.placeholder = 'Ví dụ: Kịch bản video TikTok 60s Review mỹ phẩm...';
            if (titleIcon) titleIcon.className = 'fa-solid fa-heading text-rose-400';
            if (titleLabel) titleLabel.innerText = 'Tiêu đề video';
        } else if (cat === 'content') {
            titleInput.placeholder = 'Ví dụ: Bài viết SEO giới thiệu đầm nơ cổ tiểu thư...';
            if (titleIcon) titleIcon.className = 'fa-solid fa-heading text-cyan-400';
            if (titleLabel) titleLabel.innerText = 'Tiêu đề bài viết';
        } else {
            titleInput.placeholder = 'Ví dụ: Chân dung nàng thơ áo dài trắng mùa thu Hà Nội...';
            if (titleIcon) titleIcon.className = 'fa-solid fa-heading text-emerald-400';
            if (titleLabel) titleLabel.innerText = 'Tiêu đề câu lệnh';
        }
    }

    if (charWrapper) charWrapper.classList.toggle('hidden', cat !== 'image');
    if (videoWrapper) videoWrapper.classList.toggle('hidden', cat !== 'video');
    if (contentWrapper) contentWrapper.classList.toggle('hidden', cat !== 'content');
    if (promptSection) promptSection.classList.toggle('hidden', cat === 'video');

    syncExtractJsonButtonVisibility();

    if (cat === 'video') {
        renderSceneBuilder();
        setCreateVideoMediaTab('upload');
    }
}

function setCreateVideoMediaTab(tab) {
    const uploadSection = document.getElementById('createVideoUploadSection');
    const urlSection = document.getElementById('createVideoUrlSection');
    const btnUpload = document.getElementById('btnCreateVideoTabUpload');
    const btnUrl = document.getElementById('btnCreateVideoTabUrl');

    const activeCls = 'px-2.5 py-1 rounded-md bg-dark-700 text-rose-400 font-medium transition flex items-center gap-1.5';
    const inactiveCls = 'px-2.5 py-1 rounded-md text-slate-400 hover:text-white transition flex items-center gap-1.5';

    if (tab === 'upload') {
        if (uploadSection) uploadSection.classList.remove('hidden');
        if (urlSection) urlSection.classList.add('hidden');
        if (btnUpload) btnUpload.className = activeCls;
        if (btnUrl) btnUrl.className = inactiveCls;
    } else {
        if (uploadSection) uploadSection.classList.add('hidden');
        if (urlSection) urlSection.classList.remove('hidden');
        if (btnUpload) btnUpload.className = inactiveCls;
        if (btnUrl) btnUrl.className = activeCls;
    }
}

function renderSceneBuilder() {
    const container = document.getElementById('scenesContainer');
    if (!container) return;
    container.innerHTML = videoScenes.map((scene, i) => `
        <div class="p-3 rounded-xl bg-dark-900/70 border border-dark-700 space-y-2">
            <div class="flex items-center justify-between">
                <span class="text-xs font-semibold text-rose-300 flex items-center gap-1.5">
                    <i class="fa-solid fa-clapperboard text-[10px]"></i> Cảnh ${i + 1}
                </span>
                ${videoScenes.length > 1 ? `<button type="button" onclick="removeScene(${i})" class="text-slate-500 hover:text-rose-400 transition"><i class="fa-solid fa-trash-can text-[10px]"></i></button>` : ''}
            </div>
            <textarea rows="2" placeholder="Lời thoại..." oninput="videoScenes[${i}].dialogue=this.value"
                      class="w-full px-3 py-2 bg-dark-800 text-slate-100 text-xs rounded-lg border border-dark-700 focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 placeholder-slate-500 transition">${scene.dialogue}</textarea>
            <textarea rows="2" placeholder="Hành động..." oninput="videoScenes[${i}].action=this.value"
                      class="w-full px-3 py-2 bg-dark-800 text-slate-100 text-xs rounded-lg border border-dark-700 focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 placeholder-slate-500 transition">${scene.action}</textarea>
            <input type="text" placeholder="Góc máy (VD: Close-up, Medium shot, Dolly zoom...)" oninput="videoScenes[${i}].camera=this.value" value="${scene.camera}"
                   class="w-full px-3 py-2 bg-dark-800 text-slate-100 text-xs rounded-lg border border-dark-700 focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 placeholder-slate-500 transition">
        </div>
    `).join('');
}

function addScene() {
    videoScenes.push({dialogue:'', action:'', camera:''});
    renderSceneBuilder();
}

function removeScene(index) {
    if (videoScenes.length <= 1) return;
    videoScenes.splice(index, 1);
    renderSceneBuilder();
}

function handleVideoFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    const validTypes = ['video/mp4', 'video/webm', 'video/quicktime', 'video/x-msvideo'];
    if (!validTypes.includes(file.type) && !file.name.match(/\.(mp4|webm|mov|avi)$/i)) {
        showToast('Tệp không phải định dạng video hợp lệ (MP4, WebM, MOV).');
        return;
    }
    if (file.size > 100 * 1024 * 1024) {
        showToast('Video quá lớn (vượt quá 100MB).');
        return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
        newVideoUploadedFile = { name: file.name, size: file.size, dataUrl: e.target.result };
        const preview = document.getElementById('videoFilePreview');
        const dropzone = document.getElementById('videoDropzone');
        if (preview) {
            preview.classList.remove('hidden');
            document.getElementById('videoFileName').textContent = file.name;
            document.getElementById('videoFileSize').textContent = formatFileSize(file.size);
        }
        if (dropzone) dropzone.classList.add('hidden');
    };
    reader.readAsDataURL(file);
}

function clearVideoFile() {
    newVideoUploadedFile = null;
    const preview = document.getElementById('videoFilePreview');
    const dropzone = document.getElementById('videoDropzone');
    const fileInput = document.getElementById('newVideoFileInput');
    if (preview) preview.classList.add('hidden');
    if (dropzone) dropzone.classList.remove('hidden');
    if (fileInput) fileInput.value = '';
}

function collectScenes() {
    return videoScenes.filter(s => s.dialogue.trim() || s.action.trim() || s.camera.trim());
}

async function submitCreatePrompt(event) {
    if (event && typeof event.preventDefault === 'function') {
        event.preventDefault();
    }
    const titleInput = document.getElementById('newPromptTitleInput');
    const mediaInput = document.getElementById('newMediaInput');
    const reqRefInput = document.getElementById('newPromptRequiresRefInput');
    const promptInput = document.getElementById('newPromptInput');
    const noteInput = document.getElementById('newNoteInput');
    const sampleInput = document.getElementById('newSampleContentInput');
    const submitBtn = document.getElementById('submitCreateBtn');

    const titleVal = titleInput ? titleInput.value.trim() : '';
    const promptVal = promptInput ? promptInput.value.trim() : '';
    const mediaVal = mediaInput ? mediaInput.value.trim() : '';
    const noteVal = noteInput ? noteInput.value.trim() : '';
    const sampleVal = sampleInput ? sampleInput.value.trim() : '';

    // For video, allow empty promptVal (scene builder generates it)
    if (!promptVal && createModalCategory !== 'video') {
        showToast('Vui lòng nhập nội dung câu lệnh');
        return;
    }
    if (createModalCategory === 'video') {
        const scenes = collectScenes();
        if (scenes.length === 0) {
            showToast('Vui lòng nhập ít nhất một cảnh trong phân cảnh kịch bản');
            return;
        }
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Đang lưu...</span>';

    try {
        const uploadedBase64List = newPromptUploadedFiles.map(f => f.dataUrl);

        const payload = {
            prompt: promptVal,
            category: createModalCategory
        };

        if (createModalCategory === 'video') {
            const scenes = collectScenes();
            if (scenes.length > 0) {
                let promptText = scenes.map((s, i) =>
                    `## Cảnh ${i+1}\nLời thoại: ${s.dialogue}\nHành động: ${s.action}\nGóc máy: ${s.camera}`
                ).join('\n\n');
                payload.prompt = promptText;
                payload.scenes = scenes;
            }
            const videoUrlInput = document.getElementById('newVideoUrlInput');
            const videoUrlVal = videoUrlInput ? videoUrlInput.value.trim() : '';
            if (videoUrlVal) {
                payload.media = videoUrlVal;
            }
            if (newVideoUploadedFile) {
                payload.images = [newVideoUploadedFile.dataUrl];
            }
        }

        if (titleVal) {
            payload.title = titleVal;
        }

        if (createModalCategory === 'content') {
            if (noteVal) payload.note = noteVal;
            if (sampleVal) payload.sample_content = sampleVal;
        } else if (createModalCategory === 'image') {
            payload.media = mediaVal;
            payload.images = uploadedBase64List;
            payload.requires_reference = reqRefInput ? reqRefInput.checked : true;
        }

        const res = await fetch('/api/prompts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || 'Lỗi khi tạo câu lệnh');
        }

        const newPrompt = await res.json();

        // Reset form & close modal
        if (titleInput) titleInput.value = '';
        if (mediaInput) mediaInput.value = '';
        const videoUrlInput = document.getElementById('newVideoUrlInput');
        if (videoUrlInput) videoUrlInput.value = '';
        if (reqRefInput) reqRefInput.checked = true;
        if (promptInput) promptInput.value = '';
        if (noteInput) noteInput.value = '';
        if (sampleInput) sampleInput.value = '';
        videoScenes = [{dialogue:'', action:'', camera:''}];
        clearAllNewPromptFiles();
        clearVideoFile();
        closeCreateModal();

        // Refresh stats & list, select newly created prompt
        await fetchStats();
        await loadPrompts(newPrompt.id);

        showToast('Đã thêm mới câu lệnh thành công!');
    } catch (err) {
        console.error('Error creating prompt:', err);
        showToast(`Lỗi: ${err.message}`);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fa-solid fa-plus"></i> <span>Thêm câu lệnh</span>';
    }
}

function filterByTag(tag, evt) {
    currentTag = tag;
    document.querySelectorAll('.tag-btn').forEach(btn => {
        btn.className = 'tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition';
    });
    const target = evt ? evt.currentTarget : (event ? event.currentTarget : null);
    if (target) {
        target.className = 'tag-btn active px-2.5 py-1 rounded-md bg-brand-600 text-white font-medium whitespace-nowrap transition';
    }
    loadPrompts();
}

function switchNavTab(tab, targetPromptId = null, updateRoute = true) {
    if (tab === 'character') tab = 'image';
    currentNavTab = tab;

    const btnImage = document.getElementById('navTabImage') || document.getElementById('navTabCharacter');
    const btnVideo = document.getElementById('navTabVideo');
    const btnContent = document.getElementById('navTabContent');

    const activeImageClasses = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 flex items-center gap-2 bg-gradient-to-r from-brand-600 to-emerald-600 text-white shadow-md shadow-brand-600/20';
    const activeVideoClasses = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 flex items-center gap-2 bg-gradient-to-r from-rose-600 to-pink-600 text-white shadow-md shadow-rose-600/20';
    const activeContentClasses = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 flex items-center gap-2 bg-gradient-to-r from-cyan-600 to-teal-600 text-white shadow-md shadow-cyan-600/20';
    const inactiveClasses = 'px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 flex items-center gap-2 text-slate-400 hover:text-white hover:bg-dark-750';

    if (btnImage) btnImage.className = (tab === 'image' ? activeImageClasses : inactiveClasses);
    if (btnVideo) btnVideo.className = (tab === 'video' ? activeVideoClasses : inactiveClasses);
    if (btnContent) btnContent.className = (tab === 'content' ? activeContentClasses : inactiveClasses);

    // Immediate visual toggle of media vs content container
    const genImageBtn = document.getElementById('generateImageBtn');
    const genImageActionSection = document.getElementById('genImageActionSection');
    const imageSliderContainer = document.getElementById('imageSliderContainer');
    const sampleContentContainer = document.getElementById('sampleContentContainer');
    const usePromptActionSection = document.getElementById('usePromptActionSection');

    if (tab === 'content') {
        if (genImageBtn) genImageBtn.classList.add('hidden');
        if (genImageActionSection) genImageActionSection.classList.add('hidden');
        if (imageSliderContainer) imageSliderContainer.classList.add('hidden');
        if (sampleContentContainer) sampleContentContainer.classList.remove('hidden');
        if (usePromptActionSection) usePromptActionSection.classList.remove('hidden');
    } else {
        if (genImageBtn) genImageBtn.classList.remove('hidden');
        if (genImageActionSection) genImageActionSection.classList.remove('hidden');
        if (imageSliderContainer) imageSliderContainer.classList.remove('hidden');
        if (sampleContentContainer) sampleContentContainer.classList.add('hidden');
        if (usePromptActionSection) usePromptActionSection.classList.add('hidden');
    }

    // Update tags filter bar
    const tagFilters = document.getElementById('tagFilters');
    if (tagFilters) {
        if (tab === 'content') {
            tagFilters.innerHTML = `
                <button onclick="filterByTag('all', event)" class="tag-btn active px-2.5 py-1 rounded-md bg-brand-600 text-white font-medium whitespace-nowrap transition">Tất cả</button>
                <button onclick="filterByTag('has_sample', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Có content mẫu</button>
                <button onclick="filterByTag('seo', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Bài viết SEO</button>
                <button onclick="filterByTag('live', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Livestream</button>
                <button onclick="filterByTag('json', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">JSON</button>
                <button onclick="filterByTag('text', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Văn bản</button>
            `;
        } else if (tab === 'video') {
            tagFilters.innerHTML = `
                <button onclick="filterByTag('all', event)" class="tag-btn active px-2.5 py-1 rounded-md bg-brand-600 text-white font-medium whitespace-nowrap transition">Tất cả</button>
                <button onclick="filterByTag('KOC', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">KOC AI</button>
                <button onclick="filterByTag('storyboard', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Storyboard</button>
                <button onclick="filterByTag('Kịch bản Video', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Kịch bản</button>
                <button onclick="filterByTag('TikTok', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">TikTok</button>
                <button onclick="filterByTag('YouTube', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">YouTube</button>
                <button onclick="filterByTag('has_img', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Có ảnh mẫu</button>
                <button onclick="filterByTag('json', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">JSON</button>
                <button onclick="filterByTag('text', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Văn bản</button>
            `;
        } else {
            tagFilters.innerHTML = `
                <button onclick="filterByTag('all', event)" class="tag-btn active px-2.5 py-1 rounded-md bg-brand-600 text-white font-medium whitespace-nowrap transition">Tất cả</button>
                <button onclick="filterByTag('Character', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Character</button>
                <button onclick="filterByTag('has_img', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Có ảnh mẫu</button>
                <button onclick="filterByTag('no_img', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Chưa có ảnh</button>
                <button onclick="filterByTag('storyboard', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Storyboard</button>
                <button onclick="filterByTag('portrait', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Chân dung</button>
                <button onclick="filterByTag('json', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">JSON</button>
                <button onclick="filterByTag('text', event)" class="tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition">Văn bản</button>
            `;
        }
    }
    currentTag = 'all';

    // Search input placeholder
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        if (tab === 'content') {
            searchInput.placeholder = 'Tìm theo nội dung, chú thích...';
        } else if (tab === 'video') {
            searchInput.placeholder = 'Tìm câu lệnh video, storyboard, kịch bản...';
        } else {
            searchInput.placeholder = 'Tìm theo tiêu đề, từ khóa...';
        }
        searchInput.value = '';
    }

    const clearBtn = document.getElementById('clearSearchBtn');
    if (clearBtn) clearBtn.classList.add('hidden');

    currentPromptId = null;
    currentPromptDetail = null;
    showDetailLoading();

    // Determine prompt to restore for this tab
    const promptToLoad = targetPromptId || localStorage.getItem('last_active_prompt_' + tab) || null;

    if (updateRoute) {
        updateBrowserRoute(tab, promptToLoad, false);
    }

    loadPrompts(promptToLoad);
}

// ==========================================
// Lightbox Zoom & Pan Functionality
// ==========================================
let lightboxState = {
    scale: 1,
    minScale: 0.25,
    maxScale: 8.0,
    posX: 0,
    posY: 0,
    isDragging: false,
    startX: 0,
    startY: 0,
    hasMoved: false
};

function initLightboxEvents() {
    const modal = document.getElementById('lightboxModal');
    const container = document.getElementById('lightboxContainer');
    const img = document.getElementById('lightboxImg');

    if (!container || !img || !modal) return;

    // Mouse Wheel Zoom
    container.addEventListener('wheel', (e) => {
        if (modal.classList.contains('hidden')) return;
        e.preventDefault();

        const zoomDelta = e.deltaY < 0 ? 1.18 : 0.85;
        let newScale = lightboxState.scale * zoomDelta;
        newScale = Math.min(lightboxState.maxScale, Math.max(lightboxState.minScale, newScale));
        newScale = Math.round(newScale * 100) / 100;

        if (newScale <= 1) {
            lightboxState.posX = 0;
            lightboxState.posY = 0;
        }
        lightboxState.scale = newScale;
        updateLightboxTransform();
    }, { passive: false });

    // Drag / Pan Events
    container.addEventListener('mousedown', (e) => {
        if (modal.classList.contains('hidden')) return;
        // Ignore clicks on buttons
        if (e.target.closest('button')) return;

        lightboxState.isDragging = true;
        lightboxState.hasMoved = false;
        lightboxState.startX = e.clientX - lightboxState.posX;
        lightboxState.startY = e.clientY - lightboxState.posY;
        if (lightboxState.scale > 1) {
            container.style.cursor = 'grabbing';
        }
    });

    window.addEventListener('mousemove', (e) => {
        if (!lightboxState.isDragging || modal.classList.contains('hidden')) return;
        e.preventDefault();

        const deltaX = e.clientX - (lightboxState.startX + lightboxState.posX);
        const deltaY = e.clientY - (lightboxState.startY + lightboxState.posY);
        if (Math.abs(deltaX) > 4 || Math.abs(deltaY) > 4) {
            lightboxState.hasMoved = true;
        }

        lightboxState.posX = e.clientX - lightboxState.startX;
        lightboxState.posY = e.clientY - lightboxState.startY;
        updateLightboxTransform();
    });

    window.addEventListener('mouseup', () => {
        if (!lightboxState.isDragging) return;
        lightboxState.isDragging = false;
        if (container) {
            container.style.cursor = lightboxState.scale > 1 ? 'grab' : 'default';
        }
    });

    // Double Click to Toggle Zoom
    container.addEventListener('dblclick', (e) => {
        if (modal.classList.contains('hidden')) return;
        if (e.target.closest('button')) return;
        e.preventDefault();

        if (lightboxState.scale > 1.05) {
            lightboxResetZoom();
        } else {
            lightboxState.scale = 2.5;
            lightboxState.posX = 0;
            lightboxState.posY = 0;
            updateLightboxTransform();
        }
    });

    // Click backdrop to close (only if user didn't pan/drag)
    container.addEventListener('click', (e) => {
        if (lightboxState.hasMoved) {
            lightboxState.hasMoved = false;
            return;
        }
        if (e.target === container) {
            closeLightbox();
        }
    });
}

function updateLightboxTransform() {
    const img = document.getElementById('lightboxImg');
    const badge = document.getElementById('lightboxZoomLevel');
    const container = document.getElementById('lightboxContainer');

    if (!img) return;

    img.style.transform = `translate3d(${lightboxState.posX}px, ${lightboxState.posY}px, 0px) scale(${lightboxState.scale})`;

    if (badge) {
        badge.innerText = `${Math.round(lightboxState.scale * 100)}%`;
    }

    if (container) {
        container.style.cursor = lightboxState.isDragging 
            ? 'grabbing' 
            : (lightboxState.scale > 1 ? 'grab' : 'default');
    }
}

function openLightbox(src) {
    if (!src || src.includes('placehold.co')) return;
    const modal = document.getElementById('lightboxModal');
    const img = document.getElementById('lightboxImg');
    if (!modal || !img) return;

    img.src = src;
    lightboxResetZoom();
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeLightbox() {
    const modal = document.getElementById('lightboxModal');
    if (!modal) return;
    modal.classList.add('hidden');
    document.body.style.overflow = '';
    lightboxResetZoom();
}

function lightboxZoomIn(step = 0.3) {
    let newScale = Math.min(lightboxState.maxScale, Math.round((lightboxState.scale + step) * 100) / 100);
    lightboxState.scale = newScale;
    updateLightboxTransform();
}

function lightboxZoomOut(step = 0.3) {
    let newScale = Math.max(lightboxState.minScale, Math.round((lightboxState.scale - step) * 100) / 100);
    lightboxState.scale = newScale;
    if (lightboxState.scale <= 1) {
        lightboxState.posX = 0;
        lightboxState.posY = 0;
    }
    updateLightboxTransform();
}

function lightboxResetZoom() {
    lightboxState.scale = 1;
    lightboxState.posX = 0;
    lightboxState.posY = 0;
    lightboxState.isDragging = false;
    lightboxState.hasMoved = false;
    updateLightboxTransform();
}

function lightboxDownloadImg() {
    const img = document.getElementById('lightboxImg');
    if (!img || !img.src) return;

    const rawSrc = img.src;
    const filename = rawSrc.split('/').pop().split('?')[0] || `image_${Date.now()}.png`;
    triggerDirectDownload(rawSrc, filename);
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    document.getElementById('toastMessage').innerText = msg;
    toast.classList.remove('translate-y-20', 'opacity-0');
    toast.classList.add('translate-y-0', 'opacity-100');
    setTimeout(() => {
        toast.classList.remove('translate-y-0', 'opacity-100');
        toast.classList.add('translate-y-20', 'opacity-0');
    }, 2500);
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function renderEmptyDetail() {
    document.getElementById('currentPromptTitle').innerText = 'Không có dữ liệu';
    document.getElementById('dynamicParamForm').innerHTML = '';
    document.getElementById('promptCodeDisplay').innerText = '';
    document.getElementById('charCountBadge').innerText = '0 chars';
    renderSlider([]);
    renderSampleContent([]);
    renderPromptTags([]);
    closeTagAutocomplete();
    syncDetailPaneButtonStates(null);
}

// ==========================================
// Select2-style Tags Component with Autocomplete
// ==========================================
function focusTagInput() {
    const input = document.getElementById('tagInput');
    if (input) input.focus();
}

function renderPromptTags(tags) {
    const list = document.getElementById('tagChipsList');
    if (!list) return;

    const currentTags = tags || (currentPromptDetail ? currentPromptDetail.tags : []) || [];

    if (currentTags.length === 0) {
        list.innerHTML = '';
        return;
    }

    list.innerHTML = currentTags.map(tag => `
        <span class="prompt-tag-chip inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-xs font-medium bg-brand-500/15 text-brand-300 border border-brand-500/30 group transition-all hover:bg-brand-500/25 select-none">
            <span class="cursor-pointer hover:underline" onclick="event.stopPropagation(); filterByTagDirect('${escapeHtml(tag)}')" title="Nhấp để lọc danh sách theo #${escapeHtml(tag)}">#${escapeHtml(tag)}</span>
            <button type="button" onclick="event.stopPropagation(); removePromptTag('${escapeHtml(tag)}')"
                    class="tag-remove-btn text-brand-400/60 hover:text-rose-400 hover:bg-rose-500/10 transition-all p-0.5 rounded flex items-center justify-center ml-0.5"
                    title="Gỡ tag #${escapeHtml(tag)}">
                <i class="fa-solid fa-xmark text-[10px]"></i>
            </button>
        </span>
    `).join('');
}

function filterByTagDirect(tag) {
    const searchInput = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearSearchBtn');
    if (searchInput) {
        searchInput.value = tag;
        if (clearBtn) clearBtn.classList.remove('hidden');
        loadPrompts();
        showToast(`Đang lọc theo tag: #${tag}`);
    }
}

async function fetchTagSuggestions(query) {
    const dropdown = document.getElementById('tagAutocompleteDropdown');
    if (!dropdown) return;

    const cleanQ = (query || '').trim().replace(/^#/, '');
    const thisSeq = ++tagRequestSeq;

    try {
        const url = `/api/tags?limit=15${cleanQ ? `&q=${encodeURIComponent(cleanQ)}` : ''}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to fetch tags');
        const data = await res.json();
        
        // If a newer request has already been initiated, ignore stale response
        if (thisSeq !== tagRequestSeq) return;

        const tags = data.tags || [];

        const existingPromptTags = (currentPromptDetail && currentPromptDetail.tags) || [];
        const availableTags = tags.filter(t => !existingPromptTags.map(x => x.toLowerCase()).includes(t.tag.toLowerCase()));

        currentAutocompleteItems = [];
        let html = '';

        if (availableTags.length > 0) {
            html += `<div class="px-3 py-1 text-[10px] uppercase font-bold tracking-wider text-slate-500 bg-dark-850 select-none">Gợi ý tag sẵn có</div>`;
            availableTags.forEach((t) => {
                const itemIdx = currentAutocompleteItems.length;
                currentAutocompleteItems.push({ type: 'existing', tag: t.tag });
                html += `
                    <div class="tag-option tag-autocomplete-item px-3 py-2 cursor-pointer hover:bg-dark-700/90 transition flex items-center justify-between group"
                         data-index="${itemIdx}" onclick="event.stopPropagation(); selectAutocompleteTag('${escapeHtml(t.tag)}')">
                        <span class="text-slate-200 group-hover:text-white font-medium flex items-center gap-1.5">
                            <i class="fa-solid fa-tag text-[10px] text-brand-400"></i>
                            <span>#${escapeHtml(t.tag)}</span>
                        </span>
                        <span class="text-[10px] font-mono text-slate-400 bg-dark-900 px-1.5 py-0.5 rounded border border-dark-700">
                            ${t.count} câu lệnh
                        </span>
                    </div>
                `;
            });
        }

        const exactMatch = tags.some(t => t.tag.toLowerCase() === cleanQ.toLowerCase()) || 
                           existingPromptTags.some(t => t.toLowerCase() === cleanQ.toLowerCase());
        
        if (cleanQ && !exactMatch) {
            const createIndex = currentAutocompleteItems.length;
            currentAutocompleteItems.push({ type: 'new', tag: cleanQ });
            html += `
                <div class="tag-option tag-autocomplete-item px-3 py-2 cursor-pointer hover:bg-brand-600/20 text-brand-400 hover:text-brand-300 font-medium transition flex items-center gap-2 border-t border-dark-700/60"
                     data-index="${createIndex}" onclick="event.stopPropagation(); selectAutocompleteTag('${escapeHtml(cleanQ)}')">
                    <i class="fa-solid fa-plus text-xs"></i>
                    <span>Tạo tag mới: "<strong>#${escapeHtml(cleanQ)}</strong>"</span>
                </div>
            `;
        }

        if (currentAutocompleteItems.length === 0) {
            if (cleanQ) {
                html = `<div class="p-3 text-center text-slate-400 text-xs">Tag #${escapeHtml(cleanQ)} đã có trong câu lệnh này</div>`;
            } else {
                html = `<div class="p-3 text-center text-slate-500 text-xs">Gõ để tìm kiếm hoặc tạo tag mới</div>`;
            }
        }

        dropdown.innerHTML = html;
        dropdown.classList.remove('hidden');
        activeDropdownIndex = -1;
    } catch (err) {
        console.error('Error fetching tags:', err);
        dropdown.classList.add('hidden');
    }
}

function highlightDropdownItem(index) {
    const dropdown = document.getElementById('tagAutocompleteDropdown');
    if (!dropdown) return;
    const options = dropdown.querySelectorAll('.tag-option');
    options.forEach((opt, idx) => {
        if (idx === index) {
            opt.classList.add('bg-dark-700', 'ring-1', 'ring-brand-500/50');
            opt.scrollIntoView({ block: 'nearest' });
        } else {
            opt.classList.remove('bg-dark-700', 'ring-1', 'ring-brand-500/50');
        }
    });
}

function closeTagAutocomplete() {
    const dropdown = document.getElementById('tagAutocompleteDropdown');
    if (dropdown) dropdown.classList.add('hidden');
    activeDropdownIndex = -1;
    currentAutocompleteItems = [];
}

function selectAutocompleteTag(tag) {
    addPromptTag(tag);
}

async function addPromptTag(tag) {
    if (!currentPromptId) {
        showToast('Vui lòng chọn một câu lệnh trước');
        return;
    }
    const cleanTag = (tag || '').trim().replace(/^#/, '').trim();
    if (!cleanTag) return;

    const input = document.getElementById('tagInput');
    if (input) input.value = '';
    closeTagAutocomplete();

    if (!currentPromptDetail) currentPromptDetail = {};
    if (!currentPromptDetail.tags) currentPromptDetail.tags = [];

    if (currentPromptDetail.tags.some(t => t.toLowerCase() === cleanTag.toLowerCase())) {
        showToast(`Tag #${cleanTag} đã có trong câu lệnh`);
        return;
    }

    // Optimistic UI update
    currentPromptDetail.tags.push(cleanTag);
    renderPromptTags(currentPromptDetail.tags);
    updateSidebarPromptTags(currentPromptId, currentPromptDetail.tags);

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/tags`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag: cleanTag })
        });
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Lỗi khi thêm tag');
        }
        const data = await res.json();
        if (data.tags && currentPromptDetail) {
            currentPromptDetail.tags = data.tags;
            renderPromptTags(currentPromptDetail.tags);
            updateSidebarPromptTags(currentPromptId, currentPromptDetail.tags);
        }
        showToast(`Đã thêm tag: #${cleanTag}`);
    } catch (err) {
        console.error('Error adding tag:', err);
        showToast(`Lỗi: ${err.message}`);
        // Rollback
        if (currentPromptDetail && currentPromptDetail.tags) {
            currentPromptDetail.tags = currentPromptDetail.tags.filter(t => t.toLowerCase() !== cleanTag.toLowerCase());
            renderPromptTags(currentPromptDetail.tags);
            updateSidebarPromptTags(currentPromptId, currentPromptDetail.tags);
        }
    }
}

async function removePromptTag(tag) {
    if (!currentPromptId || !tag) return;
    const cleanTag = tag.trim().replace(/^#/, '');

    // Optimistic UI update
    if (currentPromptDetail && currentPromptDetail.tags) {
        currentPromptDetail.tags = currentPromptDetail.tags.filter(t => t.toLowerCase() !== cleanTag.toLowerCase());
        renderPromptTags(currentPromptDetail.tags);
        updateSidebarPromptTags(currentPromptId, currentPromptDetail.tags);
    }

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/tags/${encodeURIComponent(cleanTag)}`, {
            method: 'DELETE'
        });
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Lỗi khi xóa tag');
        }
        const data = await res.json();
        if (data.tags && currentPromptDetail) {
            currentPromptDetail.tags = data.tags;
            renderPromptTags(currentPromptDetail.tags);
            updateSidebarPromptTags(currentPromptId, currentPromptDetail.tags);
        }
        showToast(`Đã gỡ tag #${cleanTag}`);
    } catch (err) {
        console.error('Error removing tag:', err);
        showToast(`Lỗi: ${err.message}`);
    }
}

function updateSidebarPromptTags(promptId, tags) {
    const card = document.getElementById(`prompt-card-${promptId}`);
    if (!card) return;

    // Update in memory list
    const found = currentPromptsList.find(p => p.id === promptId);
    if (found) found.tags = [...tags];

    let tagsContainer = card.querySelector('.sidebar-card-tags');
    if (!tags || tags.length === 0) {
        if (tagsContainer) tagsContainer.remove();
        return;
    }

    if (!tagsContainer) {
        tagsContainer = document.createElement('div');
        tagsContainer.className = 'sidebar-card-tags flex items-center gap-1 flex-wrap mt-1.5 pt-1 border-t border-dark-750/50';
        card.appendChild(tagsContainer);
    }

    tagsContainer.innerHTML = `
        ${tags.slice(0, 3).map(t => `<span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-dark-900/80 text-brand-400 border border-brand-500/20">#${escapeHtml(t)}</span>`).join('')}
        ${tags.length > 3 ? `<span class="text-[9px] font-mono text-slate-500">+${tags.length - 3}</span>` : ''}
    `;
}

// ==========================================
// Sample Content (Content Mẫu) Logic
// ==========================================
function renderSampleContent(sampleContents) {
    const container = document.getElementById('sampleContentContainer');
    if (!container) return;

    const samples = sampleContents || (currentPromptDetail ? currentPromptDetail.sample_contents : []) || [];
    const textEl = document.getElementById('sampleContentText');
    const headerEl = document.getElementById('sampleContentHeader');
    const toolbarEl = document.getElementById('sampleContentToolbar');
    const placeholderEl = document.getElementById('noSampleContentPlaceholder');
    const statsBadge = document.getElementById('sampleStatsBadge');
    const counterBadge = document.getElementById('sampleSliderCounter');
    const titleEl = document.getElementById('sampleContentTitle');
    const dateEl = document.getElementById('sampleContentDate');
    const prevBtn = document.getElementById('samplePrevBtn');
    const nextBtn = document.getElementById('sampleNextBtn');
    const deleteBtn = document.getElementById('btnDeleteSample');
    const copyBtn = document.getElementById('btnCopySample');

    if (!samples || samples.length === 0) {
        if (placeholderEl) {
            placeholderEl.classList.remove('hidden');
            placeholderEl.classList.add('flex');
        }
        if (textEl) {
            textEl.classList.add('hidden');
            textEl.innerText = '';
        }
        if (headerEl) headerEl.classList.add('hidden');
        if (statsBadge) statsBadge.innerText = '0 từ';
        if (counterBadge) counterBadge.innerText = '0 / 0';
        if (prevBtn) prevBtn.disabled = true;
        if (nextBtn) nextBtn.disabled = true;
        if (deleteBtn) deleteBtn.disabled = true;
        if (copyBtn) copyBtn.disabled = true;
        return;
    }

    if (placeholderEl) {
        placeholderEl.classList.add('hidden');
        placeholderEl.classList.remove('flex');
    }
    if (textEl) textEl.classList.remove('hidden');
    if (headerEl) headerEl.classList.remove('hidden');
    if (deleteBtn) deleteBtn.disabled = false;
    if (copyBtn) copyBtn.disabled = false;

    if (currentSampleContentIndex < 0) currentSampleContentIndex = 0;
    if (currentSampleContentIndex >= samples.length) currentSampleContentIndex = samples.length - 1;

    const currentItem = samples[currentSampleContentIndex];
    const contentText = currentItem ? (currentItem.content || '') : '';

    const words = contentText.trim() ? contentText.trim().split(/\s+/).filter(Boolean).length : 0;
    if (statsBadge) statsBadge.innerText = `${words} từ`;
    if (counterBadge) counterBadge.innerText = `${currentSampleContentIndex + 1} / ${samples.length}`;

    if (titleEl) {
        titleEl.innerHTML = `<i class="fa-solid fa-bookmark text-[11px]"></i> <span class="truncate">${escapeHtml(currentItem.title || `Content mẫu #${currentSampleContentIndex + 1}`)}</span>`;
    }
    if (dateEl) {
        dateEl.innerText = currentItem.created_at ? new Date(currentItem.created_at).toLocaleDateString('vi-VN') : '';
    }
    if (textEl) {
        textEl.innerText = contentText;
    }

    if (prevBtn) prevBtn.disabled = samples.length <= 1;
    if (nextBtn) nextBtn.disabled = samples.length <= 1;
}

function prevSampleContent() {
    const samples = currentPromptDetail?.sample_contents || [];
    if (samples.length <= 1) return;
    currentSampleContentIndex = (currentSampleContentIndex - 1 + samples.length) % samples.length;
    renderSampleContent(samples);
}

function nextSampleContent() {
    const samples = currentPromptDetail?.sample_contents || [];
    if (samples.length <= 1) return;
    currentSampleContentIndex = (currentSampleContentIndex + 1) % samples.length;
    renderSampleContent(samples);
}

function copyCurrentSampleContent() {
    const samples = currentPromptDetail?.sample_contents || [];
    if (!samples.length || currentSampleContentIndex >= samples.length) {
        showToast('Không có nội dung để sao chép');
        return;
    }
    const text = samples[currentSampleContentIndex].content || '';
    if (!text) {
        showToast('Nội dung mẫu đang trống');
        return;
    }
    navigator.clipboard.writeText(text).then(() => {
        showToast('Đã sao chép Content mẫu vào bộ nhớ tạm!');
    }).catch(err => {
        console.error('Clipboard error:', err);
        showToast('Không thể sao chép văn bản');
    });
}

async function deleteCurrentSampleContent() {
    const samples = currentPromptDetail?.sample_contents || [];
    if (!samples.length || currentSampleContentIndex >= samples.length) return;
    const currentItem = samples[currentSampleContentIndex];
    const name = currentItem.title || `Content mẫu #${currentSampleContentIndex + 1}`;
    if (!confirm(`Bạn có chắc chắn muốn xóa "${name}"?`)) return;

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/sample-contents/${currentItem.id}`, {
            method: 'DELETE'
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi xóa mẫu');
        }

        // Remove from currentPromptDetail
        samples.splice(currentSampleContentIndex, 1);
        if (currentSampleContentIndex >= samples.length && currentSampleContentIndex > 0) {
            currentSampleContentIndex = samples.length - 1;
        }
        renderSampleContent(samples);

        // Update card in sidebar
        const found = currentPromptsList.find(p => p.id === currentPromptId);
        if (found) {
            found.sample_count = samples.length;
        }
        updateSidebarSampleCount(currentPromptId, samples.length);

        showToast('Đã xóa Content mẫu!');
    } catch (err) {
        console.error('Error deleting sample:', err);
        showToast(`Lỗi: ${err.message}`);
    }
}

function updateSidebarSampleCount(promptId, count) {
    const activeCard = document.getElementById(`prompt-card-${promptId}`);
    if (!activeCard) return;

    const sampleBadge = activeCard.querySelector('span.text-cyan-400');
    if (count > 0) {
        if (sampleBadge) {
            sampleBadge.innerHTML = `<i class="fa-solid fa-file-lines text-[9px]"></i> ${count} Mẫu`;
        } else {
            const badgeContainer = activeCard.querySelector('.flex.items-center.gap-1\\.5');
            if (badgeContainer) {
                const newBadge = document.createElement('span');
                newBadge.className = 'text-[10px] px-1.5 py-0.5 rounded bg-dark-900/90 text-cyan-400 border border-cyan-500/20 flex items-center gap-1 font-mono';
                newBadge.innerHTML = `<i class="fa-solid fa-file-lines text-[9px]"></i> ${count} Mẫu`;
                badgeContainer.insertBefore(newBadge, badgeContainer.firstChild);
            }
        }
    } else if (sampleBadge) {
        sampleBadge.remove();
    }
}

let draggedSampleIndex = null;

function openAddSampleModal() {
    const modal = document.getElementById('addSampleContentModal');
    if (!modal) return;
    const titleInput = document.getElementById('manualSampleTitleInput');
    const textInput = document.getElementById('manualSampleTextInput');
    if (titleInput) titleInput.value = '';
    if (textInput) textInput.value = '';

    renderModalSampleList();

    modal.classList.remove('hidden');
    if (textInput) textInput.focus();
}

function closeAddSampleModal() {
    const modal = document.getElementById('addSampleContentModal');
    if (modal) modal.classList.add('hidden');
}

function renderModalSampleList() {
    const gridEl = document.getElementById('modalSampleListGrid');
    const emptyEl = document.getElementById('modalSampleEmptyState');
    const countBadge = document.getElementById('modalSampleCountBadge');
    if (!gridEl) return;

    const samples = (currentPromptDetail ? currentPromptDetail.sample_contents : []) || [];

    if (countBadge) {
        countBadge.innerText = `${samples.length} mẫu`;
    }

    if (samples.length === 0) {
        gridEl.innerHTML = '';
        if (emptyEl) emptyEl.classList.remove('hidden');
        return;
    }

    if (emptyEl) emptyEl.classList.add('hidden');
    gridEl.innerHTML = '';

    samples.forEach((item, index) => {
        const card = document.createElement('div');
        card.className = 'group relative p-3.5 rounded-xl bg-dark-900 border border-dark-750 hover:border-cyan-500/50 flex flex-col justify-between gap-2.5 transition cursor-grab active:cursor-grabbing shadow-sm select-none';
        card.setAttribute('draggable', 'true');
        card.setAttribute('data-sample-id', item.id);
        card.setAttribute('data-index', index);

        const titleText = item.title || `Content mẫu #${index + 1}`;
        const previewText = (item.content || '').trim().replace(/\s+/g, ' ').slice(0, 150);
        const wordCount = (item.content || '').trim() ? (item.content || '').trim().split(/\s+/).filter(Boolean).length : 0;
        const dateStr = item.created_at ? new Date(item.created_at).toLocaleDateString('vi-VN') : '';

        card.innerHTML = `
            <div>
                <div class="flex items-center justify-between gap-2 mb-1.5">
                    <div class="flex items-center gap-1.5 min-w-0">
                        <span class="text-slate-500 group-hover:text-cyan-400 text-xs transition cursor-grab" title="Kéo để đổi vị trí">
                            <i class="fa-solid fa-grip-vertical"></i>
                        </span>
                        <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-dark-800 text-cyan-400 border border-cyan-500/30 flex-shrink-0">
                            #${index + 1}
                        </span>
                        <h5 class="text-xs font-semibold text-slate-200 truncate group-hover:text-white transition" title="${escapeHtml(titleText)}">
                            ${escapeHtml(titleText)}
                        </h5>
                    </div>
                    <button type="button" onclick="deleteSampleFromModal(${item.id}, event)"
                            class="p-1 rounded-lg bg-rose-500/10 hover:bg-rose-500 text-rose-400 hover:text-white transition text-xs flex-shrink-0"
                            title="Xóa mẫu này">
                        <i class="fa-regular fa-trash-can"></i>
                    </button>
                </div>
                <p class="text-[11px] text-slate-400 line-clamp-2 leading-relaxed font-sans select-none">
                    ${escapeHtml(previewText)}
                </p>
            </div>
            <div class="flex items-center justify-between text-[10px] text-slate-500 font-mono border-t border-dark-800/80 pt-1.5">
                <span>${wordCount} từ</span>
                <span>${dateStr}</span>
            </div>
        `;

        // HTML5 Drag & Drop Listeners
        card.addEventListener('dragstart', (e) => {
            draggedSampleIndex = index;
            card.classList.add('opacity-40', 'scale-95', 'border-cyan-500');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', index);
        });

        card.addEventListener('dragend', () => {
            card.classList.remove('opacity-40', 'scale-95', 'border-cyan-500');
            draggedSampleIndex = null;
            document.querySelectorAll('#modalSampleListGrid > div').forEach(el => {
                el.classList.remove('border-cyan-400', 'bg-cyan-950/20', 'ring-2', 'ring-cyan-500/30');
            });
        });

        card.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            card.classList.add('border-cyan-400', 'bg-cyan-950/20');
        });

        card.addEventListener('dragleave', () => {
            card.classList.remove('border-cyan-400', 'bg-cyan-950/20');
        });

        card.addEventListener('drop', async (e) => {
            e.preventDefault();
            card.classList.remove('border-cyan-400', 'bg-cyan-950/20');
            if (draggedSampleIndex === null || draggedSampleIndex === index) return;

            const samplesArr = currentPromptDetail?.sample_contents || [];
            if (!samplesArr || samplesArr.length === 0) return;

            // Reorder elements
            const movedItem = samplesArr.splice(draggedSampleIndex, 1)[0];
            samplesArr.splice(index, 0, movedItem);

            // Re-render UI immediately
            renderModalSampleList();
            renderSampleContent(samplesArr);

            // Persist order to SQLite DB
            await persistSampleReorder();
        });

        gridEl.appendChild(card);
    });
}

async function persistSampleReorder() {
    if (!currentPromptId || !currentPromptDetail?.sample_contents) return;
    const ordered_ids = currentPromptDetail.sample_contents.map(s => s.id);
    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/sample-contents/reorder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ordered_ids })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi lưu vị trí');
        }
        showToast('Đã lưu vị trí hiển thị mẫu mới!');
    } catch (err) {
        console.error('Error reordering samples:', err);
        showToast(`Lỗi: ${err.message}`);
    }
}

async function deleteSampleFromModal(sampleId, event) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    if (!currentPromptId) return;

    const samples = currentPromptDetail?.sample_contents || [];
    const targetSample = samples.find(s => s.id === sampleId);
    const title = targetSample?.title || 'Mẫu này';

    if (!confirm(`Bạn có chắc chắn muốn xóa "${title}"?`)) return;

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/sample-contents/${sampleId}`, {
            method: 'DELETE'
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi xóa mẫu');
        }

        // Remove from currentPromptDetail
        const idx = samples.findIndex(s => s.id === sampleId);
        if (idx !== -1) {
            samples.splice(idx, 1);
        }
        if (currentSampleContentIndex >= samples.length && currentSampleContentIndex > 0) {
            currentSampleContentIndex = samples.length - 1;
        }

        renderModalSampleList();
        renderSampleContent(samples);

        // Update card in sidebar
        const found = currentPromptsList.find(p => p.id === currentPromptId);
        if (found) {
            found.sample_count = samples.length;
        }
        updateSidebarSampleCount(currentPromptId, samples.length);

        showToast('Đã xóa Content mẫu!');
    } catch (err) {
        console.error('Error deleting sample from modal:', err);
        showToast(`Lỗi: ${err.message}`);
    }
}

async function submitAddManualSample() {
    if (!currentPromptId) return;
    const title = document.getElementById('manualSampleTitleInput').value.trim();
    const content = document.getElementById('manualSampleTextInput').value.trim();
    if (!content) {
        showToast('Vui lòng nhập nội dung văn bản mẫu');
        return;
    }

    const submitBtn = document.getElementById('btnSubmitAddSample');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin text-xs"></i> <span>Đang lưu...</span>';
    }

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/sample-contents`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: title || undefined, content })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi lưu mẫu');
        }
        const resData = await res.json();
        if (resData.prompt) {
            currentPromptDetail = resData.prompt;
        } else {
            const created = resData.sample || resData;
            if (!currentPromptDetail.sample_contents) {
                currentPromptDetail.sample_contents = [];
            }
            currentPromptDetail.sample_contents.push(created);
        }
        currentSampleContentIndex = (currentPromptDetail.sample_contents || []).length - 1;

        // Reset input fields
        const titleInput = document.getElementById('manualSampleTitleInput');
        const textInput = document.getElementById('manualSampleTextInput');
        if (titleInput) titleInput.value = '';
        if (textInput) textInput.value = '';

        // Update modal gridview immediately so user sees new card
        renderModalSampleList();

        // Update main preview behind modal
        renderSampleContent(currentPromptDetail.sample_contents || []);

        const found = currentPromptsList.find(p => p.id === currentPromptId);
        if (found) {
            found.sample_count = (currentPromptDetail.sample_contents || []).length;
        }
        updateSidebarSampleCount(currentPromptId, (currentPromptDetail.sample_contents || []).length);

        showToast('Đã thêm Content mẫu thành công!');
    } catch (err) {
        console.error('Error adding sample content:', err);
        showToast(`Lỗi: ${err.message}`);
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fa-solid fa-plus text-xs"></i> <span>Lưu vào danh sách mẫu</span>';
        }
    }
}

// ==========================================
// "Sử dụng prompt này" Modal & AI Generation
// ==========================================
let usePromptTimerInterval = null;
let usePromptStartTime = 0;

function getCurrentRenderedPromptText() {
    const codeDisplay = document.getElementById('promptCodeDisplay');
    if (codeDisplay && codeDisplay.innerText.trim()) {
        return codeDisplay.innerText.trim();
    }
    if (currentPromptDetail) {
        return currentPromptDetail.raw_content || currentPromptDetail.prompt_code || '';
    }
    return '';
}

function openUsePromptModal() {
    if (!currentPromptDetail) {
        showToast('Vui lòng chọn một câu lệnh trước');
        return;
    }
    const modal = document.getElementById('usePromptModal');
    if (!modal) return;

    // Set badge & title
    const badge = document.getElementById('usePromptBadge');
    if (badge) {
        badge.innerText = `#${(currentPromptDetail.id || 'CONTENT').toUpperCase()}`;
    }

    // Populate prompt preview
    const promptText = getCurrentRenderedPromptText();
    const previewEl = document.getElementById('usePromptPreviewText');
    if (previewEl) {
        previewEl.innerText = promptText;
    }

    // Reset instruction & state
    const extraInput = document.getElementById('usePromptExtraInput');
    if (extraInput) extraInput.value = '';

    const errBanner = document.getElementById('usePromptErrorBanner');
    if (errBanner) errBanner.classList.add('hidden');

    const loadingState = document.getElementById('usePromptLoadingState');
    if (loadingState) loadingState.classList.add('hidden');

    const resultSection = document.getElementById('usePromptResultSection');
    if (resultSection) resultSection.classList.add('hidden');

    const resultText = document.getElementById('usePromptResultText');
    if (resultText) resultText.value = '';

    const copyBtn = document.getElementById('btnCopyUsePromptResult');
    if (copyBtn) copyBtn.disabled = true;

    const saveBtn = document.getElementById('btnSaveUsePromptResult');
    if (saveBtn) saveBtn.disabled = true;

    const submitBtn = document.getElementById('btnSubmitGenerateContent');
    if (submitBtn) submitBtn.disabled = false;

    setUsePromptProvider(usePromptProvider || 'openai');

    modal.classList.remove('hidden');
}

function closeUsePromptModal() {
    const modal = document.getElementById('usePromptModal');
    if (modal) modal.classList.add('hidden');
    if (usePromptTimerInterval) {
        clearInterval(usePromptTimerInterval);
        usePromptTimerInterval = null;
    }
}

function setUsePromptProvider(provider) {
    usePromptProvider = 'openai';
    const btnOpenAI = document.getElementById('btnUsePromptOpenAI');
    const badge = document.getElementById('usePromptProviderBadge');

    if (btnOpenAI) {
        btnOpenAI.className = 'px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 bg-cyan-600 text-white shadow';
    }
    if (badge) badge.innerText = 'Custom OpenAI';
}

let isUsePromptPreviewCollapsed = false;
function toggleUsePromptPreview() {
    isUsePromptPreviewCollapsed = !isUsePromptPreviewCollapsed;
    const wrapper = document.getElementById('usePromptPreviewWrapper');
    const textSpan = document.getElementById('toggleUsePromptText');
    const icon = document.getElementById('toggleUsePromptIcon');

    if (wrapper) {
        if (isUsePromptPreviewCollapsed) {
            wrapper.classList.add('hidden');
            if (textSpan) textSpan.innerText = 'Xem chi tiết';
            if (icon) icon.className = 'fa-solid fa-chevron-down text-[10px]';
        } else {
            wrapper.classList.remove('hidden');
            if (textSpan) textSpan.innerText = 'Thu gọn';
            if (icon) icon.className = 'fa-solid fa-chevron-up text-[10px]';
        }
    }
}

async function submitGenerateContent() {
    if (!currentPromptId) return;

    const promptText = getCurrentRenderedPromptText();
    if (!promptText) {
        showToast('Nội dung câu lệnh trống!');
        return;
    }

    const extraInput = document.getElementById('usePromptExtraInput');
    const extraInstruction = extraInput ? extraInput.value.trim() : '';

    const errBanner = document.getElementById('usePromptErrorBanner');
    const errText = document.getElementById('usePromptErrorText');
    if (errBanner) errBanner.classList.add('hidden');

    const loadingState = document.getElementById('usePromptLoadingState');
    const loadingTimer = document.getElementById('usePromptLoadingTimer');
    const submitBtn = document.getElementById('btnSubmitGenerateContent');
    const submitBtnText = document.getElementById('btnSubmitGenerateContentText');

    if (loadingState) loadingState.classList.remove('hidden');
    if (submitBtn) submitBtn.disabled = true;
    if (submitBtnText) submitBtnText.innerText = 'Đang gọi AI...';

    // Start timer display
    usePromptStartTime = Date.now();
    if (usePromptTimerInterval) clearInterval(usePromptTimerInterval);
    usePromptTimerInterval = setInterval(() => {
        const sec = Math.floor((Date.now() - usePromptStartTime) / 1000);
        if (loadingTimer) {
            loadingTimer.innerText = `Đang đợi phản hồi từ OpenAI (${sec}s)...`;
        }
    }, 500);

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/generate-content`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: promptText,
                extra_instruction: extraInstruction,
                provider: usePromptProvider
            })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi gọi AI sinh content');
        }

        const data = await res.json();
        const contentOutput = data.content || '';

        // Display in result box
        const resultSection = document.getElementById('usePromptResultSection');
        const resultText = document.getElementById('usePromptResultText');
        const wordBadge = document.getElementById('usePromptWordCountBadge');
        const copyBtn = document.getElementById('btnCopyUsePromptResult');
        const saveBtn = document.getElementById('btnSaveUsePromptResult');

        if (resultText) resultText.value = contentOutput;
        if (resultSection) resultSection.classList.remove('hidden');

        const words = contentOutput.trim() ? contentOutput.trim().split(/\s+/).filter(Boolean).length : 0;
        if (wordBadge) wordBadge.innerText = `${words} từ`;

        if (copyBtn) copyBtn.disabled = false;
        if (saveBtn) saveBtn.disabled = false;

        // Auto save to sample content if checked
        const chkAutoSave = document.getElementById('chkAutoSaveSample');
        if (chkAutoSave && chkAutoSave.checked) {
            await saveGeneratedContentToSample(false);
            showToast('AI đã tạo xong content và tự động lưu vào kết quả mẫu! 🎉');
        } else {
            showToast('AI đã tạo xong content!');
        }

    } catch (err) {
        console.error('Error generating content:', err);
        if (errBanner && errText) {
            errText.innerText = err.message || 'Không thể kết nối hoặc API trả về lỗi.';
            errBanner.classList.remove('hidden');
        }
        showToast(`Lỗi: ${err.message}`);
    } finally {
        if (usePromptTimerInterval) {
            clearInterval(usePromptTimerInterval);
            usePromptTimerInterval = null;
        }
        if (loadingState) loadingState.classList.add('hidden');
        if (submitBtn) submitBtn.disabled = false;
        if (submitBtnText) submitBtnText.innerText = 'Gửi AI & Tạo Content';
    }
}

function copyUsePromptResult() {
    const resultText = document.getElementById('usePromptResultText');
    if (!resultText || !resultText.value.trim()) {
        showToast('Chưa có nội dung để sao chép');
        return;
    }
    navigator.clipboard.writeText(resultText.value).then(() => {
        showToast('Đã sao chép phản hồi AI vào bộ nhớ tạm!');
    }).catch(err => {
        console.error('Clipboard error:', err);
        showToast('Lỗi khi sao chép');
    });
}

async function saveGeneratedContentToSample(showToastMessage = true) {
    if (!currentPromptId) return;
    const resultText = document.getElementById('usePromptResultText');
    const content = resultText ? resultText.value.trim() : '';

    if (!content) {
        showToast('Nội dung trống, không thể lưu vào kết quả mẫu');
        return;
    }

    const providerName = 'OpenAI';
    const title = `Phản hồi AI (${providerName})`;

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/sample-contents`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi lưu kết quả mẫu');
        }
        const resData = await res.json();
        if (resData.prompt) {
            currentPromptDetail = resData.prompt;
        } else {
            const created = resData.sample || resData;
            if (!currentPromptDetail.sample_contents) {
                currentPromptDetail.sample_contents = [];
            }
            currentPromptDetail.sample_contents.push(created);
        }
        currentSampleContentIndex = (currentPromptDetail.sample_contents || []).length - 1;

        if (currentNavTab === 'content') {
            renderSampleContent(currentPromptDetail.sample_contents || []);
        }

        const found = currentPromptsList.find(p => p.id === currentPromptId);
        if (found) {
            found.sample_count = (currentPromptDetail.sample_contents || []).length;
        }
        updateSidebarSampleCount(currentPromptId, (currentPromptDetail.sample_contents || []).length);

        if (showToastMessage) {
            showToast('Đã lưu nội dung vào kết quả mẫu thành công! ⭐');
        }
    } catch (err) {
        console.error('Error saving sample content:', err);
        showToast(`Lỗi khi lưu: ${err.message}`);
    }
}

// ==========================================
// AI Image Generation Logic
// ==========================================
let currentRefImageData = null;
let referenceImageUploadPending = false;
let currentGeneratedImageData = null;
let genTimerInterval = null;
let genTimerSeconds = 0;
let currentGenProvider = 'openai';
let providerConfigCache = null;

let currentRefSource = 'none'; // 'none' | 'koc' | 'upload' | 'existing'
let selectedKocImagePath = null;
let selectedKocImageObj = null;
let pendingUploadFileData = null;
let kocListCache = null;
let kocImagesCache = {};
let currentActiveRefTab = 'koc';

async function fetchProviderConfig() {
    try {
        const res = await fetch('/api/config/providers');
        if (res.ok) {
            providerConfigCache = await res.json();
            if (providerConfigCache.active_provider) {
                setGenProvider(providerConfigCache.active_provider, false);
            }
        }
    } catch (e) {
        console.error('Failed to fetch provider config:', e);
    }
}

function isImageReferenceSupported() {
    return !!(providerConfigCache?.openai?.image_reference_support || providerConfigCache?.image_reference_support);
}

function updateGenerateImageReferenceLayout() {
    const enabled = isImageReferenceSupported();
    const grid = document.getElementById('genPromptRefGrid');
    const section = document.getElementById('genReferenceUploadSection');
    const prompt = document.getElementById('genPromptText');

    if (grid) {
        grid.className = enabled
            ? 'grid grid-cols-1 lg:grid-cols-2 gap-4 items-start'
            : 'grid grid-cols-1 gap-4 items-start';
    }
    if (section) section.classList.toggle('hidden', !enabled);
    if (prompt) {
        prompt.rows = enabled ? 10 : 8;
        prompt.classList.toggle('min-h-[260px]', enabled);
        prompt.classList.toggle('min-h-[220px]', !enabled);
    }
    if (!enabled) clearGenRefImage();
}

function setGenProvider(provider, notify = true) {
    currentGenProvider = 'openai';
    const btnOpenAI = document.getElementById('btnProviderOpenAI');
    const badge = document.getElementById('genProviderInfoBadge');

    if (btnOpenAI) {
        btnOpenAI.className = 'px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 bg-indigo-600 text-white shadow';
    }
    if (badge) {
        const imgModel = providerConfigCache?.openai?.image_model || providerConfigCache?.image_model || 'cx/gpt-image-2.5';
        badge.innerText = `Custom OpenAI (${imgModel})`;
        badge.className = 'text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/30';
    }
}

function populateImageModelSelect() {
    const select = document.getElementById('genImageModelSelect');
    const badge = document.getElementById('genImageModelBadge');
    if (!select) return;

    const models = providerConfigCache?.openai?.image_models || 
                   providerConfigCache?.image_models || 
                   (providerConfigCache?.openai?.image_model ? [providerConfigCache.openai.image_model] : []);
    const defaultModel = providerConfigCache?.openai?.default_image_model ||
                         providerConfigCache?.default_image_model ||
                         (models.length > 0 ? models[0] : '');

    const previousValue = select.value;
    select.innerHTML = '';

    if (!models || models.length === 0) {
        const opt = document.createElement('option');
        opt.value = defaultModel || '';
        opt.textContent = defaultModel ? `${defaultModel} (Mặc định)` : '-- Mặc định --';
        select.appendChild(opt);
    } else {
        models.forEach((m, idx) => {
            const opt = document.createElement('option');
            opt.value = m;
            if (idx === 0) {
                opt.textContent = `${m} ★ (Mặc định)`;
            } else {
                opt.textContent = m;
            }
            select.appendChild(opt);
        });
    }

    if (badge) {
        badge.innerText = `${models.length || 1} model${models.length > 1 ? 's' : ''}`;
    }

    // Luôn ưu tiên chọn model đầu tiên được khai báo nếu chưa có lựa chọn hợp lệ
    if (previousValue && models.includes(previousValue)) {
        select.value = previousValue;
    } else if (defaultModel && models.includes(defaultModel)) {
        select.value = defaultModel;
    } else if (models.length > 0) {
        select.value = models[0];
    }
}

function populateVideoModelSelect() {
    const select = document.getElementById('genVideoModelSelect');
    const badge = document.getElementById('genVideoModelBadge');
    if (!select) return;

    const models = providerConfigCache?.openai?.video_models ||
                   providerConfigCache?.video_models ||
                   (providerConfigCache?.openai?.video_model ? [providerConfigCache.openai.video_model] : [
                       "zpro-payg/grok-imagine-video",
                       "zpro-payg/grok-imagine-video-1.5"
                   ]);
    const defaultModel = providerConfigCache?.openai?.default_video_model ||
                         providerConfigCache?.default_video_model ||
                         (models.length > 0 ? models[0] : '');

    const previousValue = select.value;
    select.innerHTML = '';

    if (!models || models.length === 0) {
        const opt = document.createElement('option');
        opt.value = defaultModel || '';
        opt.textContent = defaultModel ? `${defaultModel} (Mặc định)` : '-- Mặc định --';
        select.appendChild(opt);
    } else {
        models.forEach((m, idx) => {
            const opt = document.createElement('option');
            opt.value = m;
            if (idx === 0) {
                opt.textContent = `${m} ★ (Mặc định .env)`;
            } else {
                opt.textContent = m;
            }
            select.appendChild(opt);
        });
    }

    if (badge) {
        badge.innerText = `${models.length || 1} model${models.length > 1 ? 's' : ''}`;
    }

    if (previousValue && models.includes(previousValue)) {
        select.value = previousValue;
    } else if (defaultModel && models.includes(defaultModel)) {
        select.value = defaultModel;
    } else if (models.length > 0) {
        select.value = models[0];
    }
}

function getCurrentPromptCode() {
    if (!currentPromptDetail) return "";
    if (codeViewMode === 'raw') {
        return currentPromptDetail.raw_content || currentPromptDetail.prompt_code || "";
    }
    if (currentPromptDetail.parsed_json) {
        try {
            const jsonObj = JSON.parse(JSON.stringify(currentPromptDetail.parsed_json));
            for (const [path, val] of Object.entries(formState)) {
                setValueByPath(jsonObj, path, val);
            }
            return JSON.stringify(jsonObj, null, 2);
        } catch (e) {
            return currentPromptDetail.prompt_code || "";
        }
    }
    if (formState['prompt_content']) {
        return formState['prompt_content'];
    }
    let text = currentPromptDetail.prompt_code || currentPromptDetail.raw_content || "";
    if (currentPromptDetail.fields && currentPromptDetail.fields.length > 0) {
        for (const f of currentPromptDetail.fields) {
            const path = f.path;
            const val = formState[path];
            if (val !== undefined && val !== null && String(val).trim() !== '') {
                text = text.split(path).join(String(val).trim());
            }
        }
    }
    return text;
}

async function openGenerateImageModal(promptId = null) {
    if (promptId && promptId !== currentPromptId) {
        await selectPrompt(promptId, true);
    }

    if (!currentPromptDetail && currentPromptId) {
        try {
            const res = await fetch(`/api/prompts/${currentPromptId}`);
            if (res.ok) currentPromptDetail = await res.json();
        } catch (e) {
            console.error('Failed to load current prompt detail:', e);
        }
    }

    const badge = document.getElementById('genPromptBadge');
    if (badge) {
        badge.innerText = `#${(currentPromptId || 'PROMPT').toUpperCase()}`;
    }

    // Refresh provider configuration status
    await fetchProviderConfig();
    populateImageModelSelect();
    updateGenerateImageReferenceLayout();

    // Populate current prompt text
    const promptInput = document.getElementById('genPromptText');
    if (promptInput) {
        promptInput.value = getCurrentPromptCode();
    }

    // Reset extra description
    const extraDescInput = document.getElementById('genExtraDesc');
    if (extraDescInput) {
        extraDescInput.value = '';
    }

    // Auto-detect or reset size, quality, and detail
    const sizeSelect = document.getElementById('genSizeSelect');
    if (sizeSelect) {
        let detectedSize = '1024x1024';
        const promptFull = (promptInput ? promptInput.value : '') + ' ' + JSON.stringify(formState || {});
        if (/9[:/]16|1024x1792|720x1280|dọc|portrait/i.test(promptFull)) {
            detectedSize = '1024x1792';
        } else if (/16[:/]9|1792x1024|1280x720|ngang|landscape/i.test(promptFull)) {
            detectedSize = '1792x1024';
        } else if (/2[:/]3|1024x1536/i.test(promptFull)) {
            detectedSize = '1024x1536';
        } else if (/3[:/]2|1536x1024/i.test(promptFull)) {
            detectedSize = '1536x1024';
        } else if (/3[:/]4|1024x1365/i.test(promptFull)) {
            detectedSize = '1024x1365';
        } else if (/4[:/]3|1365x1024/i.test(promptFull)) {
            detectedSize = '1365x1024';
        }
        if ([...sizeSelect.options].some(o => o.value === detectedSize)) {
            sizeSelect.value = detectedSize;
        }
    }
    const qualitySelect = document.getElementById('genQualitySelect');
    if (qualitySelect && !qualitySelect.value) {
        qualitySelect.value = 'hd';
    }
    const detailSelect = document.getElementById('genDetailSelect');
    if (detailSelect && !detailSelect.value) {
        detailSelect.value = 'high';
    }

    // Reset reference image
    clearGenRefImage();
    switchRefTab('koc');
    loadKocList(false);

    // Populate existing images thumbnails if any
    const existingBox = document.getElementById('genExistingImagesBox');
    const thumbsList = document.getElementById('genExistingThumbsList');
    if (existingBox && thumbsList) {
        const images = (currentPromptDetail && currentPromptDetail.images) || [];
        if (images.length > 0) {
            existingBox.classList.remove('hidden');
            thumbsList.innerHTML = images.map((img, i) => {
                const src = getImageSource(img);
                return `
                    <button type="button" onclick="selectExistingImageAsRef('${src}')" 
                            class="w-12 h-12 rounded-lg overflow-hidden border-2 border-dark-700 hover:border-purple-500 flex-shrink-0 transition hover:scale-105"
                            title="Chọn làm ảnh tham chiếu">
                        <img src="${src}" class="w-full h-full object-cover" onerror="this.src='/static/placeholder.png'">
                    </button>
                `;
            }).join('');
        } else {
            existingBox.classList.add('hidden');
            thumbsList.innerHTML = '';
        }
    }

    // Reset results & errors
    document.getElementById('genErrorBanner').classList.add('hidden');
    document.getElementById('genLoadingState').classList.add('hidden');
    document.getElementById('genResultSection').classList.add('hidden');
    currentGeneratedImageData = null;

    // Reset submit button state
    const btnSubmit = document.getElementById('btnSubmitGenerate');
    if (btnSubmit) {
        btnSubmit.disabled = false;
        document.getElementById('btnSubmitGenerateText').innerText = 'Tạo ảnh ngay';
    }

    // Show modal
    const modal = document.getElementById('generateImageModal');
    if (modal) {
        modal.classList.remove('hidden');
    }
}

function closeGenerateImageModal() {
    const modal = document.getElementById('generateImageModal');
    if (modal) {
        modal.classList.add('hidden');
    }
    if (genTimerInterval) {
        clearInterval(genTimerInterval);
        genTimerInterval = null;
    }
}

function handleGenerateActionClick() {
    const promptCat = (currentPromptDetail && currentPromptDetail.category) || 'image';
    if (promptCat === 'video') {
        openGenerateVideoModal();
    } else {
        openGenerateImageModal();
    }
}

// ==========================================
// Video AI Modal & Multi-Scene Render Engine
// ==========================================
let videoModalScenes = [];
let currentVideoRatio = '9:16';
let videoRefMediaData = null;

function setVideoRatio(ratio) {
    currentVideoRatio = ratio;
    const btnPortrait = document.getElementById('btnRatioPortrait');
    const btnLandscape = document.getElementById('btnRatioLandscape');
    if (ratio === '9:16') {
        if (btnPortrait) btnPortrait.className = 'flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition flex items-center justify-center gap-1.5 bg-rose-600 text-white shadow-md shadow-rose-600/25';
        if (btnLandscape) btnLandscape.className = 'flex-1 py-2 px-3 rounded-lg text-xs font-medium transition flex items-center justify-center gap-1.5 bg-dark-800 text-slate-400 hover:text-white border border-dark-700 hover:bg-dark-700';
    } else {
        if (btnLandscape) btnLandscape.className = 'flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition flex items-center justify-center gap-1.5 bg-rose-600 text-white shadow-md shadow-rose-600/25';
        if (btnPortrait) btnPortrait.className = 'flex-1 py-2 px-3 rounded-lg text-xs font-medium transition flex items-center justify-center gap-1.5 bg-dark-800 text-slate-400 hover:text-white border border-dark-700 hover:bg-dark-700';
    }
}

function switchVideoRefTab(tab) {
    const uploadSection = document.getElementById('videoRefUploadSection');
    const existingSection = document.getElementById('videoRefExistingSection');
    const btnUpload = document.getElementById('btnVideoRefTabUpload');
    const btnExisting = document.getElementById('btnVideoRefTabExisting');

    if (tab === 'upload') {
        if (uploadSection) uploadSection.classList.remove('hidden');
        if (existingSection) existingSection.classList.add('hidden');
        if (btnUpload) btnUpload.className = 'px-2.5 py-1 rounded-md font-medium transition flex items-center gap-1 bg-purple-600 text-white shadow';
        if (btnExisting) btnExisting.className = 'px-2.5 py-1 rounded-md text-slate-400 hover:text-white transition flex items-center gap-1';
    } else {
        if (uploadSection) uploadSection.classList.add('hidden');
        if (existingSection) existingSection.classList.remove('hidden');
        if (btnExisting) btnExisting.className = 'px-2.5 py-1 rounded-md font-medium transition flex items-center gap-1 bg-purple-600 text-white shadow';
        if (btnUpload) btnUpload.className = 'px-2.5 py-1 rounded-md text-slate-400 hover:text-white transition flex items-center gap-1';
    }
}

function handleGenVideoRefUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (file.size > 50 * 1024 * 1024) {
        showToast('Tệp tham chiếu quá lớn (vượt quá 50MB).');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        videoRefMediaData = e.target.result;
        const preview = document.getElementById('videoRefPreview');
        const dropzone = document.getElementById('videoRefDropzone');
        const nameEl = document.getElementById('videoRefPreviewName');
        const imgEl = document.getElementById('videoRefPreviewImg');
        if (preview) preview.classList.remove('hidden');
        if (dropzone) dropzone.classList.add('hidden');
        if (nameEl) nameEl.textContent = file.name;
        if (imgEl) {
            if (file.type.startsWith('image/')) {
                imgEl.src = e.target.result;
            } else {
                imgEl.src = 'https://placehold.co/100x100/1e293b/f43f5e?text=Video+Ref';
            }
        }
        showToast(`Đã nạp tệp tham chiếu: ${file.name}`);
    };
    reader.readAsDataURL(file);
}

function clearGenVideoRef() {
    videoRefMediaData = null;
    const preview = document.getElementById('videoRefPreview');
    const dropzone = document.getElementById('videoRefDropzone');
    const fileInput = document.getElementById('genVideoRefFileInput');
    if (preview) preview.classList.add('hidden');
    if (dropzone) dropzone.classList.remove('hidden');
    if (fileInput) fileInput.value = '';
}

function selectExistingVideoRef(url, name) {
    videoRefMediaData = url;
    const preview = document.getElementById('videoRefPreview');
    const dropzone = document.getElementById('videoRefDropzone');
    const nameEl = document.getElementById('videoRefPreviewName');
    const imgEl = document.getElementById('videoRefPreviewImg');
    switchVideoRefTab('upload');
    if (preview) preview.classList.remove('hidden');
    if (dropzone) dropzone.classList.add('hidden');
    if (nameEl) nameEl.textContent = name || 'Mẫu có sẵn';
    if (imgEl) imgEl.src = url;
    showToast('Đã chọn tư liệu tham chiếu từ mẫu có sẵn');
}

function detectScenesFromCurrentPrompt() {
    const scenes = [];
    // 1. Kiểm tra parsed_json.scenes
    if (currentPromptDetail?.parsed_json?.scenes && Array.isArray(currentPromptDetail.parsed_json.scenes) && currentPromptDetail.parsed_json.scenes.length > 0) {
        currentPromptDetail.parsed_json.scenes.forEach((s, idx) => {
            let promptText = s.prompt || '';
            if (!promptText) {
                promptText = `${s.camera ? s.camera + '. ' : ''}${s.action ? s.action + '. ' : ''}${s.dialogue ? 'Speaking lines: "' + s.dialogue + '".' : ''}`.trim();
            }
            scenes.push({
                scene_number: s.scene_number || (idx + 1),
                title: s.title || `Cảnh ${idx + 1}`,
                dialogue: s.dialogue || '',
                action: s.action || '',
                camera: s.camera || '',
                prompt: promptText,
                duration: s.duration || 6,
                status: 'idle',
                video_url: '',
                error_message: ''
            });
        });
        return scenes;
    }

    // 2. Parse từ markdown text: ## Cảnh (\d+)
    const rawText = currentPromptDetail?.prompt_code || currentPromptDetail?.raw_content || '';
    const sceneRegex = /##\s*Cảnh\s*(\d+)(?::\s*([^\n]+))?/gi;
    const matches = [...rawText.matchAll(sceneRegex)];

    if (matches.length > 0) {
        for (let i = 0; i < matches.length; i++) {
            const m = matches[i];
            const sNum = parseInt(m[1]) || (i + 1);
            const sTitle = (m[2] || `Cảnh ${sNum}`).trim();
            const startIdx = m.index;
            const endIdx = (i + 1 < matches.length) ? matches[i + 1].index : rawText.length;
            const block = rawText.slice(startIdx, endIdx);

            const dMatch = block.match(/(?:Lời thoại|dialogue)[:\s*\"“]([^\n\"”]+)/i);
            const aMatch = block.match(/(?:Hành động(?: & Biểu cảm)?|action)[:\s*]([^\n]+)/i);
            const cMatch = block.match(/(?:Góc máy(?: điện ảnh)?|camera)[:\s*]([^\n]+)/i);
            const pMatch = block.match(/(?:Prompt Video AI|prompt)[:\s*`\"]([^`\"\n]+)/i);

            const dialogue = dMatch ? dMatch[1].trim() : '';
            const action = aMatch ? aMatch[1].trim() : '';
            const camera = cMatch ? cMatch[1].trim() : '';
            let promptStr = pMatch ? pMatch[1].trim() : '';
            if (!promptStr) {
                promptStr = `${camera ? camera + '. ' : ''}${action ? action + '. ' : ''}${dialogue ? 'Speaking lines: "' + dialogue + '".' : ''}`.trim() || block.replace(/##[^\n]+/g, '').trim();
            }

            scenes.push({
                scene_number: sNum,
                title: sTitle,
                dialogue: dialogue,
                action: action,
                camera: camera,
                prompt: promptStr,
                duration: 6,
                status: 'idle',
                video_url: '',
                error_message: ''
            });
        }
        return scenes;
    }

    // 3. Fallback: 1 Cảnh duy nhất
    scenes.push({
        scene_number: 1,
        title: currentPromptDetail?.title || 'Cảnh 1',
        dialogue: '',
        action: '',
        camera: 'Cinematic medium shot, 50mm f/1.8 lens, natural lighting',
        prompt: rawText,
        duration: 6,
        status: 'idle',
        video_url: '',
        error_message: ''
    });
    return scenes;
}

function setVideoSceneDuration(sceneIndex, sec) {
    if (!videoModalScenes[sceneIndex]) return;
    videoModalScenes[sceneIndex].duration = sec;
    [4, 6, 8, 10].forEach(s => {
        const btn = document.getElementById(`scene-dur-btn-${sceneIndex}-${s}`);
        if (btn) {
            if (s === sec) {
                btn.className = 'px-2 py-0.5 rounded-md font-mono text-[11px] transition bg-rose-600 text-white font-bold';
            } else {
                btn.className = 'px-2 py-0.5 rounded-md font-mono text-[11px] transition text-slate-400 hover:text-white';
            }
        }
    });
}

function onVideoSceneFieldChange(sceneIndex) {
    const scene = videoModalScenes[sceneIndex];
    if (!scene) return;
    const dEl = document.getElementById(`scene-dialogue-${sceneIndex}`);
    const aEl = document.getElementById(`scene-action-${sceneIndex}`);
    const cEl = document.getElementById(`scene-camera-${sceneIndex}`);

    if (dEl) scene.dialogue = dEl.value.trim();
    if (aEl) scene.action = aEl.value.trim();
    if (cEl) scene.camera = cEl.value.trim();

    // Tự động đồng bộ và cập nhật prompt của scene tương ứng
    let updatedPrompt = "";
    if (scene.camera) updatedPrompt += `${scene.camera}. `;
    if (scene.action) updatedPrompt += `${scene.action}. `;
    if (scene.dialogue) updatedPrompt += `Speaking lines: "${scene.dialogue}". `;
    scene.prompt = updatedPrompt.trim() || scene.prompt;

    const previewEl = document.getElementById(`scene-prompt-preview-${sceneIndex}`);
    if (previewEl) previewEl.textContent = scene.prompt;
}

function renderVideoModalSceneCards() {
    const container = document.getElementById('genVideoScenesContainer');
    if (!container) return;

    if (!videoModalScenes || videoModalScenes.length === 0) {
        container.innerHTML = `
            <div class="p-8 text-center text-slate-500 border border-dashed border-dark-700 rounded-2xl">
                <i class="fa-solid fa-clapperboard text-2xl mb-2 text-slate-600"></i>
                <p class="text-xs">Không tìm thấy phân cảnh nào trong câu lệnh này.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = videoModalScenes.map((scene, i) => {
        const sNum = scene.scene_number || (i + 1);
        const sTitle = scene.title || `Cảnh ${sNum}`;
        const sDur = scene.duration || 6;
        const isSuccess = scene.status === 'success' && scene.video_url;
        const isError = scene.status === 'error';
        const isRendering = scene.status === 'rendering';

        return `
            <div class="rounded-2xl border border-dark-700 bg-dark-850 p-4 sm:p-5 space-y-4 shadow-lg hover:border-rose-500/40 transition" id="video-scene-card-${i}">
                <!-- Scene Header -->
                <div class="flex items-center justify-between border-b border-dark-700/80 pb-3 flex-wrap gap-2">
                    <div class="flex items-center gap-2.5">
                        <span class="w-7 h-7 rounded-lg bg-rose-500/20 text-rose-300 font-bold text-xs flex items-center justify-center border border-rose-500/30">
                            ${sNum}
                        </span>
                        <div>
                            <h4 class="text-sm font-bold text-slate-100 flex items-center gap-2">
                                <span>Cảnh ${sNum}: ${escapeHtml(sTitle)}</span>
                            </h4>
                        </div>
                    </div>
                    <!-- Duration selector 4s - 6s - 8s - 10s -->
                    <div class="flex items-center gap-1.5">
                        <span class="text-[11px] text-slate-400 mr-1"><i class="fa-solid fa-clock text-[10px]"></i> Thời lượng:</span>
                        <div class="inline-flex p-0.5 bg-dark-900 rounded-lg border border-dark-700 text-xs">
                            ${[4, 6, 8, 10].map(sec => `
                                <button type="button" onclick="setVideoSceneDuration(${i}, ${sec})" id="scene-dur-btn-${i}-${sec}"
                                        class="px-2 py-0.5 rounded-md font-mono text-[11px] transition ${sec === sDur ? 'bg-rose-600 text-white font-bold' : 'text-slate-400 hover:text-white'}">
                                    ${sec}s
                                </button>
                            `).join('')}
                        </div>
                    </div>
                </div>

                <!-- Preview Box -->
                <div class="relative rounded-xl overflow-hidden bg-dark-900 border border-dark-700 flex items-center justify-center min-h-[220px] max-h-[380px]" id="scene-preview-box-${i}">
                    <!-- When idle / not rendered -->
                    <div id="scene-placeholder-${i}" class="${(isSuccess || isRendering || isError) ? 'hidden' : 'flex'} flex-col items-center justify-center p-6 text-center text-slate-500 space-y-2">
                        <div class="w-12 h-12 rounded-xl bg-dark-800 border border-dark-700 flex items-center justify-center text-slate-400">
                            <i class="fa-solid fa-film text-xl"></i>
                        </div>
                        <p class="text-xs font-medium text-slate-400">Chưa render cảnh này</p>
                        <p class="text-[11px] text-slate-600">Nhấp nút "Render cảnh này" bên dưới để AI tạo video</p>
                    </div>

                    <!-- When rendering (spinner) -->
                    <div id="scene-loading-${i}" class="${isRendering ? 'flex' : 'hidden'} flex-col items-center justify-center p-6 text-center text-rose-300 space-y-3">
                        <i class="fa-solid fa-circle-notch fa-spin text-3xl text-rose-500"></i>
                        <p class="text-xs font-semibold">Đang render video cho Cảnh ${sNum}...</p>
                        <p class="text-[11px] text-slate-500 font-mono">Quá trình có thể mất từ 30s - 2 phút tùy model</p>
                    </div>

                    <!-- When rendered success -->
                    <div id="scene-result-${i}" class="${isSuccess ? 'flex' : 'hidden'} w-full h-full flex flex-col items-center justify-center relative group/vid">
                        <video id="scene-video-player-${i}" controls class="w-full max-h-[360px] rounded-xl object-contain bg-black" src="${escapeHtml(scene.video_url || '')}"></video>
                        <div class="absolute top-2 right-2 flex items-center gap-1.5 opacity-90 group-hover/vid:opacity-100 transition">
                            <a id="scene-download-btn-${i}" href="${escapeHtml(scene.video_url || '')}" download="scene_${sNum}.mp4"
                               class="px-2.5 py-1.5 rounded-lg bg-black/80 hover:bg-emerald-600 text-white text-xs font-medium transition backdrop-blur flex items-center gap-1 shadow">
                                <i class="fa-solid fa-download"></i> Tải về
                            </a>
                        </div>
                    </div>

                    <!-- When error -->
                    <div id="scene-error-${i}" class="${isError ? 'flex' : 'hidden'} p-4 rounded-xl bg-rose-500/15 border border-rose-500/40 text-rose-300 text-xs text-center flex-col items-center space-y-2 max-w-md">
                        <i class="fa-solid fa-triangle-exclamation text-rose-400 text-lg"></i>
                        <div id="scene-error-text-${i}" class="text-xs">${escapeHtml(scene.error_message || 'Lỗi khi tạo video cảnh này')}</div>
                    </div>
                </div>

                <!-- 3 Text Inputs: Lời thoại + Hành động + Góc máy -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <!-- 1. Lời thoại -->
                    <div class="space-y-1">
                        <label class="text-[11px] font-semibold text-slate-300 flex items-center gap-1">
                            <i class="fa-solid fa-comment-dots text-rose-400 text-[10px]"></i>
                            <span>Lời thoại chính xác</span>
                        </label>
                        <textarea id="scene-dialogue-${i}" rows="3" oninput="onVideoSceneFieldChange(${i})"
                                  class="w-full px-3 py-2 bg-dark-900 text-slate-100 text-xs rounded-xl border border-dark-700 focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 transition leading-relaxed">${escapeHtml(scene.dialogue || '')}</textarea>
                    </div>

                    <!-- 2. Hành động & Biểu cảm -->
                    <div class="space-y-1">
                        <label class="text-[11px] font-semibold text-slate-300 flex items-center gap-1">
                            <i class="fa-solid fa-person-walking text-rose-400 text-[10px]"></i>
                            <span>Hành động & Biểu cảm</span>
                        </label>
                        <textarea id="scene-action-${i}" rows="3" oninput="onVideoSceneFieldChange(${i})"
                                  class="w-full px-3 py-2 bg-dark-900 text-slate-100 text-xs rounded-xl border border-dark-700 focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 transition leading-relaxed">${escapeHtml(scene.action || '')}</textarea>
                    </div>

                    <!-- 3. Góc máy điện ảnh -->
                    <div class="space-y-1">
                        <label class="text-[11px] font-semibold text-slate-300 flex items-center gap-1">
                            <i class="fa-solid fa-camera text-rose-400 text-[10px]"></i>
                            <span>Góc máy điện ảnh</span>
                        </label>
                        <textarea id="scene-camera-${i}" rows="3" oninput="onVideoSceneFieldChange(${i})"
                                  class="w-full px-3 py-2 bg-dark-900 text-slate-100 text-xs rounded-xl border border-dark-700 focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 transition leading-relaxed">${escapeHtml(scene.camera || '')}</textarea>
                    </div>
                </div>

                <!-- Render Button & Status Row -->
                <div class="flex items-center justify-between pt-2 border-t border-dark-700/60 flex-wrap gap-2">
                    <div class="text-[11px] text-slate-400 flex items-center gap-1.5 truncate max-w-xl">
                        <span class="text-rose-400 font-semibold flex-shrink-0">Prompt render:</span>
                        <span class="font-mono text-slate-500 truncate" id="scene-prompt-preview-${i}">${escapeHtml(scene.prompt || '')}</span>
                    </div>
                    <button type="button" onclick="renderVideoScene(${i})" id="btn-render-scene-${i}"
                            class="px-4 py-2 rounded-xl bg-gradient-to-r from-rose-600 via-pink-600 to-purple-600 hover:from-rose-500 hover:via-pink-500 hover:to-purple-500 text-white font-semibold text-xs shadow-md shadow-rose-600/25 flex items-center gap-2 transition active:scale-95">
                        <i class="fa-solid ${isSuccess ? 'fa-arrows-rotate' : 'fa-film'} text-xs" id="btn-render-icon-${i}"></i>
                        <span id="btn-render-text-${i}">${isSuccess ? 'Render lại cảnh này' : (isError ? 'Thử render lại' : 'Render cảnh này')}</span>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

async function renderVideoScene(sceneIndex) {
    const scene = videoModalScenes[sceneIndex];
    if (!scene) return;

    const btn = document.getElementById(`btn-render-scene-${sceneIndex}`);
    const btnText = document.getElementById(`btn-render-text-${sceneIndex}`);
    const btnIcon = document.getElementById(`btn-render-icon-${sceneIndex}`);
    const ph = document.getElementById(`scene-placeholder-${sceneIndex}`);
    const loadEl = document.getElementById(`scene-loading-${sceneIndex}`);
    const resEl = document.getElementById(`scene-result-${sceneIndex}`);
    const errEl = document.getElementById(`scene-error-${sceneIndex}`);
    const errText = document.getElementById(`scene-error-text-${sceneIndex}`);
    const player = document.getElementById(`scene-video-player-${sceneIndex}`);
    const downloadBtn = document.getElementById(`scene-download-btn-${sceneIndex}`);

    scene.status = 'rendering';
    if (ph) ph.classList.add('hidden');
    if (resEl) resEl.classList.add('hidden');
    if (errEl) errEl.classList.add('hidden');
    if (loadEl) loadEl.classList.remove('hidden');

    if (btn) btn.disabled = true;
    if (btnText) btnText.textContent = 'Đang render video...';
    if (btnIcon) btnIcon.className = 'fa-solid fa-spinner fa-spin text-xs';

    const selectedModel = document.getElementById('genVideoModelSelect')?.value || 'kling-2.0';

    try {
        const payload = {
            prompt: scene.prompt,
            model: selectedModel,
            ratio: currentVideoRatio,
            duration: scene.duration || 6,
            reference_media: videoRefMediaData,
            scene_number: scene.scene_number || (sceneIndex + 1)
        };

        const res = await fetch(`/api/prompts/${currentPromptId}/generate-video`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Lỗi khi gọi API tạo video');
        }

        const data = await res.json();
        const videoUrl = data.video_url;

        scene.status = 'success';
        scene.video_url = videoUrl;

        if (loadEl) loadEl.classList.add('hidden');
        if (resEl) resEl.classList.remove('hidden');
        if (player) player.src = videoUrl;
        if (downloadBtn) {
            downloadBtn.href = videoUrl;
            downloadBtn.download = `scene_${scene.scene_number || (sceneIndex + 1)}.mp4`;
        }

        if (btn) btn.disabled = false;
        if (btnText) btnText.textContent = 'Render lại cảnh này';
        if (btnIcon) btnIcon.className = 'fa-solid fa-arrows-rotate text-xs';

        showToast(`Đã tạo video Cảnh ${scene.scene_number || (sceneIndex + 1)} thành công!`);
    } catch (err) {
        console.error('Error rendering video scene:', err);
        scene.status = 'error';
        scene.error_message = err.message;

        if (loadEl) loadEl.classList.add('hidden');
        if (errEl) errEl.classList.remove('hidden');
        if (errText) errText.textContent = `Lỗi: ${err.message}`;

        if (btn) btn.disabled = false;
        if (btnText) btnText.textContent = 'Thử render lại';
        if (btnIcon) btnIcon.className = 'fa-solid fa-arrows-rotate text-xs';

        showToast(`Lỗi tạo video cảnh ${scene.scene_number || (sceneIndex + 1)}: ${err.message}`);
    }
}

async function openGenerateVideoModal(promptId = null) {
    if (promptId && promptId !== currentPromptId) {
        await selectPrompt(promptId, true);
    }

    if (!currentPromptDetail && currentPromptId) {
        try {
            const res = await fetch(`/api/prompts/${currentPromptId}`);
            if (res.ok) currentPromptDetail = await res.json();
        } catch (e) {
            console.error('Failed to load current prompt detail:', e);
        }
    }

    const badge = document.getElementById('genVideoPromptBadge');
    if (badge) {
        badge.innerText = `#${(currentPromptId || 'VIDEO').toUpperCase()}`;
    }

    // Refresh provider configuration & populate video models from .env
    await fetchProviderConfig();
    populateVideoModelSelect();

    // Populate Prompt text
    const promptInput = document.getElementById('genVideoPromptText');
    if (promptInput) {
        promptInput.value = currentPromptDetail?.prompt_code || currentPromptDetail?.raw_content || '';
    }

    // Reset reference
    clearGenVideoRef();
    switchVideoRefTab('upload');
    setVideoRatio('9:16');

    // Populate existing images/videos into thumbnail list
    const thumbsContainer = document.getElementById('videoRefExistingThumbs');
    if (thumbsContainer) {
        const images = (currentPromptDetail && currentPromptDetail.images) || [];
        if (images.length > 0) {
            thumbsContainer.innerHTML = images.map((img, idx) => {
                const src = getImageSource(img);
                return `
                    <div onclick="selectExistingVideoRef('${src}', 'Mẫu #${idx + 1}')"
                         class="cursor-pointer rounded-lg overflow-hidden border border-dark-700 hover:border-purple-500 transition aspect-square bg-dark-800 relative group/th">
                        <img src="${src}" class="w-full h-full object-cover" onerror="handleThumbError(this)">
                        <div class="absolute inset-0 bg-purple-600/20 opacity-0 group-hover/th:opacity-100 transition flex items-center justify-center">
                            <i class="fa-solid fa-check text-white text-xs"></i>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            thumbsContainer.innerHTML = '<p class="text-xs text-slate-500 col-span-full">Không có tư liệu mẫu nào trong câu lệnh này.</p>';
        }
    }

    // Detect scenes from current prompt
    videoModalScenes = detectScenesFromCurrentPrompt();

    const countBadge = document.getElementById('genVideoScenesCountBadge');
    if (countBadge) {
        countBadge.innerText = `${videoModalScenes.length} scenes`;
    }

    // Render Scene cards
    renderVideoModalSceneCards();

    const modal = document.getElementById('generateVideoModal');
    if (modal) {
        modal.classList.remove('hidden');
    }
}

function closeGenerateVideoModal() {
    const modal = document.getElementById('generateVideoModal');
    if (modal) {
        modal.classList.add('hidden');
        // Pause any video players
        const videos = modal.querySelectorAll('video');
        videos.forEach(v => {
            try { v.pause(); } catch (e) {}
        });
    }
}

function switchRefTab(tab) {
    currentActiveRefTab = tab;
    const btnKoc = document.getElementById('btnRefTabKoc');
    const btnUpload = document.getElementById('btnRefTabUpload');
    const kocContent = document.getElementById('refTabKocContent');
    const uploadContent = document.getElementById('refTabUploadContent');

    if (tab === 'koc') {
        if (btnKoc) btnKoc.className = 'px-2.5 py-1 rounded-md font-medium transition flex items-center gap-1.5 bg-purple-600 text-white shadow';
        if (btnUpload) btnUpload.className = 'px-2.5 py-1 rounded-md font-medium text-slate-400 hover:text-white transition flex items-center gap-1.5';
        if (kocContent) kocContent.classList.remove('hidden');
        if (uploadContent) uploadContent.classList.add('hidden');
        if (!kocListCache) {
            loadKocList(false);
        }
    } else {
        if (btnUpload) btnUpload.className = 'px-2.5 py-1 rounded-md font-medium transition flex items-center gap-1.5 bg-purple-600 text-white shadow';
        if (btnKoc) btnKoc.className = 'px-2.5 py-1 rounded-md font-medium text-slate-400 hover:text-white transition flex items-center gap-1.5';
        if (uploadContent) uploadContent.classList.remove('hidden');
        if (kocContent) kocContent.classList.add('hidden');
    }
}

async function loadKocList(forceRefresh = false) {
    const select = document.getElementById('genKocSelect');
    const icon = document.getElementById('kocRefreshIcon');
    if (icon) icon.classList.add('fa-spin');

    if (select && (!kocListCache || forceRefresh)) {
        select.innerHTML = '<option value="">-- Đang nạp danh sách KOC... --</option>';
        select.disabled = true;
    }

    try {
        const res = await fetch(`/api/koc/list?refresh=${forceRefresh ? 'true' : 'false'}`);
        const data = await res.json();
        if (!res.ok || data.status !== 'success') {
            throw new Error(data.detail || 'Không thể tải danh sách KOC');
        }

        kocListCache = data.kocs || [];
        if (select) {
            select.disabled = false;
            if (kocListCache.length === 0) {
                select.innerHTML = '<option value="">-- Không có KOC nào --</option>';
            } else {
                const prevVal = select.value;
                select.innerHTML = [
                    `<option value="">-- Chọn nhân vật KOC (${kocListCache.length}) --</option>`,
                    ...kocListCache.map(k => `<option value="${escapeHtml(k.name)}">${escapeHtml(k.name)} (${k.count} ảnh)</option>`)
                ].join('');

                if (prevVal && kocListCache.some(k => k.name === prevVal)) {
                    select.value = prevVal;
                    onKocSelectChange();
                }
            }
        }
        if (forceRefresh) {
            showToast('Đã quét và làm mới danh sách KOC');
        }
    } catch (err) {
        console.error('Failed to load KOC list:', err);
        if (select) {
            select.disabled = false;
            select.innerHTML = '<option value="">-- Lỗi nạp danh sách KOC --</option>';
        }
        showGenError('Không thể lấy danh sách KOC từ koc_management: ' + err.message);
    } finally {
        if (icon) icon.classList.remove('fa-spin');
    }
}

async function onKocSelectChange() {
    const select = document.getElementById('genKocSelect');
    const kocName = select ? select.value : '';
    const container = document.getElementById('kocGalleryContainer');
    const nameText = document.getElementById('kocSelectedNameText');
    const countBadge = document.getElementById('kocSelectedCountBadge');
    const listEl = document.getElementById('kocImagesList');

    if (!kocName) {
        if (container) container.classList.add('hidden');
        if (currentRefSource === 'koc') {
            clearGenRefImage();
        }
        return;
    }

    if (nameText) nameText.innerText = kocName;
    if (container) container.classList.remove('hidden');
    if (listEl) {
        listEl.innerHTML = '<div class="col-span-full py-4 text-center text-xs text-slate-400"><i class="fa-solid fa-spinner fa-spin mr-1.5 text-purple-400"></i> Đang nạp danh sách ảnh...</div>';
    }

    try {
        let images = kocImagesCache[kocName];
        if (!images) {
            const res = await fetch(`/api/koc/images?name=${encodeURIComponent(kocName)}`);
            const data = await res.json();
            if (!res.ok || data.status !== 'success') {
                throw new Error(data.detail || 'Không thể lấy ảnh KOC');
            }
            images = data.images || [];
            kocImagesCache[kocName] = images;
        }

        if (countBadge) countBadge.innerText = `${images.length} ảnh`;

        if (!images || images.length === 0) {
            if (listEl) listEl.innerHTML = '<div class="col-span-full py-4 text-center text-xs text-slate-500">Chưa có ảnh nào cho KOC này</div>';
            return;
        }

        if (listEl) {
            listEl.innerHTML = images.map((img, idx) => {
                const isSelected = selectedKocImagePath === img.path;
                const encodedImg = encodeURIComponent(JSON.stringify(img));
                return `
                    <button type="button" onclick="selectKocImage('${encodedImg}')"
                            id="kocCard_${idx}"
                            class="koc-image-card relative group rounded-lg overflow-hidden border-2 transition aspect-square bg-dark-900 flex flex-col justify-end p-1 text-left ${isSelected ? 'border-purple-500 ring-2 ring-purple-500/50 bg-purple-500/10' : 'border-dark-700 hover:border-purple-400/80'}"
                            title="${escapeHtml(img.name)}${img.caption ? ' - ' + escapeHtml(img.caption) : ''}">
                        <img src="${img.url}" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition" loading="lazy" onerror="this.src='/static/favicon.png'">
                        <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition"></div>
                        <span class="koc-selected-badge absolute top-1 right-1 w-4 h-4 rounded-full bg-purple-600 text-white flex items-center justify-center text-[9px] shadow ${isSelected ? '' : 'hidden'}">
                            <i class="fa-solid fa-check"></i>
                        </span>
                        <span class="relative z-10 text-[9px] text-slate-200 truncate w-full px-1 py-0.5 rounded bg-black/70 backdrop-blur-xs font-mono">
                            ${escapeHtml(img.name)}
                        </span>
                    </button>
                `;
            }).join('');
        }
    } catch (err) {
        console.error('Failed to load KOC images:', err);
        if (listEl) listEl.innerHTML = `<div class="col-span-full py-4 text-center text-xs text-rose-400">Lỗi: ${escapeHtml(err.message)}</div>`;
    }
}

function selectKocImage(encodedImgJson) {
    try {
        const img = JSON.parse(decodeURIComponent(encodedImgJson));
        const select = document.getElementById('genKocSelect');
        const kocName = select ? select.value : 'KOC';

        currentRefSource = 'koc';
        selectedKocImagePath = img.path;
        selectedKocImageObj = img;
        pendingUploadFileData = null;
        currentRefImageData = null; // Sẽ upload lên S3 khi bấm "Tạo ảnh ngay"

        // Update card styles
        document.querySelectorAll('.koc-image-card').forEach(card => {
            card.classList.remove('border-purple-500', 'ring-2', 'ring-purple-500/50', 'bg-purple-500/10');
            card.classList.add('border-dark-700');
            const badge = card.querySelector('.koc-selected-badge');
            if (badge) badge.classList.add('hidden');
        });

        // Highlight selected card
        const allCards = document.querySelectorAll('.koc-image-card');
        allCards.forEach(card => {
            if (card.title.includes(img.name)) {
                card.classList.remove('border-dark-700');
                card.classList.add('border-purple-500', 'ring-2', 'ring-purple-500/50', 'bg-purple-500/10');
                const badge = card.querySelector('.koc-selected-badge');
                if (badge) badge.classList.remove('hidden');
            }
        });

        // Show preview box
        const previewBox = document.getElementById('genRefImagePreview');
        const previewImg = document.getElementById('genRefImagePreviewImg');
        const sourceBadge = document.getElementById('genRefSourceBadge');
        const captionBox = document.getElementById('genRefImageCaptionBox');

        if (previewImg) previewImg.src = img.url;
        if (sourceBadge) sourceBadge.innerText = `KOC: ${kocName}`;
        if (captionBox) {
            captionBox.innerHTML = `
                <div class="font-medium text-slate-200 truncate">${escapeHtml(img.name)}</div>
                <div class="text-[10px] text-slate-400 mt-0.5 line-clamp-2">${escapeHtml(img.caption || 'Chưa có chú thích')}</div>
            `;
            captionBox.classList.remove('hidden');
        }
        if (previewBox) previewBox.classList.remove('hidden');
        document.getElementById('genErrorBanner')?.classList.add('hidden');

        showToast(`Đã chọn ảnh của ${kocName}`);
    } catch (e) {
        console.error('Failed to select KOC image:', e);
    }
}

function handleGenRefImageUpload(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
        showGenError('Vui lòng chọn file ảnh hợp lệ (PNG, JPG, WEBP).');
        return;
    }
    if (file.size > 15 * 1024 * 1024) {
        showGenError('Ảnh tham chiếu không được vượt quá 15MB.');
        return;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
        const localData = e.target.result;
        currentRefSource = 'upload';
        pendingUploadFileData = localData;
        selectedKocImagePath = null;
        selectedKocImageObj = null;
        currentRefImageData = null; // Sẽ upload lên S3 khi bấm "Tạo ảnh ngay"

        // Unhighlight any KOC cards
        document.querySelectorAll('.koc-image-card').forEach(card => {
            card.classList.remove('border-purple-500', 'ring-2', 'ring-purple-500/50', 'bg-purple-500/10');
            card.classList.add('border-dark-700');
            const badge = card.querySelector('.koc-selected-badge');
            if (badge) badge.classList.add('hidden');
        });

        // Show preview box
        const previewBox = document.getElementById('genRefImagePreview');
        const previewImg = document.getElementById('genRefImagePreviewImg');
        const sourceBadge = document.getElementById('genRefSourceBadge');
        const captionBox = document.getElementById('genRefImageCaptionBox');

        if (previewImg) previewImg.src = localData;
        if (sourceBadge) sourceBadge.innerText = `Tệp tải lên: ${file.name}`;
        if (captionBox) {
            captionBox.innerHTML = `
                <div class="font-medium text-slate-200 truncate">${escapeHtml(file.name)}</div>
                <div class="text-[10px] text-slate-400 mt-0.5">Dung lượng: ${formatFileSize(file.size)} • Sẵn sàng tải lên S3 khi tạo ảnh</div>
            `;
            captionBox.classList.remove('hidden');
        }
        if (previewBox) previewBox.classList.remove('hidden');
        document.getElementById('genErrorBanner')?.classList.add('hidden');

        showToast('Đã nạp ảnh từ máy tính (sẽ upload lên S3 khi bấm Tạo ảnh ngay)');
    };
    reader.onerror = function() {
        showGenError('Không thể đọc file ảnh từ máy tính.');
    };
    reader.readAsDataURL(file);
}

function clearGenRefImage() {
    currentRefSource = 'none';
    selectedKocImagePath = null;
    selectedKocImageObj = null;
    pendingUploadFileData = null;
    currentRefImageData = null;
    referenceImageUploadPending = false;

    const fileInput = document.getElementById('genRefImageUpload');
    if (fileInput) fileInput.value = '';

    const previewBox = document.getElementById('genRefImagePreview');
    if (previewBox) previewBox.classList.add('hidden');

    document.querySelectorAll('.koc-image-card').forEach(card => {
        card.classList.remove('border-purple-500', 'ring-2', 'ring-purple-500/50', 'bg-purple-500/10');
        card.classList.add('border-dark-700');
        const badge = card.querySelector('.koc-selected-badge');
        if (badge) badge.classList.add('hidden');
    });
}

function selectExistingImageAsRef(src) {
    if (!src) return;
    currentRefSource = 'existing';
    currentRefImageData = src;
    selectedKocImagePath = null;
    selectedKocImageObj = null;
    pendingUploadFileData = null;

    const previewBox = document.getElementById('genRefImagePreview');
    const previewImg = document.getElementById('genRefImagePreviewImg');
    const sourceBadge = document.getElementById('genRefSourceBadge');
    const captionBox = document.getElementById('genRefImageCaptionBox');

    if (previewImg) previewImg.src = src;
    if (sourceBadge) sourceBadge.innerText = 'Ảnh mẫu từ bản ghi';
    if (captionBox) {
        captionBox.innerHTML = '<div class="text-[10px] text-slate-400">Đã chọn ảnh mẫu có sẵn của câu lệnh này làm ảnh tham chiếu</div>';
        captionBox.classList.remove('hidden');
    }
    if (previewBox) previewBox.classList.remove('hidden');
    document.getElementById('genErrorBanner')?.classList.add('hidden');
}

function showGenError(msg) {
    const banner = document.getElementById('genErrorBanner');
    const textEl = document.getElementById('genErrorText');
    if (banner && textEl) {
        textEl.innerText = msg;
        banner.classList.remove('hidden');
    }
}

function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

async function submitGenerateImage() {
    if (!currentPromptId) {
        showGenError('Vui lòng chọn một bản ghi prompt trước khi tạo ảnh.');
        return;
    }

    const promptText = document.getElementById('genPromptText').value.trim();
    if (!promptText) {
        showGenError('Vui lòng nhập nội dung câu lệnh prompt.');
        return;
    }

    const extraDesc = document.getElementById('genExtraDesc').value.trim();
    const genSize = document.getElementById('genSizeSelect')?.value || '1024x1024';
    const genQuality = document.getElementById('genQualitySelect')?.value || 'hd';
    const genDetail = document.getElementById('genDetailSelect')?.value || 'high';

    // UI state: reset banners
    document.getElementById('genErrorBanner').classList.add('hidden');
    document.getElementById('genResultSection').classList.add('hidden');

    const btnSubmit = document.getElementById('btnSubmitGenerate');
    const btnText = document.getElementById('btnSubmitGenerateText');
    if (btnSubmit) btnSubmit.disabled = true;

    // 1. Upload reference image to S3 if not uploaded yet
    let refImageUrl = currentRefImageData;
    if (!refImageUrl) {
        let uploadTarget = null;
        let uploadMsg = '';

        if (currentRefSource === 'koc' && selectedKocImagePath) {
            uploadTarget = selectedKocImagePath;
            uploadMsg = 'Đang tải ảnh KOC lên S3...';
        } else if (currentRefSource === 'upload' && pendingUploadFileData) {
            uploadTarget = pendingUploadFileData;
            uploadMsg = 'Đang tải ảnh lên S3...';
        }

        if (uploadTarget) {
            if (btnText) btnText.innerText = uploadMsg;
            referenceImageUploadPending = true;
            try {
                const uploadRes = await fetch('/api/reference-images/upload', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: uploadTarget })
                });
                const uploadData = await uploadRes.json();
                if (!uploadRes.ok || !uploadData.url) {
                    throw new Error(uploadData.detail || uploadData.message || 'Không nhận được URL từ S3');
                }
                refImageUrl = uploadData.url;
                currentRefImageData = refImageUrl;
                showToast('Đã tải ảnh tham chiếu lên S3 thành công');
            } catch (uploadErr) {
                referenceImageUploadPending = false;
                if (btnSubmit) btnSubmit.disabled = false;
                if (btnText) btnText.innerText = 'Tạo ảnh ngay';
                showGenError('Tải ảnh lên S3 thất bại: ' + uploadErr.message);
                return;
            } finally {
                referenceImageUploadPending = false;
            }
        }
    }

    // 2. AI Image Generation
    document.getElementById('genLoadingState').classList.remove('hidden');
    if (btnText) btnText.innerText = 'Đang tạo ảnh AI...';

    const selectedModel = document.getElementById('genImageModelSelect')?.value || undefined;

    // Timer counter
    genTimerSeconds = 0;
    const timerEl = document.getElementById('genLoadingTimer');
    const modelDisplayName = selectedModel || 'Custom OpenAI Router';
    if (timerEl) timerEl.innerText = `Đang kết nối tới ${modelDisplayName} (0s)...`;
    if (genTimerInterval) clearInterval(genTimerInterval);
    genTimerInterval = setInterval(() => {
        genTimerSeconds++;
        if (timerEl) {
            timerEl.innerText = `Đang kết nối tới ${modelDisplayName} (${genTimerSeconds}s)...`;
        }
    }, 1000);

    try {
        const response = await fetch(`/api/prompts/${currentPromptId}/generate-image-stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: promptText,
                reference_image: refImageUrl,
                extra_description: extraDesc,
                size: genSize,
                quality: genQuality,
                image_detail: genDetail,
                provider: currentGenProvider,
                model: selectedModel
            })
        });

        if (!response.ok) {
            const responseText = await response.text();
            let errData;
            try { errData = JSON.parse(responseText); } catch (_) {}
            throw new Error(errData?.detail || errData?.message || ('Lỗi server HTTP ' + response.status));
        }

        // Đọc SSE stream realtime
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let receivedImage = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed.startsWith('data:')) continue;
                const dataStr = trimmed.slice(5).trim();
                if (!dataStr || dataStr === '[DONE]') continue;

                let evt;
                try {
                    evt = JSON.parse(dataStr);
                } catch (_) {
                    continue;
                }

                if (evt.type === 'status') {
                    if (timerEl) {
                        timerEl.innerText = `${evt.message} (${genTimerSeconds}s)...`;
                    }
                } else if (evt.type === 'complete' && evt.image_url) {
                    receivedImage = true;
                    currentGeneratedImageData = evt.image_url;

                    const resultImg = document.getElementById('genResultImg');
                    if (resultImg) resultImg.src = evt.image_url;

                    const formatBadge = document.getElementById('genResultFormatBadge');
                    if (formatBadge) {
                        formatBadge.innerText = (evt.format || 'IMAGE').toUpperCase();
                    }

                    const noteEl = document.getElementById('genResultNote');
                    if (noteEl) {
                        noteEl.innerText = evt.message || 'Tạo ảnh thành công từ AI';
                    }
                } else if (evt.type === 'error') {
                    throw new Error(evt.message || 'Lỗi từ mô hình AI');
                }
            }
        }

        if (!receivedImage) {
            throw new Error('Mô hình AI không trả về ảnh kết quả');
        }

        // Reset save button state
        const btnSave = document.getElementById('btnSaveToRecord');
        if (btnSave) {
            btnSave.disabled = false;
            btnSave.className = 'flex-1 px-4 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-bold shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 transition active:scale-95';
            btnSave.innerHTML = '<i class="fa-solid fa-floppy-disk text-sm"></i><span>Lưu vào bản ghi này</span>';
        }

        document.getElementById('genLoadingState').classList.add('hidden');
        document.getElementById('genResultSection').classList.remove('hidden');

        // Scroll modal into result
        document.getElementById('genResultSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        showToast('AI đã tạo ảnh thành công!');

    } catch (err) {
        console.error('Error generating image:', err);
        document.getElementById('genLoadingState').classList.add('hidden');
        showGenError(err.message || 'Lỗi khi gửi yêu cầu tới AI. Vui lòng kiểm tra lại cấu hình .env.');
    } finally {
        if (genTimerInterval) {
            clearInterval(genTimerInterval);
            genTimerInterval = null;
        }
        btnSubmit.disabled = false;
        btnText.innerText = 'Tạo lại / Sinh ảnh mới';
    }
}

async function triggerDirectDownload(urlOrDataUri, defaultFilename = 'download_image.png') {
    if (!urlOrDataUri) return;

    // Desktop app (pywebview): use native Save-As dialog
    if (window.pywebview && window.pywebview.api && window.pywebview.api.save_file) {
        let dataUri = urlOrDataUri;
        // If not a data URI, fetch and convert to data URI
        if (!urlOrDataUri.startsWith('data:')) {
            try {
                const res = await fetch(urlOrDataUri);
                const blob = await res.blob();
                dataUri = await new Promise(resolve => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.readAsDataURL(blob);
                });
            } catch (err) {
                showToast('Lỗi khi tải ảnh: ' + err.message);
                return;
            }
        }
        try {
            const result = await window.pywebview.api.save_file(defaultFilename, dataUri);
            if (result) {
                showToast(`Đã lưu ảnh: ${result}`);
            }
        } catch (err) {
            showToast('Lỗi khi lưu: ' + err.message);
        }
        return;
    }

    // Browser: standard download
    if (urlOrDataUri.startsWith('data:')) {
        const a = document.createElement('a');
        a.href = urlOrDataUri;
        a.download = defaultFilename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast(`Đã tải ảnh về: ${defaultFilename}`);
        return;
    }

    try {
        showToast('Đang tải ảnh về máy...');
        const res = await fetch(urlOrDataUri);
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = defaultFilename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
        showToast(`Đã lưu ảnh về máy: ${defaultFilename}`);
    } catch (err) {
        const a = document.createElement('a');
        a.href = urlOrDataUri;
        a.target = '_blank';
        a.download = defaultFilename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast('Đang mở ảnh để tải về...');
    }
}

async function downloadCurrentGeneratedImage() {
    if (!currentGeneratedImageData) {
        showToast('Chưa có dữ liệu ảnh để tải về.');
        return;
    }
    const filename = `${currentPromptId || 'prompt'}_ai_${Date.now()}.png`;
    await triggerDirectDownload(currentGeneratedImageData, filename);
}

async function saveGeneratedImageToRecord() {
    if (!currentGeneratedImageData || !currentPromptId) {
        showToast('Chưa có ảnh hoặc bản ghi được chọn.');
        return;
    }

    const btnSave = document.getElementById('btnSaveToRecord');
    btnSave.disabled = true;
    btnSave.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin text-sm"></i><span>Đang lưu vào bản ghi...</span>';

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/save-generated-image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image_data: currentGeneratedImageData })
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'Không thể lưu ảnh vào bản ghi');
        }

        // Update current prompt detail
        if (data.prompt) {
            currentPromptDetail = data.prompt;
            const images = currentPromptDetail.images || [];

            // Update in local prompts list
            const found = currentPromptsList.find(p => p.id === currentPromptId);
            if (found) {
                found.images = images;
                found.image_count = images.length;
            }

            // Re-render detail workspace & slider (ensures container is shown, counter & thumbnails updated)
            renderDetail(currentPromptDetail);

            // Re-render sidebar list & update card image badge
            renderPromptList(currentPromptsList);
            highlightActivePromptCard(currentPromptId);
            updateSidebarImageCount(currentPromptId, images.length);

            // Go to newest slide
            if (images.length > 0) {
                goToSlide(images.length - 1);
            }

            // Update stats
            fetchStats();
        }

        btnSave.className = 'flex-1 px-4 py-2.5 rounded-xl bg-emerald-600 text-white text-xs font-bold shadow-lg shadow-emerald-600/25 flex items-center justify-center gap-2 transition';
        btnSave.innerHTML = '<i class="fa-solid fa-circle-check text-sm text-emerald-200"></i><span>Đã lưu vào bản ghi!</span>';
        showToast('Đã thêm ảnh vào bộ sưu tập của câu lệnh này thành công!');

    } catch (err) {
        console.error('Error saving image to record:', err);
        showToast(`Lỗi khi lưu ảnh: ${err.message}`);
        btnSave.disabled = false;
        btnSave.innerHTML = '<i class="fa-solid fa-floppy-disk text-sm"></i><span>Lưu vào bản ghi này</span>';
    }
}

// ==========================================
// AI Prompt Improvement Logic
// ==========================================
let currentImproveProvider = 'openai';
let currentImproveResult = null;
let improveTimerInterval = null;
let improveTimerSeconds = 0;
let isOriginalPromptCollapsed = false;

function setImproveProvider(provider) {
    currentImproveProvider = 'openai';
    const btnOpenAI = document.getElementById('btnImproveProviderOpenAI');
    const badge = document.getElementById('improveProviderInfoBadge');

    if (btnOpenAI) {
        btnOpenAI.className = 'px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 bg-emerald-600 text-white shadow';
    }
    if (badge) {
        const chatModel = providerConfigCache?.openai?.chat_model || 'Custom Router';
        badge.innerText = `Custom OpenAI (${chatModel})`;
        badge.className = 'text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30';
    }
}

async function openImproveModal(promptId = null) {
    if (promptId && promptId !== currentPromptId) {
        await selectPrompt(promptId, true);
    }

    if (currentPromptId && hasBackgroundTask(currentPromptId, 'improve_prompt')) {
        showToast('Tác vụ cải tiến câu lệnh này đang được xử lý trong nền...');
        return;
    }

    if (!currentPromptDetail && currentPromptId) {
        try {
            const res = await fetch(`/api/prompts/${currentPromptId}`);
            if (res.ok) currentPromptDetail = await res.json();
        } catch (e) {
            console.error('Failed to load current prompt detail:', e);
        }
    }

    // Refresh provider config cache
    await fetchProviderConfig();
    if (providerConfigCache?.active_provider) {
        setImproveProvider(providerConfigCache.active_provider);
    } else {
        setImproveProvider('openai');
    }

    // Badge
    const badge = document.getElementById('improvePromptBadge');
    if (badge) {
        badge.innerText = `#${(currentPromptId || 'PROMPT').toUpperCase()}`;
    }

    // Original Prompt Text
    const origCode = getCurrentPromptCode();
    const origDisplay = document.getElementById('improveOriginalPromptText');
    if (origDisplay) {
        origDisplay.innerText = origCode || '(Không có nội dung câu lệnh)';
    }

    // Reset instruction input
    const instructionInput = document.getElementById('improveInstructionInput');
    if (instructionInput) {
        instructionInput.value = '';
    }

    // Reset error, loading, and results
    document.getElementById('improveErrorBanner').classList.add('hidden');
    document.getElementById('improveLoadingState').classList.add('hidden');
    document.getElementById('improveResultSection').classList.add('hidden');
    currentImproveResult = null;

    // Reset buttons
    const btnSubmit = document.getElementById('btnSubmitImprove');
    if (btnSubmit) {
        btnSubmit.disabled = false;
        document.getElementById('btnSubmitImproveText').innerText = 'Gửi AI cải tiến';
    }

    const btnOverwrite = document.getElementById('btnImproveOverwrite');
    const btnNewVersion = document.getElementById('btnImproveNewVersion');
    if (btnOverwrite) btnOverwrite.disabled = true;
    if (btnNewVersion) btnNewVersion.disabled = true;

    // Show modal
    const modal = document.getElementById('improvePromptModal');
    if (modal) {
        modal.classList.remove('hidden');
    }

    setTimeout(() => {
        if (instructionInput) instructionInput.focus();
    }, 150);
}

function closeImproveModal() {
    const modal = document.getElementById('improvePromptModal');
    if (modal) {
        modal.classList.add('hidden');
    }
    if (improveTimerInterval) {
        clearInterval(improveTimerInterval);
        improveTimerInterval = null;
    }
    // Hủy kết quả cải tiến tạm thời nếu đóng hộp thoại mà chưa bấm Lưu đè
    currentImproveResult = null;
    const resultSection = document.getElementById('improveResultSection');
    if (resultSection) {
        resultSection.classList.add('hidden');
    }
    const errorBanner = document.getElementById('improveErrorBanner');
    if (errorBanner) {
        errorBanner.classList.add('hidden');
    }
    const loadingState = document.getElementById('improveLoadingState');
    if (loadingState) {
        loadingState.classList.add('hidden');
    }
}

function toggleImproveOriginalPrompt() {
    isOriginalPromptCollapsed = !isOriginalPromptCollapsed;
    const wrapper = document.getElementById('improveOriginalPromptWrapper');
    const icon = document.getElementById('toggleOrigPromptIcon');
    const text = document.getElementById('toggleOrigPromptText');
    if (isOriginalPromptCollapsed) {
        if (wrapper) wrapper.classList.add('hidden');
        if (icon) icon.className = 'fa-solid fa-chevron-down text-[10px]';
        if (text) text.innerText = 'Xem chi tiết';
    } else {
        if (wrapper) wrapper.classList.remove('hidden');
        if (icon) icon.className = 'fa-solid fa-chevron-up text-[10px]';
        if (text) text.innerText = 'Thu gọn';
    }
}

function appendImproveSuggestion(snippet) {
    const input = document.getElementById('improveInstructionInput');
    if (!input) return;
    if (!input.value.trim()) {
        input.value = snippet;
    } else {
        input.value = input.value.trim() + ' ' + snippet;
    }
    input.focus();
}

function showImproveError(msg) {
    const banner = document.getElementById('improveErrorBanner');
    const text = document.getElementById('improveErrorText');
    if (banner && text) {
        text.innerText = msg || 'Đã xảy ra lỗi khi cải tiến prompt.';
        banner.classList.remove('hidden');
    }
}

async function submitImprovePrompt() {
    if (!currentPromptId) {
        showToast('Vui lòng chọn một bản ghi prompt trước');
        return;
    }

    const targetPromptId = currentPromptId;
    const targetTitle = (currentPromptDetail && currentPromptDetail.title) || `#${targetPromptId}`;

    const instructionInput = document.getElementById('improveInstructionInput');
    const instruction = instructionInput ? instructionInput.value.trim() : '';
    if (!instruction) {
        showImproveError('Vui lòng nhập nội dung yêu cầu cải tiến vào ô bên dưới.');
        if (instructionInput) instructionInput.focus();
        return;
    }

    if (hasActiveOrQueuedTask(targetPromptId, 'improve_prompt')) {
        showToast('Tác vụ cải tiến câu lệnh này đã có trong hàng đợi hoặc đang chạy.');
        return;
    }

    document.getElementById('improveErrorBanner').classList.add('hidden');
    document.getElementById('improveResultSection').classList.add('hidden');
    const loadingEl = document.getElementById('improveLoadingState');
    if (loadingEl) loadingEl.classList.remove('hidden');

    const btnSubmit = document.getElementById('btnSubmitImprove');
    if (btnSubmit) {
        btnSubmit.disabled = true;
        const btnText = document.getElementById('btnSubmitImproveText');
        if (btnText) btnText.innerText = 'Đang xử lý ngầm...';
    }

    // Start timer in modal
    improveTimerSeconds = 0;
    const timerText = document.getElementById('improveLoadingTimer');
    if (timerText) {
        timerText.innerText = `Đang kết nối tới mô hình AI (${currentImproveProvider})... (0s)`;
    }
    if (improveTimerInterval) clearInterval(improveTimerInterval);
    improveTimerInterval = setInterval(() => {
        improveTimerSeconds++;
        if (timerText) {
            timerText.innerText = `Đang tối ưu hóa câu lệnh & bóc tách dynamic form... (${improveTimerSeconds}s)`;
        }
    }, 1000);

    enqueueAiTask(targetPromptId, 'improve_prompt', targetTitle, async () => {
        try {
            const res = await fetch(`/api/prompts/${targetPromptId}/improve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    instruction: instruction,
                    provider: currentImproveProvider,
                    auto_save: false
                })
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `Lỗi máy chủ (${res.status})`);
            }

            const data = await res.json();
            currentImproveResult = data;

            // Render modal preview (không tự động lưu đè cho đến khi người dùng bấm 'Lưu đè')
            const modal = document.getElementById('improvePromptModal');
            const isModalOpen = modal && !modal.classList.contains('hidden');
            if (isModalOpen && currentPromptId === targetPromptId) {

                // Render Explanation
                const expEl = document.getElementById('improveExplanationText');
                if (expEl) {
                    expEl.innerText = data.explanation || 'Đã tối ưu hóa và tích hợp đầy đủ các yêu cầu bổ sung vào prompt.';
                }

                // Render Changes List
                const changesListEl = document.getElementById('improveChangesList');
                if (changesListEl) {
                    const changes = data.changes || [];
                    if (changes.length > 0) {
                        changesListEl.innerHTML = `
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                                ${changes.map(ch => `
                                    <div class="p-2.5 rounded-lg bg-dark-900 border border-dark-700/80 space-y-1">
                                        <div class="flex items-center justify-between">
                                            <span class="text-[11px] font-semibold text-emerald-400 flex items-center gap-1">
                                                <i class="fa-solid fa-arrow-trend-up text-[10px]"></i>
                                                ${escapeHtml(ch.area || 'Điểm nâng cấp')}
                                            </span>
                                        </div>
                                        ${ch.before ? `<p class="text-[11px] text-slate-500 line-through"><span class="text-slate-600">Trước:</span> ${escapeHtml(ch.before)}</p>` : ''}
                                        <p class="text-[11px] text-slate-200"><span class="text-emerald-400/90 font-medium">Sau:</span> ${escapeHtml(ch.after || '')}</p>
                                        ${ch.reason ? `<p class="text-[10px] text-slate-400 italic"><span class="text-slate-500">Lý do:</span> ${escapeHtml(ch.reason)}</p>` : ''}
                                    </div>
                                `).join('')}
                            </div>
                        `;
                    } else {
                        changesListEl.innerHTML = '';
                    }
                }

                // Render Improved Prompt Code Display
                const codeDisplay = document.getElementById('improvePromptCodeDisplay');
                if (codeDisplay) {
                    codeDisplay.innerText = data.prompt_code || '';
                }
                const charBadge = document.getElementById('improveCharCountBadge');
                if (charBadge) {
                    charBadge.innerText = `${(data.prompt_code || '').length} chars`;
                }

                const typeBadge = document.getElementById('improveResultTypeBadge');
                if (typeBadge) {
                    typeBadge.innerText = (data.prompt_type || 'JSON').toUpperCase();
                }

                // Render Dynamic Form Fields Table/Grid
                const fields = data.fields || [];
                const countBadge = document.getElementById('improveDynamicFieldsCount');
                if (countBadge) {
                    countBadge.innerText = `${fields.length} trường`;
                }

                const fieldsContainer = document.getElementById('improveDynamicFieldsContainer');
                if (fieldsContainer) {
                    if (fields.length > 0) {
                        fieldsContainer.innerHTML = fields.map((f, idx) => `
                            <div class="flex flex-col sm:flex-row sm:items-center justify-between p-2.5 rounded-lg bg-dark-850 border border-dark-750 gap-2">
                                <div class="flex items-center gap-2 min-w-0 sm:w-1/3">
                                    <span class="w-5 h-5 rounded bg-dark-900 text-slate-400 text-[10px] font-mono flex items-center justify-center flex-shrink-0 border border-dark-700">
                                        ${idx + 1}
                                    </span>
                                    <div class="min-w-0">
                                        <div class="text-xs font-semibold text-slate-200 truncate">${escapeHtml(f.label || f.key)}</div>
                                        <div class="text-[10px] font-mono text-slate-500 truncate">${escapeHtml(f.path)}</div>
                                    </div>
                                </div>
                                <div class="sm:w-2/3">
                                    <input type="text" value="${escapeHtml(f.value || '')}"
                                           onchange="onImproveFieldEdit('${escapeHtml(f.path)}', this.value)"
                                           class="w-full px-2.5 py-1.5 bg-dark-900 text-slate-100 text-xs font-mono rounded border border-dark-700 focus:outline-none focus:border-emerald-500 transition">
                                </div>
                            </div>
                        `).join('');
                    } else {
                        fieldsContainer.innerHTML = `
                            <div class="p-4 text-center text-slate-500 text-xs">
                                Không có trường tham số động riêng lẻ nào.
                            </div>
                        `;
                    }
                }

                // Enable Save Buttons
                const btnOverwrite = document.getElementById('btnImproveOverwrite');
                const btnNewVersion = document.getElementById('btnImproveNewVersion');
                if (btnOverwrite) btnOverwrite.disabled = false;
                if (btnNewVersion) btnNewVersion.disabled = false;

                // Reveal Result Section
                const resultSection = document.getElementById('improveResultSection');
                if (resultSection) {
                    resultSection.classList.remove('hidden');
                    resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }

                showToast(`✓ Đã tạo bản cải tiến cho "${targetTitle}". Xem kết quả bên dưới và bấm "Lưu đè" nếu đồng ý.`);
            } else {
                showToast(`✓ Đã tạo bản cải tiến cho "${targetTitle}". Mở hộp thoại để xem và chọn lưu.`);
            }

        } catch (err) {
            console.error('Improve error:', err);
            const modal = document.getElementById('improvePromptModal');
            const isModalOpen = modal && !modal.classList.contains('hidden');
            if (isModalOpen && currentPromptId === targetPromptId) {
                showImproveError(`Lỗi: ${err.message}`);
            } else {
                showToast(`Lỗi khi cải tiến "${targetTitle}": ${err.message}`);
            }
        } finally {
            if (improveTimerInterval) {
                clearInterval(improveTimerInterval);
                improveTimerInterval = null;
            }
            const loadingEl = document.getElementById('improveLoadingState');
            if (loadingEl) loadingEl.classList.add('hidden');
            const btnSubmit = document.getElementById('btnSubmitImprove');
            if (btnSubmit) {
                btnSubmit.disabled = false;
                const btnText = document.getElementById('btnSubmitImproveText');
                if (btnText) btnText.innerText = 'Gửi AI cải tiến lại';
            }
        }
    });
}

function onImproveFieldEdit(path, newValue) {
    if (!currentImproveResult || !currentImproveResult.fields) return;
    const f = currentImproveResult.fields.find(item => item.path === path);
    if (f) {
        f.value = newValue;
    }
    // If parsed_json exists, update it as well
    if (currentImproveResult.parsed_json) {
        setValueByPath(currentImproveResult.parsed_json, path, newValue);
        currentImproveResult.prompt_code = JSON.stringify(currentImproveResult.parsed_json, null, 2);
        const codeDisplay = document.getElementById('improvePromptCodeDisplay');
        if (codeDisplay) {
            codeDisplay.innerText = currentImproveResult.prompt_code;
        }
        const charBadge = document.getElementById('improveCharCountBadge');
        if (charBadge) {
            charBadge.innerText = `${currentImproveResult.prompt_code.length} chars`;
        }
    }
}

function copyImprovedPromptCode() {
    const codeDisplay = document.getElementById('improvePromptCodeDisplay');
    const text = codeDisplay ? codeDisplay.innerText : '';
    if (!text) return;

    navigator.clipboard.writeText(text).then(() => {
        showToast('Đã chép câu lệnh cải tiến vào bộ nhớ tạm!');
    }).catch(() => {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('Đã chép câu lệnh!');
    });
}

async function saveImproveOverwrite() {
    if (!currentPromptId || !currentImproveResult) return;

    const btn = document.getElementById('btnImproveOverwrite');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i><span>Đang lưu đè...</span>';

    try {
        const origRaw = (currentPromptDetail && (currentPromptDetail.original_raw_content || currentPromptDetail.raw_content || currentPromptDetail.prompt_code)) || '';
        const res = await fetch(`/api/prompts/${currentPromptId}/save-improved`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: 'overwrite',
                title: currentImproveResult.title,
                prompt_code: currentImproveResult.prompt_code,
                raw_content: origRaw,
                prompt_type: currentImproveResult.prompt_type,
                parsed_json: currentImproveResult.parsed_json,
                fields: currentImproveResult.fields
            })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi lưu đè câu lệnh');
        }

        const data = await res.json();
        currentPromptDetail = data.prompt;

        // Update in currentPromptsList
        const found = currentPromptsList.find(p => p.id === currentPromptId);
        if (found) {
            found.title = currentPromptDetail.title;
            found.prompt_type = currentPromptDetail.prompt_type;
            found.parsed_json = currentPromptDetail.parsed_json;
            found.raw_content = currentPromptDetail.raw_content;
            found.original_raw_content = currentPromptDetail.original_raw_content;
        }

        // Update card in sidebar
        const cardTitle = document.querySelector(`#prompt-card-${currentPromptId} h4`);
        if (cardTitle) {
            cardTitle.innerText = currentPromptDetail.title;
        }
        const cardBadge = document.querySelector(`#prompt-card-${currentPromptId} span:last-child`);
        if (cardBadge) {
            const isJson = currentPromptDetail.prompt_type === 'json' || currentPromptDetail.parsed_json;
            cardBadge.innerText = isJson ? 'JSON' : 'TEXT';
            cardBadge.className = `text-[10px] px-1.5 py-0.5 rounded font-medium ${isJson ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'bg-slate-700/50 text-slate-300'}`;
        }

        // Re-render detail workspace
        renderDetail(currentPromptDetail);

        closeImproveModal();
        showToast('Đã lưu đè thành công câu lệnh (văn bản gốc được bảo toàn)!');

    } catch (err) {
        console.error('Save overwrite error:', err);
        showToast(`Lỗi: ${err.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-pen-to-square"></i><span>Lưu đè</span>';
    }
}

async function saveImproveNewVersion() {
    if (!currentPromptId || !currentImproveResult) return;

    const btn = document.getElementById('btnImproveNewVersion');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i><span>Đang tạo phiên bản mới...</span>';

    try {
        const origRaw = (currentPromptDetail && (currentPromptDetail.original_raw_content || currentPromptDetail.raw_content || currentPromptDetail.prompt_code)) || '';
        const res = await fetch(`/api/prompts/${currentPromptId}/save-improved`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: 'new_version',
                title: currentImproveResult.title,
                prompt_code: currentImproveResult.prompt_code,
                raw_content: origRaw,
                prompt_type: currentImproveResult.prompt_type,
                parsed_json: currentImproveResult.parsed_json,
                fields: currentImproveResult.fields
            })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi lưu phiên bản mới');
        }

        const data = await res.json();
        const newPrompt = data.prompt;

        closeImproveModal();

        // Refresh stats & load prompts, selecting the newly created prompt
        await fetchStats();
        await loadPrompts(newPrompt.id);

        showToast(`Đã lưu thành công phiên bản mới: "${newPrompt.title}"!`);

    } catch (err) {
        console.error('Save new version error:', err);
        showToast(`Lỗi: ${err.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-copy"></i><span>Lưu thành phiên bản mới</span>';
    }
}

// ==========================================
// Add Media / Additional Images Functionality
// ==========================================
let addMediaUploadedFiles = [];
let currentAddMediaTab = 'upload';
let modalExistingImages = [];
let draggedImageIndex = null;

function setAddMediaTab(tab) {
    currentAddMediaTab = tab;
    const tabUpload = document.getElementById('tabAddMediaUpload');
    const tabUrl = document.getElementById('tabAddMediaUrl');
    const paneUpload = document.getElementById('paneAddMediaUpload');
    const paneUrl = document.getElementById('paneAddMediaUrl');

    if (tab === 'url') {
        if (tabUpload) {
            tabUpload.className = 'px-3 py-1 rounded-md font-medium transition flex items-center gap-1.5 text-slate-400 hover:text-white';
        }
        if (tabUrl) {
            tabUrl.className = 'px-3 py-1 rounded-md font-medium transition flex items-center gap-1.5 bg-dark-700 text-brand-400';
        }
        if (paneUpload) paneUpload.classList.add('hidden');
        if (paneUrl) paneUrl.classList.remove('hidden');
        const urlInput = document.getElementById('addMediaUrlInput');
        if (urlInput) setTimeout(() => urlInput.focus(), 50);
    } else {
        if (tabUpload) {
            tabUpload.className = 'px-3 py-1 rounded-md font-medium transition flex items-center gap-1.5 bg-dark-700 text-brand-400';
        }
        if (tabUrl) {
            tabUrl.className = 'px-3 py-1 rounded-md font-medium transition flex items-center gap-1.5 text-slate-400 hover:text-white';
        }
        if (paneUpload) paneUpload.classList.remove('hidden');
        if (paneUrl) paneUrl.classList.add('hidden');
    }
}

function openAddMediaModal() {
    if (!currentPromptId) {
        showToast('Vui lòng chọn một câu lệnh trước khi tải thêm ảnh!');
        return;
    }

    const badge = document.getElementById('addMediaPromptBadge');
    if (badge) {
        badge.innerText = `#${currentPromptId.toUpperCase()}`;
    }

    const errBanner = document.getElementById('addMediaErrorBanner');
    if (errBanner) errBanner.classList.add('hidden');

    const urlInput = document.getElementById('addMediaUrlInput');
    if (urlInput) urlInput.value = '';

    clearAllAddMediaFiles();
    setAddMediaTab('upload');

    // Render current existing images in prompt
    renderModalExistingImages(currentPromptDetail?.images || []);

    const modal = document.getElementById('addMediaModal');
    if (modal) {
        modal.classList.remove('hidden');
    }
}

function closeAddMediaModal() {
    const modal = document.getElementById('addMediaModal');
    if (modal) {
        modal.classList.add('hidden');
    }
    clearAllAddMediaFiles();
}

function handleAddMediaFiles(e) {
    const files = e.target.files;
    if (files && files.length > 0) {
        processAddMediaFiles(files);
    }
}

function processAddMediaFiles(files) {
    const validImageTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/svg+xml'];
    let errorMsg = null;

    Array.from(files).forEach(file => {
        if (!validImageTypes.includes(file.type) && !file.name.match(/\.(jpg|jpeg|png|webp|gif|svg)$/i)) {
            errorMsg = `Tệp "${file.name}" không phải định dạng ảnh hợp lệ (PNG, JPG, WEBP, GIF).`;
            return;
        }
        if (file.size > 15 * 1024 * 1024) {
            errorMsg = `Ảnh "${file.name}" quá lớn (vượt quá 15MB).`;
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            addMediaUploadedFiles.push({
                name: file.name,
                size: file.size,
                dataUrl: e.target.result
            });
            renderAddMediaThumbnails();
        };
        reader.readAsDataURL(file);
    });

    if (errorMsg) {
        showToast(errorMsg);
    }
}

function renderAddMediaThumbnails() {
    const previewBox = document.getElementById('addMediaPreviewContainer');
    const thumbnails = document.getElementById('addMediaThumbnails');
    const countEl = document.getElementById('addMediaUploadedCount');
    const tabLabel = document.getElementById('labelTabAddMediaUpload');

    if (tabLabel) {
        tabLabel.innerText = addMediaUploadedFiles.length > 0 ? `Tải ảnh lên (${addMediaUploadedFiles.length})` : 'Tải ảnh lên từ máy';
    }

    if (!previewBox || !thumbnails) return;

    if (addMediaUploadedFiles.length === 0) {
        previewBox.classList.add('hidden');
        thumbnails.innerHTML = '';
        return;
    }

    previewBox.classList.remove('hidden');
    if (countEl) {
        countEl.innerText = `${addMediaUploadedFiles.length} ảnh mới đã chọn`;
    }

    thumbnails.innerHTML = addMediaUploadedFiles.map((fileObj, idx) => `
        <div class="relative group/thumb flex-shrink-0 w-16 h-16 rounded-xl overflow-hidden border border-dark-700 bg-dark-900 shadow">
            <img src="${fileObj.dataUrl}" alt="${escapeHtml(fileObj.name)}" class="w-full h-full object-cover">
            <button type="button" onclick="removeAddMediaFile(${idx})"
                    title="Gỡ ảnh này"
                    class="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/80 hover:bg-rose-600 text-white text-[10px] flex items-center justify-center transition shadow">
                <i class="fa-solid fa-xmark"></i>
            </button>
            <div class="absolute bottom-0 inset-x-0 bg-dark-900/80 px-1 py-0.5 text-[9px] text-slate-300 font-mono truncate text-center pointer-events-none">
                ${formatFileSize(fileObj.size)}
            </div>
        </div>
    `).join('');
}

function removeAddMediaFile(index) {
    if (index >= 0 && index < addMediaUploadedFiles.length) {
        addMediaUploadedFiles.splice(index, 1);
        renderAddMediaThumbnails();
    }
}

function clearAllAddMediaFiles() {
    addMediaUploadedFiles = [];
    const fileInput = document.getElementById('addMediaFileInput');
    if (fileInput) fileInput.value = '';
    renderAddMediaThumbnails();
}

async function submitAddMedia() {
    if (!currentPromptId) {
        showToast('Vui lòng chọn một câu lệnh trước khi thêm ảnh!');
        return;
    }

    const banner = document.getElementById('addMediaErrorBanner');
    const errorText = document.getElementById('addMediaErrorText');
    if (banner) banner.classList.add('hidden');

    const urlInput = document.getElementById('addMediaUrlInput');
    const urlVal = urlInput ? urlInput.value.trim() : '';
    const uploadedBase64List = addMediaUploadedFiles.map(f => f.dataUrl);

    if (uploadedBase64List.length === 0 && !urlVal) {
        if (banner && errorText) {
            errorText.innerText = 'Vui lòng chọn ít nhất một tệp ảnh để tải lên hoặc dán ít nhất một đường dẫn (URL) ảnh!';
            banner.classList.remove('hidden');
        } else {
            showToast('Vui lòng chọn ảnh từ máy hoặc dán link ảnh!');
        }
        return;
    }

    const btnSubmit = document.getElementById('btnSubmitAddMedia');
    const btnText = document.getElementById('btnSubmitAddMediaText');
    btnSubmit.disabled = true;
    if (btnText) btnText.innerText = 'Đang lưu ảnh...';

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/add-images`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                media: urlVal,
                images: uploadedBase64List
            })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi thêm ảnh vào câu lệnh');
        }

        const data = await res.json();
        const refreshedPrompt = data.prompt;

        if (refreshedPrompt) {
            currentPromptDetail = refreshedPrompt;

            // Update in currentPromptsList
            const found = currentPromptsList.find(p => p.id === currentPromptId);
            if (found) {
                found.images = refreshedPrompt.images || [];
                found.image_count = found.images.length;
            }

            // Re-render slider & detail outside
            renderDetail(currentPromptDetail);

            // Re-render modal existing images
            renderModalExistingImages(currentPromptDetail.images || []);

            // Clear upload inputs
            clearAllAddMediaFiles();
            if (urlInput) urlInput.value = '';

            // Update sidebar card count badge and list
            renderPromptList(currentPromptsList);
            highlightActivePromptCard(currentPromptId);
            updateSidebarImageCount(currentPromptId, (currentPromptDetail.images || []).length);
            fetchStats();

            // Navigate slider to the newly added image (last image)
            if (currentPromptDetail.images && currentPromptDetail.images.length > 0) {
                goToSlide(currentPromptDetail.images.length - 1);
            }
        }

        showToast(data.message || 'Đã nạp thêm ảnh vào câu lệnh thành công!');

    } catch (err) {
        console.error('Error adding images:', err);
        if (banner && errorText) {
            errorText.innerText = err.message || 'Đã xảy ra lỗi khi thêm ảnh';
            banner.classList.remove('hidden');
        } else {
            showToast(`Lỗi: ${err.message}`);
        }
    } finally {
        btnSubmit.disabled = false;
        if (btnText) btnText.innerText = 'Nạp ảnh mới vào câu lệnh';
    }
}

// ==========================================
// Existing Images Management (Drag Reorder & Delete)
// ==========================================

function renderModalExistingImages(images) {
    modalExistingImages = images ? [...images] : [];
    const listEl = document.getElementById('modalExistingImagesList');
    const emptyEl = document.getElementById('modalNoExistingImages');
    const badgeEl = document.getElementById('modalExistingImgCountBadge');

    if (badgeEl) {
        badgeEl.innerText = `${modalExistingImages.length} ảnh`;
    }

    if (!listEl) return;

    if (modalExistingImages.length === 0) {
        listEl.innerHTML = '';
        if (emptyEl) emptyEl.classList.remove('hidden');
        return;
    }

    if (emptyEl) emptyEl.classList.add('hidden');

    listEl.innerHTML = modalExistingImages.map((img, idx) => {
        const src = getImageSource(img);
        const name = img.filename || (img.url ? img.url.split('/').pop().split('?')[0] : `Ảnh #${idx + 1}`);
        const isCover = idx === 0;

        return `
            <div class="existing-img-card relative group rounded-xl bg-dark-900 border ${isCover ? 'border-brand-500/60 ring-1 ring-brand-500/20' : 'border-dark-700'} p-2 flex flex-col gap-1.5 transition-all duration-150 cursor-grab active:cursor-grabbing hover:border-brand-500/40 hover:bg-dark-850 shadow-md"
                 draggable="true"
                 data-index="${idx}"
                 ondragstart="handleImageDragStart(event, ${idx})"
                 ondragover="handleImageDragOver(event, ${idx})"
                 ondragenter="handleImageDragEnter(event, ${idx})"
                 ondragleave="handleImageDragLeave(event, ${idx})"
                 ondrop="handleImageDrop(event, ${idx})"
                 ondragend="handleImageDragEnd(event)">
                 
                <!-- Top Header: Order Badge & Drag Grip -->
                <div class="flex items-center justify-between gap-1 text-[10px] pointer-events-none">
                    <span class="font-mono px-1.5 py-0.5 rounded text-[10px] font-bold ${isCover ? 'bg-brand-500 text-white shadow-sm' : 'bg-dark-800 text-slate-300 border border-dark-700'}">
                        ${isCover ? 'Ảnh bìa (#1)' : `#${idx + 1}`}
                    </span>
                    <span class="text-slate-500 group-hover:text-brand-400 transition">
                        <i class="fa-solid fa-grip-vertical text-xs"></i>
                    </span>
                </div>

                <!-- Thumbnail Preview -->
                <div class="relative w-full aspect-square rounded-lg overflow-hidden bg-dark-950 border border-dark-800 pointer-events-none flex items-center justify-center">
                    <img src="${src}" alt="${escapeHtml(name)}" class="w-full h-full object-cover select-none" onerror="handleThumbError(this)">
                </div>

                <!-- Card Footer: Name & Action -->
                <div class="flex items-center justify-between gap-1 pt-0.5">
                    <span class="text-[10px] text-slate-400 font-mono truncate flex-1 pointer-events-none" title="${escapeHtml(name)}">
                        ${escapeHtml(name)}
                    </span>
                    <button type="button" 
                            onclick="deletePromptExistingImage(event, ${img.id})"
                            class="w-6 h-6 rounded-lg bg-dark-800 hover:bg-rose-600 text-slate-400 hover:text-white text-xs flex items-center justify-center transition shadow flex-shrink-0"
                            title="Xóa ảnh này khỏi câu lệnh">
                        <i class="fa-regular fa-trash-can text-[11px]"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function handleImageDragStart(e, index) {
    draggedImageIndex = index;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', index);
    setTimeout(() => {
        if (e.target) {
            e.target.classList.add('opacity-40', 'scale-95', 'border-dashed', 'border-brand-500');
        }
    }, 0);
}

function handleImageDragOver(e, index) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
}

function handleImageDragEnter(e, index) {
    e.preventDefault();
    if (index === draggedImageIndex) return;
    const card = e.currentTarget;
    if (card) {
        card.classList.add('ring-2', 'ring-brand-500', 'scale-105', 'bg-dark-800');
    }
}

function handleImageDragLeave(e, index) {
    const card = e.currentTarget;
    if (card) {
        card.classList.remove('ring-2', 'ring-brand-500', 'scale-105', 'bg-dark-800');
    }
}

async function handleImageDrop(e, targetIndex) {
    e.preventDefault();
    e.stopPropagation();

    const card = e.currentTarget;
    if (card) {
        card.classList.remove('ring-2', 'ring-brand-500', 'scale-105', 'bg-dark-800');
    }

    if (draggedImageIndex === null || draggedImageIndex === targetIndex) {
        return;
    }

    // Reorder array locally
    const movedItem = modalExistingImages.splice(draggedImageIndex, 1)[0];
    modalExistingImages.splice(targetIndex, 0, movedItem);

    // Re-render modal existing images
    renderModalExistingImages(modalExistingImages);

    // Update main screen detail and slider
    if (currentPromptDetail) {
        currentPromptDetail.images = [...modalExistingImages];
        renderDetail(currentPromptDetail);
    }
    const found = currentPromptsList.find(p => p.id === currentPromptId);
    if (found) {
        found.images = [...modalExistingImages];
    }

    // Call API to persist reordering
    try {
        const imageIds = modalExistingImages.map(img => img.id);
        const res = await fetch(`/api/prompts/${currentPromptId}/reorder-images`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image_ids: imageIds })
        });
        if (res.ok) {
            const data = await res.json();
            if (data.prompt) {
                currentPromptDetail = data.prompt;
                modalExistingImages = [...(currentPromptDetail.images || [])];
            }
            showToast('Đã đổi thứ tự ảnh thành công!');
        } else {
            throw new Error('Lỗi từ máy chủ khi lưu thứ tự');
        }
    } catch (err) {
        console.error('Error reordering images:', err);
        showToast('Không thể lưu thứ tự ảnh mới');
    }
}

function handleImageDragEnd(e) {
    draggedImageIndex = null;
    document.querySelectorAll('.existing-img-card').forEach(card => {
        card.classList.remove('opacity-40', 'scale-95', 'border-dashed', 'border-brand-500', 'ring-2', 'ring-brand-500', 'scale-105', 'bg-dark-800');
    });
}

async function deletePromptExistingImage(e, imgId) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }
    if (!currentPromptId || !imgId) return;

    if (!confirm('Bạn có chắc chắn muốn xóa ảnh này khỏi câu lệnh?')) {
        return;
    }

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/images/${imgId}`, {
            method: 'DELETE'
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi xóa ảnh');
        }

        const data = await res.json();
        const refreshed = data.prompt;

        if (refreshed) {
            currentPromptDetail = refreshed;
            modalExistingImages = [...(refreshed.images || [])];

            // Re-render modal existing images
            renderModalExistingImages(modalExistingImages);

            // Re-render detail & slider outside
            renderDetail(currentPromptDetail);

            // Update in currentPromptsList
            const found = currentPromptsList.find(p => p.id === currentPromptId);
            if (found) {
                found.images = refreshed.images || [];
                found.image_count = found.images.length;
            }

            // Update sidebar card badge and list
            renderPromptList(currentPromptsList);
            highlightActivePromptCard(currentPromptId);
            updateSidebarImageCount(currentPromptId, (refreshed.images || []).length);
            fetchStats();
        }

        showToast('Đã xóa ảnh khỏi câu lệnh!');
    } catch (err) {
        console.error('Error deleting image:', err);
        showToast(`Lỗi: ${err.message}`);
    }
}

function updateSidebarImageCount(promptId, count) {
    const activeCard = document.getElementById(`prompt-card-${promptId}`);
    if (!activeCard) return;

    const imgBadge = activeCard.querySelector('span.text-amber-400\\/90');
    if (count > 0) {
        if (imgBadge) {
            imgBadge.innerHTML = `<i class="fa-solid fa-image text-[9px]"></i> ${count}`;
        } else {
            const badgeContainer = activeCard.querySelector('.flex.items-center.gap-1\\.5');
            if (badgeContainer) {
                const newBadge = document.createElement('span');
                newBadge.className = 'text-[10px] px-1.5 py-0.5 rounded bg-dark-900/90 text-amber-400/90 border border-amber-500/20 flex items-center gap-1';
                newBadge.innerHTML = `<i class="fa-solid fa-image text-[9px]"></i> ${count}`;
                badgeContainer.insertBefore(newBadge, badgeContainer.firstChild);
            }
        }
    } else if (imgBadge) {
        imgBadge.remove();
    }
}

// ==========================================
// AI Assistant Search & Recommendation Chat Module
// ==========================================
let isAiChatOpen = false;
let aiChatCategory = 'all'; // 'all' | 'image' | 'content'
let aiChatHistory = [];
let isAiChatLoading = false;

function initAiChatListeners() {
    const chatInput = document.getElementById('aiChatInput');
    if (chatInput) {
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendAiChatMessage();
            }
        });

        chatInput.addEventListener('input', () => {
            chatInput.style.height = 'auto';
            chatInput.style.height = Math.min(chatInput.scrollHeight, 96) + 'px';
        });
    }

    // Auto-close on mobile when clicking outside
    document.addEventListener('click', (e) => {
        const widget = document.getElementById('aiChatWidget');
        const fab = document.getElementById('aiAssistantFab');
        if (isAiChatOpen && widget && fab && !widget.contains(e.target) && !fab.contains(e.target)) {
            if (window.innerWidth < 640) {
                closeAiChat();
            }
        }
    });

    // Try restoring conversation from sessionStorage
    try {
        const saved = sessionStorage.getItem('ai_chat_history');
        if (saved) {
            aiChatHistory = JSON.parse(saved);
        }
    } catch (e) {}
}

function toggleAiChat() {
    if (isAiChatOpen) {
        closeAiChat();
    } else {
        openAiChat();
    }
}

function openAiChat() {
    const widget = document.getElementById('aiChatWidget');
    const fabIcon = document.getElementById('aiFabIcon');
    if (!widget) return;

    isAiChatOpen = true;
    widget.classList.remove('hidden');

    if (fabIcon) {
        fabIcon.className = 'fa-solid fa-xmark';
    }

    // Render messages or welcome if empty
    const messagesEl = document.getElementById('aiChatMessages');
    if (messagesEl) {
        if (!aiChatHistory || aiChatHistory.length === 0) {
            renderAiChatWelcome();
        } else if (messagesEl.children.length === 0) {
            renderAllChatHistory();
        }
    }

    const input = document.getElementById('aiChatInput');
    if (input) {
        setTimeout(() => input.focus(), 100);
    }
    scrollAiChatToBottom();
}

function closeAiChat() {
    const widget = document.getElementById('aiChatWidget');
    const fabIcon = document.getElementById('aiFabIcon');
    if (!widget) return;

    isAiChatOpen = false;
    widget.classList.add('hidden');

    if (fabIcon) {
        fabIcon.className = 'fa-solid fa-wand-magic-sparkles';
    }
}

function setAiChatCategory(cat) {
    aiChatCategory = cat;
    const btnAll = document.getElementById('aiCatAll');
    const btnImg = document.getElementById('aiCatImage');
    const btnCnt = document.getElementById('aiCatContent');
    const badge = document.getElementById('aiChatCandidatesBadge');

    const activeClasses = 'px-2 py-0.5 rounded font-semibold transition bg-brand-600 text-white shadow-xs';
    const inactiveClasses = 'px-2 py-0.5 rounded font-medium text-slate-400 hover:text-white transition';

    if (btnAll) btnAll.className = cat === 'all' ? activeClasses : inactiveClasses;
    if (btnImg) btnImg.className = cat === 'image' ? activeClasses : inactiveClasses;
    if (btnCnt) btnCnt.className = cat === 'content' ? activeClasses : inactiveClasses;

    if (badge) {
        if (cat === 'image') badge.innerText = '351 prompt ảnh';
        else if (cat === 'content') badge.innerText = '88 prompt content';
        else badge.innerText = '439 prompts sẵn sàng';
    }

    // If chat is showing only welcome, refresh quick chips
    if (aiChatHistory.length === 0) {
        renderAiChatWelcome();
    }
}

function clearAiChat() {
    aiChatHistory = [];
    try {
        sessionStorage.removeItem('ai_chat_history');
    } catch (e) {}

    const input = document.getElementById('aiChatInput');
    if (input) {
        input.value = '';
        input.style.height = 'auto';
    }

    renderAiChatWelcome();
    showToast('Đã làm mới cuộc trò chuyện AI!');
}

function renderAiChatWelcome() {
    const messagesEl = document.getElementById('aiChatMessages');
    if (!messagesEl) return;

    let chips = [];
    if (aiChatCategory === 'content') {
        chips = [
            'Kịch bản video TikTok 60s KOC review mỹ phẩm',
            'Kịch bản livestream chốt đơn flash sale dồn dập',
            'Bài viết blog chuẩn SEO 1500 từ tiếp thị liên kết',
            'Kịch bản video hài hước tình huống đời sống'
        ];
    } else if (aiChatCategory === 'image') {
        chips = [
            'Chân dung cô gái áo dài vintage chiều thu Hà Nội',
            'Storyboard 12 ô truyện tranh phong cách anime',
            'Ảnh chụp sản phẩm đồ uống studio ánh sáng neon',
            'Chân dung nàng thơ điện ảnh Cinematic ngoài trời'
        ];
    } else {
        chips = [
            'Chân dung cô gái áo dài vintage chiều thu Hà Nội',
            'Kịch bản video TikTok 60s review mỹ phẩm mờ thâm',
            'Storyboard 12 ô truyện tranh phong cách anime',
            'Kịch bản livestream chốt đơn Shopee / TikTok Shop'
        ];
    }

    messagesEl.innerHTML = `
        <div class="space-y-3 animate-fade-in">
            <div class="flex items-start gap-2.5">
                <div class="w-7 h-7 rounded-xl bg-gradient-to-tr from-indigo-600 to-brand-500 flex items-center justify-center text-white flex-shrink-0 text-xs shadow-md shadow-indigo-500/20">
                    <i class="fa-solid fa-wand-magic-sparkles text-amber-300"></i>
                </div>
                <div class="bg-dark-800 border border-dark-700/80 rounded-2xl rounded-tl-sm p-3.5 space-y-2 text-slate-200 leading-relaxed shadow-sm max-w-[92%]">
                    <p class="font-bold text-white text-xs flex items-center gap-1.5">
                        <span>Xin chào! Tôi là Trợ Lý AI Tìm Prompt</span>
                        <span class="text-[10px] px-1.5 py-0.2 rounded bg-brand-500/20 text-brand-400 border border-brand-500/30">Online</span>
                    </p>
                    <p class="text-slate-300 text-[11px] leading-relaxed">
                        Bạn đang cần tạo hình ảnh hay viết kịch bản gì nhưng không nhớ nổi tên câu lệnh? Hãy mô tả ý tưởng hoặc mục đích bằng ngôn ngữ tự nhiên, tôi sẽ quét toàn bộ kho dữ liệu, gợi ý prompt phù hợp nhất và chấm điểm độ phù hợp cho bạn!
                    </p>
                    <div class="pt-2 space-y-1.5 border-t border-dark-700/60">
                        <span class="text-[10px] font-semibold uppercase tracking-wider text-indigo-400 block flex items-center gap-1">
                            <i class="fa-solid fa-bolt text-amber-400"></i>
                            <span>Bấm để hỏi nhanh:</span>
                        </span>
                        <div class="flex flex-wrap gap-1.5">
                            ${chips.map(chip => `
                                <button type="button" onclick="sendAiChatMessage('${escapeHtml(chip).replace(/'/g, "\\'")}')"
                                        class="px-2.5 py-1 rounded-xl bg-dark-900 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 hover:border-indigo-500/40 text-[11px] transition text-left flex items-center gap-1.5 active:scale-95 shadow-xs">
                                    <i class="fa-solid fa-magnifying-glass text-[9px] text-indigo-400"></i>
                                    <span>${escapeHtml(chip)}</span>
                                </button>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderAllChatHistory() {
    const messagesEl = document.getElementById('aiChatMessages');
    if (!messagesEl) return;
    messagesEl.innerHTML = '';

    aiChatHistory.forEach(item => {
        if (item.role === 'user') {
            appendUserMessageToUI(item.content);
        } else {
            appendAssistantMessageToUI(item.content, item.recommendations, item.suggested_questions);
        }
    });
}

function appendUserMessageToUI(content) {
    const messagesEl = document.getElementById('aiChatMessages');
    if (!messagesEl) return;

    const div = document.createElement('div');
    div.className = 'flex justify-end';
    div.innerHTML = `
        <div class="max-w-[85%] bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-2xl rounded-tr-sm px-3.5 py-2.5 text-xs shadow-md shadow-indigo-600/15 leading-relaxed break-words">
            ${escapeHtml(content)}
        </div>
    `;
    messagesEl.appendChild(div);
}

function formatAiMarkdown(text) {
    if (!text) return '';
    let s = escapeHtml(text);

    // Bold **text**
    s = s.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>');
    
    // Italic *text*
    s = s.replace(/\*(.*?)\*/g, '<em class="text-slate-300 italic">$1</em>');

    // Inline code `code`
    s = s.replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-dark-900 text-amber-300 font-mono text-[10px] border border-dark-700">$1</code>');

    // Bullet list: lines starting with "- " or "* "
    s = s.replace(/(?:^|\n)[-*]\s+(.+)/g, '<div class="flex items-start gap-1.5 my-1"><span class="text-indigo-400 mt-0.5">•</span><span>$1</span></div>');

    // Numbered list: lines starting with "1. ", "2. "
    s = s.replace(/(?:^|\n)(\d+)\.\s+(.+)/g, '<div class="flex items-start gap-1.5 my-1"><span class="font-mono text-indigo-400 font-bold">$1.</span><span>$2</span></div>');

    // Newlines
    s = s.replace(/\n\n+/g, '<div class="h-2"></div>');
    s = s.replace(/\n/g, '<br>');

    return s;
}

function renderPromptRecommendationCard(rec) {
    const score = rec.match_score || 90;
    let scoreBadge = '';
    if (score >= 90) {
        scoreBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1"><i class="fa-solid fa-circle-check text-[9px]"></i>${score}% Rất phù hợp</span>`;
    } else if (score >= 75) {
        scoreBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold font-mono bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 flex items-center gap-1"><i class="fa-solid fa-check text-[9px]"></i>${score}% Phù hợp</span>`;
    } else {
        scoreBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold font-mono bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1">${score}% Tham khảo</span>`;
    }

    const isContent = rec.category === 'content';
    const catBadge = isContent
        ? `<span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 flex items-center gap-1"><i class="fa-solid fa-file-lines text-[8px]"></i>Content</span>`
        : `<span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center gap-1"><i class="fa-solid fa-image text-[8px]"></i>Image</span>`;

    let thumbSrc = rec.thumbnail || '';
    if (thumbSrc.startsWith('/data/images/')) {
        thumbSrc = thumbSrc.replace('/data/images/', '/media/');
    }
    const thumbnailHtml = thumbSrc ? `
        <div class="w-14 h-14 rounded-xl overflow-hidden bg-dark-900 border border-dark-700 flex-shrink-0 cursor-pointer hover:opacity-90 transition relative group/thumb" onclick="navigateToPromptFromChat('${rec.id}', '${rec.category}')" title="Nhấp để mở câu lệnh">
            <img src="${escapeHtml(thumbSrc)}" alt="Thumbnail" class="w-full h-full object-cover" onerror="this.parentElement.style.display='none'">
        </div>
    ` : '';

    return `
        <div class="bg-dark-900/90 border border-dark-700 hover:border-indigo-500/50 rounded-xl p-3 space-y-2.5 transition-all duration-200 shadow-sm hover:shadow-indigo-500/5 group/card">
            <!-- Header: Cat & Score -->
            <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-1.5">
                    <span class="text-[10px] font-mono font-semibold text-slate-400 bg-dark-800 px-1.5 py-0.5 rounded border border-dark-750">#${escapeHtml(rec.id)}</span>
                    ${catBadge}
                </div>
                ${scoreBadge}
            </div>

            <!-- Title & Thumbnail -->
            <div class="flex items-start gap-2.5">
                ${thumbnailHtml}
                <div class="flex-1 min-w-0">
                    <h4 onclick="navigateToPromptFromChat('${rec.id}', '${rec.category}')"
                        class="font-bold text-white text-xs leading-snug hover:text-brand-400 cursor-pointer transition line-clamp-2">
                        ${escapeHtml(rec.title)}
                    </h4>
                    ${rec.tags && rec.tags.length > 0 ? `
                        <div class="flex flex-wrap gap-1 mt-1.5">
                            ${rec.tags.map(t => `<span class="text-[9px] px-1.5 py-0.2 rounded bg-dark-800 text-slate-400 border border-dark-750">#${escapeHtml(t)}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>

            <!-- Reason Box -->
            ${rec.reason ? `
                <div class="bg-dark-850 border border-dark-750 rounded-lg p-2 text-[11px] text-slate-300 leading-relaxed">
                    <div class="text-indigo-400 font-semibold mb-0.5 flex items-center gap-1 text-[10px]">
                        <i class="fa-solid fa-lightbulb text-amber-400"></i>
                        <span>Tại sao nên dùng:</span>
                    </div>
                    <div>${escapeHtml(rec.reason)}</div>
                </div>
            ` : ''}

            <!-- Adjustments Box -->
            ${rec.recommended_adjustments ? `
                <div class="bg-indigo-950/20 border border-indigo-500/20 rounded-lg p-2 text-[11px] text-indigo-200/90 leading-relaxed">
                    <div class="text-indigo-400 font-semibold mb-0.5 flex items-center gap-1 text-[10px]">
                        <i class="fa-solid fa-sliders text-cyan-400"></i>
                        <span>Gợi ý tùy chỉnh tham số:</span>
                    </div>
                    <div>${escapeHtml(rec.recommended_adjustments)}</div>
                </div>
            ` : ''}

            <!-- Action Buttons -->
            <div class="flex items-center gap-2 pt-1 border-t border-dark-800">
                <button type="button" onclick="navigateToPromptFromChat('${rec.id}', '${rec.category}')"
                        class="flex-1 py-1.5 px-2.5 rounded-lg bg-gradient-to-r from-brand-600 to-emerald-600 hover:from-brand-500 hover:to-emerald-500 text-white font-semibold text-[11px] flex items-center justify-center gap-1.5 transition shadow shadow-brand-600/15 active:scale-95">
                    <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
                    <span>Mở trong Studio</span>
                </button>
                <button type="button" onclick="copyPromptCodeFromChat('${rec.id}')"
                        title="Sao chép toàn bộ Prompt này"
                        class="py-1.5 px-2.5 rounded-lg bg-dark-800 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 text-[11px] flex items-center justify-center gap-1.5 transition active:scale-95">
                    <i class="fa-regular fa-copy text-[11px]"></i>
                    <span>Sao chép</span>
                </button>
            </div>
        </div>
    `;
}

function appendAssistantMessageToUI(replyText, recommendations = [], suggestedQuestions = []) {
    const messagesEl = document.getElementById('aiChatMessages');
    if (!messagesEl) return;

    const div = document.createElement('div');
    div.className = 'flex items-start gap-2.5 animate-fade-in';

    let recsHtml = '';
    if (recommendations && recommendations.length > 0) {
        recsHtml = `
            <div class="space-y-2.5 pt-1">
                <div class="flex items-center justify-between text-[11px] font-bold text-white border-b border-dark-700/60 pb-1.5">
                    <span class="flex items-center gap-1.5 text-indigo-400">
                        <i class="fa-solid fa-ranking-star text-amber-400"></i>
                        <span>Gợi ý ${recommendations.length} câu lệnh tốt nhất:</span>
                    </span>
                    <span class="text-[10px] text-slate-400 font-normal">Chấm điểm theo yêu cầu</span>
                </div>
                <div class="space-y-2">
                    ${recommendations.map(r => renderPromptRecommendationCard(r)).join('')}
                </div>
            </div>
        `;
    }

    let questionsHtml = '';
    if (suggestedQuestions && suggestedQuestions.length > 0) {
        questionsHtml = `
            <div class="pt-2 border-t border-dark-700/60 space-y-1.5">
                <span class="text-[10px] font-semibold text-slate-400 block flex items-center gap-1">
                    <i class="fa-regular fa-comments text-indigo-400"></i>
                    <span>Gợi ý bước tiếp theo:</span>
                </span>
                <div class="flex flex-wrap gap-1.5">
                    ${suggestedQuestions.map(q => `
                        <button type="button" onclick="sendAiChatMessage('${escapeHtml(q).replace(/'/g, "\\'")}')"
                                class="px-2.5 py-1 rounded-full bg-dark-900 hover:bg-dark-750 text-indigo-300 hover:text-white border border-indigo-500/25 hover:border-indigo-500/50 text-[10px] transition text-left flex items-center gap-1 active:scale-95">
                            <i class="fa-solid fa-arrow-turn-down fa-rotate-90 text-[8px] text-indigo-400"></i>
                            <span>${escapeHtml(q)}</span>
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
    }

    div.innerHTML = `
        <div class="w-7 h-7 rounded-xl bg-gradient-to-tr from-indigo-600 to-brand-500 flex items-center justify-center text-white flex-shrink-0 text-xs shadow-md shadow-indigo-500/20 mt-0.5">
            <i class="fa-solid fa-wand-magic-sparkles text-amber-300"></i>
        </div>
        <div class="bg-dark-800 border border-dark-700/80 rounded-2xl rounded-tl-sm p-3.5 space-y-3 text-slate-200 leading-relaxed shadow-sm max-w-[92%] break-words text-xs">
            <div class="text-slate-200 leading-relaxed font-sans">${formatAiMarkdown(replyText)}</div>
            ${recsHtml}
            ${questionsHtml}
        </div>
    `;

    messagesEl.appendChild(div);
}

async function sendAiChatMessage(customText = null) {
    if (isAiChatLoading) return;

    const input = document.getElementById('aiChatInput');
    const message = (customText || (input ? input.value : '')).trim();
    if (!message) return;

    if (input) {
        input.value = '';
        input.style.height = 'auto';
    }

    // Append to UI
    appendUserMessageToUI(message);

    // Save to history
    aiChatHistory.push({ role: 'user', content: message });
    try {
        sessionStorage.setItem('ai_chat_history', JSON.stringify(aiChatHistory));
    } catch (e) {}

    scrollAiChatToBottom();

    // Show loading indicator
    isAiChatLoading = true;
    const typingEl = document.getElementById('aiChatTyping');
    const sendBtn = document.getElementById('btnSendAiChat');
    if (typingEl) typingEl.classList.remove('hidden');
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin text-xs"></i>';
    }

    try {
        // Clean history to send only role and string text, avoiding sending nested arrays/objects
        const cleanHistory = (aiChatHistory || [])
            .slice(0, -1)
            .filter(item => item && item.content && typeof item.content === 'string')
            .map(item => ({
                role: item.role === 'user' ? 'user' : 'assistant',
                content: item.content
            }))
            .slice(-6);

        const payload = {
            message: message,
            history: cleanHistory,
            category: aiChatCategory
        };

        const res = await fetch('/api/assistant/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            let errMsg = 'Lỗi máy chủ khi xử lý yêu cầu AI';
            if (err && err.detail) {
                if (typeof err.detail === 'string') {
                    errMsg = err.detail;
                } else if (Array.isArray(err.detail)) {
                    errMsg = err.detail.map(d => (d && d.msg) ? d.msg : JSON.stringify(d)).join('; ');
                } else if (typeof err.detail === 'object') {
                    errMsg = JSON.stringify(err.detail);
                }
            }
            throw new Error(errMsg);
        }

        const data = await res.json();
        const reply = data.reply || 'Dưới đây là các câu lệnh phù hợp nhất:';
        const recs = data.recommendations || [];
        const questions = data.suggested_questions || [];

        // Save assistant message to history
        aiChatHistory.push({
            role: 'assistant',
            content: reply,
            recommendations: recs,
            suggested_questions: questions
        });
        try {
            sessionStorage.setItem('ai_chat_history', JSON.stringify(aiChatHistory));
        } catch (e) {}

        // Render assistant message to UI
        appendAssistantMessageToUI(reply, recs, questions);

    } catch (err) {
        console.error('AI chat error:', err);
        const messagesEl = document.getElementById('aiChatMessages');
        if (messagesEl) {
            const errDiv = document.createElement('div');
            errDiv.className = 'flex items-start gap-2.5 animate-fade-in';
            errDiv.innerHTML = `
                <div class="w-7 h-7 rounded-xl bg-rose-500/20 text-rose-400 flex items-center justify-center flex-shrink-0 text-xs border border-rose-500/30">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                </div>
                <div class="bg-dark-800 border border-rose-500/30 rounded-2xl rounded-tl-sm p-3 text-rose-300 text-xs leading-relaxed max-w-[90%]">
                    <p class="font-bold text-white mb-1">Không thể nhận phản hồi từ AI</p>
                    <p class="text-[11px] text-slate-300">${escapeHtml(err.message)}</p>
                    <button type="button" onclick="sendAiChatMessage('${escapeHtml(message).replace(/'/g, "\\'")}')"
                            class="mt-2 px-2.5 py-1 rounded bg-rose-600/30 hover:bg-rose-600/50 text-rose-200 border border-rose-500/40 text-[10px] flex items-center gap-1 transition">
                        <i class="fa-solid fa-rotate-right"></i>
                        <span>Thử lại</span>
                    </button>
                </div>
            `;
            messagesEl.appendChild(errDiv);
        }
    } finally {
        isAiChatLoading = false;
        if (typingEl) typingEl.classList.add('hidden');
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="fa-solid fa-paper-plane text-xs"></i>';
        }
        scrollAiChatToBottom();
        if (input) input.focus();
    }
}

function scrollAiChatToBottom() {
    const messagesEl = document.getElementById('aiChatMessages');
    if (messagesEl) {
        setTimeout(() => {
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }, 50);
    }
}

function navigateToPromptFromChat(promptId, targetCategory) {
    if (!promptId) return;

    // Check if category switch is needed
    if (targetCategory && (targetCategory === 'image' || targetCategory === 'content') && targetCategory !== currentNavTab) {
        switchNavTab(targetCategory, promptId, true);
    } else {
        selectPrompt(promptId, true);
    }

    showToast(`Đã mở câu lệnh #${promptId} trong Studio!`);

    // On mobile devices, close chat to let user interact with the studio workspace
    if (window.innerWidth < 768) {
        closeAiChat();
    }
}

async function copyPromptCodeFromChat(promptId) {
    if (!promptId) return;

    let promptCode = '';

    // First check in currentPromptDetail if it's already active
    if (currentPromptDetail && currentPromptDetail.id === promptId) {
        promptCode = currentPromptDetail.prompt_code || currentPromptDetail.raw_content || '';
    }

    // Next check in currentPromptsList
    if (!promptCode && currentPromptsList) {
        const found = currentPromptsList.find(p => p.id === promptId);
        if (found) {
            promptCode = found.prompt_code || found.raw_content || '';
        }
    }

    // If still not found, fetch from API
    if (!promptCode) {
        try {
            const res = await fetch(`/api/prompts/${promptId}`);
            if (res.ok) {
                const data = await res.json();
                promptCode = data.prompt_code || data.raw_content || '';
            }
        } catch (e) {
            console.error('Fetch prompt to copy failed:', e);
        }
    }

    if (promptCode) {
        try {
            await navigator.clipboard.writeText(promptCode);
            showToast(`Đã sao chép prompt #${promptId} vào bộ nhớ tạm!`);
        } catch (err) {
            try {
                const ta = document.createElement('textarea');
                ta.value = promptCode;
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                showToast(`Đã sao chép prompt #${promptId}!`);
            } catch (e2) {
                showToast('Không thể sao chép tự động, vui lòng chọn và sao chép thủ công.');
            }
        }
    } else {
        showToast('Không thể lấy nội dung câu lệnh để sao chép.');
    }
}

// ============================================================
//  SYNC — Kiểm tra & Tải cập nhật dữ liệu / phần mềm
// ============================================================

function openSyncModal() {
    document.getElementById('syncModal').classList.remove('hidden');
    document.getElementById('syncStatus').innerHTML = '<p class="text-slate-400">Nhấn nút bên dưới để kiểm tra bản cập nhật mới.</p>';
    document.getElementById('syncPullBtn').classList.add('hidden');
    document.getElementById('syncCheckBtn').disabled = false;
}

function closeSyncModal() {
    document.getElementById('syncModal').classList.add('hidden');
}

async function doSyncCheck() {
    const btn = document.getElementById('syncCheckBtn');
    const status = document.getElementById('syncStatus');
    const pullBtn = document.getElementById('syncPullBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Đang kiểm tra...';
    status.innerHTML = '<p class="text-slate-400 animate-pulse">Đang kết nối tới máy chủ...</p>';

    try {
        const resp = await fetch('/api/sync/check');
        const data = await resp.json();

        if (data.error) {
            status.innerHTML = `<p class="text-red-400"><i class="fa-solid fa-circle-exclamation mr-1"></i> ${data.error}</p>`;
        } else {
            let html = '';
            if (data.has_data) {
                html += `<p class="text-emerald-400"><i class="fa-solid fa-database mr-1"></i> Có <strong>${data.new_count}</strong> prompt mới!</p>`;
                pullBtn.classList.remove('hidden');
            } else {
                html += '<p class="text-slate-400"><i class="fa-solid fa-check-circle mr-1 text-emerald-500"></i> Dữ liệu đã cập nhật mới nhất.</p>';
            }
            if (data.has_app_update) {
                html += `<p class="text-amber-400 mt-2"><i class="fa-solid fa-arrow-up-from-bracket mr-1"></i> Có phiên bản phần mềm mới: <strong>v${data.latest_version}</strong></p>`;
                if (data.installer_url) {
                    html += `<a href="${data.installer_url}" target="_blank" class="inline-block mt-1 text-brand-400 hover:underline text-xs"><i class="fa-solid fa-download mr-1"></i> Tải bộ cài mới</a>`;
                }
            }
            status.innerHTML = html;
        }
    } catch (e) {
        status.innerHTML = `<p class="text-red-400"><i class="fa-solid fa-wifi mr-1"></i> Không thể kết nối. Kiểm tra mạng internet.</p>`;
    }
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-magnifying-glass mr-1"></i> Kiểm tra';
}

async function doSyncPull() {
    const btn = document.getElementById('syncPullBtn');
    const status = document.getElementById('syncStatus');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Đang tải...';

    try {
        const resp = await fetch('/api/sync/pull', { method: 'POST' });
        const data = await resp.json();

        if (data.error) {
            status.innerHTML = `<p class="text-red-400">${data.error}</p>`;
        } else {
            let html = `<p class="text-emerald-400"><i class="fa-solid fa-check-circle mr-1"></i> Đã thêm <strong>${data.inserted}</strong> prompt mới!</p>`;
            if (data.images_queued > 0) {
                html += `<p class="text-slate-400 text-xs mt-1"><i class="fa-solid fa-image mr-1"></i> ${data.images_queued} ảnh đang tải ngầm...</p>`;
            }
            status.innerHTML = html;
            btn.classList.add('hidden');
            if (typeof loadPrompts === 'function') loadPrompts();
            showToast(`Đã cập nhật ${data.inserted} prompt mới!`);
        }
    } catch (e) {
        status.innerHTML = '<p class="text-red-400">Lỗi kết nối khi tải dữ liệu.</p>';
    }
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-download mr-1"></i> Tải về';
}

// ============================================================
//  SETTINGS — Cấu hình AI trong app
// ============================================================

let cfgProvider = 'openai';

function openSettingsModal() {
    document.getElementById('settingsModal').classList.remove('hidden');
    document.getElementById('cfgMsg').textContent = '';
    // Load current config
    fetch('/api/config').then(r => r.json()).then(cfg => {
        cfgProvider = 'openai';
        document.getElementById('cfgBaseUrl').value = cfg.base_url || '';
        document.getElementById('cfgChatModel').value = cfg.chat_model || cfg.model || '';
        document.getElementById('cfgImageModel').value = cfg.image_model || '';
        document.getElementById('cfgImageRefSupport').checked = cfg.image_reference_support || false;
        document.getElementById('cfgS3Enabled').checked = cfg.s3_enabled || false;
        document.getElementById('cfgS3Endpoint').value = cfg.s3_endpoint_url || '';
        document.getElementById('cfgS3Region').value = cfg.s3_region || 'auto';
        document.getElementById('cfgS3Bucket').value = cfg.s3_bucket || '';
        document.getElementById('cfgS3Prefix').value = cfg.s3_key_prefix || 'references';
        document.getElementById('cfgS3AccessKey').value = cfg.s3_access_key_id || '';
        document.getElementById('cfgS3SecretKey').value = '';
        document.getElementById('cfgS3SecretKey').placeholder = cfg.has_s3_secret ? '••••••• (để trống = giữ nguyên)' : 'Secret access key';
        document.getElementById('cfgTimeout').value = cfg.timeout || 300;
        document.getElementById('cfgApiKey').value = '';
        document.getElementById('cfgApiKey').placeholder = cfg.has_api_key ? '••••••• (để trống = giữ nguyên)' : 'sk-...';
    }).catch(() => {});
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.add('hidden');
}

async function cfgSave() {
    const msg = document.getElementById('cfgMsg');
    const payload = {
        provider: 'openai',
        base_url: document.getElementById('cfgBaseUrl').value.trim(),
        api_key: document.getElementById('cfgApiKey').value.trim(),
        chat_model: document.getElementById('cfgChatModel').value.trim(),
        image_model: document.getElementById('cfgImageModel').value.trim(),
        image_reference_support: document.getElementById('cfgImageRefSupport').checked,
        s3_enabled: document.getElementById('cfgS3Enabled').checked,
        s3_endpoint_url: document.getElementById('cfgS3Endpoint').value.trim(),
        s3_region: document.getElementById('cfgS3Region').value.trim() || 'auto',
        s3_bucket: document.getElementById('cfgS3Bucket').value.trim(),
        s3_key_prefix: document.getElementById('cfgS3Prefix').value.trim() || 'references',
        s3_access_key_id: document.getElementById('cfgS3AccessKey').value.trim(),
        s3_secret_access_key: document.getElementById('cfgS3SecretKey').value.trim(),
        timeout: parseInt(document.getElementById('cfgTimeout').value) || 300,
        stream: true,
    };
    try {
        const resp = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (data.ok) {
            msg.className = 'text-xs text-center min-h-[16px] text-emerald-400';
            msg.textContent = 'Đã lưu cấu hình thành công!';
            showToast('Đã lưu cấu hình AI!');
            // Refresh provider cache
            await fetchProviderConfig();
        }
    } catch (e) {
        msg.className = 'text-xs text-center min-h-[16px] text-red-400';
        msg.textContent = 'Lỗi lưu cấu hình: ' + e.message;
    }
}
