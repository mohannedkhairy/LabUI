/*
 * @-mentions: type "@" in any attached textarea to search across manuscripts,
 * experiments, tasks, papers, memories, and notes, and insert a reference.
 *
 * Usage:
 *   attachMentions(document.getElementById('some-textarea'));
 *
 * Storage format (plain text, portable across the app):
 *   @[Title](mention:type:id)
 * This is valid Markdown link syntax on purpose — marked.js renders it as
 * <a href="mention:type:id">Title</a> with zero special parsing, and
 * renderMentionsHtml() below turns that anchor into a clickable chip.
 * renderMentionsPlain() does the same directly on raw (non-markdown) text.
 */
(function () {
  'use strict';

  const TYPE_META = {
    manuscript: { icon: '📄', label: 'Manuscript' },
    experiment: { icon: '🧪', label: 'Experiment' },
    task:       { icon: '✅', label: 'Task' },
    paper:      { icon: '📚', label: 'Paper' },
    memory:     { icon: '🧠', label: 'Memory' },
    note:       { icon: '📝', label: 'Note' },
  };
  const MENTION_TOKEN_RE = /@\[([^\]]+)\]\(mention:([a-z]+):([^)]+)\)/g;

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
  }

  function mentionHref(type, id) {
    switch (type) {
      case 'manuscript': return '/manuscripts/' + encodeURIComponent(id) + '/edit';
      case 'experiment': return '/experiments/' + encodeURIComponent(id);
      case 'task':       return '/tasks?open=' + encodeURIComponent(id);
      case 'paper':      return '/research/paper/' + encodeURIComponent(id) + '/view';
      case 'memory':     return '/research/memory';
      case 'note':       return '/research/notes?open=' + encodeURIComponent(id);
      default:           return '#';
    }
  }

  window.openMention = function (type, id) {
    window.location.href = mentionHref(type, id);
  };

  // Single delegated listener for every rendered chip, keyed off data-*
  // attributes. Deliberately NOT inline onclick="...(id)": an id embedded in
  // an HTML attribute is HTML-entity-decoded by the parser before an inline
  // handler's JS runs, so HTML-escaping alone does not make it JS-string-safe
  // there. data-* attributes stay inert text — always safe.
  document.addEventListener('click', (e) => {
    const chip = e.target.closest && e.target.closest('.mention-chip[data-mid]');
    if (chip) openMention(chip.dataset.mtype, chip.dataset.mid);
  });

  function chipHtml(title, type, id) {
    const meta = TYPE_META[type] || { icon: '🔗', label: type };
    const safeTitle = escapeHtml(title);
    const safeType = escapeHtml(type);
    const safeId = escapeHtml(String(id));
    return `<span class="mention-chip" data-mtype="${safeType}" data-mid="${safeId}" ` +
           `title="${safeTitle} (${meta.label})">${meta.icon} ${safeTitle}</span>`;
  }

  // Convert @[Title](mention:type:id) tokens found in already-marked-rendered
  // HTML (marked turns the markdown-link-shaped token into a plain <a>).
  window.renderMentionsHtml = function (html) {
    if (!html || html.indexOf('mention:') === -1) return html;
    const div = document.createElement('div');
    div.innerHTML = html;
    div.querySelectorAll('a[href^="mention:"]').forEach(a => {
      const rest = a.getAttribute('href').slice('mention:'.length);
      const sep = rest.indexOf(':');
      if (sep === -1) return;
      const type = rest.slice(0, sep);
      const id = rest.slice(sep + 1);
      const tmp = document.createElement('div');
      tmp.innerHTML = chipHtml(a.textContent, type, id);
      a.replaceWith(tmp.firstChild);
    });
    return div.innerHTML;
  };

  // Convert @[Title](mention:type:id) tokens directly in raw (non-markdown)
  // text — for compact previews (task cards, etc.) that skip marked entirely.
  window.renderMentionsPlain = function (text) {
    const src = text || '';
    const re = new RegExp(MENTION_TOKEN_RE.source, 'g');
    let out = '', last = 0, m;
    while ((m = re.exec(src)) !== null) {
      out += escapeHtml(src.slice(last, m.index));
      out += chipHtml(m[1], m[2], m[3]);
      last = m.index + m[0].length;
    }
    out += escapeHtml(src.slice(last));
    return out;
  };

  // Strip mention tokens down to their plain title — for contexts (card
  // titles, notifications) that need short plain text, not HTML.
  window.stripMentionsToText = function (text) {
    return String(text || '').replace(MENTION_TOKEN_RE, (_m, title) => title);
  };

  // ── Caret-position mirror (so the dropdown opens right under the "@") ──────
  const MIRROR_PROPS = [
    'boxSizing', 'width', 'fontFamily', 'fontSize', 'fontWeight', 'fontStyle',
    'letterSpacing', 'lineHeight', 'paddingTop', 'paddingRight', 'paddingBottom',
    'paddingLeft', 'borderTopWidth', 'borderRightWidth', 'borderBottomWidth',
    'borderLeftWidth', 'textTransform',
  ];

  function caretCoords(el, pos) {
    const style = getComputedStyle(el);
    const mirror = document.createElement('div');
    MIRROR_PROPS.forEach(p => { mirror.style[p] = style[p]; });
    mirror.style.position = 'absolute';
    mirror.style.visibility = 'hidden';
    mirror.style.whiteSpace = 'pre-wrap';
    mirror.style.wordWrap = 'break-word';
    mirror.style.top = '0';
    mirror.style.left = '-9999px';
    mirror.style.height = 'auto';
    document.body.appendChild(mirror);
    mirror.textContent = el.value.substring(0, pos);
    const marker = document.createElement('span');
    marker.textContent = '​';
    mirror.appendChild(marker);
    const rect = el.getBoundingClientRect();
    const markerRect = marker.getBoundingClientRect();
    const mirrorRect = mirror.getBoundingClientRect();
    const top = rect.top + (markerRect.top - mirrorRect.top) - el.scrollTop;
    const left = rect.left + (markerRect.left - mirrorRect.left) - el.scrollLeft;
    document.body.removeChild(mirror);
    return { top, left, lineHeight: parseFloat(style.lineHeight) || 18 };
  }

  // Find an open "@query" immediately before the caret, if any. The trigger
  // must start at a word boundary (start of text / after whitespace) and the
  // text since "@" must not already contain a closed mention token.
  function findTrigger(value, caret) {
    const upto = value.slice(0, caret);
    const at = upto.lastIndexOf('@');
    if (at === -1) return null;
    if (at > 0 && !/[\s([{]/.test(upto[at - 1])) return null;   // not a boundary
    const query = upto.slice(at + 1);
    if (query.length > 60) return null;                          // runaway guard
    if (/[\n]/.test(query)) return null;                          // stop at newline
    if (query.indexOf('](') !== -1) return null;                  // already a token
    return { start: at, query };
  }

  function attachMentions(textarea) {
    if (!textarea || textarea.__mentionsAttached) return;
    textarea.__mentionsAttached = true;

    let dropdown = null;
    let items = [];
    let activeIndex = 0;
    let trigger = null;
    let debounceTimer = null;
    let requestSeq = 0;

    function closeDropdown() {
      if (dropdown) { dropdown.remove(); dropdown = null; }
      trigger = null;
      items = [];
    }

    function positionDropdown() {
      if (!dropdown || !trigger) return;
      const coords = caretCoords(textarea, textarea.selectionStart);
      dropdown.style.top = (coords.top + coords.lineHeight + 4) + 'px';
      dropdown.style.left = coords.left + 'px';
      // Keep on-screen if it would overflow the right/bottom edge.
      const rect = dropdown.getBoundingClientRect();
      if (rect.right > window.innerWidth - 8) {
        dropdown.style.left = Math.max(8, window.innerWidth - rect.width - 8) + 'px';
      }
      if (rect.bottom > window.innerHeight - 8) {
        dropdown.style.top = (coords.top - rect.height - 4) + 'px';
      }
    }

    function renderDropdown() {
      if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.className = 'mention-dropdown';
        document.body.appendChild(dropdown);
      }
      if (!items.length) {
        dropdown.innerHTML = '<div class="mention-empty">No matches</div>';
      } else {
        dropdown.innerHTML = items.map((it, i) => {
          const meta = TYPE_META[it.type] || { icon: '🔗', label: it.type };
          return `<div class="mention-item${i === activeIndex ? ' active' : ''}" data-i="${i}">
            <span class="mention-item-icon">${meta.icon}</span>
            <span class="mention-item-title">${escapeHtml(it.title)}</span>
            <span class="mention-item-type">${meta.label}</span>
          </div>`;
        }).join('');
        dropdown.querySelectorAll('.mention-item').forEach(el => {
          el.addEventListener('mousedown', (e) => {
            e.preventDefault();
            selectItem(parseInt(el.dataset.i, 10));
          });
        });
      }
      positionDropdown();
    }

    function selectItem(i) {
      const it = items[i];
      if (!it || !trigger) return;
      const token = `@[${it.title}](mention:${it.type}:${it.id}) `;
      const value = textarea.value;
      const before = value.slice(0, trigger.start);
      const after = value.slice(textarea.selectionStart);
      textarea.value = before + token + after;
      const newPos = (before + token).length;
      textarea.setSelectionRange(newPos, newPos);
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
      closeDropdown();
      textarea.focus();
    }

    async function runSearch(query) {
      const seq = ++requestSeq;
      try {
        const r = await fetch('/api/mentions/search?q=' + encodeURIComponent(query) + '&limit=6');
        if (!r.ok) return;
        const d = await r.json();
        if (seq !== requestSeq || !trigger) return;   // stale response / closed meanwhile
        items = d.results || [];
        activeIndex = 0;
        renderDropdown();
      } catch (e) { /* network hiccup — leave dropdown as-is */ }
    }

    textarea.addEventListener('input', () => {
      const t = findTrigger(textarea.value, textarea.selectionStart);
      if (!t) { closeDropdown(); return; }
      trigger = t;
      renderDropdown();  // show immediately (loading state via last results)
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => runSearch(t.query), 180);
    });

    textarea.addEventListener('keydown', (e) => {
      if (!dropdown || !trigger) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIndex = Math.min(activeIndex + 1, Math.max(0, items.length - 1));
        renderDropdown();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        renderDropdown();
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        if (items.length) { e.preventDefault(); selectItem(activeIndex); }
      } else if (e.key === 'Escape') {
        closeDropdown();
      }
    });

    textarea.addEventListener('blur', () => {
      // Let a mousedown-selection register before we tear the dropdown down.
      setTimeout(closeDropdown, 150);
    });
    window.addEventListener('scroll', () => { if (dropdown) positionDropdown(); }, true);
  }

  window.attachMentions = attachMentions;

  // Auto-attach to any textarea opted in via data-mentions="1", including ones
  // added to the DOM later (task drawer, etc.).
  function autoAttach(root) {
    (root || document).querySelectorAll('textarea[data-mentions="1"]').forEach(attachMentions);
  }
  document.addEventListener('DOMContentLoaded', () => autoAttach());
  window.mentionsAutoAttach = autoAttach;
})();
