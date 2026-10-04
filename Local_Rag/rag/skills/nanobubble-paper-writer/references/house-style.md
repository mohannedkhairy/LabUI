# House Style: Register, Cohesion, and the Anti-AI-Tell Catalogue

Read this before writing any section. It applies to the whole paper equally.

Companion files: `corpus.md` (what was measured and from what), `phrase-bank.md` (attested frames
per rhetorical move, with the connective budget), `paragraph-and-sentence.md` (paragraph structure,
given-new chaining, the twelve precision rules), `ai-tells.md` (the full anti-tell catalogue and the
mechanical pre-delivery scan).

## Measured targets

From ~76,000 words of published prose in the reference corpus. Hit these; do not merely approximate
them.

| Property | Corpus value | What it means for a draft |
|---|---|---|
| Sentence length | median **23** words; IQR 17–31; p90 = 40 | 17 % of sentences under 15 words, 26 % over 30. **Variance is the target, not just the median** — uniform sentence length is itself a tell. |
| Paragraph length | median **76** words, **4** sentences; IQR 39–127 | Past ~180 words, split. |
| `we` / `our` | 3.16 / 1.12 per 1,000 words | First person plural is normal, not to be avoided. |
| `was`/`were` + participle | 4.29 per 1,000 words | Passive is the default in Methods and for observations. |
| Hedges vs. proof verbs | `may/might/could` 2.15; `suggest*` 0.91; `demonstrat*` 0.41; `confirm*` 0.36 | Hedges outnumber strong claims about two to one. |
| Semicolon vs. em dash | 0.97 vs. **0.05** per 1,000 words | The semicolon does the work; the em dash is effectively absent from this literature. |
| Sentence openers | ~21 % `The`, ~5 % `This`, <10 % connectives | Most sentences open on old information, not on a connective. |

## Why this matters

Reviewers and editors increasingly distrust prose that carries the fingerprints of machine writing, and in science that distrust is corrosive: it makes the reader doubt the rigor behind the words. A 2025 analysis of more than 15 million PubMed abstracts found a sharp post-2022 rise in a set of "style words" that now mark text as LLM-assisted. Helpfully, these tells are the same vague, unfalsifiable, hype-laden habits that good scientific writing already rejects, so removing them also makes the prose more precise. The goal is not camouflage; it is the genuine article.

## Register and voice

- **Reasoning voice.** Use first-person plural to walk the reader through inference and to report what was done ("we measured", "we therefore expect", "we note that"). Impersonal constructions are fine where they read more naturally ("the samples were stored at..."). Mix the two as strong experimental papers do; do not commit rigidly to all-passive or all-active.
- **Calibrated certainty.** Assert settled results plainly. Hedge open ones honestly ("may contribute", "cannot be ruled out", "the present data do not distinguish between..."). The calibration itself signals expertise. Never upgrade a hypothesis to a fact for rhetorical smoothness, and never soften an established fact into a hedge for false modesty.
- **Formality.** No contractions, no casualisms, no hype ("revolutionary", "groundbreaking", "remarkable" as filler), restrained adverbs. Precision beats emphasis: a number is more emphatic than an adjective.
- **Quantitative prose.** Prefer the measured value with its uncertainty and units over qualitative description. "The mean diameter decreased from 210 ± 15 nm to 145 ± 10 nm over 30 days" beats "the bubbles shrank considerably over time" in every section of the paper.
- **Sentence craft.** Build complex but controlled sentences: one main clause, with subordinate clauses carrying conditions and justifications ("since...", "owing to...", "provided that..."). Vary sentence length deliberately; a run of same-length sentences reads mechanical. A short declarative sentence after two long ones lands with force.

## Coherence and cohesion

- **Given-new chaining.** End a sentence on the concept the next sentence picks up, so the reader is handed from idea to idea without gaps. This is the single biggest driver of prose that "flows".
- **One function per paragraph.** A topic sentence orients; the rest elaborates and supplies evidence. If a paragraph does two jobs, split it.
- **Honest connectives.** Do not write "thus" or "it follows that" unless an inference genuinely follows; do not write "however" without a real contrast. Most sentences should connect through their content, with no connective at all.
- **Define before use.** Every symbol, variable, abbreviation, and piece of jargon is defined the first time it appears, then used consistently. Do not switch between synonyms for the same quantity ("diameter"/"size"/"dimension") once one is established.
- **Parallel structure for parallel content.** When comparing conditions or samples, keep the grammatical frame constant so the differences stand out.

