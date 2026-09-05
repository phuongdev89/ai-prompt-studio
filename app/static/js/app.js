let currentPromptsList = [];
let currentPromptId = null;
let currentPromptDetail = null;
let formState = {};
let currentSlideIndex = 0;
let currentTag = 'all';
let currentTab = 'featured';
let searchDebounceTimer = null;

// Initialize app on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    fetchStats();
    loadPrompts();
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
            closeImproveModal();
            closeAddMediaModal();
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

    // URL Hash deep linking support
    window.addEventListener('hashchange', () => {
        const hashId = window.location.hash.replace(/^#/, '').trim();
        if (hashId && hashId !== currentPromptId) {
            selectPrompt(hashId, false);
        }
    });
}

// Fetch stats from backend
async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        if (res.ok) {
            const stats = await res.json();
            const badge = document.getElementById('promptCountBadge');
            if (badge) {
                badge.innerText = `${stats.total_prompts} Câu lệnh`;
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

        const hashId = window.location.hash.replace(/^#/, '').trim();
        let targetId = null;

        if (selectedIdToKeep) {
            targetId = selectedIdToKeep;
        } else if (hashId) {
            targetId = hashId;
        } else if (currentPromptsList.length > 0) {
            targetId = currentPromptsList[0].id;
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
        return `
            <div onclick="selectPrompt('${item.id}')" id="prompt-card-${item.id}"
                 class="prompt-card group p-3 rounded-xl cursor-pointer transition-all duration-200 hover:bg-dark-700/70 border border-transparent hover:border-dark-600">
                <div class="flex items-start justify-between gap-2 mb-1.5">
                    <span class="text-[11px] font-mono font-semibold px-2 py-0.5 rounded bg-dark-900 text-slate-400 border border-dark-700 group-hover:border-slate-600">
                        #${idx + 1}
                    </span>
                    <div class="flex items-center gap-1.5">
                        ${imgCount > 0 ? `
                            <span class="text-[10px] px-1.5 py-0.5 rounded bg-dark-900/90 text-amber-400/90 border border-amber-500/20 flex items-center gap-1">
                                <i class="fa-solid fa-image text-[9px]"></i> ${imgCount}
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

async function selectPrompt(promptId, updateHash = true) {
    if (!promptId) return;
    currentPromptId = promptId;

    // Update browser URL Hash for direct linking
    if (updateHash && window.location.hash !== '#' + promptId) {
        history.replaceState(null, '', '#' + promptId);
    }

    // Highlight active in sidebar and scroll card into view
    document.querySelectorAll('.prompt-card').forEach(el => {
        el.classList.remove('bg-dark-700', 'border-brand-500/50', 'ring-1', 'ring-brand-500/30', 'bg-gradient-to-r', 'from-brand-950/40', 'to-dark-700');
    });
    const activeEl = document.getElementById(`prompt-card-${promptId}`);
    if (activeEl) {
        activeEl.classList.add('bg-dark-700', 'border-brand-500/50', 'ring-1', 'ring-brand-500/30');
        activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

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

    // Header info
    document.getElementById('currentPromptIdBadge').innerText = (prompt.id || 'PROMPT').toUpperCase();
    const isJson = prompt.prompt_type === 'json' || prompt.parsed_json;
    const typeBadge = document.getElementById('currentPromptTypeBadge');
    typeBadge.innerText = isJson ? 'JSON Structured' : 'Text Structured';
    typeBadge.className = `px-2 py-0.5 rounded text-xs font-semibold border ${isJson ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' : 'bg-slate-700/50 text-slate-300 border-slate-600'}`;

    // Show AI convert button if prompt is raw text
    const convertBtn = document.getElementById('convertJsonBtn');
    if (convertBtn) {
        if (!isJson) {
            convertBtn.classList.remove('hidden');
        } else {
            convertBtn.classList.add('hidden');
        }
    }

    const images = prompt.images || [];
    document.getElementById('imgCountText').innerText = `${images.length} Ảnh`;
    document.getElementById('currentPromptTitle').innerText = prompt.title || 'Không có tiêu đề';

    // Initialize Form State
    formState = {};
    if (prompt.fields && prompt.fields.length > 0) {
        prompt.fields.forEach(f => {
            formState[f.path] = f.value || '';
        });
    }

    // Render Image Slider
    currentSlideIndex = 0;
    renderSlider(images);

    // Render Dynamic Form
    renderDynamicForm(prompt.fields || []);

    // Render Code Display
    updatePromptCodeDisplay();
}

function renderSlider(images) {
    const sliderImg = document.getElementById('currentSliderImg');
    const noImgPlaceholder = document.getElementById('noImgPlaceholder');
    const sliderCounter = document.getElementById('sliderCounter');
    const thumbnailsContainer = document.getElementById('sliderThumbnails');
    const prevBtn = document.getElementById('sliderPrevBtn');
    const nextBtn = document.getElementById('sliderNextBtn');
    const expandBtn = document.getElementById('sliderExpandBtn');

    if (!images || images.length === 0) {
        sliderImg.classList.add('hidden');
        noImgPlaceholder.classList.remove('hidden');
        noImgPlaceholder.classList.add('flex');
        sliderCounter.innerText = '0 / 0';
        thumbnailsContainer.innerHTML = '';
        prevBtn.classList.add('hidden');
        nextBtn.classList.add('hidden');
        expandBtn.classList.add('hidden');
        return;
    }

    sliderImg.classList.remove('hidden');
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
    sliderImg.src = src;
    sliderImg.dataset.remoteUrl = typeof imgObj === 'object' ? imgObj.url : imgObj;

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
    document.getElementById('allFieldsCount').innerText = fields.length;

    if (!fields || fields.length === 0) {
        formEl.innerHTML = `
            <div class="p-6 text-center text-slate-500 text-xs">
                <i class="fa-solid fa-list-check text-xl mb-1 text-slate-600"></i>
                <p>Không có trường tham số động cho câu lệnh này.</p>
            </div>
        `;
        return;
    }

    let displayedFields = fields;
    if (currentTab === 'featured' && fields.length > 6) {
        const featuredKeywords = ['prompt', 'subject', 'style', 'camera', 'background', 'lighting', 'clothing', 'pose', 'character', 'setting', 'positive_prompt'];
        const matched = fields.filter(f => featuredKeywords.some(k => f.path.toLowerCase().includes(k) || f.key.toLowerCase().includes(k)));
        displayedFields = matched.length >= 3 ? matched : fields.slice(0, 8);
    }

    formEl.innerHTML = displayedFields.map((field) => {
        const val = formState[field.path] !== undefined ? formState[field.path] : field.value;
        const isTextarea = field.type === 'textarea' || (val && val.length > 50);

        return `
            <div class="space-y-1.5 p-3 rounded-xl bg-dark-900/60 border border-dark-700/70 hover:border-dark-600 transition">
                <div class="flex items-center justify-between">
                    <label class="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                        <i class="fa-solid fa-pen-to-square text-brand-500 text-[10px]"></i>
                        ${escapeHtml(field.label || field.key)}
                    </label>
                    <span class="text-[10px] font-mono text-slate-500">${escapeHtml(field.path)}</span>
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
    }).join('');
}

function setFormTab(tab) {
    currentTab = tab;
    const btnFeatured = document.getElementById('tabBtnFeatured');
    const btnAll = document.getElementById('tabBtnAll');

    if (tab === 'featured') {
        btnFeatured.className = 'px-3 py-1 rounded-md bg-dark-700 text-white font-medium transition';
        btnAll.className = 'px-3 py-1 rounded-md text-slate-400 hover:text-white transition';
    } else {
        btnAll.className = 'px-3 py-1 rounded-md bg-dark-700 text-white font-medium transition';
        btnFeatured.className = 'px-3 py-1 rounded-md text-slate-400 hover:text-white transition';
    }

    if (currentPromptDetail) {
        renderDynamicForm(currentPromptDetail.fields || []);
    }
}

let codeViewMode = 'live';

function setCodeViewMode(mode) {
    codeViewMode = mode;
    const btnLive = document.getElementById('btnViewLive');
    const btnRaw = document.getElementById('btnViewRaw');
    const title = document.getElementById('codeBoxTitle');

    if (mode === 'live') {
        if (btnLive) btnLive.className = 'px-2.5 py-1 rounded-md bg-dark-700 text-white font-medium transition';
        if (btnRaw) btnRaw.className = 'px-2.5 py-1 rounded-md text-slate-400 hover:text-white transition';
        if (title) title.innerText = 'CÂU LỆNH PROMPT TÙY BIẾN';
    } else {
        if (btnRaw) btnRaw.className = 'px-2.5 py-1 rounded-md bg-dark-700 text-white font-medium transition';
        if (btnLive) btnLive.className = 'px-2.5 py-1 rounded-md text-slate-400 hover:text-white transition';
        if (title) title.innerText = 'VĂN BẢN GỐC (RAW PROMPT)';
    }
    updatePromptCodeDisplay();
}

function onFieldChange(path, newValue) {
    formState[path] = newValue;
    updatePromptCodeDisplay();
}

function updatePromptCodeDisplay() {
    if (!currentPromptDetail) return;

    let generatedCode = "";

    if (codeViewMode === 'raw') {
        generatedCode = currentPromptDetail.raw_content || currentPromptDetail.prompt_code || "";
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
                generatedCode = currentPromptDetail.prompt_code || currentPromptDetail.raw_content || "";
            }
        }
    }

    const codeEl = document.getElementById('promptCodeDisplay');
    codeEl.innerText = generatedCode;
    document.getElementById('charCountBadge').innerText = `${generatedCode.length} chars`;
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
    const btn = document.getElementById('convertJsonBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Đang phân tích AI...</span>';
    showToast('Đang gọi AI phân tích & chuyển đổi prompt sang JSON...');

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/convert-json`, {
            method: 'POST'
        });

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || 'Lỗi khi gọi AI');
        }

        const updatedPrompt = await res.json();
        currentPromptDetail = updatedPrompt;

        // Update in local prompts list
        const found = currentPromptsList.find(p => p.id === currentPromptId);
        if (found) {
            found.prompt_type = 'json';
            found.parsed_json = updatedPrompt.parsed_json;
        }

        // Re-render sidebar card type badge
        const card = document.getElementById(`prompt-card-${currentPromptId}`);
        if (card) {
            const typeBadge = card.querySelector('span:last-child');
            if (typeBadge) {
                typeBadge.innerText = 'JSON';
                typeBadge.className = 'text-[10px] px-1.5 py-0.5 rounded font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20';
            }
        }

        // Re-render detail view with newly generated dynamic form
        renderDetail(currentPromptDetail);
        showToast('Đã chuyển đổi sang cấu trúc JSON thành công!');
    } catch (err) {
        console.error('AI Convert error:', err);
        showToast(`Lỗi: ${err.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles text-amber-300"></i> <span>Chuyển sang JSON</span>';
    }
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

    const btn = document.getElementById('btnGenerateTitleAI');
    if (!btn) return;

    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin text-[11px] text-amber-300"></i><span>Đang đặt tên...</span>';

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/suggest-title`, {
            method: 'POST'
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Lỗi khi gọi AI gợi ý tiêu đề');
        }

        const data = await res.json();
        const newTitle = data.title;

        if (newTitle) {
            // Update title in detail view
            const titleEl = document.getElementById('currentPromptTitle');
            if (titleEl) {
                titleEl.innerText = newTitle;
            }

            // Update in memory states
            if (currentPromptDetail) {
                currentPromptDetail.title = newTitle;
            }
            const found = currentPromptsList.find(p => p.id === currentPromptId);
            if (found) {
                found.title = newTitle;
            }

            // Update sidebar card text
            const cardTitle = document.querySelector(`#prompt-card-${currentPromptId} h4`);
            if (cardTitle) {
                cardTitle.innerText = newTitle;
            }

            showToast(`AI đã áp dụng tiêu đề mới: "${newTitle}"`);
        }
    } catch (err) {
        console.error('generateTitleAI error:', err);
        showToast(`Lỗi: ${err.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
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

function renderNewPromptFilesPreview() {
    const previewBox = document.getElementById('createUploadedPreviewContainer');
    const thumbnails = document.getElementById('createUploadedThumbnails');
    const countEl = document.getElementById('createUploadedCount');
    const tabLabel = document.getElementById('labelTabUpload');

    if (!previewBox || !thumbnails) return;

    if (tabLabel) {
        tabLabel.innerText = newPromptUploadedFiles.length > 0 ? `Tải ảnh lên (${newPromptUploadedFiles.length})` : 'Tải ảnh lên';
    }

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
    }
}

function clearAllNewPromptFiles() {
    newPromptUploadedFiles = [];
    const fileInput = document.getElementById('newImageFileInput');
    if (fileInput) fileInput.value = '';
    renderNewPromptFilesPreview();
}

function openCreateModal() {
    const modal = document.getElementById('createModal');
    if (modal) {
        modal.classList.remove('hidden');
        clearAllNewPromptFiles();
        setCreateMediaTab('upload');
        const mediaInput = document.getElementById('newMediaInput');
        if (mediaInput) mediaInput.value = '';
        const promptInput = document.getElementById('newPromptInput');
        if (promptInput) {
            promptInput.value = '';
            promptInput.focus();
        }
    }
}

function closeCreateModal() {
    const modal = document.getElementById('createModal');
    if (modal) {
        modal.classList.add('hidden');
    }
    clearAllNewPromptFiles();
}

async function submitCreatePrompt(event) {
    if (event && typeof event.preventDefault === 'function') {
        event.preventDefault();
    }
    const mediaInput = document.getElementById('newMediaInput');
    const promptInput = document.getElementById('newPromptInput');
    const submitBtn = document.getElementById('submitCreateBtn');

    const promptVal = promptInput.value.trim();
    const mediaVal = mediaInput ? mediaInput.value.trim() : '';

    if (!promptVal) {
        showToast('Vui lòng nhập nội dung câu lệnh');
        return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Đang lưu...</span>';

    try {
        const uploadedBase64List = newPromptUploadedFiles.map(f => f.dataUrl);

        const res = await fetch('/api/prompts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: promptVal,
                media: mediaVal,
                images: uploadedBase64List
            })
        });

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || 'Lỗi khi tạo câu lệnh');
        }

        const newPrompt = await res.json();
        
        // Reset form & close modal
        if (mediaInput) mediaInput.value = '';
        promptInput.value = '';
        clearAllNewPromptFiles();
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


function filterByTag(tag) {
    currentTag = tag;
    document.querySelectorAll('.tag-btn').forEach(btn => {
        btn.className = 'tag-btn px-2.5 py-1 rounded-md bg-dark-700 hover:bg-dark-600 text-slate-300 whitespace-nowrap transition';
    });
    if (event && event.currentTarget) {
        event.currentTarget.className = 'tag-btn active px-2.5 py-1 rounded-md bg-brand-600 text-white font-medium whitespace-nowrap transition';
    }
    loadPrompts();
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

    const a = document.createElement('a');
    a.href = img.src;
    const filename = img.src.split('/').pop().split('?')[0] || 'prompt-image.jpg';
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast(`Đang tải ảnh: ${filename}`);
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
}

// ==========================================
// AI Image Generation Logic
// ==========================================
let currentRefImageData = null;
let currentGeneratedImageData = null;
let genTimerInterval = null;
let genTimerSeconds = 0;
let currentGenProvider = 'openai';
let providerConfigCache = null;

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

function setGenProvider(provider, notify = true) {
    currentGenProvider = provider;
    const btnOpenAI = document.getElementById('btnProviderOpenAI');
    const btnGemini = document.getElementById('btnProviderGemini');
    const badge = document.getElementById('genProviderInfoBadge');

    if (provider === 'gemini') {
        if (btnOpenAI) {
            btnOpenAI.className = 'px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 text-slate-400 hover:text-white';
        }
        if (btnGemini) {
            btnGemini.className = 'px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 bg-gradient-to-r from-amber-600 to-orange-600 text-white shadow';
        }
        if (badge) {
            const imgModel = providerConfigCache?.gemini?.image_model || 'imagen-3.0-generate-002';
            badge.innerText = `Google Gemini (${imgModel})`;
            badge.className = 'text-[11px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30';
        }
        if (notify && providerConfigCache && !providerConfigCache.gemini.has_key) {
            showGenError('Lưu ý: GEMINI_API_KEY chưa có giá trị trong .env. Vui lòng nhập API Key của Gemini vào .env trước khi tạo ảnh.');
        }
    } else {
        if (btnOpenAI) {
            btnOpenAI.className = 'px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 bg-indigo-600 text-white shadow';
        }
        if (btnGemini) {
            btnGemini.className = 'px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 text-slate-400 hover:text-white';
        }
        if (badge) {
            const imgModel = providerConfigCache?.openai?.image_model || 'Custom Router';
            badge.innerText = `Custom OpenAI (${imgModel})`;
            badge.className = 'text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/30';
        }
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
    return currentPromptDetail.prompt_code || currentPromptDetail.raw_content || "";
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
    removeRefImage();

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

function handleRefFileSelect(event) {
    const file = event.target.files && event.target.files[0];
    if (file) {
        processRefImageFile(file);
    }
}

function processRefImageFile(file) {
    if (!file || !file.type.startsWith('image/')) {
        showGenError('Vui lòng chọn tệp hình ảnh hợp lệ (PNG, JPG, WEBP).');
        return;
    }
    if (file.size > 15 * 1024 * 1024) {
        showGenError('Kích thước ảnh quá lớn (tối đa 15MB).');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        currentRefImageData = e.target.result;
        document.getElementById('genRefPreviewImg').src = currentRefImageData;
        document.getElementById('genRefFileName').innerText = file.name;
        document.getElementById('genRefFileSize').innerText = formatFileSize(file.size);
        document.getElementById('genRefPreviewBox').classList.remove('hidden');
        document.getElementById('genRefDropzone').classList.add('hidden');
        document.getElementById('genErrorBanner').classList.add('hidden');
    };
    reader.onerror = () => {
        showGenError('Không thể đọc file ảnh.');
    };
    reader.readAsDataURL(file);
}

function removeRefImage() {
    currentRefImageData = null;
    const fileInput = document.getElementById('genRefFileInput');
    if (fileInput) fileInput.value = '';
    const previewBox = document.getElementById('genRefPreviewBox');
    if (previewBox) previewBox.classList.add('hidden');
    const dropzone = document.getElementById('genRefDropzone');
    if (dropzone) dropzone.classList.remove('hidden');
}

function selectExistingImageAsRef(src) {
    if (!src) return;
    currentRefImageData = src;
    document.getElementById('genRefPreviewImg').src = src;
    document.getElementById('genRefFileName').innerText = 'Ảnh mẫu từ bản ghi';
    document.getElementById('genRefFileSize').innerText = 'Đã chọn';
    document.getElementById('genRefPreviewBox').classList.remove('hidden');
    document.getElementById('genRefDropzone').classList.add('hidden');
    document.getElementById('genErrorBanner').classList.add('hidden');
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

    // UI state: loading
    document.getElementById('genErrorBanner').classList.add('hidden');
    document.getElementById('genResultSection').classList.add('hidden');
    document.getElementById('genLoadingState').classList.remove('hidden');

    const btnSubmit = document.getElementById('btnSubmitGenerate');
    const btnText = document.getElementById('btnSubmitGenerateText');
    btnSubmit.disabled = true;
    btnText.innerText = 'Đang xử lý...';

    // Timer counter
    genTimerSeconds = 0;
    const timerEl = document.getElementById('genLoadingTimer');
    const providerName = currentGenProvider === 'gemini' ? 'Google Gemini Official API' : 'Custom OpenAI Router';
    if (timerEl) timerEl.innerText = `Đang kết nối tới ${providerName} (0s)...`;
    if (genTimerInterval) clearInterval(genTimerInterval);
    genTimerInterval = setInterval(() => {
        genTimerSeconds++;
        if (timerEl) {
            timerEl.innerText = `Đang kết nối tới ${providerName} (${genTimerSeconds}s)...`;
        }
    }, 1000);

    try {
        const response = await fetch(`/api/prompts/${currentPromptId}/generate-image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: promptText,
                reference_image: currentRefImageData,
                extra_description: extraDesc,
                size: genSize,
                quality: genQuality,
                image_detail: genDetail,
                provider: currentGenProvider
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Không thể tạo ảnh từ mô hình AI');
        }

        currentGeneratedImageData = data.image_url;

        // Display result
        const resultImg = document.getElementById('genResultImg');
        resultImg.src = data.image_url;

        const formatBadge = document.getElementById('genResultFormatBadge');
        if (formatBadge) {
            formatBadge.innerText = (data.format || 'IMAGE').toUpperCase();
        }

        const noteEl = document.getElementById('genResultNote');
        if (noteEl) {
            noteEl.innerText = data.message || 'Tạo ảnh thành công từ AI';
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

async function downloadCurrentGeneratedImage() {
    if (!currentGeneratedImageData) {
        showToast('Chưa có dữ liệu ảnh để tải về.');
        return;
    }

    const filename = `${currentPromptId || 'prompt'}_ai_${Date.now()}.png`;

    if (currentGeneratedImageData.startsWith('data:')) {
        const a = document.createElement('a');
        a.href = currentGeneratedImageData;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast(`Đã tải ảnh về: ${filename}`);
        return;
    }

    try {
        showToast('Đang tải ảnh về máy...');
        const res = await fetch(currentGeneratedImageData);
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(blobUrl);
        showToast(`Đã lưu ảnh về máy: ${filename}`);
    } catch (err) {
        const a = document.createElement('a');
        a.href = currentGeneratedImageData;
        a.target = '_blank';
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast('Đang mở ảnh để tải về...');
    }
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
            // Update in local prompts list
            const found = currentPromptsList.find(p => p.id === currentPromptId);
            if (found) {
                found.images = data.prompt.images;
                found.image_count = data.prompt.images ? data.prompt.images.length : 0;
            }
            // Update header badge
            const images = data.prompt.images || [];
            document.getElementById('imgCountText').innerText = `${images.length} Ảnh`;
            // Re-render slider
            renderSlider(images);
            // Go to newest slide
            goToSlide(images.length - 1);
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
    currentImproveProvider = provider;
    const btnOpenAI = document.getElementById('btnImproveProviderOpenAI');
    const btnGemini = document.getElementById('btnImproveProviderGemini');
    const badge = document.getElementById('improveProviderInfoBadge');

    if (provider === 'gemini') {
        if (btnOpenAI) {
            btnOpenAI.className = 'px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 text-slate-400 hover:text-white';
        }
        if (btnGemini) {
            btnGemini.className = 'px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 bg-gradient-to-r from-amber-600 to-orange-600 text-white shadow';
        }
        if (badge) {
            const chatModel = providerConfigCache?.gemini?.chat_model || 'gemini-2.0-flash';
            badge.innerText = `Google Gemini (${chatModel})`;
            badge.className = 'text-[11px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30';
        }
    } else {
        if (btnOpenAI) {
            btnOpenAI.className = 'px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 bg-emerald-600 text-white shadow';
        }
        if (btnGemini) {
            btnGemini.className = 'px-3 py-1.5 rounded-lg font-medium transition flex items-center gap-1.5 text-slate-400 hover:text-white';
        }
        if (badge) {
            const chatModel = providerConfigCache?.openai?.chat_model || 'Custom Router';
            badge.innerText = `Custom OpenAI (${chatModel})`;
            badge.className = 'text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30';
        }
    }
}

async function openImproveModal(promptId = null) {
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

    const instructionInput = document.getElementById('improveInstructionInput');
    const instruction = instructionInput ? instructionInput.value.trim() : '';
    if (!instruction) {
        showImproveError('Vui lòng nhập nội dung yêu cầu cải tiến vào ô bên dưới.');
        if (instructionInput) instructionInput.focus();
        return;
    }

    document.getElementById('improveErrorBanner').classList.add('hidden');
    document.getElementById('improveResultSection').classList.add('hidden');
    const loadingEl = document.getElementById('improveLoadingState');
    loadingEl.classList.remove('hidden');

    const btnSubmit = document.getElementById('btnSubmitImprove');
    btnSubmit.disabled = true;
    document.getElementById('btnSubmitImproveText').innerText = 'Đang xử lý...';

    // Start timer
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

    try {
        const res = await fetch(`/api/prompts/${currentPromptId}/improve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                instruction: instruction,
                provider: currentImproveProvider
            })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Lỗi máy chủ (${res.status})`);
        }

        const data = await res.json();
        currentImproveResult = data;

        // Render Explanation (Giải thích những chỗ sửa)
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
        document.getElementById('improveResultSection').classList.remove('hidden');
        document.getElementById('improveResultSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        showToast('AI đã hoàn tất việc cải tiến câu lệnh!');

    } catch (err) {
        console.error('Improve error:', err);
        showImproveError(`Lỗi: ${err.message}`);
    } finally {
        if (improveTimerInterval) {
            clearInterval(improveTimerInterval);
            improveTimerInterval = null;
        }
        loadingEl.classList.add('hidden');
        btnSubmit.disabled = false;
        document.getElementById('btnSubmitImproveText').innerText = 'Gửi AI cải tiến lại';
    }
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
        const res = await fetch(`/api/prompts/${currentPromptId}/save-improved`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: 'overwrite',
                title: currentImproveResult.title,
                prompt_code: currentImproveResult.prompt_code,
                raw_content: currentImproveResult.prompt_code,
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
        showToast('Đã lưu đè thành công câu lệnh với nội dung cải tiến!');

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
        const res = await fetch(`/api/prompts/${currentPromptId}/save-improved`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: 'new_version',
                title: currentImproveResult.title,
                prompt_code: currentImproveResult.prompt_code,
                raw_content: currentImproveResult.prompt_code,
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

            // Update sidebar card count badge
            updateSidebarImageCount(currentPromptId, (currentPromptDetail.images || []).length);

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

            // Update sidebar card badge
            updateSidebarImageCount(currentPromptId, (refreshed.images || []).length);
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


