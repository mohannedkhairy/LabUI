#!/usr/bin/env python3
"""Generate the browsable phrase-bank page from a skill pack's phrase-bank.md.

    python3 build_phrasebank_html.py                       # default skill
    python3 build_phrasebank_html.py --skill <name>
    python3 build_phrasebank_html.py --out /tmp/preview.html

Writes `<skill>/phrase-bank.html`, which LabUI serves at
`/api/rag/skills/<skill>/phrasebank.html` and embeds in the Phrase Bank tab.

The page is a self-contained artifact: open it directly in a browser and it
works. Inside LabUI it sits in an iframe and follows the app's theme toggle via
a postMessage bridge (`{type: 'labui-theme', theme: 'dark'|'light'}`), falling
back to `prefers-color-scheme` when opened standalone.

Inside LabUI the page is rendered on request by `render()` (so it never goes
stale), with the user's own sentences — mined from their writing-style samples
by `skills/style_bank.py` — merged into each move under the source "You".
Running this script writes the same page, without personal exemplars, to disk
as a standalone artifact.

Stdlib only.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.resolve()
DEFAULT_SKILL = "nanobubble-paper-writer"

# Source keys → a human label for the filter chips' tooltips. Unknown keys still
# work; they just show the bare key.
SOURCE_META = {
    "Attard-2003":     "Attard, Adv. Colloid Interface Sci. 104 (2003)",
    "Yoon-2000":       "Yoon, Int. J. Miner. Process. 58 (2000)",
    "Jungwirth-2006":  "Jungwirth & Tobias, Chem. Rev. 106 (2006)",
    "JCIS-2015":       "Bubble–particle interactions, JCIS 449 (2015)",
    "Zhang-2016":      "Zhang & Seddon, Langmuir (2016)",
    "Meegoda-2019":    "Meegoda et al., Langmuir 35 (2019)",
    "Yasui-2019":      "Yasui et al., Langmuir",
    "Hewage-2021":     "Aluthgun Hewage et al., Colloids Surf. A 609 (2021)",
    "Alheshibri-2021": "Alheshibri et al., Curr. Opin. Colloid Interface Sci.",
    "Ma-2022":         "Ma, Li, Ohl et al., JCIS 606 (2022)",
    "Sullivan-2023":   "Sullivan et al., Int. J. Heat Mass Transf. 217 (2023)",
    "LB-2024":         "Nanobubbles on Langmuir–Blodgett films, JCIS 669 (2024)",
    "Abolfath-2024":   "Abolfath et al., arXiv:2403.05880",
    "Kubelka-JCIS":    "Kubelka, Taman & Piri, JCIS (R3) — house paper",
    "Khairy-2025":     "Khairy, Kubelka & Piri, Langmuir (2025) — your paper",
    "Box-1976":        "Box, J. Am. Stat. Assoc. 71 (1976)",
    "Cuntz-2010":      "Cuntz et al., PLoS Comput. Biol. 6 (2010)",
}
HOUSE_SOURCES = {"Kubelka-JCIS", "Khairy-2025"}
MINE = "You"           # source key for sentences mined from the user's style samples
SOURCE_META[MINE] = "Your own writing — mined from your style samples"

QUOTE_RE = re.compile(r'^>\s*"(.+?)"\s*—\s*([A-Za-z0-9\-]+)(?:,\s*(.+))?$')


def is_pattern_line(line: str) -> bool:
    """True when a line is (nearly) all backticked frames joined by ' / '.

    A prose line that merely opens with a backticked term is not a pattern line —
    that distinction keeps notes like "`respectively` is the corpus's standard
    device…" out of the pattern chips.
    """
    inside = sum(len(x) for x in re.findall(r"`([^`]+)`", line))
    outside = re.sub(r"`[^`]+`", "", line).strip()
    if not inside:
        return False
    if re.fullmatch(r"[/\s,.;()…]*", outside):
        return True
    return inside / max(len(line), 1) > 0.75


def parse(md: str) -> tuple[list[dict], list[tuple[str, str, str]]]:
    """→ (cards, budget_rows). One card per rhetorical move."""
    sections: list[dict] = []
    cur_sec = cur_move = None
    for line in md.split("\n"):
        if line.startswith("## "):
            cur_sec = {"title": line[3:].strip(), "moves": [], "notes": [], "ex": [], "bullets": []}
            sections.append(cur_sec)
            cur_move = None
        elif line.startswith("### ") and cur_sec:
            cur_move = {"title": line[4:].strip(), "patterns": [], "ex": [], "note": []}
            cur_sec["moves"].append(cur_move)
        elif line.startswith('> "'):
            m = QUOTE_RE.match(line)
            if m and cur_sec:
                e = {"q": m.group(1), "src": m.group(2), "sec": (m.group(3) or "").strip()}
                (cur_move["ex"] if cur_move else cur_sec["ex"]).append(e)
        elif line.startswith("`") and cur_move is not None and is_pattern_line(line):
            cur_move["patterns"] += [p for p in re.findall(r"`([^`]+)`", line) if len(p) > 3]
        elif line.startswith("- ") and cur_sec and not cur_move:
            cur_sec["bullets"].append(line[2:].strip())
        elif line.strip() and not line.startswith(("---", "|", "#")):
            (cur_move["note"] if cur_move else cur_sec["notes"] if cur_sec else []).append(line)

    cards: list[dict] = []
    for s in sections:
        title = s["title"]
        if title.startswith("0."):
            continue
        short = title.split(". ", 1)[-1]
        if s["ex"] or s["bullets"]:
            cards.append({
                "sec": title, "move": short, "ex": s["ex"], "bullets": s["bullets"],
                "patterns": [p for p in re.findall(r"`([^`]+)`", " ".join(s["notes"])) if len(p) > 3],
                "note": " ".join(s["notes"]),
            })
        for mv in s["moves"]:
            cards.append({"sec": title, "move": mv["title"], "patterns": mv["patterns"],
                          "ex": mv["ex"], "bullets": [], "note": " ".join(mv["note"])})

    budget = []
    for m in re.finditer(r"^\|\s*(.+?)\s*\|\s*\*{0,2}([\d.]+)\*{0,2}([^|]*)\|\s*(.+?)\s*\|$", md, re.M):
        label = re.sub(r"`", "", m.group(1)).strip()
        if label.lower().startswith(("marker", "property", "---")) or "|" in label:
            continue
        num = m.group(2) + (" " + m.group(3).strip() if m.group(3).strip() else "")
        budget.append((label, num, m.group(4).strip()))
    return cards, budget[:16]


def md_inline(text: str) -> str:
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
    return t


def _mine_q(e: dict) -> str:
    """A personal exemplar with the frame's literal words emphasised, so the
    reader sees the move inside their own sentence."""
    parts = e.get("parts")
    if not parts:
        return html.escape(e["q"])
    return "".join(html.escape(t) if slot else f"<b>{html.escape(t)}</b>" for t, slot in parts)


def merge_personal(cards: list[dict], bank: dict | None) -> int:
    """Append the user's mined sentences to the matching cards, in place."""
    if not bank:
        return 0
    by_key = {(c["sec"], c["move"]): c for c in cards}
    n = 0
    for mv in bank.get("moves", []):
        c = by_key.get((mv["sec"], mv["move"]))
        if not c:
            continue
        mine = [{"q": y["text"], "src": MINE, "sec": y.get("sample", ""), "parts": y.get("parts")}
                for y in mv.get("yours", [])]
        c["ex"] = mine + c["ex"]          # yours first: it is the point of the page
        n += len(mine)
    return n