## The anti-AI-tell catalogue (condensed; `ai-tells.md` is the authoritative full version, with the substitution table and the mechanical pre-delivery scan — read it before finalizing any draft)

### Vocabulary to cut entirely (figurative filler with no place in technical prose)

delve, dive into, navigate/navigating (figurative), landscape (figurative), realm, tapestry, unlock, unleash, harness, leverage (as a buzzword), bolster, foster (figurative), empower, endeavor, showcase, spotlight, shed light on, pave the way, underscore, testament, game-changing, cutting-edge, groundbreaking, transformative, revolutionary, seamless, vibrant, multifaceted, holistic, paradigm shift, ever-evolving, myriad, plethora, akin to, amidst, elucidate (prefer "explain", "identify", "determine"), utilize (prefer "use"), aforementioned, in the realm of, at the forefront, burgeoning, plays a vital/key/crucial role (name the role instead).

### Use only in the literal, technical sense, never as vague emphasis

- *crucial, pivotal, critical, vital, essential*: only when something is genuinely necessary and the sentence says why; otherwise delete.
- *robust*: only in its technical meaning (a robust estimator, robust to pH variation), never as generic praise.
- *significant*: reserve strictly for statistical significance with the test and p-value stated, or for a quantified effect; never as a synonym for "large" or "important". In a Results section this rule is absolute.
- *novel*: only when the sentence states precisely what is new.
- *comprehensive, intricate, meticulous*: prefer plain words, or better, describe the actual thing.
- *interestingly, curiously, notably, remarkably, importantly, surprisingly*: rationed under a whole-manuscript budget of about three, all varieties combined; each must sit on a genuinely surprising quantitative observation (a sign reversal, a five-fold disparity), never stacked, never in adjacent paragraphs. Both house corpora use them; the presubmission drafts overuse them, and the difference is exactly what this budget controls. Full rule in `ai-tells.md`.
- Intensifier inflation (*exceptional, remarkable, profound, dramatic, superior, striking*): replace with the measured comparison; two or three survivors per manuscript at most. Full rule in `ai-tells.md`.
- *dramatic/dramatically*: replace with the number.

### Constructions to avoid

- **The false contrast / negative parallelism**: "It is not just X, it is Y", "This is not merely X but Y", "Not because X, but because Y", "No X. No Y. Just Z." These mimic the shape of insight without its content.
- **Corporate tricolons**, especially alliterative ("fast, flexible, and future-proof"). One genuine list is fine; the rhythmic triple as a default rhythm is a tell.
- **Copula avoidance**: "serves as", "stands as", "acts as" (unless a real proxy relation), "featuring", "boasting", "representing a...". Use plain "is", "has", "shows".
- **Strings of -ing summary clauses**: "..., highlighting..., reflecting..., underscoring...". Rewrite as separate assertions or cut.
- **Vague attribution**: "studies show", "experts believe", "it is widely accepted", "research suggests". Every such claim carries a specific citation or it goes.
- **Throat-clearing openers**: "In recent years, there has been growing interest in...", "In today's rapidly evolving...", "When it comes to...", "At its core...", "It is worth noting that...", "It is important to note that...", "One of the most important...". Open with substance. ("In recent years" with a specific, cited development is acceptable; as a generic curtain-raiser it is not.)
- **Filler connectives**: "Moreover", "Furthermore", "Additionally", "In order to" used as padding. Reach for a connective only when it marks a real logical move, and never stack them.
- **Symmetrical hedging**: "While X, it is also true that Y" repeated as a template. Real qualification is asymmetric; say which side the evidence favors.
- **The inflated segue**: "Building on these findings...", "With this in mind...", "Against this backdrop...". Usually deletable; the paragraph order already does this work.
- **End-of-section throat-clearing**: "In conclusion", "In summary", "Taken together" as reflexes; "the future looks bright"; "only time will tell". A Conclusions section may open with "In summary" at most once in the paper, and only if the journal convention expects it.

### Punctuation and format

- **Do not use the em-dash as a rhythm device.** Rewrite with a comma, parentheses, a colon, or two sentences. Numeric ranges keep the en-dash (10–100 nm). Overuse of the em-dash is the single most recognizable visual tell, and avoiding it is a deliberate house-style choice.
- No emoji, no exclamation marks.
- No bolded inline-header lists ("**Stability:** the bubbles were stable...") inside running prose. Sections of a paper are continuous argument, not bulleted notes. Bullets are acceptable only where the target journal uses them (rare; sometimes in Methods for reagent lists).
- No Title-Case Headings unless the journal requires them; follow the venue's convention.
- Units with a non-breaking space convention (100 nm, 25 °C, 18.2 MΩ·cm), SI throughout unless the field convention differs.

