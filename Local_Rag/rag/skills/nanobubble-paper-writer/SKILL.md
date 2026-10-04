---
name: nanobubble-paper-writer
description: Draft, revise, or polish any part of a scientific paper on nanobubbles (surface or bulk), nanobubble stability, interfacial gas states, or adjacent colloid/interface science, section by section (Introduction, Methods, Results, Discussion or combined Results-and-discussion, Conclusions, Abstract, Highlights, Title), in publication-grade prose free of AI-writing tells, plus response-to-reviewer letters. Use WHENEVER the user is writing, rewriting, tightening, or seeking feedback on a manuscript, preprint, thesis chapter, journal submission, or referee response in this domain, even without the word 'skill' or 'paper', including when they paste raw notes, data, bullets, or a rough draft and ask to 'write this up', 'make it publishable', 'sound less AI', or 'academic tone'. Also trigger for single sections ('write my methods', 'polish the discussion'), for turning results or figures into narrative, and for general scientific-paper writing. Craft rules generalize; the domain primer is nanobubble-specific.
---

# Nanobubble Paper Writer

This skill writes at the register of the strongest work in the nanobubble and interfacial-physics
literature. That register is not described from memory here: it was **measured** from a twenty-document
reference corpus — roughly 76,000 words of published prose across fifteen research papers in
*J. Colloid Interface Sci.*, *Langmuir*, *Chem. Rev.*, *Adv. Colloid Interface Sci.*,
*Int. J. Heat Mass Transf.*, *Colloids Surf. A*, *Curr. Opin. Colloid Interface Sci.*, and arXiv,
plus one full referee correspondence and five craft sources. `references/corpus.md` lists every
source and records the measurement. Every budget, ratio, and attested exemplar in this skill traces
back to it.

Two things outrank everything else and must never be traded away for style:

1. **Scientific accuracy.** No invented facts, numbers, mechanisms, citations, instruments, or
   protocol details. Ever.
2. **Coherence.** Every sentence follows from the last; every paragraph has exactly one job; every
   section fulfills its contract with the reader.

A beautifully phrased paper that misstates the science, or a factually sound one that wanders, is a
failure.

## How to use this skill

1. Read `references/house-style.md` **first, always**, before writing a single sentence. It carries
   the measured register targets and the cohesion rules, and it applies to every section equally.
2. Read `references/paragraph-and-sentence.md` before drafting any continuous prose. It is the
   craft layer: one idea per paragraph, the Context–Content–Conclusion structure, given-new
   chaining, the twelve precision rules, and Box on parsimony and selective worry. Most drafts that
   "read wrong" fail here rather than at the level of word choice.
3. Identify which section(s) the user needs and read the matching guide. Each opens with a
   **Corpus anchors** table giving that section's measured citation density, passive rate, hedging
   rate, and sentence length, so the draft can be checked against real numbers rather than instinct:
   - `references/introduction.md` — funnel structure, the seven moves, gap and aim.
   - `references/methods.md` — reproducibility standard, materials, instruments, controls, statistics.
   - `references/results.md` — figure-driven narrative, reporting numbers, tense discipline.
   - `references/discussion.md` — interpretation, mechanism, literature comparison, alternative
     explanations, limitations.
   - `references/conclusions.md` — closure without inflation; also covers Abstract and Title.
   - `references/journal-conventions.md` — JCIS/Elsevier formats: structured Hypothesis/Methods/
     Findings abstracts, Highlights, graphical abstracts, combined "Results and discussion"
     sections, experiment + simulation papers, and response-to-reviewer letters. Read whenever the
     target is a colloid/interface journal, the paper combines experiments with simulations, or the
     user is answering referees.
4. Keep `references/phrase-bank.md` open while drafting. It is organised by rhetorical move, and
   each move gives a reusable pattern plus verbatim exemplars from the corpus with their source and
   section. **The exemplars calibrate; they are never pasted into a manuscript.**
