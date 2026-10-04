# Materials and Methods

The Methods section has one contract: a competent peer, with the same equipment class, could reproduce the work from this text alone. It specifies; it does not narrate a lab diary, and it does not report results.

House style applies, with one relaxation: Methods tolerates a plainer, more procedural rhythm than the argumentative sections. Plainness is a virtue here; elegance is not the goal, completeness and exactness are. Attested frames are in `phrase-bank.md` §3.

## Corpus anchors (measured from the reference Methods sections)

| Property | Rate per 1,000 words | Reading |
|---|---|---|
| Passive (`was`/`were` + participle) | **27.45** | Ten times the rate of any other section. This is the one place where near-total passive is correct: the agent is irrelevant, the operation is the point. |
| `However` | **0.19** | Effectively zero. Methods does not argue, so it does not contrast. A `However` here almost always signals a result that has leaked in. |
| Hedges (`may`/`might`/`could`) | 1.33 | The lowest of any section. What was done is not hedged; only the justification of a modelling choice is. |
| `suggest` / `indicate` | 0.57 | Near-zero. Interpretation belongs elsewhere. |
| Sentence length | median **21** words, p90 35 | The shortest and tightest sentences in the paper. |

The distinguishing habit of the corpus's strongest Methods sections is that **every simplifying
assumption is stated as a decision with a reason attached** — "Electronic continuum correction (ECC)
was invoked to account for water polarizability by scaling all ion charges by 0.75 [46]", "the pH
range was restricted to between 4 and 10 due to equipment limitations". An unexplained assumption is
what a referee attacks first.

## Voice and tense

- **Past tense throughout** for what was done ("samples were prepared", "we measured"). Present tense only for standing facts and for describing apparatus that still exists ("the flow cell consists of...", acceptable but not required).
- Mixed passive/active is the norm in strong experimental papers. Passive foregrounds the procedure ("the suspension was sonicated for 10 min"); active foregrounds a choice the authors made and should defend ("we chose nitrogen rather than air to exclude CO2-mediated effects"). Use active voice precisely where a decision needs an owner.
- No justification essays. One clause of rationale where a choice is non-obvious ("filtered through a 20 nm membrane to exclude pre-existing particulates") is enough; extended argument belongs in the Discussion.

## Structure

Order subsections by the logic of the experiment, typically:

1. **Materials.** Every substance with grade/purity and supplier in the field's convention ("ethanol (≥99.8%, Sigma-Aldrich)"). Water deserves a full sentence in nanobubble work: source, resistivity, TOC if known, and any degassing or filtration (see domain notes below).
2. **Sample preparation / generation.** The generation method with every parameter that matters: device and model, power, frequency, duration, flow rate, gas species and saturation state, temperature, container material and cleaning protocol.
3. **Characterization / measurements.** One subsection per technique. Instrument make and model, the settings actually used (laser wavelength, camera level, capture duration, number of frames, scan rate, cantilever type and spring constant, and so on), calibration, and the environment (temperature, whether sealed against gas exchange).
4. **Controls and blanks.** What was run to exclude artifacts, described with the same specificity as the main experiments.
5. **Data analysis and statistics.** Software with version, the quantities extracted, how replicates are defined (independent preparations vs. repeated measurements of one sample; the distinction matters and referees check), the statistical tests, and how uncertainties are reported (SD vs. SEM, n).

Numbered or named subsections follow the target journal's convention.

## What does NOT belong here

- Results ("the measurement revealed a mean size of..."): move to Results.
- Interpretation ("suggesting the entities are gaseous"): move to Discussion.
- Motivational context ("nanobubbles have attracted attention because..."): that ship sailed in the Introduction.
- Vague quantities: "briefly sonicated", "thoroughly cleaned", "left for some time", "room temperature" without a value. Every such phrase is replaced by a number or flagged as a placeholder for the user to supply.

## Domain notes: what nanobubble referees look for in Methods

Because the central controversy in this field is whether observed nano-entities are gas bubbles or contaminant particles, the Methods section carries unusual evidentiary weight. A nanobubble Methods section that omits the following invites rejection:

- **Water quality**, stated explicitly: ultrapure water (resistivity 18.2 MΩ·cm at 25 °C is the standard figure) and its source system; storage vessel material; time between production and use.
- **Cleaning protocols** for all glassware and cells in contact with samples, since trace surfactants alter interfacial behavior at the concentrations relevant here.
- **Gas handling**: which gas, how saturation or supersaturation was set, whether and how solutions were degassed for controls.
- **Controls that discriminate bubbles from particles**, described exactly: degassed-water blanks, filtered blanks, solvent-only blanks (essential in water–organic mixing studies), freeze–thaw cycles, pressurization/compression tests, or density-sensitive measurements (e.g., resonant mass measurement). Which controls apply depends on the study; the section must state which were done and their parameters, not their outcomes.
- **Sizing-technique limitations acknowledged implicitly through settings**: for nanoparticle tracking analysis (NTA) and dynamic light scattering (DLS), the settings and dilutions used, since both techniques count scatterers of any composition and this is precisely the interpretive weakness the controls address.
- **The defensive-interpretation paragraph (corpus pattern; often born in review).** When a technique has a known weakness under the study's conditions (zeta potential at high ionic strength is the field's standard example), preempt the referee inside the characterization subsection with a four-move paragraph: (i) name the difficulty and its physical cause, with citations; (ii) bound its consequence precisely ("these limitations primarily constrain the precision of the absolute magnitude rather than the sign or the direction of its variation"); (iii) state the interpretive discipline adopted ("we have therefore interpreted the data comparatively rather than as absolute determinations", with precedent cited); (iv) name the corroborating measurements so that "no conclusion rests on X alone". This single paragraph converts a standing objection into evidence of rigor.
- For **surface nanobubble** studies: substrate material and preparation, AFM mode (tapping/peak-force), tip specification, setpoint ratio, and the solvent-exchange or other nucleation protocol in full.

## Checklist (in addition to the global one)

- [ ] A peer could reproduce every step; no vague quantities survive.
- [ ] Every material has grade and supplier; every instrument has make, model, and the settings used.
- [ ] Water, cleaning, gas handling, and controls specified (nanobubble papers).
- [ ] Replicate structure and statistics defined; uncertainty convention stated.
- [ ] No results, no interpretation, no motivation.
- [ ] Past tense for actions; every missing detail is a visible placeholder, not a plausible guess.
