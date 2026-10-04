# Discussion

The Discussion is where the paper argues. It interprets the findings, proposes or tests mechanism, places the work against the literature, confronts alternative explanations honestly, admits limits, and states implications at their true size. It is the hardest section to write well and the one where AI-flavored prose fails most visibly, because vague synthesis ("these findings highlight the complex interplay of...") is precisely what this section must not do.

House style applies in full. Calibrated certainty is the organizing discipline of the entire section. For combined "Results and discussion" sections and for experiment + simulation papers, also read `journal-conventions.md`; its two rules on separating experimental evidence from simulation-based inference are binding here. Attested frames for every move below are in `phrase-bank.md` §5, which also carries the hedging ladder.

## Corpus anchors

Most of this corpus uses a combined "Results and discussion", so the Discussion register is measured
against the Results numbers above rather than separately. Three findings transfer directly:

- **Hedges outnumber proof verbs about two to one.** Across the corpus: `may`/`might`/`could` 2.15
  per 1,000 words against `demonstrat*` 0.41 and `confirm*` 0.36. A Discussion in which most claims
  are asserted at full strength is miscalibrated, not confident.
- **`confirm` is reserved for direct verification** — a control that came out clean, a measurement
  that closed a loop. Not for "our data are compatible with our idea". The corpus's own referee
  correspondence contains a request to demote "support" to "consistent with aspects of"; that
  formulation is the honest middle rung and it is worth reaching for deliberately.
- **Disagreements are named and then bounded.** The corpus's characteristic move is to state a
  discrepancy and immediately delimit what it can affect: "The only consequence of this discrepancy
  would be quantitative overestimation of the rate and, possibly, relative contribution of this
  process." That sentence shape defuses a referee objection before it is raised, and it is the
  clearest single marker of an author who has thought the objection through.

## Structure: the argumentative moves

A strong discussion typically runs through these moves, though the order of 2–4 can vary:

1. **Answer the question.** Open by stating what the results establish, in one or two sentences tied directly to the aim from the Introduction. Not a summary of everything; the answer. ("The measurements above show that the nano-entities produced by acoustic cavitation are gas-filled and persist for at least N weeks.")
2. **Interpret and mechanize.** Explain *why* the observations come out as they do, connecting them to the governing physics quantitatively where possible. An estimate is worth a paragraph of qualitative talk: compare the observed lifetime with the Epstein–Plesset prediction for the measured radius; compare the measured zeta potential with the magnitude needed for electrostatic stabilization. Where the paper proposes a mechanism, state its assumptions and what observations it does and does not account for.
3. **Compare with the literature.** Agreement and disagreement both, with specific citations, specific numbers, and stated reasons where the results differ ("our densities are an order of magnitude below those of Ref. [n], plausibly because..."). Fair attribution: represent rival interpretations as their authors would recognize them.
4. **Confront alternative explanations.** For each plausible alternative, state it fairly, then state which of the present observations bears on it and how strongly. Rank the strength of the exclusion honestly: "excluded by", "difficult to reconcile with", "not distinguished by the present data". A discussion that ignores a live alternative will not survive review.
5. **Limitations.** Name the real ones: what the techniques cannot see, what parameter space was not covered, what the sample size supports. Precise and unapologetic; two or three genuine limitations stated exactly beat a defensive paragraph of soft ones. Where possible, state what would resolve each.
6. **Implications and outlook**, at their true size. What follows for theory, for applications, or for method, phrased no larger than the evidence. One short paragraph; expansion belongs to review articles.

## Craft notes

- **Hedge with structure, not fog.** "The most likely explanation is X, for reasons A and B; explanation Y cannot be excluded but would require Z" is calibrated. "These results may suggest a possible role for various factors" is fog.
- **Keep the chain of inference visible.** Each interpretive claim should trace to named results ("the insensitivity to filtration (Fig. 4) rules out...") so the reader can audit the argument. Refer to results by figure/table, not by re-narrating them.
- **Do not re-report.** Any sentence that merely restates a result without adding interpretation is dead weight here.
- **No new results.** If an observation matters, it appears in Results first.
- **Watch the summary-voice drift.** Long discussions written by machines slide into a uniform present-tense gloss ("the findings demonstrate... the data reveal... this highlights..."). Keep the tense discipline: past for what this work found, present for what is generally true or what the findings *now* establish.

## Domain notes: the alternative-explanation obligation in nanobubble work

Move 4 is not optional in this field; it is the referee's first question.

- **For bulk nanobubbles**, the standing alternative is that the observed scatterers are solid or supramolecular contaminants (organics from water, vessels, or added solutes) rather than gas bodies. The literature contains documented cases where "nanobubbles" produced by ethanol–water mixing were shown to be non-gaseous particles. Any bulk-nanobubble discussion must state which of its observations discriminate gas from non-gas (degassing response, freeze–thaw, compression response, density-sensitive measurement, internal-composition probes) and how conclusive each is. Where the evidence is a battery of indirect tests, say so in those words; overclaiming "conclusive proof" from indirect evidence has drawn published rebuttals in this exact field.
- **For bulk nanobubble stability**, present candidate mechanisms as candidates: electrostatic stabilization by interfacial charge, ion or contaminant enrichment at the interface reducing effective surface tension, oversaturation with diffusive shielding in clusters, and dynamic-equilibrium pictures. State which the data support, which they disfavor, and which they do not test. The field has no consensus; the discussion must not manufacture one.
- **For surface nanobubbles**, the stability question is regarded as settled (contact-line pinning plus gas oversaturation), so the discussion instead engages: whether the observed objects meet the identification criteria distinguishing them from droplets or particles, the role of substrate chemistry and history, and quantitative comparison with the pinning theory's predictions (e.g., the relation between contact angle, footprint, and saturation).
- **Quantitative sanity checks belong here**: Laplace pressure at the measured radius, the classical dissolution time at the measured size and saturation, gas content implied by the number density versus solubility. A discussion that runs these numbers reads as written by someone who understands the physics; one that does not, does not.

See `nanobubble-domain.md` for the mechanisms, the canonical references, and the numbers commonly used in such estimates.

## Checklist (in addition to the global one)

- [ ] Opens by answering the aim, not by summarizing.
- [ ] Mechanistic interpretation is quantitative where the data allow (order-of-magnitude estimates run, not gestured at).
- [ ] Literature comparison specific: numbers, citations, reasons for discrepancies.
- [ ] Every live alternative explanation stated fairly and confronted with named evidence; strength of exclusion ranked honestly.
- [ ] Limitations real, precise, unapologetic.
- [ ] Implications sized to the evidence; no field-transforming rhetoric.
- [ ] No new results; no re-reporting; inference chain auditable via figure/table references.