def card_html(c: dict) -> str:
    pats = "".join(f'<button class="pat" title="click to copy">{md_inline(p)}</button>'
                   for p in c["patterns"])
    exs = "".join(
        f'<blockquote class="{"mine" if e["src"] == MINE else "house" if e["src"] in HOUSE_SOURCES else ""}">'
        f'<span class="q">{_mine_q(e) if e["src"] == MINE else html.escape(e["q"])}</span>'
        f'<cite title="{html.escape(SOURCE_META.get(e["src"], e["src"]))}">{html.escape(e["src"])}'
        + (f' <span class="sec">· {html.escape(e["sec"])}</span>' if e["sec"] else "")
        + "</cite></blockquote>"
        for e in c["ex"])
    if c["bullets"]:
        exs += "<ul class='bl'>" + "".join(f"<li>{md_inline(b)}</li>" for b in c["bullets"]) + "</ul>"
    note = f'<p class="note">{md_inline(c["note"])}</p>' if c["note"] else ""
    haystack = " ".join([c["move"], *c["patterns"], *(e["q"] for e in c["ex"]),
                         *c["bullets"], c["note"]]).lower()
    return (f'<article class="card" data-sec="{html.escape(c["sec"])}" '
            f'data-text="{html.escape(haystack)}" '
            f'data-srcs="{html.escape(" ".join(e["src"] for e in c["ex"]))}">'
            f'<h3>{md_inline(c["move"])}<span class="tag">{html.escape(c["sec"])}</span></h3>'
            f'{"<div class=pats>" + pats + "</div>" if pats else ""}{exs}{note}</article>')


