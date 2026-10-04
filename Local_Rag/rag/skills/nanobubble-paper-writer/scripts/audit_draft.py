#!/usr/bin/env python3
"""Audit a manuscript draft against the reference-corpus register profile.

CLI:
    python3 audit_draft.py draft.md [draft2.txt ...]
    python3 audit_draft.py --section methods draft.md
    python3 audit_draft.py --json --section results draft.md

Library:
    from audit_draft import audit_text
    report = audit_text(open("draft.md").read(), section="results")   # -> dict

Targets come from ~76,000 words of published prose in the corpus described in
references/corpus.md. Rates are per 1,000 words. Every flag is a prompt to look,
not an automatic defect: a rate outside range means "justify this", not "delete it".

Two known limits. Citation counting is tuned to bracketed styles ([12], [3,4]) and
author-date; ACS-style superscripts and reference-manager field codes are not
detected, and the report says so when it finds none. And the paragraph-opener
listing cannot be scored automatically: read the openers in order and judge
whether they tell the section's argument.

Stdlib only. No third-party imports, by design — this runs anywhere.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import unicodedata

# ── Targets ───────────────────────────────────────────────────────────────────
# (label, regex, low, high) — rates per 1,000 words; None = unbounded.
GLOBAL: list[tuple[str, str, float | None, float | None]] = [
    ("However",                       r"\bhowever\b",                                 0.6, 2.6),
    ("Thus/Therefore/Hence",          r"\b(thus|therefore|hence)\b",                  0.8, 3.6),
    ("Moreover",                      r"\bmoreover\b",                                0.0, 0.7),
    ("Furthermore",                   r"\bfurthermore\b",                             0.0, 0.7),
    ("Additionally",                  r"\badditionally\b",                            0.0, 0.10),
    ("Notably",                       r"\bnotably\b",                                 0.0, 0.12),
    ("Importantly",                   r"\bimportantly\b",                             0.0, 0.10),
    ("It is worth/important to note", r"it (is|should be) (worth|important to) (not|ment)", 0.0, 0.10),
    ("Interestingly",                 r"\binterestingly\b",                           0.0, 0.30),
    ("em dash",                       r"—",                                      0.0, 0.15),
    ("semicolon",                     r";",                                           0.2, 2.0),
    ("may/might/could",               r"\b(may|might|could)\b",                       1.0, 4.0),
    ("suggest*",                      r"\bsuggest",                                   0.2, 1.8),
    ("indicat*",                      r"\bindicat",                                   0.2, 1.6),
    ("demonstrat*",                   r"\bdemonstrat",                                0.0, 0.9),
    ("confirm*",                      r"\bconfirm",                                   0.0, 0.8),
    ("we/our",                        r"\b(we|our)\b",                                1.0, 8.0),
    ("was/were + participle",         r"\bw(as|ere)\s+\w+ed\b",                       1.0, None),
    ("significant(ly)",               r"\bsignificant",                               0.0, 1.3),
    ("crucial/critical/essential",    r"\b(crucial|critical|essential)\b",            0.0, 1.0),
    ("novel",                         r"\bnovel\b",                                   0.0, 0.25),
]

HARD_PATTERNS = {
    "banned vocabulary": r"\b(robust|delve|delving|realm|landscape|tapestry|testament|showcase|showcasing|multifaceted|intricate|meticulous|pivotal|underscore|underscores|underscoring|holistic|seamless|myriad|plethora|burgeoning|utilize|utilizing|elucidate|leverage|leveraging|groundbreaking|cutting-edge|transformative|paradigm shift)\b",
    "vague attribution": r"\b(studies (have )?show|research suggests|experts (believe|agree)|it is widely (accepted|believed|known)|many researchers)\b",
    "participial tail": r",\s+(highlighting|underscoring|reflecting|showcasing|emphasizing|demonstrating|illustrating|revealing|providing|offering)\b",
    "false contrast": r"\b(not (just|merely|simply|only) [^.;]{0,60}?(\bbut\b|,\s*(it|they|this|these|that)\s+\w+))",
    "throat-clearing opener": r"(in recent years|in today's|with the advent of|when it comes to|at its core|it is well known that)",
}

SECTION_TARGETS = {
    "intro":      {"citations [n]": (4.5, 10.0), "passive": (1.0, 5.0),   "however": (0.8, 3.0)},
    "methods":    {"citations [n]": (1.5,  7.0), "passive": (15.0, None), "however": (0.0, 0.6)},
    "results":    {"citations [n]": (2.5,  9.0), "passive": (1.0, 5.0),   "fig/table refs": (4.0, 22.0)},
    "discussion": {"citations [n]": (2.5,  9.0), "passive": (1.0, 5.0),   "however": (0.8, 3.0)},
    "conclusion": {"citations [n]": (1.0,  6.0), "passive": (0.5, 5.0),   "however": (0.8, 4.0)},
    "abstract":   {"citations [n]": (0.0,  0.5), "passive": (3.0, 12.0)},
}
EXTRA = {
    "citations [n]":  r"\[\d|\(\d{4}[a-z]?\)",
    "passive":        r"\bw(as|ere)\s+\w+ed\b",
    "fig/table refs": r"\b(Fig\.|Figure|Table|Fig )",
    "however":        r"\bhowever\b",
}

# Corpus reference values, carried in the report so a UI can show them.
CORPUS = {
    "sentence_median": 23, "sentence_iqr": [17, 31], "sentence_p90": 40,
    "pct_under_15": 17, "pct_over_30": 26,
    "paragraph_median_words": 76, "paragraph_median_sentences": 4,
}

ABBR = (r"(?<!\bet al)(?<!\bFig)(?<!\bEq)(?<!\bRef)(?<!\be\.g)(?<!\bi\.e)"
        r"(?<!\bcf)(?<!\bvs)(?<!\bapprox)(?<!\bca)(?<!\bNo)")
SPLIT = re.compile(ABBR + r"(?<=[.!?])[\"')\]]?\s+(?=[A-Z(\"'])")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SPLIT.split(text) if len(s.split()) >= 3]


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.split()) >= 15]


def _verdict(value: float, low: float | None, high: float | None) -> str:
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "ok"


def audit_text(text: str, section: str | None = None) -> dict:
    """Analyse `text` and return a JSON-serializable report.

    Keys: ok, words, sentences, paragraphs, sentence_length, paragraph_length,
    markers, section (optional), hard_flags, openers, corpus, summary.
    """
    text = unicodedata.normalize("NFKC", text or "")
    words = len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", text))
    if words < 80:
        return {"ok": False, "words": words,
                "error": f"too short to audit ({words} words; need 80+)"}

    S, P = sentences(text), paragraphs(text)
    L = [len(s.split()) for s in S] or [0]
    PL = [len(p.split()) for p in P]

    q = statistics.quantiles(L, n=4) if len(L) > 3 else [L[0], statistics.median(L), L[0]]
    p90 = statistics.quantiles(L, n=10)[8] if len(L) > 9 else max(L)
    pct_short = round(100 * sum(1 for x in L if x < 15) / len(L))
    pct_long = round(100 * sum(1 for x in L if x > 30) / len(L))

    sl_notes = []
    if pct_short < 8:
        sl_notes.append("Too few short sentences — the rhythm is uniform. Break some long ones.")
    if pct_long < 12:
        sl_notes.append("Too few long sentences — the argument may be under-subordinated.")
    if q[2] - q[0] < 10:
        sl_notes.append("Sentence lengths cluster too tightly (IQR < 10). "
                        "This is the strongest single tell.")

    markers = []
    for label, pat, lo, hi in GLOBAL:
        n = len(re.findall(pat, text, re.I))
        rate = round(1000 * n / words, 2)
        markers.append({"label": label, "n": n, "rate": rate,
                        "low": lo, "high": hi, "verdict": _verdict(rate, lo, hi)})

    sec_block = None
    if section in SECTION_TARGETS:
        rows, note = [], None
        for label, (lo, hi) in SECTION_TARGETS[section].items():
            n = len(re.findall(EXTRA[label], text, re.I))
            rate = round(1000 * n / words, 2)
            rows.append({"label": label, "n": n, "rate": rate,
                         "low": lo, "high": hi, "verdict": _verdict(rate, lo, hi)})
            if label == "citations [n]" and n == 0 and lo > 0:
                note = ("No bracketed or author-date citations found. If this draft uses "
                        "ACS superscripts or reference-manager field codes, ignore that row.")
        sec_block = {"name": section, "rows": rows, "note": note}

    hard = []
    for label, pat in HARD_PATTERNS.items():
        for m in re.finditer(pat, text, re.I):
            a, b = max(0, m.start() - 45), min(len(text), m.end() + 45)
            hard.append({"kind": label, "match": m.group(0),
                         "context": re.sub(r"\s+", " ", text[a:b]).strip()})

    openers = []
    for i, p in enumerate(P, 1):
        first = sentences(p)
        openers.append({"n": i, "text": (first[0] if first else p)[:160]})

    off = sum(1 for m in markers if m["verdict"] != "ok")
    if sec_block:
        off += sum(1 for r in sec_block["rows"] if r["verdict"] != "ok")
    summary = (f"{words} words · {len(S)} sentences · {len(P)} paragraphs · "
               f"{len(hard)} hard flag(s) · {off} marker(s) outside range")

    return {
        "ok": True,
        "words": words, "sentences": len(S), "paragraphs": len(P),
        "sentence_length": {
            "median": round(statistics.median(L)), "p25": round(q[0]), "p75": round(q[2]),
            "p90": round(p90), "pct_under_15": pct_short, "pct_over_30": pct_long,
            "notes": sl_notes,
        },
        "paragraph_length": {
            "median": round(statistics.median(PL)) if PL else 0,
            "max": max(PL) if PL else 0,
            "over_180": sum(1 for x in PL if x > 180),
        },
        "markers": markers,
        "section": sec_block,
        "hard_flags": hard,
        "openers": openers,
        "corpus": CORPUS,
        "summary": summary,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print(path: str, r: dict) -> None:
    if not r.get("ok"):
        print(f"{path}: {r.get('error')}")
        return
    print(f"\n{'=' * 74}\n{path}   {r['summary']}\n{'=' * 74}")

    sl, c = r["sentence_length"], r["corpus"]
    print(f"\n-- SENTENCE LENGTH --   corpus: med {c['sentence_median']}, "
          f"IQR {c['sentence_iqr'][0]}-{c['sentence_iqr'][1]}, p90 {c['sentence_p90']}")
    print(f"   median {sl['median']}   IQR {sl['p25']}-{sl['p75']}   p90 {sl['p90']}   "
          f"under-15w {sl['pct_under_15']}% (corpus {c['pct_under_15']}%)   "
          f"over-30w {sl['pct_over_30']}% (corpus {c['pct_over_30']}%)")
    for n in sl["notes"]:
        print(f"   FLAG: {n}")

    pl = r["paragraph_length"]
    print(f"\n-- PARAGRAPH LENGTH --  corpus: med {c['paragraph_median_words']} words / "
          f"{c['paragraph_median_sentences']} sentences")
    print(f"   median {pl['median']} words   max {pl['max']}   over 180w: {pl['over_180']}")

    print("\n-- MARKER RATES (per 1,000 words) --")
    for m in r["markers"]:
        if m["verdict"] == "ok" and not m["n"]:
            continue
        rng = f"{m['low'] if m['low'] is not None else '-'}-{m['high'] if m['high'] is not None else '-'}"
        print(f"   [{m['verdict']:<4}] {m['label']:32s} n={m['n']:4d}  {m['rate']:6.2f}   target {rng}")

    if r.get("section"):
        s = r["section"]
        print(f"\n-- SECTION PROFILE: {s['name']} --")
        for row in s["rows"]:
            rng = f"{row['low']}-{row['high'] if row['high'] is not None else '-'}"
            print(f"   [{row['verdict']:<4}] {row['label']:20s} n={row['n']:4d}  "
                  f"{row['rate']:6.2f}   target {rng}")
        if s.get("note"):
            print(f"        ({s['note']})")

    print("\n-- HARD FLAGS (each hit must be removed or justified) --")
    if r["hard_flags"]:
        for f in r["hard_flags"]:
            print(f"   {f['kind']:22s} ...{f['context']}...")
    else:
        print("   none")

    print("\n-- PARAGRAPH OPENERS (read in order: do they tell the argument?) --")
    for o in r["openers"]:
        print(f"   {o['n']:2d}. {o['text'][:110]}")


def main(argv: list[str]) -> int:
    args, section, as_json = list(argv), None, False
    if "--section" in args:
        i = args.index("--section"); section = args[i + 1]; del args[i:i + 2]
    if "--json" in args:
        as_json = True; args.remove("--json")
    if not args:
        print(__doc__)
        return 1
    for path in args:
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError as e:
            print(f"{path}: {e}")
            continue
        report = audit_text(text, section)
        if as_json:
            print(json.dumps(report, indent=2))
        else:
            _print(path, report)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except BrokenPipeError:      # piping into head/less
        sys.stderr.close()
        raise SystemExit(0)
