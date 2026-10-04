# Results

The Results section reports what was observed, in a deliberate order, quantitatively, with just enough framing for the reader to follow and no more. It shows; the Discussion argues. A Results section that editorializes reads as insecure, and one that merely lists numbers reads as unwritten. The craft is the narrative line between the two.

House style applies in full; the ban on "significant" outside statistics is absolute here. If the target journal uses a combined "Results and discussion" section (common in colloid and interface science), read `journal-conventions.md` for how to interleave this section's register with the Discussion's. Attested frames are in `phrase-bank.md` §4.

## Corpus anchors (measured from the reference Results sections)

| Property | Rate per 1,000 words | Reading |
|---|---|---|
| Figure / Table references | **8.31** | Three times the rate of any other section — roughly one pointer every six words of running text. Every quantitative claim travels with its receipt. |
| `we` / `our` | **5.93** | Twice the Introduction's rate. First-person plural is the corpus's normal device for marking transitions between experiments ("We now turn to...", "Finally, we explore..."). |
| Citations `[n]` | 5.29 | High. Results in this corpus cite constantly — for methods borrowed, for values compared against, for the theory a trend is checked against. |
| Hedges | 2.24 | Interpretation stays at the `consistent with` / `indicating that` level. |
| `consistent with` | 0.75 | The single most common interpretive verb phrase in Results. |
| Sentence length | median 24 words, p90 39 | Comparable to the Introduction. |

The corpus uses 176 distinct figure-pointing constructions across the section. Vary them. Six
consecutive paragraphs opening "Figure N shows" is the most common structural tell in a Results
draft.

## Voice and tense

- **Past tense** for what was measured and found ("the mean diameter was 152 ± 12 nm"; "the number density decreased by a factor of three").
- **Present tense** for pointing at displayed items ("Figure 2 shows...", "the distributions in Figure 3 are unimodal") and for statements treated as established by the data just presented ("the size is independent of the generation time").
- First-person plural is available and natural ("we observed", "we then varied..."), especially at transitions between experiments.

## Structure: the narrative of evidence

- **Order by logic, not chronology.** The sequence should build a case: characterize the system first, then the behavior under the key variable, then the discriminating experiments. The order of experiments in the lab is irrelevant.
- **One finding per paragraph.** Open with a sentence that states the finding or the question the experiment answers; follow with the quantitative substance; close on the element the next paragraph picks up (given-new chaining across paragraphs, not only sentences).
- **Anchor every claim to its display item.** Every figure and table is called out in order, and no figure is left uncalled. The text states what the figure shows and gives the key numbers; it does not duplicate the entire figure in words.
- **Transitions carry the experimental logic**: "To test whether the entities were gas-filled, we...", "Having established the size distribution, we next examined its evolution over time." These are honest, load-bearing transitions, not filler.

## Reporting standards

- Every quantitative claim carries value, uncertainty, units, and n where applicable: "210 ± 15 nm (mean ± SD, n = 5 independent preparations)".
- Statistical claims name the test and the statistic: "(p = 0.003, two-tailed t-test)". Without this, the word "significant" may not appear.
- Comparisons are quantified: not "much larger", but "larger by a factor of 2.3" or "larger by 40 ± 6 %".
- Trends are described with direction, magnitude, and range of validity ("increased monotonically with power between 20 and 80 W, from ... to ...").
- Negative and null results are reported plainly and are often the most important sentences in a nanobubble paper ("no scatterers above the detection limit were observed in the degassed control").
- Report what the data show even when inconvenient; the Discussion is the place to reconcile.

## Interpretation: how much is allowed

Light framing that names what an observation indicates at the level of the measurement itself is acceptable and normal: "consistent with a gas-filled interior" after a compression test, "indicating that the entities are not removed by filtration". What is not allowed here: mechanism proposals, comparison with literature, weighing of alternative explanations, or claims about what the findings mean for the field. Any sentence beginning to argue rather than report gets moved to the Discussion.

## Domain notes for nanobubble Results

- Report **number density together with size distribution**, since the two respond differently to the classic artifacts; state the dilution at measurement.
- Report **zeta potential** with the medium's pH and ionic strength; the value is meaningless without them.
- **Time-series stability data** state the storage conditions (sealed or open, temperature, container) alongside the decay in density and any drift in size; longevity claims are only as strong as these details.
- **Control outcomes are results**, not asides, and deserve their own paragraph(s): degassed blanks, solvent blanks, freeze–thaw response, response to pressurization, response of the signal to added surfactant or salt. In this field the controls usually carry the paper.
- Where two techniques were used on the same samples (e.g., NTA and DLS), report both and quantify the agreement or the discrepancy; do not average across techniques.

## Checklist (in addition to the global one)

- [ ] Findings ordered as an evidentiary narrative; one finding per paragraph.
- [ ] Every figure/table called out in order; text gives key numbers, not a prose copy of the figure.
- [ ] Every value has uncertainty, units, and n; every "significant" has a test.
- [ ] Comparisons and trends quantified; null results stated plainly.
- [ ] Interpretation limited to measurement-level framing; no mechanisms, no literature.
- [ ] Control outcomes reported with the same prominence as headline results.