CSS = """
/* Bench — matches LabUI's shell so the embedded page doesn't read as a guest. */
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Public+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--surface:#fbf8f3;--raised:#fff;--sunken:#f4efe6;--ink:#171512;--mut:#6e675d;--faint:#9a9184;
      --line:#e6dece;--firm:#d3c8b6;--signal:#de4b2c;--signal-ink:#9e2d17;--wash:#fdf0ec;
      --data:#0e7c6e;--house:#b06a12;--grid:rgba(23,21,18,.055)}
@media(prefers-color-scheme:dark){html:not([data-theme="light"]){--surface:#141210;--raised:#1c1a16;--sunken:#171512;
      --ink:#f2ece2;--mut:#a79e90;--faint:#7a7266;--line:#2b2721;--firm:#3c362d;--signal:#ff6a45;
      --signal-ink:#ff8f73;--wash:#2a1611;--data:#2fbfac;--house:#e0a94a;--grid:rgba(242,236,226,.05)}}
html[data-theme="dark"]{--surface:#141210;--raised:#1c1a16;--sunken:#171512;--ink:#f2ece2;--mut:#a79e90;
      --faint:#7a7266;--line:#2b2721;--firm:#3c362d;--signal:#ff6a45;--signal-ink:#ff8f73;--wash:#2a1611;
      --data:#2fbfac;--house:#e0a94a;--grid:rgba(242,236,226,.05)}
*{box-sizing:border-box}
body{margin:0;color:var(--ink);font:15px/1.65 var(--font-sans,'Public Sans',system-ui,sans-serif);
     background-color:var(--surface);
     background-image:linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px);
     background-size:26px 26px}
.embedded header h1{display:none}
.embedded header{padding-top:12px}
header{position:sticky;top:0;z-index:20;background:var(--surface);border-bottom:1px solid var(--line);padding:16px 22px 10px}
h1{margin:0 0 2px;font-family:var(--font-display,'Fraunces',Georgia,serif);font-size:23px;font-weight:600;
   font-variation-settings:'SOFT' 0,'WONK' 1,'opsz' 60;letter-spacing:-.015em}
.sub{color:var(--mut);font-size:12.5px;margin-bottom:11px;max-width:74ch}
.controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input[type=search]{flex:1 1 240px;min-width:200px;padding:8px 12px;border:1px solid var(--line);border-radius:6px;
                   background:var(--sunken);color:var(--ink);font:14px var(--font-sans,'Public Sans',system-ui,sans-serif)}
input[type=search]:focus{outline:none;border-color:var(--signal)}
.chips{display:flex;gap:5px;flex-wrap:wrap;margin-top:9px}
.chip{border:1px solid var(--line);background:var(--raised);color:var(--mut);border-radius:6px;padding:3px 9px;
      font:10.5px/1.5 var(--font-mono,'JetBrains Mono',monospace);letter-spacing:.05em;text-transform:uppercase;cursor:pointer}
.chip:hover{border-color:var(--firm);color:var(--ink)}
.chip.on{background:var(--signal);border-color:var(--signal);color:#fff}
main{max-width:1180px;margin:0 auto;padding:20px 22px 80px;column-width:400px;column-gap:18px}
.card,.panel{break-inside:avoid;background:var(--raised);border:1px solid var(--line);border-radius:10px;
             padding:15px 17px;margin:0 0 16px;display:inline-block;width:100%}
.card[hidden],.panel[hidden],#empty[hidden]{display:none!important}
.card h3{margin:0 0 9px;font-family:var(--font-display,'Fraunces',Georgia,serif);font-size:15.5px;font-weight:600;
         display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.tag{font:9.5px var(--font-mono,'JetBrains Mono',monospace);color:var(--faint);white-space:nowrap;letter-spacing:.1em;
     text-transform:uppercase;flex:0 0 auto}
.pats{margin:0 0 11px;display:flex;flex-wrap:wrap;gap:5px}
.pat{font:12/1.45 var(--font-mono,'JetBrains Mono',monospace);font-size:12px;background:var(--sunken);color:var(--ink);
     border:1px solid var(--line);border-radius:5px;padding:3px 8px;cursor:copy;text-align:left}
.pat:hover{border-color:var(--signal)}
.pat.copied{background:var(--signal);border-color:var(--signal);color:#fff}
blockquote{margin:0 0 9px;padding:7px 0 7px 12px;border-left:2px solid var(--line);font-size:14px;
           font-family:var(--font-display,'Fraunces',Georgia,serif);font-variation-settings:'SOFT' 0,'opsz' 14}
blockquote.house{border-left-color:var(--house)}
.q{display:block}.q::before{content:'"'}.q::after{content:'"'}
cite{display:block;margin-top:4px;font:10.5px var(--font-mono,'JetBrains Mono',monospace);color:var(--faint);font-style:normal;
     letter-spacing:.03em}
blockquote.house cite{color:var(--house)}
blockquote.mine{border-left-color:var(--data)}
blockquote.mine cite{color:var(--data)}
blockquote.mine b{font-weight:600;color:var(--data)}
.chip.src.me{border-color:var(--data);color:var(--data)}
.chip.src.me.on{background:var(--data);border-color:var(--data);color:#fff}
.over{color:var(--danger,#c0392b);font-weight:600}
.opener{display:flex;justify-content:space-between;gap:10px;padding:5px 0;border-bottom:1px solid var(--line);font-size:13px}
.opener:last-child{border-bottom:0}
.sec{opacity:.75}
.note{margin:9px 0 0;font-size:13px;color:var(--mut);line-height:1.55}
.bl{margin:0 0 4px;padding-left:18px;font-size:13px;line-height:1.55}
.bl li{margin-bottom:6px}
table{border-collapse:collapse;width:100%;font-size:12.5px}
td,th{padding:4px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font:9.5px var(--font-mono,'JetBrains Mono',monospace);letter-spacing:.1em;text-transform:uppercase;color:var(--faint);font-weight:500}
.num{text-align:right;font-family:var(--font-mono,'JetBrains Mono',monospace);white-space:nowrap}
code{font:12px var(--font-mono,'JetBrains Mono',monospace);background:var(--sunken);border:1px solid var(--line);
     padding:1px 4px;border-radius:4px}
kbd{font:10px var(--font-mono,'JetBrains Mono',monospace);border:1px solid var(--firm);border-bottom-width:2px;border-radius:4px;
    padding:1px 4px;color:var(--mut)}
.empty{color:var(--mut);font-size:14px;padding:30px 0}
#count{font:11px var(--font-mono,'JetBrains Mono',monospace);color:var(--faint);margin-left:auto;letter-spacing:.06em}
"""

