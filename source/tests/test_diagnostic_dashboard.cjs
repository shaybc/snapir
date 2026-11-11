/* Exercise offline dashboard interactions with a minimal DOM, without a browser or network. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.handlers = {}; this.value = ''; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return (this.text || '') + this.children.map(child => child.textContent).join(''); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.text = ''; this.children = children; }
  get childNodes() { return this.children; }
  addEventListener(name, callback) { this.handlers[name] = callback; }
  focus() {}
  scrollIntoView() {}
}
const elements = new Map();
const get = id => {
  if (!elements.has(id)) elements.set(id, new Element('div'));
  return elements.get(id);
};
for (const id of ['type', 'operation', 'direction', 'evidence-status']) get(id).value = 'all';
get('status').value = 'attention';
const events = {};
let hash = '';
const location = {
  get hash() { return hash; },
  set hash(value) { hash = value ? '#' + value.replace(/^#/, '') : ''; if (events.hashchange) events.hashchange(); }
};
const context = vm.createContext({
  window: {addEventListener: (name, callback) => { events[name] = callback; }},
  document: {getElementById: get, createElement: tag => new Element(tag)}, location,
  navigator: {}, console
});
const root = process.argv[2];
vm.runInContext(fs.readFileSync(path.join(root, 'report-data.js'), 'utf8'), context);
vm.runInContext(fs.readFileSync(path.join(root, 'dashboard.js'), 'utf8'), context);

assert.match(get('result-count').textContent, /2 of 1254/);
assert.equal(get('targets').children.length, 2, 'The opening view hides planned work, successes and policy exclusions');
assert.match(get('targets').children[0].textContent, /CCString/);
get('status').value = 'all'; get('status').handlers.input();
assert.equal(get('targets').children.length, 50, 'Large lists are paginated');
get('next').onclick(); assert.match(get('page').textContent, /Page 2/);
get('search').value = 'Entry method'; get('search').handlers.input();
assert.equal(get('targets').children.length, 1);
const filtered = get('search').value;
get('targets').children[0].children[0].children[0].onclick();
assert.equal(get('detail').hidden, false);
assert.match(get('detail-title').textContent, /CCString/);
assert.match(get('detail-body').textContent, /Entry method has no supplied Java source/);
assert.match(get('detail-body').textContent, /CCXML/);
const fileButton = get('detail-body').children.find(child => child.tag === 'button');
fileButton.onclick();
assert.match(get('file-scope').textContent, /CCString/);
assert.equal(get('all-files').hidden, false);
get('all-files').onclick(); assert.equal(get('all-files').hidden, true);
get('back').onclick();
assert.equal(get('detail').hidden, true);
assert.equal(get('search').value, filtered, 'Returning to the list preserves filters');
get('search').value = ''; get('search').handlers.input();
get('status').value = 'completed'; get('status').handlers.input();
assert.equal(get('targets').children.length, 1);
get('status').value = 'all'; get('status').handlers.input();
get('operation').value = 'BANK/Other'; get('operation').handlers.input();
assert.equal(get('targets').children.length, 1);
get('operation').value = 'all'; get('operation').handlers.input();
get('direction').value = 'unformat'; get('direction').handlers.input();
assert.equal(get('targets').children.length, 1);
location.hash = 'target=%invalid'; assert.equal(get('detail').hidden, true);
get('saved-panel').open = true; get('saved-panel').handlers.toggle();
assert.match(get('evidence-count').textContent, /1 saved records/);
assert.match(get('evidence-list').textContent, /CCString/);
console.log('Offline dashboard interactions passed: filtering, pagination, drill-down, relationships, files, back navigation and saved evidence.');
