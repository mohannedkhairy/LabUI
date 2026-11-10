/* Citation completion for CodeMirror 5 and exact, alias-aware preview tokens. */
(function (root) {
  'use strict';

  function context(editor) {
    if (editor.somethingSelected && editor.somethingSelected()) return null;
    const position = editor.getCursor();
    const cursor = {line: position.line, ch: position.ch};
    const line = editor.getLine(cursor.line);
    const match = line.slice(0, cursor.ch).match(/(^|[^\w.\-@])@([A-Za-z0-9_\-]*)$/);
    if (!match) return null;
    // Keep literal examples inside inline code out of the citation picker.
    if ((line.slice(0, cursor.ch).match(/`/g) || []).length % 2) return null;
    const tail = line.slice(cursor.ch).match(/^[A-Za-z0-9_\-]*/)[0];
    return {query: match[2], line, cursor, from: {line: cursor.line, ch: cursor.ch - match[2].length - 1},
      to: {line: cursor.line, ch: cursor.ch + tail.length}};
  }

  function attachAutocomplete(editor, options = {}) {
    const CM = options.CodeMirror || root.CodeMirror;
    const request = options.fetch || root.fetch.bind(root);
    let sequence = 0, timer, controller, shown;

    function cancel() {
      sequence++;
      clearTimeout(timer);
      if (controller) controller.abort();
    }

    function schedule() {
      cancel();
      const trigger = context(editor);
      if (editor.closeHint) editor.closeHint();
      shown = null;
      if (!trigger) return;
      const ticket = sequence;
      timer = setTimeout(async () => {
        if (!CM || !editor.showHint) {
          if (options.onUnavailable) options.onUnavailable();
          return;
        }
        controller = new AbortController();
        try {
          const response = await request('/api/rag/citations/autocomplete?q=' + encodeURIComponent(trigger.query) + '&limit=12', {signal: controller.signal});
          if (!response.ok) throw new Error('Citation search failed');
          const data = await response.json();
          const current = context(editor);
          if (ticket !== sequence || !current || current.line !== trigger.line ||
              current.cursor.line !== trigger.cursor.line || current.cursor.ch !== trigger.cursor.ch) return;
          const items = (data.citations || []).map(paper => ({
            text: '@' + (paper.citation_key || paper.key || paper.paper_id),
            displayText: '@' + (paper.citation_key || paper.key || paper.paper_id) + ' — ' + (paper.title || 'Untitled'),
            render(element) {
              const doc = element.ownerDocument;
              const key = doc.createElement('strong'); key.textContent = '@' + (paper.citation_key || paper.key || paper.paper_id);
              const title = doc.createElement('div'); title.textContent = paper.title || 'Untitled';
              const meta = doc.createElement('small'); meta.textContent = (paper.authors || 'Author unavailable') + ' · ' + (paper.year || 'Date unavailable');
              element.append(key, title, meta);
            },
            hint(cm, hints, completion) {
              cm.replaceRange(completion.text, hints.from, hints.to, 'complete');
              if (options.onPick) options.onPick(paper);
            },
          }));
          if (!items.length) return;
          // CM5's instance method takes ONE options object. Passing a hint
          // function as the first argument silently selects the wrong helper.
          editor.showHint({hint: () => ({list: items, from: trigger.from, to: trigger.to}),
            completeSingle: false, closeOnUnfocus: true, updateOnCursorActivity: false});
          shown = trigger;
        } catch (error) {
          if (error.name !== 'AbortError' && ticket === sequence && options.onUnavailable) options.onUnavailable();
        }
      }, options.delay === undefined ? 120 : options.delay);
    }

    editor.on('inputRead', schedule);
    editor.on('changes', (_cm, changes) => {
      if (changes.some(change => change.origin === 'setValue')) {
        cancel();
        if (editor.closeHint) editor.closeHint();
      } else if (changes.some(change => /delete/.test(change.origin || ''))) schedule();
    });
    editor.on('cursorActivity', () => {
      const trigger = context(editor);
      if (!trigger || shown && (shown.cursor.line !== trigger.cursor.line ||
          shown.cursor.ch !== trigger.cursor.ch || shown.line !== trigger.line)) {
        cancel();
        if (editor.closeHint) editor.closeHint();
        shown = null;
      }
    });
    editor.on('blur', () => { cancel(); });
    return {schedule, cancel};
  }

  function index(records) {
    const map = Object.create(null);
    for (const record of records || []) {
      for (const token of [record.paper_id, record.citation_key, ...(record.aliases || [])]) {
        if (token && /^[A-Za-z0-9_\-]+$/.test(token)) map[token] = record;
      }
    }
    return map;
  }

  function unique(map) {
    return [...new Map(Object.values(map).map(record => [record.paper_id || record.citation_key, record])).values()]
      .sort((left, right) => left.n - right.n);
  }

  function render(text, map, escape) {
    return text.replace(/(?<![\w.\-])@([A-Za-z0-9_\-]+)/g, (match, token) => {
      const record = Object.prototype.hasOwnProperty.call(map, token) && map[token];
      if (!record) return match;
      return '<span class="cite-chip" data-paper-id="' + escape(record.paper_id || record.citation_key) +
        '" title="[' + record.n + '] ' + escape(record.title || token) + '">[' + record.n + ']</span>';
    });
  }

  const api = {context, attachAutocomplete, index, unique, render};
  root.LabUICitations = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
