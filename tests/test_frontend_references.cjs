const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const elements = new Map();
const requests = [];
const context = vm.createContext({
    console,
    document: {
        addEventListener() {},
        getElementById(id) {
            if (!elements.has(id)) elements.set(id, { value: '', checked: false });
            return elements.get(id);
        },
    },
    fetch: async (url) => {
        requests.push(url);
        return { ok: true, json: async () => url === '/api/config/providers'
            ? { active_provider: 'openai', openai: { image_model: 'updated-image-model' } }
            : { ok: true } };
    },
});
vm.runInContext(fs.readFileSync(path.join(root, 'app/static/js/app.js'), 'utf8'), context);
// Check named function calls in static HTML handlers without executing clicks.
const html = fs.readFileSync(path.join(root, 'app/templates/index.html'), 'utf8');
let checked = 0;
for (const [, handler] of html.matchAll(/\bon\w+="([^"]*)"/g)) {
    const code = handler.replace(/'(?:\\.|[^'\\])*'/g, "''");
    for (const [, name] of code.matchAll(/(?<![\w.])([A-Za-z_$][\w$]*)\s*\(/g)) {
        if (['if', 'switch'].includes(name)) continue;
        assert.equal(typeof context[name], 'function', `Missing HTML handler: ${name}`);
        checked++;
    }
}
context.showToast = () => {};
(async () => {
    // Web no longer saves config; provider refresh still runs on modal open.
    await context.fetchProviderConfig();
    assert.deepEqual(requests, ['/api/config/providers']);
    assert.match(elements.get('genProviderInfoBadge').innerText, /updated-image-model/);
    console.log(`PASS: ${checked} HTML handler calls and settings provider refresh`);
})().catch(error => { console.error(error); process.exitCode = 1; });
