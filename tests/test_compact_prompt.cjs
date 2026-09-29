const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const elements = new Map();

function getEl(id) {
    if (!elements.has(id)) {
        elements.set(id, {
            id,
            disabled: false,
            innerHTML: '',
            innerText: '',
            className: '',
            classList: {
                _classes: new Set(),
                add(c) { this._classes.add(c); },
                remove(c) { this._classes.delete(c); },
                contains(c) { return this._classes.has(c); },
                toggle(c) { if (this.contains(c)) this.remove(c); else this.add(c); }
            },
            querySelector() { return null; },
            appendChild() {},
            removeAttribute() {},
            title: ''
        });
    }
    return elements.get(id);
}

let fetchCalls = [];

const context = vm.createContext({
    console,
    document: {
        addEventListener() {},
        getElementById(id) { return getEl(id); },
        createElement(tag) { return getEl(`el_${tag}_${Date.now()}`); },
        querySelector() { return null; },
        querySelectorAll() { return []; }
    },
    setTimeout: (fn, ms) => setTimeout(fn, ms),
    clearTimeout: (id) => clearTimeout(id),
    setInterval: (fn, ms) => setInterval(fn, ms),
    clearInterval: (id) => clearInterval(id),
    fetch: async (url, options = {}) => {
        fetchCalls.push({ url, options });
        if (url.includes('/compact')) {
            return {
                ok: true,
                json: async () => ({
                    status: 'success',
                    prompt_id: 'test_p1',
                    compact_prompt: 'A concise photo prompt under 1000 characters with 8k quality and clean lighting.',
                    char_count: 81
                })
            };
        }
        return { ok: true, json: async () => ({}) };
    },
    showToast: () => {},
    localStorage: {
        getItem: () => null,
        setItem: () => {}
    },
    history: { pushState() {}, replaceState() {} },
    location: { pathname: '/', hash: '', origin: 'http://localhost:8000' }
});

vm.runInContext(fs.readFileSync(path.join(root, 'app/static/js/app.js'), 'utf8'), context);

(async () => {
    console.log('Testing Compact Prompt Tab and AI Generation Flow...');

    // Setup initial prompt with > 1000 chars without compact_prompt
    vm.runInContext(`
        currentPromptId = 'test_p1';
        currentPromptDetail = {
            id: 'test_p1',
            title: 'Test Prompt Title',
            prompt_code: 'A very detailed cinematic storyboard prompt with intricate composition and rules. '.repeat(20),
            raw_content: 'A very detailed cinematic storyboard prompt with intricate composition and rules. '.repeat(20),
            compact_prompt: ''
        };
        currentPromptsList = [currentPromptDetail];
    `, context);

    // 1. Initial mode is 'live'
    assert.equal(vm.runInContext('codeViewMode', context), 'live');

    // 2. User clicks "Prompt tối giản 1000 ký tự" tab
    context.setCodeViewMode('compact');
    assert.equal(vm.runInContext('codeViewMode', context), 'compact');

    // Tab buttons styling check
    const btnCompact = getEl('btnViewCompact');
    assert.match(btnCompact.className, /bg-dark-700/);

    // Wait for the async task queue to process
    await new Promise(r => setTimeout(r, 120));

    // Verify AI endpoint was called
    const compactCall = fetchCalls.find(c => c.url === '/api/prompts/test_p1/compact');
    assert.ok(compactCall, 'Should have called /api/prompts/test_p1/compact');
    const body = JSON.parse(compactCall.options.body);
    assert.equal(body.force_refresh, false);

    // Verify compact_prompt was updated on the model and displayed in the UI
    const promptDetail = vm.runInContext('currentPromptDetail', context);
    assert.equal(promptDetail.compact_prompt, 'A concise photo prompt under 1000 characters with 8k quality and clean lighting.');

    const codeDisplay = getEl('promptCodeDisplay');
    assert.equal(codeDisplay.innerText, 'A concise photo prompt under 1000 characters with 8k quality and clean lighting.');

    const charBadge = getEl('charCountBadge');
    assert.match(charBadge.innerText, /80 \/ 1000 chars/);

    // 3. User switches to 'raw' mode and then back to 'compact'
    fetchCalls = [];
    context.setCodeViewMode('raw');
    assert.equal(vm.runInContext('codeViewMode', context), 'raw');
    assert.equal(codeDisplay.innerText, 'A very detailed cinematic storyboard prompt with intricate composition and rules. '.repeat(20));

    context.setCodeViewMode('compact');
    assert.equal(vm.runInContext('codeViewMode', context), 'compact');
    assert.equal(codeDisplay.innerText, 'A concise photo prompt under 1000 characters with 8k quality and clean lighting.');
    // Should NOT have made another fetch call since compact_prompt already exists!
    assert.equal(fetchCalls.length, 0, 'Should not re-fetch when compact_prompt is already cached');

    // 4. User clicks "Tạo lại" (regenerateCompactPrompt)
    context.regenerateCompactPrompt();
    await new Promise(r => setTimeout(r, 120));

    const regenCall = fetchCalls.find(c => c.url === '/api/prompts/test_p1/compact');
    assert.ok(regenCall, 'Should have called /api/prompts/test_p1/compact for regenerate');
    const regenBody = JSON.parse(regenCall.options.body);
    // 5. User enters a new prompt (renderDetail called): mode must reset to 'live'
    context.renderDetail({
        id: 'test_p2',
        title: 'New Prompt Item',
        prompt_code: 'A new short prompt code under 1000 chars.',
        raw_content: 'A new short prompt code under 1000 chars.',
        fields: []
    });
    assert.equal(vm.runInContext('codeViewMode', context), 'live', 'Entering a new item must reset code tab to live (Prompt tùy biến)');
    const btnLive = getEl('btnViewLive');
    assert.match(btnLive.className, /bg-dark-700/, 'Live button must be active');

    // 6. Test prompt < 1000 chars bypass: clicking compact on test_p2 uses raw text directly without calling AI
    fetchCalls = [];
    context.setCodeViewMode('compact');
    assert.equal(codeDisplay.innerText, 'A new short prompt code under 1000 chars.');
    assert.equal(fetchCalls.length, 1, 'Calls backend to persist, but no AI task was queued');

    console.log('ALL Compact Prompt tests PASSED!');
})().catch(err => {
    console.error('Test FAILED:', err);
    process.exit(1);
});
