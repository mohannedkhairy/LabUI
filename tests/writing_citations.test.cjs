const assert = require('node:assert/strict');
const {test} = require('node:test');
const citations = require('../submission_strategy/jfr/web/static/writing_citations.js');
const pause = (ms = 10) => new Promise(resolve => setTimeout(resolve, ms));

function editor(text) {
  return {text, cursor: {line: 0, ch: text.length}, events: {}, state: {},
    getLine() { return this.text; }, getCursor() { return this.cursor; }, somethingSelected() { return false; },
    on(event, fn) { this.events[event] = fn; }, closeHint() { this.hints = null; },
    showHint(options) { assert.equal(typeof options.hint, 'function'); this.hints = options.hint(); this.hintOptions = options; },
    replaceRange(value, from, to) { this.text = this.text.slice(0,from.ch)+value+this.text.slice(to.ch); },
  };
}
const paper = {citation_key:'cai2024', paper_id:'long-paper-id', title:'CO2 nanobubbles for oil recovery', authors:'Liyuan Cai', year:2024};

test('bare @, one-letter queries, emails and inline code have correct trigger boundaries', () => {
  assert.equal(citations.context(editor('@')).query, '');
  assert.equal(citations.context(editor('Evidence @c')).query, 'c');
  assert.equal(citations.context(editor('[@cai')).query, 'cai');
  for (const value of ['user@cai','file.@cai','@@cai','`@cai','@cai ']) assert.equal(citations.context(editor(value)), null, value);
});

test('bare @ fetches suggestions with the CM5 options API and never auto-inserts a sole match', async () => {
  const cm = editor('@'); let url;
  citations.attachAutocomplete(cm, {CodeMirror:{}, delay:0, fetch:async value => {url=value;return {ok:true,json:async()=>({citations:[paper]})};}});
  cm.events.inputRead(); await pause();
  assert.ok(url.includes('q=&'));
  assert.equal(cm.text,'@'); assert.equal(cm.hintOptions.completeSingle,false);
  assert.equal(cm.hints.list[0].text,'@cai2024');
});

test('selecting replaces the full trigger once, preserves following punctuation and invokes save', async () => {
  const cm = editor('Evidence @cai.'); cm.cursor.ch--;
  let chosen;
  citations.attachAutocomplete(cm, {CodeMirror:{}, delay:0, onPick:p=>{chosen=p;}, fetch:async()=>({ok:true,json:async()=>({citations:[paper]})})});
  cm.events.inputRead(); await pause();
  const result = cm.hints;
  result.list[0].hint(cm,result,result.list[0]);
  assert.equal(cm.text,'Evidence @cai2024.'); assert.equal(chosen,paper);
});

test('responses for an old query cannot replace results for the newer query', async () => {
  const cm = editor('@ca'); let oldResolve;
  citations.attachAutocomplete(cm, {CodeMirror:{}, delay:0, fetch:async url => {
    if (url.includes('q=ca&')) return new Promise(resolve=>{oldResolve=resolve;});
    return {ok:true,json:async()=>({citations:[paper]})};
  }});
  cm.events.inputRead(); await pause();
  cm.text='@cai'; cm.cursor.ch=4; cm.events.inputRead(); await pause();
  oldResolve({ok:true,json:async()=>({citations:[{...paper,citation_key:'wrong2025'}]})}); await pause();
  assert.equal(cm.hints.list[0].text,'@cai2024');
});

test('moving the cursor or replacing the section invalidates outstanding suggestions', async () => {
  const cm = editor('@cai'); let resolve;
  citations.attachAutocomplete(cm, {CodeMirror:{}, delay:0, fetch:async()=>new Promise(done=>{resolve=done;})});
  cm.events.inputRead(); await pause();
  cm.cursor.ch=0; cm.events.cursorActivity();
  resolve({ok:true,json:async()=>({citations:[paper]})}); await pause();
  assert.equal(cm.hints,null);
});

test('aliases render once, prefix keys stay distinct, and email addresses are unchanged', () => {
  const one={...paper,n:1,aliases:['old-cai']}; const two={...paper,paper_id:'second',citation_key:'cai2024a',n:2};
  const map=citations.index([one,two]);
  assert.equal(citations.unique(map).length,2);
  const rendered=citations.render('@cai2024a @cai2024 @old-cai @long-paper-id user@cai2024 @unknown',map,String);
  assert.ok(rendered.startsWith('<span class="cite-chip" data-paper-id="second"'));
  assert.equal((rendered.match(/\[1\]<\/span>/g)||[]).length,3);
  assert.ok(rendered.includes('user@cai2024 @unknown'));
});

test('an open picker closes when the cursor moves to a different citation', async () => {
  const cm = editor('@cai and @khairy'); cm.cursor.ch=4;
  citations.attachAutocomplete(cm, {CodeMirror:{}, delay:0, fetch:async()=>({ok:true,json:async()=>({citations:[paper]})})});
  cm.events.inputRead(); await pause();
  assert.ok(cm.hints);
  cm.cursor.ch=cm.text.length; cm.events.cursorActivity();
  assert.equal(cm.hints,null);
});