### Tone

- No chatbot pleasantries, no addressing the reader, no meta-commentary about the writing itself ("this section will discuss...").
- No significance inflation ("a watershed moment", "poised to revolutionize water treatment"). State what the work does and let the result carry its own weight.
- No enthusiasm markers. The most confident scientific prose is the calmest.

## Signature features of the house register (from the reference corpus)

These eight patterns recur across the corpus and are what distinguish this voice from generic
formal science writing. Deploy them where they fit; they are the fastest route away from
machine-flavored prose. Attested exemplars for each are in `phrase-bank.md`.

- **Concession-first sentences.** The corpus's single most characteristic shape: a subordinate
  concession, then the claim in the stress position. "Although aqueous NB stability is crucial for
  the practical applications, most also involve hydrophobic organic substances." (Kubelka-JCIS).
  It carries two propositions in one sentence and emphasises the right one. Machine prose almost
  always writes this as two sentences joined by `However`.
- **Mid-clause connectives.** `thus`, `however`, and `therefore` are placed *inside* the clause as
  often as at its front: "The large drop in energy upon ion hydration **is thus** the reason for
  the preference of the ions for the aqueous bulk." (Jungwirth-2006). Alternating front and mid
  placement is the cheapest way to break the front-loaded rhythm that marks generated text.
- **Candid inline limitation, bounded.** Difficulties are reported in place, with the reason, and
  the surrounding claim still stands: "Bursting of the NBs upon colliding with the oil (Figure 6)
  may also contribute to the IFT reduction [31], **but we cannot directly quantify this effect**."
  (Kubelka-JCIS). Two or three per paper is the natural dose.
- **Bounding a discrepancy.** After naming a disagreement with prior work or between methods, state
  what it can and cannot affect: "The only consequence of this discrepancy would be quantitative
  overestimation of the rate and, possibly, relative contribution of this process." (Kubelka-JCIS).
  This defuses a referee objection before it is raised.
- **Expectation–observation reversal.** State the expected picture, then the data, then the verdict:
  "**While** the excess heptane at the interface (Figures 2b, 3b) **may indeed cause** the depletion
  of water from the NB surface, **there is no detectable** N2 accumulation around the heptane."
  (Kubelka-JCIS). Impossible for lazy prose to fake, because it requires an actual argument.
- **Plain declarative punch after qualification.** After a hedged passage, land the settled point in
  one short unhedged sentence: "By contrast, the bulk oil depletes the NBs, as indicated by both
  experiments and simulations." (Kubelka-JCIS). One main clause, no adverbs. The rhythm — long
  qualified, then short flat — is what makes the argument feel earned.
- **Dense parenthetical cross-referencing.** Evidence pointers ride inside the sentence:
  "(Figures 2b, 3b)", "(Table 1, SI, Figure S5)", "(see Section 2.1)". Claims travel with their
  receipts. Every quantitative claim in Results and every evidence-bearing claim in Discussion
  carries one.
- **The former / the latter** for compact back-reference to two just-named items, used freely:
  "Thus, the former excitation converts to heat in the environment at a rate five orders of
  magnitude higher than the latter." (Abolfath-2024).
- **A hedging ladder used deliberately** (see `phrase-bank.md` §5): surmise < speculate < suggest <
  indicate < imply < is consistent with < support < show < establish < demonstrate < confirm, with
  `confirm` reserved for direct verification such as blank controls. Referees in this field read
  these verbs literally; the corpus's own referee correspondence contains a request to demote
  "support" to "consistent with aspects of" for exactly this reason. The corpus supplies the honest
  middle formulation: "our results are consistent with the aspects of one of the leading theories"
  (Kubelka-JCIS).

One warning from the same corpus: closing paragraphs are where even strong human writing drifts into promotional boilerplate ("underscore the importance", "sets the stage for future research", "leveraging X-based technologies in next-generation processes"). Those phrases are on the banned list for good reason, and reviewers now read them as machine-flavored regardless of provenance. End instead on the last substantive finding, the sharpest open question, or the specific next experiment.

## When revising a user's draft

Name each tell found (briefly, in a note after the revision) rather than only deleting silently, so the user learns to spot the patterns. Group them ("removed six instances of filler 'Moreover'; replaced two false contrasts") rather than itemizing every line.
