"""
Personal phrase bank — the skill pack's rhetorical moves, attested in YOUR prose.

The skill pack's phrase bank (references/phrase-bank.md) gives each rhetorical
move a set of pattern frames (`However, X.`, `X may be attributed to Y.`) and
exemplars quoted from published papers. This module reads the user's writing-
style samples, splits them into sentences, and matches every sentence against
those frames. A sentence that fits a frame becomes a personal exemplar of that
move — the same move, in the user's own voice.

It also measures the samples against the corpus: connective rates per 1,000
words next to the phrase bank's measured budget, and the sentence openers the
user reaches for repeatedly (candidate frames the pack does not have yet).

The result is cached as STYLE_DIR/.phrasebank.json and rebuilt automatically
whenever a sample is added, edited, or deleted (the check is an mtime compare,
and a rebuild is a few regexes over a few thousand words — milliseconds).

Consumers:
  - the Phrase Bank page (your sentences appear beside the corpus exemplars)
  - the Writing Style page (which frames each sample uses)
  - the writing brief (generation/agents.py) — the Style Writer is shown your
    own sentences for the moves of the section it is drafting
  - the Phrases panel in the writing workspace

Stdlib only; every entry point degrades to an empty bank instead of raising.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path

from skills.build_phrasebank_html import parse as parse_phrasebank
from skills.loader import DEFAULT_SKILL, SECTION_MAP, skill_dir

BANK_FILE = ".phrasebank.json"
HIDDEN_FILE = ".phrasebank-hidden.json"
VERSION = 2

# ── Sentence splitting ────────────────────────────────────────────────────────
# Scientific prose is full of abbreviations that end in a period; a naive split
# on ". " turns "Zhang et al. reported" into two sentences.
_ABBREV = (
    r"et al|Fig|Figs|Eq|Eqs|Ref|Refs|e\.g|i\.e|vs|approx|ca|cf|No|Nos|Sect|Sec|Tab|"
    r"Dr|Prof|wt|vol|resp|min|max|Ch|ref|fig|eq|al|St|Mt|Jr|Sr|Inc|Ltd|Co|viz|etc"
)
_ABBREV_RE = re.compile(rf"\b({_ABBREV})\.", re.I)
_SPLIT_RE = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]?[A-Z0-9])")
_GUARD = "⁣"      # invisible separator — stands in for a protected period


def split_sentences(text: str) -> list[str]:
    """Paragraph-aware sentence split that survives `et al.`, `Fig. 2`, `e.g.`."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text or ""):
        lines = [ln.strip() for ln in para.split("\n")]
        # Drop markdown headings, list bullets' markers, and reference-list lines.
        lines = [ln for ln in lines if ln and not ln.startswith("#")
                 and not re.match(r"^\[\d+\]|^\d+\.\s+[A-Z][a-z]+,\s", ln)]
        para = re.sub(r"^\s*[-*•]\s+", "", " ".join(lines))
        para = re.sub(r"\s+", " ", para).strip()
        if not para:
            continue
        guarded = _ABBREV_RE.sub(lambda m: m.group(1) + _GUARD, para)
        for s in _SPLIT_RE.split(guarded):
            s = s.replace(_GUARD, ".").strip()
            if len(s.split()) >= 4:          # fragments and headings are not sentences
                out.append(s)
    return out


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z][A-Za-z'\-]*", text or ""))


# ── Pattern frames → matchers ─────────────────────────────────────────────────
# Slots in the phrase bank: single capitals (X, Y, Z, A, B, N, …), bracketed
# placeholders ([n], [refs], [question]) and ellipses. Everything else is the
# literal frame.
_SLOT_RE = re.compile(r"\[[^\]]*\]|\.\.\.|…|~?\b[A-Z]\b")


class Frame:
    __slots__ = ("pattern", "regex", "literal", "anchored", "move", "sec")

    def __init__(self, pattern: str, regex: re.Pattern, literal: int,
                 anchored: bool, move: str, sec: str):
        self.pattern, self.regex, self.literal = pattern, regex, literal
        self.anchored, self.move, self.sec = anchored, move, sec


def _compile_frame(pattern: str, move: str, sec: str) -> Frame | None:
    p = pattern.strip()
    # Multi-sentence frames ("Two X have been proposed. In the first, …") cannot
    # match a single sentence; skip them.
    if re.search(r"[.?!]\s+[A-Z]", p.rstrip(".")):
        return None
    p = re.sub(r"[.;:]\s*$", "", p)                 # sentence-final punctuation
    pieces: list[str] = []
    literal = 0
    pos = 0
    slot_i = 0
    for m in _SLOT_RE.finditer(p):
        lit = p[pos:m.start()]
        pieces.append(_literal_regex(lit))
        literal += len(lit.strip())
        pieces.append(f"(?P<s{slot_i}>.+?)")
        slot_i += 1
        pos = m.end()
    tail = p[pos:]
    pieces.append(_literal_regex(tail))
    literal += len(tail.strip())
    if literal < 4:                                 # "X, Y" carries no frame
        return None
    first = p.lstrip()
    anchored = bool(first) and first[0].isupper() and not _SLOT_RE.match(first)
    body = "".join(pieces)
    # Frames that open a sentence must open it; fragments ("consistent with X")
    # may sit anywhere but must start on a word boundary.
    regex = re.compile((r"^" if anchored else r"(?:^|\b)") + body, re.I)
    return Frame(pattern, regex, literal, anchored, move, sec)


def _literal_regex(lit: str) -> str:
    """Escape a literal run; `a/b/c` alternations become (?:a|b|c); spacing is loose."""
    out = []
    for tok in re.split(r"(\s+)", lit):
        if not tok:
            continue
        if tok.isspace():
            out.append(r"\s+")
        elif "/" in tok and re.fullmatch(r"[A-Za-z/]+[,.;:]?", tok):
            alts, punct = (tok[:-1], tok[-1]) if tok[-1] in ",.;:" else (tok, "")
            out.append("(?:" + "|".join(re.escape(a) for a in alts.split("/") if a) + ")"
                       + re.escape(punct))
        else:
            out.append(re.escape(tok))
    return "".join(out)


def load_frames(skill: str = DEFAULT_SKILL) -> tuple[list[Frame], list[dict], list[tuple]]:
    """→ (frames, cards, budget_rows) parsed from the skill's phrase-bank.md."""
    src = skill_dir(skill) / "references" / "phrase-bank.md"
    try:
        md = src.read_text(encoding="utf-8")
    except OSError:
        return [], [], []
    cards, budget = parse_phrasebank(md)
    frames = []
    for c in cards:
        for pat in c["patterns"]:
            f = _compile_frame(pat, c["move"], c["sec"])
            if f:
                frames.append(f)
    return frames, cards, budget


def match_sentence(sentence: str, frames: list[Frame]) -> tuple[Frame, list[list]] | None:
    """Best (most specific) frame for a sentence, plus the sentence cut into
    [text, is_slot] parts so a UI can show the frame inside the user's words."""
    best = None
    for f in frames:
        m = f.regex.search(sentence)
        if not m:
            continue
        # Prefer the frame with the most literal text; ties go to anchored frames.
        key = (f.literal, f.anchored)
        if best is None or key > best[0]:
            best = (key, f, m)
    if not best:
        return None
    _, f, m = best
    # Walk the match only; text before it (a mid-sentence fragment frame) is
    # added once, as content, after the loop.
    parts, cur = [], m.start()
    spans = sorted((m.span(g) for g in m.groupdict() if m.group(g) is not None))
    for a, b in spans:
        if a > cur:
            parts.append([sentence[cur:a], False])
        parts.append([sentence[a:b], True])
        cur = b
    if m.end() > cur:
        parts.append([sentence[cur:m.end()], False])
    if m.end() < len(sentence):
        parts.append([sentence[m.end():], True])
    if m.start() > 0:
        parts.insert(0, [sentence[:m.start()], True])
    return f, parts


# ── Register measurements ─────────────────────────────────────────────────────

def _marker_regex(label: str) -> re.Pattern | None:
    """Budget-table label ("Thus / Therefore / Hence", "em dash —") → counter regex."""
    low = label.lower()
    if "em dash" in low:
        return re.compile("—")
    if "semicolon" in low:
        return re.compile(";")
    alts = [a.strip() for a in label.split("/") if a.strip()]
    if not alts:
        return None
    return re.compile(r"\b(?:" + "|".join(re.escape(a) for a in alts) + r")\b", re.I)


def connective_rates(text: str, budget: list[tuple]) -> list[dict]:
    words = max(word_count(text), 1)
    rows = []
    for label, num, note in budget:
        rx = _marker_regex(label)
        try:
            corpus = float(re.findall(r"[\d.]+", num)[0])
        except (IndexError, ValueError):
            continue
        if not rx:
            continue
        n = len(rx.findall(text))
        yours = round(n * 1000 / words, 2)
        # Over = more than twice the corpus rate and used more than once; that is
        # the "reads as machine-assembled" zone the phrase bank warns about.
        status = "over" if (n >= 2 and yours > max(corpus * 2, 0.3)) else ("ok" if n else "unused")
        rows.append({"marker": label, "count": n, "yours_per_k": yours,
                     "corpus_per_k": corpus, "note": note, "status": status})
    return rows


_STOP_OPENERS = {"the", "a", "an", "this", "these", "it", "in", "of", "for", "to", "and", "as"}


def recurring_openers(sentences: list[tuple[str, str]], min_count: int = 2) -> list[dict]:
    """Three-word sentence openers used at least `min_count` times — the frames
    the writer reaches for by habit, whether or not the pack lists them."""
    counts: Counter = Counter()
    example: dict[str, tuple[str, str]] = {}
    for sent, sample in sentences:
        toks = re.findall(r"[A-Za-z][A-Za-z'\-]*|,", sent)[:3]
        if len(toks) < 3:
            continue
        key = " ".join(toks).replace(" ,", ",")
        if all(t.lower() in _STOP_OPENERS or t == "," for t in toks):
            continue
        counts[key.lower()] += 1
        example.setdefault(key.lower(), (key, sent, sample))
    out = []
    for k, n in counts.most_common(40):
        if n < min_count:
            break
        disp, sent, sample = example[k]
        out.append({"opener": disp, "count": n, "example": sent, "sample": sample})
    return out


# ── Build / cache ─────────────────────────────────────────────────────────────

def _samples(style_dir: Path) -> list[Path]:
    if not style_dir.is_dir():
        return []
    return sorted(
        (f for f in style_dir.iterdir()
         if f.is_file() and f.suffix.lower() in (".md", ".txt")
         and not f.name.startswith((".", "._"))),
        key=lambda f: f.name,
    )


def _fingerprint(style_dir: Path, skill: str) -> str:
    h = hashlib.sha1(f"v{VERSION}:{skill}".encode())
    for f in _samples(style_dir):
        st = f.stat()
        h.update(f"{f.name}:{st.st_mtime_ns}:{st.st_size};".encode())
    pb = skill_dir(skill) / "references" / "phrase-bank.md"
    if pb.is_file():
        h.update(f"pb:{pb.stat().st_mtime_ns}".encode())
    hidden = style_dir / HIDDEN_FILE
    if hidden.is_file():
        h.update(f"hid:{hidden.stat().st_mtime_ns}".encode())
    return h.hexdigest()


def sentence_id(text: str) -> str:
    return hashlib.sha1(re.sub(r"\s+", " ", text.strip().lower()).encode()).hexdigest()[:12]


def _load_hidden(style_dir: Path) -> set[str]:
    try:
        return set(json.loads((style_dir / HIDDEN_FILE).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def build(style_dir: Path, skill: str = DEFAULT_SKILL) -> dict:
    """Mine every sample and return the bank (also written to the cache file)."""
    frames, cards, budget = load_frames(skill)
    hidden = _load_hidden(style_dir)
    order = {(c["sec"], c["move"]): i for i, c in enumerate(cards)}
    patterns_by_move = {(c["sec"], c["move"]): c["patterns"] for c in cards}

    moves: dict[tuple[str, str], list[dict]] = {}
    all_sentences: list[tuple[str, str]] = []
    samples_meta, full_text = [], []
    matched = 0
    for f in _samples(style_dir):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        sents = split_sentences(text)
        full_text.append(text)
        n_match = 0
        for s in sents:
            all_sentences.append((s, f.stem))
            hit = match_sentence(s, frames) if frames else None
            if not hit:
                continue
            frame, parts = hit
            sid = sentence_id(s)
            if sid in hidden:
                continue
            moves.setdefault((frame.sec, frame.move), []).append({
                "id": sid, "text": s, "sample": f.stem,
                "pattern": frame.pattern, "parts": parts,
            })
            n_match += 1
        matched += n_match
        samples_meta.append({"id": f.stem, "words": word_count(text),
                             "sentences": len(sents), "matched": n_match})

    joined = "\n\n".join(full_text)
    total_words = word_count(joined)
    bank = {
        "version": VERSION,
        "skill": skill,
        "fingerprint": _fingerprint(style_dir, skill),
        "built_at": time.time(),
        "samples": samples_meta,
        "stats": {
            "words": total_words,
            "sentences": len(all_sentences),
            "matched": matched,
            "mean_sentence_words": round(
                sum(word_count(s) for s, _ in all_sentences) / max(len(all_sentences), 1), 1),
            "hidden": len(hidden),
        },
        "connectives": connective_rates(joined, budget) if joined.strip() else [],
        "moves": [
            {"sec": sec, "move": move, "patterns": patterns_by_move.get((sec, move), []),
             "yours": items}
            for (sec, move), items in sorted(moves.items(), key=lambda kv: order.get(kv[0], 999))
        ],
        "openers": recurring_openers(all_sentences),
    }
    try:
        style_dir.mkdir(parents=True, exist_ok=True)
        (style_dir / BANK_FILE).write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return bank


def load(style_dir: Path, skill: str = DEFAULT_SKILL, force: bool = False) -> dict:
    """The cached bank, rebuilt first if any sample (or the pack) changed."""
    if not force:
        try:
            bank = json.loads((style_dir / BANK_FILE).read_text(encoding="utf-8"))
            if bank.get("fingerprint") == _fingerprint(style_dir, skill):
                return bank
        except (OSError, ValueError):
            pass
    try:
        return build(style_dir, skill)
    except Exception as e:                   # never take a page down over this
        return {"version": VERSION, "skill": skill, "error": f"{type(e).__name__}: {e}",
                "samples": [], "stats": {}, "connectives": [], "moves": [], "openers": []}


def set_hidden(style_dir: Path, sentence_ids: list[str], hidden: bool = True) -> int:
    """Hide (or restore) personal exemplars that were matched to the wrong move."""
    cur = _load_hidden(style_dir)
    cur = (cur | set(sentence_ids)) if hidden else (cur - set(sentence_ids))
    style_dir.mkdir(parents=True, exist_ok=True)
    (style_dir / HIDDEN_FILE).write_text(json.dumps(sorted(cur)), encoding="utf-8")
    return len(cur)


def clear_hidden(style_dir: Path) -> None:
    (style_dir / HIDDEN_FILE).unlink(missing_ok=True)


# ── Views for consumers ───────────────────────────────────────────────────────

def section_bank_title(section: str | None) -> str | None:
    spec = SECTION_MAP.get(section or "")
    return spec["bank"] if spec else None


def moves_for_section(bank: dict, section: str | None) -> list[dict]:
    """The user's moves for a writing section, plus the general logical moves."""
    title = section_bank_title(section)
    out = []
    for mv in bank.get("moves", []):
        if mv["sec"].startswith("1.") or (title and mv["sec"].lower() == title.lower()):
            out.append(mv)
    return out


def brief_slice(bank: dict, section: str | None, mode: str = "draft",
                budget_chars: int = 2400) -> str:
    """Markdown for the writing brief: the user's own sentences for this
    section's moves, and the connectives they already over-use.

    Unlike the corpus exemplars (stripped from prompts because a local model
    copies them), these are the user's own sentences — echoing their rhythm is
    the point. They are still framed as patterns, not text to paste.
    """
    if not bank or not bank.get("moves"):
        return ""
    lines: list[str] = []
    total = 0
    picked = moves_for_section(bank, section)
    # Section-specific moves first, then the general ones.
    picked.sort(key=lambda mv: mv["sec"].startswith("1."))
    for mv in picked:
        examples = mv["yours"][:2]
        if not examples:
            continue
        block = [f"- **{mv['move']}** — e.g. " + " / ".join(f"\"{e['text']}\"" for e in examples)]
        size = sum(len(b) for b in block)
        if total + size > budget_chars:
            continue
        lines.extend(block)
        total += size
    over = [c for c in bank.get("connectives", []) if c.get("status") == "over"]
    if over:
        lines.append(
            "- Connectives these samples already over-use (relative to the corpus "
            "budget) — do not add more: "
            + ", ".join(f"{c['marker']} ({c['yours_per_k']}/1k vs {c['corpus_per_k']})"
                        for c in over[:6])
        )
    if not lines:
        return ""
    head = ("## The author's own phrasing (mined from their style samples)\n\n"
            "These sentences are the author's own. When a sentence in your draft has to "
            "perform one of these moves, prefer the author's frame over a generic one: "
            "reuse the shape and the connective, never the content.\n\n")
    return head + "\n".join(lines)
