const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

// Test that improvement does NOT auto-overwrite and that close discards while saveImproveOverwrite overwrites.
(async () => {
    console.log('Testing Improve Modal Flow (No Auto-Overwrite, Close Discards, Lưu đè Overwrites)...');

    const appJsCode = fs.readFileSync(path.join(__dirname, '../app/static/js/app.js'), 'utf-8');

    const elements = {};
    function getEl(id) {
        if (!elements[id]) {
            elements[id] = {
                id,
                value: '',
                innerText: '',
                innerHTML: '',
                className: '',
                classList: {
                    classes: new Set(),
                    add(c) { this.classes.add(c); },
                    remove(c) { this.classes.delete(c); },
                    contains(c) { return this.classes.has(c); }
                },
                disabled: false,
                focus() {},
                scrollIntoView() {},
                querySelector() { return null; },
                appendChild() {},
                remove() {},
                setAttribute() {},
                removeAttribute() {}
            };
        }
        return elements[id];
    }

    let fetchCalls = [];
    const context = {
        document: {
            getElementById: (id) => getEl(id),
            querySelector: () => null,
            querySelectorAll: () => [],
            createElement: (tag) => getEl(`mock_${tag}_${Math.random()}`),
            body: { appendChild() {}, removeChild() {} },
            addEventListener: () => {}
        },
        window: {
            location: { hash: '' },
            addEventListener: () => {}
        },
        fetch: async (url, options = {}) => {
            fetchCalls.push({ url, options });
            if (url.includes('/improve')) {
                return {
                    ok: true,
                    json: async () => ({
                        status: 'success',
                        title: 'Improved Title From AI',
                        prompt_code: 'Improved Prompt Code Content',
                        prompt_type: 'json',
                        parsed_json: { test: 1 },
                        fields: [],
                        explanation: 'Optimized lighting and camera',
                        changes: [{ area: 'Camera', before: 'old', after: 'new', reason: '8k' }],
                        saved_prompt: null // Backend does NOT auto-save when auto_save=false
                    })
                };
            }
            if (url.includes('/save-improved')) {
                const body = JSON.parse(options.body);
                return {
                    ok: true,
                    json: async () => ({
                        status: 'success',
                        prompt: {
                            id: 'p_test',
                            title: body.title,
                            prompt_code: body.prompt_code,
                            prompt_type: body.prompt_type,
                            parsed_json: body.parsed_json,
                            fields: body.fields,
                            original_raw_content: body.raw_content
                        }
                    })
                };
            }
            return { ok: true, json: async () => ({}) };
        },
        showToast: (msg) => { context.lastToast = msg; },
        setInterval: setInterval,
        clearInterval: clearInterval,
        setTimeout: setTimeout,
        clearTimeout: clearTimeout,
        console: console
    };

    vm.createContext(context);
    vm.runInContext(appJsCode, context);

    // Setup initial prompt using renderDetail
    context.renderDetail({
        id: 'p_test',
        title: 'Original Title',
        prompt_code: 'Original Code',
        raw_content: 'Original Raw Text',
        original_raw_content: 'Original Raw Text',
        prompt_type: 'text',
        fields: []
    });
    vm.runInContext('currentPromptsList = [currentPromptDetail]', context);

    // 1. Submit improvement
    getEl('improveInstructionInput').value = 'Add 8k camera';
    getEl('improvePromptModal').classList.remove('hidden');

    context.submitImprovePrompt();
    await new Promise(r => setTimeout(r, 150));

    // Verify improve fetch was called with auto_save: false
    const improveCall = fetchCalls.find(c => c.url.includes('/improve'));
    assert.ok(improveCall, 'Fetch to /improve must be made');
    const improveBody = JSON.parse(improveCall.options.body);
    assert.strictEqual(improveBody.auto_save, false, 'Improve request MUST send auto_save: false');

    // Verify currentPromptDetail and currentPromptsList have NOT been overwritten!
    const detailAfterImprove = vm.runInContext('currentPromptDetail', context);
    const listAfterImprove = vm.runInContext('currentPromptsList', context);
    assert.strictEqual(detailAfterImprove.title, 'Original Title', 'Prompt title must NOT be modified before user clicks Lưu đè');
    assert.strictEqual(detailAfterImprove.prompt_code, 'Original Code', 'Prompt code must NOT be modified before user clicks Lưu đè');
    assert.strictEqual(listAfterImprove[0].title, 'Original Title', 'Prompt list must NOT be modified before user clicks Lưu đè');

    // Verify modal preview was rendered
    const previewResult = vm.runInContext('currentImproveResult', context);
    assert.ok(previewResult, 'Preview result should be stored in currentImproveResult');
    assert.strictEqual(previewResult.title, 'Improved Title From AI');

    // 2. Test closing modal -> should discard preview
    context.closeImproveModal();
    assert.strictEqual(vm.runInContext('currentImproveResult', context), null, 'Closing modal must discard temporary improve result');
    assert.strictEqual(vm.runInContext('currentPromptDetail', context).title, 'Original Title', 'Prompt remains completely unmodified after close');

    // 3. Test explicit "Lưu đè" (saveImproveOverwrite)
    // Simulate user re-opening and having improve result
    vm.runInContext('currentImproveResult = { title: "Explicit Saved Title", prompt_code: "Explicit Code", prompt_type: "text", parsed_json: null, fields: [] }', context);
    await context.saveImproveOverwrite();

    const saveCall = fetchCalls.find(c => c.url.includes('/save-improved'));
    assert.ok(saveCall, 'saveImproveOverwrite must call /save-improved');
    const saveBody = JSON.parse(saveCall.options.body);
    assert.strictEqual(saveBody.mode, 'overwrite');
    assert.strictEqual(saveBody.title, 'Explicit Saved Title');
    assert.strictEqual(saveBody.raw_content, 'Original Raw Text', 'Original raw text must be preserved');

    // Verify after explicit save, local state is updated
    const finalDetail = vm.runInContext('currentPromptDetail', context);
    assert.strictEqual(finalDetail.title, 'Explicit Saved Title');
    assert.strictEqual(finalDetail.prompt_code, 'Explicit Code');

    console.log('ALL Improve Modal Flow tests PASSED!');
})().catch(err => {
    console.error('Test FAILED:', err);
    process.exit(1);
});