5. If the paper concerns nanobubbles or nearby topics, read `references/nanobubble-domain.md` for
   the physical background, standard symbols, live controversies, and canonical references.
6. Before delivering anything, run the mechanical scan at the end of `references/ai-tells.md`.
   Twelve steps, most of them literal string searches. It is not optional.
7. Where a shell is available, run the scan automatically instead of by hand:

   ```
   python3 scripts/audit_draft.py --section results draft.md
   ```

   It reports the draft's sentence-length distribution, paragraph lengths, every marker rate
   against its corpus target, section-specific citation/passive/figure-reference density, hard
   flags for banned vocabulary and vague attribution, and — most usefully — the opening sentence
   of every paragraph in order, so the section's argument can be read at a glance. Sections are
   `intro`, `methods`, `results`, `conclusion`, `abstract`; omit `--section` for a whole-manuscript
   pass. Treat every flag as a prompt to look, not an automatic defect.

When drafting a full paper, work section by section in a sensible order — usually Methods and
Results first, since they are constrained by what was actually done; then Discussion; then
Introduction; then Conclusions, Abstract, and Title last. Confirm the plan with the user before
writing everything in one pass.

## The measured targets, in brief

The full tables are in `house-style.md` and `phrase-bank.md` §0. The five that catch the most
problems:

- **Sentence length: median 23 words, but 17 % under 15 and 26 % over 30.** The *variance* is the
  target. Uniform sentence length is itself a tell, even when every sentence is correct.
- **Paragraph length: median 76 words, 4 sentences.** Past ~180 words, split.
- **Em dash: 4 occurrences in 76,000 words.** Effectively absent from this literature. The semicolon
  (0.97 per 1,000 words) does the work.
- **`Additionally`: 4 occurrences in 76,000 words. `Importantly`: 3. `It is worth noting`: 3.**
  Treat all three as banned; the corpus's guidance marker is `Note that`.
- **Zero occurrences of** *robust, delve, realm, landscape, tapestry, testament, showcase,
  multifaceted, intricate, meticulous.* Any of them in a draft is a defect.

## Three modes

**Draft mode.** The user supplies content (data, findings, protocol notes, bullet points, figures
described in words) and the skill supplies the prose. Structure and register come from this skill;
every fact comes from the user or from clearly attributed literature.

**Revise mode.** The user pastes an existing draft. Rework it for structure, voice, cohesion, and
phrasing **without altering or inventing scientific content**. If a claim looks wrong, unsupported,
or internally inconsistent, flag it in a note rather than silently "fixing" it. When removing AI
tells, name the patterns found so the user learns to spot them, and give the counts
("removed six filler `Moreover`s; eleven em dashes rewritten as semicolons or commas").

**Scaffold mode.** The user has an idea but not all the material. Produce a section skeleton with
the argumentative moves laid out and every missing fact marked with a visible placeholder
(`[VALUE: units]`, `[REF]`, `[INSTRUMENT MODEL]`, `[N = ?]`). Never fill a gap with something
plausible-looking.

## Inputs to gather first

Ask for missing essentials in **one short round**, not an interrogation. Adjust to the section
requested:

- The system studied (bulk or surface nanobubbles; gas species; liquid; substrate if surface).
- The central claim or headline result.
- What is new relative to prior work.
- For Methods: what was actually done — materials, instruments, settings, sample sizes, controls.
- For Results: the actual numbers, trends, and figures (described or summarized).
- References, or explicit permission to use placeholders.
- Target journal and citation style if known (default: numbered brackets `[n]`).

If the user wants text before they have all of this, switch to scaffold mode rather than inventing
content.

## Section contracts (one-line summaries; full guides in references/)

- **Introduction** funnels from broad context to a precise gap and an explicit aim. It promises.
- **Methods** lets a competent peer reproduce the work. It specifies.
- **Results** reports what was observed, quantitatively and in order, with minimal interpretation.
  It shows.
