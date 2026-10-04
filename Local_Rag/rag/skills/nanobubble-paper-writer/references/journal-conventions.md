# Journal Conventions and Special Formats

Formats observed in the house corpus (Journal of Colloid and Interface Science and similar Elsevier colloid/interface venues) plus guidance for two paper shapes the standard section guides do not fully cover: the combined Results and Discussion, and the experiment + simulation study. Always check the target journal's current Guide for Authors; these notes encode the common case, not a substitute for it.

## Structured abstract (JCIS style: Hypothesis / Methods (or Experiments) / Findings)

Three labeled paragraphs, total typically under 200 words:

1. **Hypothesis.** Two moves: why the question matters (one or two sentences of application or theoretical stakes), then an explicit, falsifiable hypothesis introduced with "We hypothesize that ...". The hypothesis should be directional and testable ("a small amount of X stabilizes Y, but bulk X causes dissolution owing to ..."), not a vague aim.
2. **Methods / Experiments.** One or two sentences: the experimental probes with their acronyms defined, and the modeling approach and its role ("MD simulations were used to uncover the underlying mechanisms of ...").
3. **Findings.** The results in descending order of importance, hedged on the ladder each has earned: what experiments show plainly, what simulations *suggest*, and where the two agree ("..., consistently with experiments"). No citations, no undefined abbreviations beyond those just introduced.

The Hypothesis paragraph and the Conclusions must agree: if review forces a recalibration of a claim, both get updated.

## Unstructured abstract (CEJ and most Elsevier engineering venues)

A single paragraph, typically 200-300 words, same moves without labels: the application stakes and the problem's cause in two or three sentences; the approach with the conditions matrix spelled out (concentrations, ranges, durations, controls); the findings with their numbers in descending importance; one closing sentence of significance at laboratory strength ("Our results show that X effectively overcomes ..., improving their viability for practical applications"), not field-deployment strength. State the mechanism hypothesis in the abstract only at the rung the paper earns for it.

## Highlights (Elsevier)

Three to five bullet points, each a standalone declarative sentence of one finding or approach, within the journal's character limit (commonly 85 characters including spaces; check and obey, since the editorial system enforces it). Order: what was done (one bullet), the principal findings (two or three bullets), the significance (at most one bullet, stated concretely, not promotionally). Write them last, from the Conclusions.

## Graphical abstract

One image, readable at thumbnail size, telling the single central result; typically the key data panel paired with the most legible mechanistic snapshot. The skill writes no images, but when drafting captions or advising, push for one message per graphic and no more than two panels.

## "Implications and practical applications" subsection

The second house corpus closes its combined Results and discussion with an applications subsection (one sub-heading per application domain). Its register is distinct and must not leak into the data subsections: every claim is an extrapolation and rides the low rungs of the hedging ladder ("may remain functional", "is expected to suppress", "could deliver"), every invoked mechanism carries a citation, quantitative anchors from the literature are given where available (formation temperatures, salinities, reported recovery improvements), and compositional or regime gaps between the laboratory system and the application are stated plainly with "warrants future investigation". This subsection is where promotional drift is most likely; run the `ai-tells.md` scan on it twice.

## Elsevier back matter

CRediT authorship contribution statement (each author with their roles from the standard taxonomy), Declaration of Competing Interest, Acknowledgements with funders named, and Supporting Information callouts as "(SI, Figure SN)" throughout the text. These are boilerplate to format, not to write creatively.

## Combined "Results and discussion" section

Common in JCIS, Langmuir, and much of colloid science. The contracts of the separate sections still hold; what changes is their interleaving:

- **Organize by evidence block** (e.g., experiments first: system characterization, then the key variable; then simulations: equilibrium systems, then dynamics), each block a numbered subsection.
- **Report, then interpret, in place.** Each subsection opens by reporting what was measured or computed (Results register: numbers, uncertainties, figure callouts), then moves to interpretation of that block (Discussion register: mechanism, comparison with literature, alternatives). Do not defer all interpretation to the end, and do not interpret before the numbers are on the table.
- **Keep the registers distinguishable sentence by sentence.** A reader should always know whether a sentence reports or argues. The hedging ladder does this work: reported facts carry "was/were"; interpretations carry "suggests/implies/is consistent with".
- **Bridge between blocks** with the experimental logic: "Before discussing X, it is worth examining Y", "Turning to X, ...", "Finally, we explore ...", "..., which are the focus of the following section."
- **The global obligations survive the merger**: alternative explanations confronted, quantitative sanity checks run, limitations named where they bite. A combined section makes it easier to forget them; the checklist in `discussion.md` still applies to the section as a whole.

## Experiment + simulation papers

The house corpus is this shape, and review of it produced two rules worth treating as law:

1. **Separate what is directly shown experimentally from what is proposed mechanistically from simulation.** Every mechanistic claim must be traceable to its source: "Experiments (Section 3.1.1) indeed suggest ...", "The MD simulations suggest ...", "as indicated by both experiments and simulations". A reviewer will explicitly demand this separation if the prose blurs it. Simulation-only inferences about the real system are hypotheses, and the Conclusions must label them as such.
2. **Calibrate theory-support claims to the simulation's known gaps.** Where the simulated system departs from reality in a relevant way (e.g., stability requiring supersaturation levels far above ambient, sizes an order of magnitude below experiment), results "are consistent with aspects of" a theory; they do not "support" or "confirm" it. State the departure and, where possible, argue its consequence ("the only consequence of this discrepancy would be a quantitative overestimation of the rate, not a qualitative change").

Further craft for this shape:

- **Reconcile explicitly, discrepancies included.** Where simulation predicts an effect experiment does not see, say so and argue detectability: "The simulations also suggest an increase in size, which is not observed; however, at the experimental scale (~100 nm diameter) a change of a few nm will be very difficult to detect."
- **Run the bridging estimates** that connect the two scales: equation-of-state internal pressures, curvature corrections (Tolman-type), classical dissolution kinetics fits (Epstein–Plesset), comparison of computed and literature interfacial tensions with the force field's known systematic errors acknowledged.
- **Report model limitations as facts about the model**, with the validation evidence: which properties the force field reproduces, which it systematically misses and by how much, and why the conclusion is robust to the miss ("the trend is clearly not just an artifact of the inaccurate IFT").

## Response to reviewers

The corpus includes a model response document. The format that works:

- **Structure.** Open with one sentence of thanks. Then, for each reviewer: quote or restate each comment verbatim (visually distinguished), followed by the response. Every response that changed the manuscript quotes the new text verbatim with its location: (Results, p. 15) "...". Every response ends with the change made or the reason none was needed.
- **Do the work when the request is reasonable.** "We thank the reviewer for the suggestion. We have conducted a new set of experiments and monitored ... over two weeks." New data, new figures, new SI items get named explicitly.
- **Push back with arguments, not adjectives, when the request is not.** The register is polite and firm: "We respectfully disagree. The fact that something is expected, and makes physical sense, does not mean that investigating it lacks novelty." The strongest rebuttal in the corpus is a back-of-envelope calculation: take the reviewer's scenario, deliberately exaggerate every parameter in its favor, and show the effect is still negligible, with the arithmetic on the page. Emulate that.
- **Correct misreadings precisely.** If the reviewer attributes to the manuscript a discrepancy that is actually a known discrepancy within the literature, say exactly that, cite the reviews, and note where the manuscript already states it.
- **Concede cleanly.** Where a reviewer asks for toned-down claims, make the recalibration visible: quote the old implication, quote the new wording, and propagate it to the Abstract, Discussion, and Conclusions consistently.
- **Tone guard.** No sarcasm, no "as we already stated" resentment, no flattery beyond the opening thanks. Confidence comes from the arithmetic and the citations.

The second response corpus (a CEJ revision) adds several conventions worth adopting:

- **A formatting legend up front.** One sentence after the opening thanks: reviewers' comments in plain text, responses in italics, manuscript insertions in quotation marks with section and page numbers. It makes a long document navigable and signals care.
- **Response-only figures.** New data generated for the rebuttal but not added to the paper are presented as Figure R1, R2, ... inside the response, with full captions. A repeated measurement that reproduces a questioned feature is the strongest possible answer to "is this an artifact?".
- **The reframe move.** When a reviewer calls a premise "an assumption", show its double grounding: "advanced not as an unsupported assumption but as a hypothesis grounded in both the literature and our own measurements", then cite the specific prior work and the specific in-house observation (with figure callouts). Concede the residual confound honestly ("We recognize, nevertheless, that ...") and close it with new experiments rather than words.
- **Design-of-experiment justification.** When defending controls or isolating variables, state what each comparison isolates: "Comparing chemically distinct buffers at a common concentration isolates the role of the buffer identity, whereas comparing the matched-pH pair differing tenfold in ionic strength isolates the role of the ionic strength."
- **The semi-quantitative exhaustion rebuttal.** For "you should at least attempt an explanation": enumerate every known governing property with its magnitude of variation over the range, show each varies smoothly where the data show a threshold, conclude none can account for it, verify the feature by repetition, and *keep* the candid admission, now framed as an open question for dedicated future work. Honesty defended with numbers survives review; a confected explanation does not.
- **Scope defense with a receipt.** Decline out-of-scope requests explicitly ("falls outside the scope of the present study and is identified as an important direction for future work") and add one acknowledging sentence, with the suggested citation, to the manuscript so the decline leaves a trace.
- **Inconsistency repair.** When a reviewer catches two passages in conflict, diagnose the origin (typically an extrapolation from a different regime), delete or correct the offending passage, and where possible add the model or diagram that settles the chemistry (a speciation calculation in the SI, for instance) rather than only rewording.