JS = """
const q=document.getElementById('q'),cards=[...document.querySelectorAll('.card')],
 cnt=document.getElementById('count'),empty=document.getElementById('empty');
let fSec='*',fSrc='*';
function apply(){
 const t=q.value.trim().toLowerCase();let n=0;
 cards.forEach(c=>{
  const ok=(fSec==='*'||c.dataset.sec===fSec)&&(fSrc==='*'||c.dataset.srcs.split(' ').includes(fSrc))
   &&(!t||c.dataset.text.includes(t));
  c.hidden=!ok;if(ok)n++;
 });
 cnt.textContent=n+' move'+(n===1?'':'s');empty.hidden=n>0;
}
q.addEventListener('input',apply);
document.getElementById('secs').addEventListener('click',e=>{
 if(!e.target.dataset.f)return;fSec=e.target.dataset.f;
 [...e.currentTarget.children].forEach(b=>b.classList.toggle('on',b===e.target));apply();});
document.getElementById('srcs').addEventListener('click',e=>{
 if(!e.target.dataset.s)return;fSrc=e.target.dataset.s==='*'?'*':e.target.dataset.s;
 [...e.currentTarget.children].forEach(b=>b.classList.toggle('on',b===e.target));apply();});
document.addEventListener('click',e=>{
 if(!e.target.classList.contains('pat'))return;
 const s=e.target.textContent;
 (navigator.clipboard?navigator.clipboard.writeText(s):Promise.reject()).then(()=>{
   e.target.classList.add('copied');setTimeout(()=>e.target.classList.remove('copied'),700);}).catch(()=>{});
});
document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement!==q){e.preventDefault();q.focus();}
 if(e.key==='Escape'){q.value='';apply();q.blur();}});
// Theme bridge: LabUI's shell posts its theme in; standalone falls back to the
// prefers-color-scheme media query in the stylesheet.
window.addEventListener('message',e=>{
 const d=e.data;
 if(!d||d.type!=='labui-theme')return;
 if(d.theme==='dark'||d.theme==='light')document.documentElement.setAttribute('data-theme',d.theme);
 // The shell may also pass its live palette and fonts so the page follows
 // whichever LabUI theme is selected, not just light/dark.
 if(d.vars&&typeof d.vars==='object')for(const k in d.vars)
   if(/^--[\\w-]+$/.test(k))document.documentElement.style.setProperty(k,String(d.vars[k]));
 if(typeof d.fontHref==='string'&&d.fontHref.indexOf('https://fonts.googleapis.com/')===0){
   let l=document.getElementById('labui-font');
   if(!l){l=document.createElement('link');l.rel='stylesheet';l.id='labui-font';document.head.appendChild(l);}
   if(l.href!==d.fontHref)l.href=d.fontHref;}
});
// Embedded in LabUI the host page already carries the title; drop ours.
if(window.parent!==window){document.documentElement.classList.add('embedded');
 window.parent.postMessage({type:'labui-phrasebank-ready'},'*');}
apply();
"""


