"""
Progressive skill loader.

A "skill" here is a folder of markdown following the Claude skill layout:

    skills/<skill-name>/
        SKILL.md                 # frontmatter (name, description) + overview
        references/*.md          # the detailed guides
        scripts/*.py             # optional tooling (e.g. audit_draft.py)

The whole nanobubble-paper-writer skill is ~33k tokens of markdown, which does
not fit in RAG_GEN_NUM_CTX (32768) — let alone alongside retrieved excerpts.
So nothing here ever loads a skill whole. Instead `build_writing_brief()`
assembles a compact brief from named slices, cheapest-and-most-useful first,
under an explicit character budget: the measured connective budget, the
section's corpus anchors, the phrase-bank moves for that section (patterns
only, exemplars dropped unless budget allows), and the banned-vocabulary list.

That keeps one source of truth on disk — drop in an updated skill folder and
the prompts change with it — while sending the model ~3-5k tokens instead of 33k.

Stdlib only. Import is safe even when no skill is installed: every function
degrades to empty output rather than raising.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.resolve()
DEFAULT_SKILL = "nanobubble-paper-writer"

# Roughly 4 chars per token. The brief targets ~3.5k tokens, leaving the bulk of
# a 32k window for excerpts, style samples, the user's draft, and the answer.
DEFAULT_BUDGET_CHARS = 14_000

# Writing sections the app exposes → the phrase-bank chapter and the reference
# guide that cover them.
SECTION_MAP: dict[str, dict[str, str]] = {
    "intro":      {"guide": "introduction.md", "bank": "2. Introduction",  "label": "Introduction"},
    "methods":    {"guide": "methods.md",      "bank": "3. Methods",       "label": "Methods"},
    "results":    {"guide": "results.md",      "bank": "4. Results",       "label": "Results"},
    "discussion": {"guide": "discussion.md",   "bank": "5. Discussion",    "label": "Discussion"},
    "conclusion": {"guide": "conclusions.md",  "bank": "7. Conclusions",   "label": "Conclusions"},
    "abstract":   {"guide": "conclusions.md",  "bank": "8. Abstract",      "label": "Abstract"},
    "reviewer":   {"guide": "journal-conventions.md",
                   "bank": "9. Response to reviewers", "label": "Response to reviewers"},
}
SECTIONS = list(SECTION_MAP)


# ── Filesystem + parsing ──────────────────────────────────────────────────────

def skill_dir(skill: str = DEFAULT_SKILL) -> Path:
    return SKILLS_DIR / skill


def is_installed(skill: str = DEFAULT_SKILL) -> bool:
    return (skill_dir(skill) / "SKILL.md").is_file()


def phrasebank_html(skill: str = DEFAULT_SKILL) -> Path | None:
    """Path to the pre-built browsable phrase-bank page, if it exists.

    Build artifact, not a live view — regenerate with
    `python3 skills/build_phrasebank_html.py` after editing phrase-bank.md.
    """
    p = skill_dir(skill) / "phrase-bank.html"
    return p if p.is_file() else None


def list_skills() -> list[dict]:
    """Every installed skill, with its frontmatter name and description."""
    out = []
    if not SKILLS_DIR.is_dir():
        return out
    for d in sorted(SKILLS_DIR.iterdir()):
        if not (d / "SKILL.md").is_file():
            continue
        meta = _frontmatter(_read(d.name, "SKILL.md"))
        out.append({
            "id": d.name,
            "name": meta.get("name", d.name),
            "description": meta.get("description", ""),
            "sections": SECTIONS,
            "has_phrasebank": phrasebank_html(d.name) is not None,
        })
    return out


@lru_cache(maxsize=64)
def _read(skill: str, relpath: str) -> str:
    p = skill_dir(skill) / relpath
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _frontmatter(md: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", md, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).split("\n"):
        if ":" in line and not line.startswith((" ", "\t", "-")):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _blocks(md: str, level: int = 2) -> dict[str, str]:
    """Split markdown into {heading_text: body} at the given heading level."""
    hashes = "#" * level
    pat = re.compile(rf"^{hashes} (?!#)(.+?)\s*$", re.M)
    marks = list(pat.finditer(md))
    out: dict[str, str] = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(md)
        out[m.group(1).strip()] = md[m.end():end].strip()
    return out


def _find(blocks: dict[str, str], prefix: str) -> str:
    """Body of the first block whose heading starts with `prefix` (case-insensitive)."""
    p = prefix.lower()
    for k, v in blocks.items():
        if k.lower().startswith(p):
            return v
    return ""


# ── Slice extraction ──────────────────────────────────────────────────────────

_EXEMPLAR = re.compile(r"^>\s*\".*$", re.M)
_BLANKS = re.compile(r"\n{3,}")


def _strip_exemplars(md: str) -> str:
    """Drop the `> "quoted sentence" — Source` lines, keeping patterns and notes.

    Exemplars are the bulk of the phrase bank by volume and the least useful part
    for a local model, which imitates a quoted sentence rather than abstracting
    from it. Patterns carry the reusable shape at a fraction of the cost.
    """
    return _BLANKS.sub("\n\n", _EXEMPLAR.sub("", md)).strip()


def _trim(md: str, limit: int) -> str:
    md = re.sub(r"\n-{3,}\s*$", "", md).rstrip()   # drop a trailing horizontal rule
    if len(md) <= limit:
        return md
    cut = md[:limit]
    nl = cut.rfind("\n")
    return (cut[:nl] if nl > limit * 0.6 else cut).rstrip() + "\n…"


def connective_budget(skill: str = DEFAULT_SKILL) -> str:
    body = _find(_blocks(_read(skill, "references/phrase-bank.md")), "0. the connective budget")
    return _trim(body, 2200)


def measured_targets(skill: str = DEFAULT_SKILL) -> str:
    return _trim(_find(_blocks(_read(skill, "references/house-style.md")), "measured targets"), 1800)


def banned_vocabulary(skill: str = DEFAULT_SKILL) -> str:
    b = _blocks(_read(skill, "references/ai-tells.md"))
    return _trim(_find(b, "2. vocabulary: banned outright"), 1300)


def predelivery_scan(skill: str = DEFAULT_SKILL) -> str:
    return _trim(_find(_blocks(_read(skill, "references/ai-tells.md")), "9. pre-delivery scan"), 2600)


def sentence_craft(skill: str = DEFAULT_SKILL) -> str:
    b = _blocks(_read(skill, "references/paragraph-and-sentence.md"))
    para = _trim(_find(b, "1. the paragraph"), 1100)
    sent = _trim(_find(b, "2. the sentence"), 1300)
    return (para + "\n\n" + sent).strip()


def section_anchors(section: str, skill: str = DEFAULT_SKILL) -> str:
    spec = SECTION_MAP.get(section)
    if not spec:
        return ""
    return _trim(_find(_blocks(_read(skill, f"references/{spec['guide']}")), "corpus anchors"), 1800)


def section_moves(section: str, skill: str = DEFAULT_SKILL, exemplars: bool = False) -> str:
    spec = SECTION_MAP.get(section)
    if not spec:
        return ""
    body = _find(_blocks(_read(skill, "references/phrase-bank.md")), spec["bank"].lower())
    if not body:
        return ""
    return _trim(body if exemplars else _strip_exemplars(body), 3400)


def general_moves(skill: str = DEFAULT_SKILL, exemplars: bool = False) -> str:
    body = _find(_blocks(_read(skill, "references/phrase-bank.md")), "1. general logical moves")
    if not body:
        return ""
    return _trim(body if exemplars else _strip_exemplars(body), 2200)


def house_signature(skill: str = DEFAULT_SKILL) -> str:
    b = _blocks(_read(skill, "references/house-style.md"))
    return _trim(_strip_exemplars(_find(b, "signature features")), 2400)


def domain_primer(skill: str = DEFAULT_SKILL) -> str:
    b = _blocks(_read(skill, "references/nanobubble-domain.md"))
    parts = [_find(b, "2. the stability paradox"), _find(b, "3. stability mechanisms")]
    return _trim("\n\n".join(p for p in parts if p), 2000)


# ── Brief assembly ────────────────────────────────────────────────────────────

def build_writing_brief(
    section: str | None = None,
    mode: str = "draft",
    skill: str = DEFAULT_SKILL,
    budget_chars: int = DEFAULT_BUDGET_CHARS,
    include_domain: bool = False,
) -> str:
    """Assemble the writing brief injected into the Style Writer system prompt.

    `mode`: "draft" (writing new prose) or "revise" (reworking an existing draft;
    swaps the phrase-bank weighting for the mechanical pre-delivery scan).

    Slices are added highest-value-first and stop at `budget_chars`, so a smaller
    budget degrades gracefully instead of truncating mid-table.
    """
    if not is_installed(skill):
        return ""

    section = section if section in SECTION_MAP else None
    label = SECTION_MAP[section]["label"] if section else None

    # (title, text) in priority order — earlier survives a tight budget.
    slices: list[tuple[str, str]] = [
        ("Measured register targets (hit these; they are counts from published prose, not style advice)",
         measured_targets(skill)),
        ("Connective budget", connective_budget(skill)),
    ]
    if section:
        slices.append((f"{label}: measured corpus anchors", section_anchors(section, skill)))

    if mode == "revise":
        slices.append(("Pre-delivery scan — run every step on the draft", predelivery_scan(skill)))
        slices.append(("Banned vocabulary", banned_vocabulary(skill)))
        if section:
            slices.append((f"{label}: rhetorical moves available", section_moves(section, skill)))
    else:
        if section:
            slices.append((f"{label}: rhetorical moves and sentence frames", section_moves(section, skill)))
        slices.append(("General logical moves", general_moves(skill)))
        slices.append(("Banned vocabulary", banned_vocabulary(skill)))

    slices.append(("Paragraph and sentence craft", sentence_craft(skill)))
    slices.append(("Signature features of the house register", house_signature(skill)))
    if include_domain:
        slices.append(("Domain primer: what is settled and what is disputed", domain_primer(skill)))

    head = (
        "# Writing standard (from the nanobubble-paper-writer skill)\n\n"
        "Every number below was measured from ~76,000 words of published prose in "
        "this field. They are targets, not suggestions. Where a rate is given per "
        "1,000 words, a draft that exceeds it reads as machine-written even when "
        "each sentence is individually defensible.\n"
    )

    parts, total = [], len(head)
    for title, text in slices:
        text = (text or "").strip()
        if not text:
            continue
        block = f"## {title}\n\n{text}"
        if total + len(block) > budget_chars:
            continue          # skip this slice, try the next (they get smaller)
        parts.append(block)
        total += len(block) + 2

    if not parts:
        return ""
    return head + "\n\n" + "\n\n".join(parts)


def brief_stats(section: str | None = None, mode: str = "draft",
                skill: str = DEFAULT_SKILL) -> dict:
    """Size report for a brief — used by tests and the /skills status endpoint."""
    text = build_writing_brief(section, mode, skill)
    return {
        "skill": skill,
        "section": section,
        "mode": mode,
        "chars": len(text),
        "approx_tokens": len(text) // 4,
        "installed": is_installed(skill),
    }
