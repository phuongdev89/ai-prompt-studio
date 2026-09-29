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
    fetch: async () => ({ ok: true, json: async () => ({}) }),
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
    console.log('Testing AI Task Queue & Button State Isolation...');

    const setCurrentPromptId = (id) => vm.runInContext(`currentPromptId = ${id ? `'${id}'` : 'null'};`, context);

    // 1. Initial State: no tasks running
    context.syncDetailPaneButtonStates('prompt_1');
    const btnSuggest = getEl('btnSuggestPrimary');
    const btnConvert = getEl('convertJsonBtn');
    assert.equal(btnSuggest.disabled, false);
    assert.match(btnSuggest.innerHTML, /AI Gợi ý thuộc tính/);
    assert.equal(btnConvert.disabled, false);
    assert.match(btnConvert.innerHTML, /Chuyển sang JSON/);

    // 2. Enqueue task for prompt_1
    let prompt1Finished = false;
    let finishPrompt1Resolve;
    const prompt1Promise = new Promise(resolve => { finishPrompt1Resolve = resolve; });

    setCurrentPromptId('prompt_1');
    context.enqueueAiTask('prompt_1', 'suggest_primary', 'Prompt 1', async () => {
        await prompt1Promise;
        prompt1Finished = true;
    });

    // Check prompt_1 button: should be disabled and spinning
    assert.equal(btnSuggest.disabled, true);
    assert.match(btnSuggest.innerHTML, /fa-spinner/);
    assert.match(btnSuggest.innerHTML, /Đang gợi ý ngầm/);

    // 3. User switches to prompt_2
    setCurrentPromptId('prompt_2');
    context.syncDetailPaneButtonStates('prompt_2');

    // On prompt_2, the button MUST NOT be spinning! It must be idle and enabled!
    assert.equal(btnSuggest.disabled, false, 'Button on prompt_2 must not be disabled');
    assert.match(btnSuggest.innerHTML, /AI Gợi ý thuộc tính/, 'Button on prompt_2 must have idle HTML');
    assert.doesNotMatch(btnSuggest.innerHTML, /fa-spinner/, 'Button on prompt_2 must not have spinner');

    // 4. User triggers a task on prompt_2 while prompt_1 is still running
    let prompt2Finished = false;
    let finishPrompt2Resolve;
    const prompt2Promise = new Promise(resolve => { finishPrompt2Resolve = resolve; });

    context.enqueueAiTask('prompt_2', 'suggest_primary', 'Prompt 2', async () => {
        await prompt2Promise;
        prompt2Finished = true;
    });

    // Since prompt_1 is running and MAX_CONCURRENT_AI_TASKS is 1, prompt_2 must be queued
    assert.equal(btnSuggest.disabled, true, 'Button on prompt_2 must be disabled while queued');
    assert.match(btnSuggest.innerHTML, /Đang trong hàng đợi/, 'Button on prompt_2 should show queued text');

    // 5. User switches back to prompt_1 while prompt_1 is still running
    setCurrentPromptId('prompt_1');
    context.syncDetailPaneButtonStates('prompt_1');
    assert.equal(btnSuggest.disabled, true);
    assert.match(btnSuggest.innerHTML, /Đang gợi ý ngầm/);

    // 6. Finish prompt_1
    finishPrompt1Resolve();
    await new Promise(r => setTimeout(r, 80)); // wait for task 1 finally & queue pick task 2

    assert.equal(prompt1Finished, true, 'Prompt 1 task should be finished');

    // Prompt 1 is now done: since user is currently on prompt_1, button should be idle
    assert.equal(btnSuggest.disabled, false, 'Button on prompt_1 should be re-enabled after completion');
    assert.match(btnSuggest.innerHTML, /AI Gợi ý thuộc tính/);

    // Now switch to prompt_2: prompt_2 should now be RUNNING (picked from queue)
    setCurrentPromptId('prompt_2');
    context.syncDetailPaneButtonStates('prompt_2');
    assert.equal(btnSuggest.disabled, true, 'Prompt 2 task should now be running');
    assert.match(btnSuggest.innerHTML, /Đang gợi ý ngầm/, 'Prompt 2 button should show running spinner');

    // 7. Finish prompt_2
    finishPrompt2Resolve();
    await new Promise(r => setTimeout(r, 80));

    assert.equal(prompt2Finished, true, 'Prompt 2 task should be finished');
    assert.equal(btnSuggest.disabled, false, 'Prompt 2 button should be re-enabled after completion');
    assert.match(btnSuggest.innerHTML, /AI Gợi ý thuộc tính/);

    console.log('ALL AI Task Queue tests PASSED!');
})().catch(err => {
    console.error('Test FAILED:', err);
    process.exit(1);
});