def render(skill: str = DEFAULT_SKILL, personal: dict | None = None) -> tuple[str, dict]:
    """→ (page_html, counts). `personal` is a bank from skills/style_bank.py."""
    src = SKILLS_DIR / skill / "references" / "phrase-bank.md"
    if not src.is_file():
        raise FileNotFoundError(f"no phrase-bank.md in skill '{skill}' ({src})")
    md = src.read_text(encoding="utf-8")
    cards, budget = parse(md)
    n_mine = merge_personal(cards, personal)

    secnames: list[str] = []
    for c in cards:
        if c["sec"] not in secnames:
            secnames.append(c["sec"])

    chips = "".join(
        f'<button class="chip" data-f="{html.escape(s)}">{html.escape(s.split(". ", 1)[-1])}</button>'
        for s in secnames)
    used = {e["src"] for c in cards for e in c["ex"]}
    srcchips = "".join(
        f'<button class="chip src{" me" if k == MINE else ""}" data-s="{k}" '
        f'title="{html.escape(SOURCE_META.get(k, k))}">{k}</button>'
        for k in [MINE, *(k for k in SOURCE_META if k != MINE)] if k in used)
    budget_rows = "".join(
        f'<tr><td><code>{html.escape(a)}</code></td><td class="num">{html.escape(b)}</td>'
        f'<td>{md_inline(c)}</td></tr>' for a, b, c in budget)
    n_ex = sum(len(c["ex"]) for c in cards) - n_mine
    personal_html = _personal_panels(personal, n_mine)

    page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phrase Bank — {html.escape(skill)}</title><style>{CSS}</style></head><body>