- **Discussion** interprets, mechanizes, compares with literature, confronts alternative
  explanations, and admits limits. It argues.
- **Conclusions** restates what was established, no more and no less, and points forward briefly.
  It settles.

Tense discipline across sections: what *was done and found* in this work is past tense; what *is
generally true*, what *a figure shows*, and what *the data indicate* is present tense; the
Introduction and Discussion mix the two as the logic requires. Never drift into a uniform
present-tense summary voice; that drift is itself an AI tell.

## Scientific accuracy guardrails (read this twice)

This skill writes prose; it does not supply facts. The user owns verification, and the skill must
make that easy and safe:

- **Never fabricate** citations, reference numbers, DOIs, author names, equation numbers, numerical
  values, instrument models, reagent grades, or statistical outputs. Insert a visible placeholder
  instead.
- **Never invent** mechanisms, results, or protocol steps the user did not provide. Every factual
  statement must trace to user-supplied material or to clearly attributed prior work.
- **Never paste a corpus exemplar into a manuscript.** The exemplars in `phrase-bank.md` are quoted
  from published papers by other authors and are there to calibrate rhythm and hedging strength.
  Take the shape; supply your own content. This is a hard rule, not a stylistic preference.
- The domain primer (`references/nanobubble-domain.md`) exists to make the prose fluent and the
  framing correct. Its facts and its reference list may be used, but any specific number or citation
  drawn from it must still appear on the verification list for the user to confirm against the
  original source.
- **Separate the settled from the conjectural.** In nanobubble science this is not optional: the
  stability of surface nanobubbles has a widely accepted explanation (contact-line pinning plus gas
  oversaturation), while the stability and even the existence of bulk nanobubbles remain actively
  disputed. Prose that asserts contested points as settled will be rejected by referees who know the
  field.
- **Keep numbers consistent** across sections: units, orders of magnitude, sample sizes, and figure
  references must agree everywhere they appear.
- **Append a verification list.** End every draft with "Please verify before submission:"
  enumerating each placeholder, each number, each citation, and any claim the user should confirm.
  Mandatory, not optional.

## Before you finish: quality checklist

Run this on every draft. Every box must be checkable:

- [ ] The section fulfills its contract (see one-liners above and the full guide).
- [ ] The section's measured anchors are met: citation density, passive rate, hedging rate, and
      sentence-length spread are in range for that section (tables in each guide).
- [ ] Register matches `house-style.md`: formal, measured, first-person-plural reasoning voice where
      apt, calibrated certainty throughout.
- [ ] Paragraph openers, read alone and in order, tell the section's argument.
- [ ] Given-new chaining holds; one idea per paragraph; every connective reflects a true logical
      relation.
- [ ] The twelve-step scan at the end of `ai-tells.md` has been run, not skimmed.
- [ ] Every symbol, term, and abbreviation defined at first use; consistent thereafter.
- [ ] Tense discipline correct for the section.
- [ ] Established results asserted, contested ones hedged, and the two never blurred.
- [ ] All numbers, units, and cross-references internally consistent.
- [ ] No fabricated content; no corpus exemplar reproduced; all placeholders visibly marked.
- [ ] Citations attached to the specific claims they support, in a consistent style.
- [ ] "Please verify before submission" list appended.

## Scope note

The register is tuned to experimental and theoretical physical chemistry and interfacial physics,
the home field of the nanobubble literature. The section contracts, cohesion rules, craft layer,
anti-tell catalogue, and accuracy guardrails transfer to any scientific field; vocabulary, citation
norms, and the balance of hedging should be adapted for biology, clinical, engineering, or
environmental venues. The domain primer is specific to nanobubbles and should simply be skipped for
other topics.

To extend the corpus with new papers and re-derive the numbers, follow the re-mining procedure at the
end of `references/corpus.md`.
