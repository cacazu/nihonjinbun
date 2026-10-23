// Run with: node tests/test_reading_preferences.cjs (no dependencies).
// Behavior tests use a small DOM/storage double, not a real browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const code = fs.readFileSync(path.join(__dirname, '../scripts/reading_site.js'), 'utf8');
const key = 'nihonjinbun-reader-settings-v1';
function setup(saved, denied = false, hash = '') {
  const buttons = ['ja', 'parallel'].map(mode => ({ dataset: { mode }, attributes: {} }))
    .concat(['small', 'medium', 'large'].map(size => ({ dataset: { size }, attributes: {} })));
  buttons.forEach(button => { button.setAttribute = (name, value) => { button.attributes[name] = value; }; });
  const callbacks = {}, events = {}, root = { dataset: {} }, storage = {}, writes = [];
  if (saved !== undefined) storage[key] = saved;
  const source = { closest: selector => selector === '.source-column', scrollIntoView: () => { source.scrolled = true; } };
  const controls = {
    hidden: true,
    querySelectorAll: selector => buttons.filter(button => selector === '[data-mode]' ? button.dataset.mode : button.dataset.size),
    addEventListener: (name, callback) => { callbacks[name] = callback; },
  };
  const document = {
    documentElement: root, querySelector: () => controls,
    getElementById: id => id === 'source-anchor' ? source : null,
    addEventListener: (name, callback) => { events[name] = callback; },
  };
  const window = { addEventListener: (name, callback) => { events[name] = callback; } };
  const location = { hash };
  const localStorage = {
    getItem: name => { if (denied) throw new Error('denied'); return storage[name] || null; },
    setItem: (name, value) => { if (denied) throw new Error('denied'); storage[name] = value; writes.push(name); },
  };
  vm.runInNewContext(code, { document, window, location, localStorage, requestAnimationFrame: fn => fn() });
  return { root, controls, buttons, storage, writes, source, events, location,
    setStorageDenied(value) { denied = value; },
    click(name, value) { callbacks.click({ target: { closest: () => buttons.find(button => button.dataset[name] === value) } }); },
    sourceBacklink() { events.click({ target: { closest: () => ({ hash: '#source-anchor' }) } }); },
  };
}
let app = setup();
assert.deepEqual(app.root.dataset, { mode: 'ja', size: 'medium' });
assert.equal(app.controls.hidden, false);
app.click('mode', 'parallel'); app.click('size', 'large');
assert.deepEqual(app.root.dataset, { mode: 'parallel', size: 'large' });
assert.equal(app.buttons.find(b => b.dataset.mode === 'parallel').attributes['aria-pressed'], 'true');
assert.equal(app.buttons.find(b => b.dataset.mode === 'ja').attributes['aria-pressed'], 'false');
assert.deepEqual(JSON.parse(app.storage[key]), { mode: 'parallel', size: 'large' });
assert(app.writes.every(name => name === key));
app = setup(app.storage[key]);
assert.deepEqual(app.root.dataset, { mode: 'parallel', size: 'large' });
for (const malformed of ['{bad', 'null', '[]', '"str"', '{"mode":"evil","size":42}', '{"mode":"ja","other":"untrusted"}']) {
  const state = setup(malformed);
  assert.deepEqual(state.root.dataset, { mode: 'ja', size: 'medium' });
}
app = setup(undefined, true);
app.click('mode', 'parallel'); app.click('size', 'small');
assert.deepEqual(app.root.dataset, { mode: 'parallel', size: 'small' });
app = setup(); app.sourceBacklink();
assert.equal(app.root.dataset.mode, 'parallel'); assert(app.source.scrolled);
app.click('mode', 'ja'); app.sourceBacklink();
assert.equal(app.root.dataset.mode, 'parallel');
app = setup(undefined, false, '#source-anchor');
assert.equal(app.root.dataset.mode, 'parallel');
app.click('mode', 'ja'); app.events.hashchange();
assert.equal(app.root.dataset.mode, 'parallel');
app.click('mode', 'ja'); app.events.pageshow();
assert.equal(app.root.dataset.mode, 'parallel');
app.location.hash = '#%bad'; assert.doesNotThrow(() => app.events.hashchange());
// A BFCache-restored document must reflect preferences changed on another page.
app = setup(JSON.stringify({ mode: 'ja', size: 'small' }));
app.storage[key] = JSON.stringify({ mode: 'parallel', size: 'large' });
app.events.pageshow({ persisted: true });
assert.deepEqual(app.root.dataset, { mode: 'parallel', size: 'large' });
assert.equal(app.buttons.find(b => b.dataset.mode === 'parallel').attributes['aria-pressed'], 'true');
assert.equal(app.buttons.find(b => b.dataset.size === 'large').attributes['aria-pressed'], 'true');
assert.equal(app.buttons.find(b => b.dataset.size === 'small').attributes['aria-pressed'], 'false');
assert.deepEqual(app.writes, [], 'Restoration must not overwrite the saved preferences');
app.click('size', 'small');
assert.deepEqual(app.root.dataset, { mode: 'parallel', size: 'small' });
assert.deepEqual(JSON.parse(app.storage[key]), { mode: 'parallel', size: 'small' });
const writesBeforeRestore = app.writes.length;
// Repeated restoration reads the latest values, not the first page's cached copy.
app.storage[key] = JSON.stringify({ mode: 'ja', size: 'medium' });
app.events.pageshow({ persisted: true });
assert.deepEqual(app.root.dataset, { mode: 'ja', size: 'medium' });
assert.equal(app.writes.length, writesBeforeRestore);
// Corrupt, missing, incomplete, or inaccessible storage must preserve local choices.
for (const malformed of ['{bad', 'null', '[]', '"str"', '{"mode":"evil","size":42}', '{"mode":"ja","size":"evil"}', '{"mode":"ja"}', undefined]) {
  app = setup(JSON.stringify({ mode: 'parallel', size: 'large' }));
  app.storage[key] = malformed;
  app.events.pageshow({ persisted: true });
  assert.deepEqual(app.root.dataset, { mode: 'parallel', size: 'large' });
  assert.deepEqual(app.writes, []);
}
app = setup(JSON.stringify({ mode: 'parallel', size: 'large' }));
app.storage[key] = JSON.stringify({ mode: 'ja', size: 'small' });
app.setStorageDenied(true);
app.events.pageshow({ persisted: true });
assert.deepEqual(app.root.dataset, { mode: 'parallel', size: 'large' });
app.setStorageDenied(false);
app.events.pageshow({ persisted: true });
assert.deepEqual(app.root.dataset, { mode: 'ja', size: 'small' });
// An original-text deep link still becomes visible after storage is refreshed.
app = setup();
app.storage[key] = JSON.stringify({ mode: 'ja', size: 'large' });
app.location.hash = '#source-anchor';
app.events.pageshow({ persisted: true });
assert.deepEqual(app.root.dataset, { mode: 'parallel', size: 'large' });
assert(app.source.scrolled);
assert.deepEqual(JSON.parse(app.storage[key]), { mode: 'parallel', size: 'large' });
console.log('PASS: preference defaults, mode/font controls, aria-pressed, persistence, allowed keys, malformed/blocked storage, original-note backlinks, repeated clicks, deep links, history events and BFCache preference synchronization.');