<header>
<h1>Phrase Bank</h1>
<div class="sub">{len(cards)} rhetorical moves &middot; {n_ex} attested exemplars, each verified verbatim
against ~76,000 words of published prose from 15 papers. Gold rule = house papers{
"; teal rule = <strong>your own sentences</strong> (" + str(n_mine) + ", from your style samples)" if n_mine else ""}.
Click any pattern to copy. Press <kbd>/</kbd> to search.</div>
<div class="controls"><input type="search" id="q" placeholder="Search patterns, exemplars, notes… (e.g. 'gap', 'hedge', 'consistent with')" autocomplete="off"><span id="count"></span></div>
<div class="chips" id="secs"><button class="chip on" data-f="*">All sections</button>{chips}</div>
<div class="chips" id="srcs"><button class="chip src on" data-s="*">All sources</button>{srcchips}</div>
</header>
<main id="main">
{personal_html}<div class="panel"><h3 style="margin:0 0 8px;font-size:15px">The connective budget (measured)</h3>
<table><thead><tr><th>Marker</th><th class="num">per 1,000 w</th><th>Budget for a 6,000-word paper</th></tr></thead>
<tbody>{budget_rows}</tbody></table>
<p class="note"><strong>Zero occurrences</strong> in the whole corpus: <em>robust, delve, realm,
landscape, tapestry, testament, showcase, intricate, multifaceted, meticulous.</em> Any of them in a
draft is a defect.</p></div>
{"".join(card_html(c) for c in cards)}
<div class="empty" id="empty" hidden>No moves match that search.</div>
</main>
<script>{JS}</script></body></html>"""
    return page, {"moves": len(cards), "exemplars": n_ex, "mine": n_mine, "budget_rows": len(budget)}


def _personal_panels(bank: dict | None, n_mine: int) -> str:
    """Two panels summarising the user's samples against the corpus: connective
    rates next to the measured budget, and their habitual sentence openers."""
    if not bank or not bank.get("samples"):
        return ""
    st = bank.get("stats", {})
    rows = "".join(
        f'<tr><td><code>{html.escape(c["marker"])}</code></td>'
        f'<td class="num{" over" if c["status"] == "over" else ""}">{c["yours_per_k"]}</td>'
        f'<td class="num">{c["corpus_per_k"]}</td></tr>'
        for c in bank.get("connectives", []) if c["count"])
    conn = (f'<table><thead><tr><th>Marker</th><th class="num">yours /1k w</th>'
            f'<th class="num">corpus /1k w</th></tr></thead><tbody>{rows}</tbody></table>'
            if rows else '<p class="note">None of the budgeted connectives appear in your samples.</p>')
    openers = "".join(
        f'<div class="opener"><span><code>{html.escape(o["opener"])} …</code></span>'
        f'<span class="num">×{o["count"]}</span></div>'
        for o in bank.get("openers", [])[:10])
    return (
        '<div class="panel" data-personal><h3 style="margin:0 0 6px;font-size:15px">Your samples against the corpus</h3>'
        f'<p class="note" style="margin:0 0 8px">{len(bank["samples"])} samples · {st.get("words", 0):,} words · '
        f'{st.get("sentences", 0)} sentences, {n_mine} matched to a move · mean sentence '
        f'{st.get("mean_sentence_words", 0)} words. Red = more than twice the corpus rate.</p>{conn}</div>'
        + ('<div class="panel" data-personal><h3 style="margin:0 0 6px;font-size:15px">Openers you reach for</h3>'
           '<p class="note" style="margin:0 0 6px">Three-word sentence openings used more than once '
           'across your samples — candidate frames of your own.</p>' + openers + '</div>'
           if openers else "")
    )


def build(skill: str = DEFAULT_SKILL, out: Path | None = None) -> Path:
    try:
        page, n = render(skill)
    except FileNotFoundError as e:
        raise SystemExit(str(e))
    dest = out or (SKILLS_DIR / skill / "phrase-bank.html")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page, encoding="utf-8")
    print(f"{dest}  —  {n['moves']} moves, {n['exemplars']} exemplars, {n['budget_rows']} budget rows, "
          f"{len(page):,} bytes")
    return dest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skill", default=DEFAULT_SKILL)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    sys.exit(0 if build(a.skill, a.out) else 1)
