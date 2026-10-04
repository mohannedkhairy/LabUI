# Phrase Bank — mined from the reference corpus

Every pattern below was derived from a 20-document corpus of nanobubble, colloid-and-interface,
and interfacial-physics papers (~76,000 words of running research prose after removing
references, captions, and equation debris), plus five craft sources. Counts are real counts from
that corpus. Source keys are defined in `corpus.md`.

**How to read an entry.** Each move gives a *pattern* (the reusable frame, with `X`/`Y` slots),
then one or more *attested* sentences quoted verbatim from the corpus with their source and
section. The attested lines are there to calibrate rhythm and hedging strength, not to be pasted.
Never copy an attested sentence into a manuscript; it is someone else's text. Take the shape,
supply your own content.

**How to use it.** Reach for this bank when a sentence has to carry a *logical* load — a
contrast, an inference, a concession, a comparison with prior work. Most sentences should connect
through their content alone; a connective on every sentence is itself a defect. Do not repeat a
frame within a section.

---

## 0. The connective budget (measured, not invented)

Rates per 1,000 words of running text in the corpus. These are the empirical ceilings. A draft
that exceeds them reads as machine-assembled even when each individual sentence is defensible.

| Marker | Corpus rate | Practical budget for a 6,000-word paper |
|---|---|---|
| `However` | 1.67 | ~10 total; the workhorse contrastive |
| `Thus` / `Therefore` / `Hence` | 2.40 (combined) | ~14 combined; vary among the three |
| `In contrast` / `By contrast` | 0.37 | ~2 |
| `Furthermore` | 0.32 | ~2 |
| `Moreover` | 0.29 | ~2 |
| `In addition` | 0.25 | ~1–2 |
| `Consequently` | 0.24 | ~1–2 |
| `Nevertheless` / `Nonetheless` | 0.21 | ~1 |
| `On the other hand` | 0.14 | ~1, and only after a real "on one hand" |
| `Interestingly` | 0.13 | ~1, attached to a genuinely surprising number |
| `Additionally` | **0.05** | ~0. Four occurrences in 76,000 words. Use `In addition` or nothing. |
| `Notably` | **0.05** | ~0 |
| `Importantly` | **0.04** | ~0 |
| `It is worth noting` / `It is important to note` | **0.05** | ~0. Use the corpus form `Note that ...` |
| em dash `—` | **0.05** | ~0. Four in 76,000 words. |
| semicolon `;` | 0.97 | ~6. Twenty times more common than the em dash — use it instead. |

Words with **zero occurrences** in 76,000 words of this corpus: *robust, delve, realm, landscape,
tapestry, testament, showcase, intricate, multifaceted, meticulous, pivotal (1), underscore (1)*.
Treat any of them in a draft as a defect.

`novel` appears 7 times in 76,000 words (0.09/1,000). `crucial`/`critical`/`essential` together
appear at 0.45/1,000 — roughly three times in a paper, always attached to a specific thing that is
critical *for* something, never as generic praise.

---

## 1. General logical moves

### Inference
`Thus, X.` / `Therefore, X.` / `Hence, X.` / `Consequently, X.` / `It follows that X.` / `X; consequently, Y.`

> "Thus, there must be a third force that is responsible for the rupture of wetting films during flotation." — Yoon-2000, Intro
> "Thus, the radius of curvature is negative, which results in the negative Laplace pressure." — Yasui-2019
> "The large drop in energy upon ion hydration is thus the reason for the preference of the ions for the aqueous bulk." — Jungwirth-2006, Intro

Note the third form: `thus` placed *inside* the clause rather than at the front. The corpus does
this constantly and it is the single cheapest way to break the front-loaded-connective rhythm that
marks machine prose.

### Contrast
`However, X.` / `X, however, Y.` / `By contrast, X.` / `In contrast, X.` / `Unlike X, Y.` / `whereas` / `Conversely, X.`

> "However, Weber and Paddock did not verify this relationship experimentally." — Yoon-2000, Intro
> "The surface tension of the 1.2 M NaOH solution, however, was higher by about 4 mN/m." — Jungwirth-2006, Intro
> "By contrast, the bulk oil depletes the NBs, as indicated by both experiments and simulations." — Kubelka-JCIS, Conclusions
> "Unlike solid-state surfaces, the air/water interface is hard to probe experimentally." — Jungwirth-2006, Conclusions
> "Conversely, a negative Γ12 means that there is a depletion of component 2 in the interfacial region." — Jungwirth-2006, Intro

Mid-sentence `, however,` is used almost as often as sentence-initial `However,` in the corpus.
Alternate them.

### Reversing an expectation
`On the contrary, X.` (only to reverse something just stated) / `In fact, X.` / `Instead, X.`

> "On the contrary, gas diffuses out of the bubble from the other part of the uncovered bubble surface." — Yasui-2019
> "In fact, NB bursting and the associated disruption of the surface was proposed as one possible reason for the lower surface tension [31]." — Kubelka-JCIS, Results

### Concession before assertion
`Although X, Y.` / `While X, Y.` / `Even though X, Y.` / `Despite X, Y.` / `X, albeit Y.`

> "Although aqueous NB stability is crucial for the practical applications, most also involve hydrophobic organic substances." — Kubelka-JCIS, Intro
> "Despite the significance of wettability in bubble nucleation [12] and departure from the surface [3], its effect on growth rate remains unexplored." — Sullivan-2023, Intro
> "Although the mechanisms by which nanobubbles are stabilized remain unresolved, the usefulness of bulk is being investigated and applied in many ways." — Alheshibri-2021, Intro
> "Moreover, single ions interacting with water molecules can also be observed experimentally, albeit only in cluster systems." — Jungwirth-2006, Intro
> "Even though it was expected that, with high surface charge densities, internal pressures inside the bubble would reduce, the results indicate that the contribution was minimal." — Meegoda-2019, Results

This is the corpus's most characteristic sentence shape: subordinate concession first, main claim in
the stress position at the end. It does the work that a bare `However` sentence does, but it packs
two propositions into one sentence and puts the emphasis where it belongs.

### Guiding the reader
`Note that X.` / `It should be noted that X.` / `It should be stressed that X.` / `We now consider X.` / `We now turn to X.` / `Before discussing X, it is worth examining Y.` / `In the following, we ...`

> "Note that this nanoscale adsorbed layer is only a few molecules thick, and is distinct from the micron-sized liquid micro-layer observed in pool boiling phenomena [22]." — Sullivan-2023, Intro
> "We now consider the structure of the electrical double layer." — Ma-2022, Results
> "We now address whether or not the nanobubbles in suspension interact with the Au nanoparticles in suspension." — Zhang-2016, Results
> "Before discussing the impact of the oil, it is worth examining the distribution of aqueous ions around the NB." — Kubelka-JCIS, Results
> "It should be stressed that the role of a specific ion being classified as of structure-breaking, structure-making or a borderline case is still an open question." — Ma-2022, Results
> "In the following discussion, we thus ignore the influence from this part of nanoparticle." — Ma-2022, Results

`Note that` (17 occurrences) is the corpus's guidance marker. `It is worth noting that` appears
three times in 76,000 words — treat it as near-banned and use `Note that`.

### Compact back-reference
`the former ... the latter` / `An example of the latter is X.` / `The latter contradicts Y.`

> "The latter contradicts the predictions of the MD simulations." — Jungwirth-2006, Intro
> "An example of the latter is the case of the sodium halide solutions." — Jungwirth-2006, Intro
> "Thus, the former excitation converts to heat in the environment at a rate five orders of magnitude higher than the latter [62]." — Abolfath-2024, Results

### Setting up alternatives
`Two X have been proposed. In the first, ... In the second, ...` / `either X or Y` / `depending on whether X` / `We can envision two scenarios.`

> "Various mechanisms for the apparent stability against diffusional collapse have been proposed." — Ma-2022, Intro
> "Inorganic ions can interact with the charged surface in either nonspecific ion adsorption or specific ion adsorption." — Hewage-2021, Results
> "Two experimental lines of enquiry have bolstered the case for nanobubbles as the origin of the hydrophobic attraction." — Attard-2003, Intro
> "This leads to two fundamental questions: (a) by what mechanism does the NEL influence the contact angle behaviour? and (b) when and why does the NEL form?" — Sullivan-2023, Results

---

## 2. Introduction

### Opening the field (the widest ring of the funnel)
`X are used in many applications involving Y.` / `X underpin Y, and the quantitative understanding of Z has led to ...` / `X has emerged as an effective tool for ...`

> "Aqueous nanobubbles (NBs) have emerged as an effective tool for a variety of practical applications." — Kubelka-JCIS, Conclusions
> "These four forces underpin colloid science, and the quantitative understanding of their molecular basis has lead to their widespread control and exploitation." — Attard-2003, Intro
> "Vapour bubble formation has been attributed as the driving factor behind natural phenomena, such as geyser formation and volcanic eruptions [1]." — Sullivan-2023, Intro

Note what the corpus does *not* do: it does not open with "In recent years, X has attracted
significant attention." That construction is absent. Openings name a concrete use, a concrete
phenomenon, or a concrete theoretical commitment.

### Establishing that the problem matters
`Controlling X is critical to Y.` / `Understanding X is critical for Z.` / `Particularly important is X, where Y.`

> "Controlling the size, concentration, and stability of NBs is critical to harnessing their full capabilities." — Khairy-2025, Intro
> "Understanding the NB behavior under different conditions of both generation and target application is critical for developing and optimizing NB-based EOR technologies, leading to more efficient and cost-effective subsurface resource extraction." — Khairy-2025, Intro
> "Particularly important is the interaction between particles and nanobubbles, where the interfacial features play a dominant role [32]." — Alheshibri-2021, Intro

### Scaffolding prior work
`X et al. [n] reported/showed/observed/proposed Y.` / `They found that Y.` / `In another study, X et al. [n] explored Y.` / `Recently, X et al. [n] reported Y.` / `A similar viewpoint by X et al. [n] has suggested that Y.`

> "Nirmalkar et al.[ref] experimentally proved that bulk nanobubbles do exist, they are filled with gas, and they survive for a long period of time." — Meegoda-2019, Intro
> "In another study, Xiao et al. [30] explored the impact of nanobubbles on phosphine recovery in artificial wastewater." — Alheshibri-2021, Intro
> "Recently, Tan et al. [7] reported a model accounting for the long lifetime of bulk nanobubbles based on experimental studies." — Alheshibri-2021, Intro
> "A similar viewpoint by Vacha et al. [27] has suggested that zeta potential can be ascribed to bubble interface polarization." — Alheshibri-2021, Intro
> "They found that the measured forces were strongly attractive and increased with increasing contact angle." — Yoon-2000, Intro
> "Uchida et al.[ref] used a transmission electron microscope to analyze nanobubbles and observed a thin film around the bubble surface." — Meegoda-2019, Results

Attribution in the corpus is *specific*: a named group, a numbered citation, and the actual finding.
Vague attribution ("studies have shown", "research suggests", "it is widely believed") is the
single most reliable marker of unsourced writing. If you cannot name who, do not make the claim.

### Naming the tension
`X remains enigmatic, with Y continuing to be the subject of active debate [refs].` / `X defies classical expectations, and there is currently no consensus on its origins.` / `This apparently contradicts the prediction by Z [ref].` / `discrepancies persist between X and Y`

> "One of the most intriguing aspects of NBs is their stability, which defies classical expectations and there is currently no consensus its origins [23–25]." — Kubelka-JCIS, Intro
> "This apparently contradicts the prediction by the classical Epstein-Plesset theory [14], that nanobubbles are unstable and should dissolve on a timescale of milliseconds to microseconds under standard conditions." — Ma-2022, Intro
> "However, while it is generally accepted that NBs are negatively charged [21,24,26] due to the accumulation of hydroxide ions (OH⁻) on their surfaces [24], discrepancies persist between macroscopic versus microscopic experimental data and simulations [27]." — Kubelka-JCIS, Intro
> "There is no consensus, and even numerous experiments and calculations seemingly support contradictory conclusions." — Ma-2022, Results
> "This discrepancy suggests that there may be other factors affecting the stability of wetting films." — Yoon-2000, Intro

### Stating the gap
`To the best of our knowledge, however, X has not yet been studied.` / `X remains unclear.` / `X has not been established.` / `X is not well understood.` / `no systematic investigation has been conducted concerning X` / `X has yet to be satisfactorily explained.`

> "To the best of our knowledge, however, the behavior of NBs in the presence of oil or any hydrophobic, organic molecules, has not yet been studied." — Kubelka-JCIS, Intro
> "While the effects of either salt or pH on NBs have been previously tested,[refs] no systematic investigation has been conducted concerning the solution conditions used for NB generation versus changes introduced postgeneration." — Khairy-2025, Intro
> "The presence of stable bulk nanobubbles seems to have been experimentally confirmed, yet a convincing theoretical basis that is tested by experiments has not been established." — Ma-2022, Intro
> "However, the role that the surface plays in determining the growth of a bubble is still poorly understood." — Sullivan-2023
> "To what extent the gas bubbles may contribute to these short-ranged interactions remains unclear." — Alheshibri-2021, Intro
> "The kinetic data for nanobubbles are lacking; further studies are needed to address this issue." — Alheshibri-2021, Intro

The corpus's gap statements are narrow and checkable. "X has not yet been studied" is qualified by
"to the best of our knowledge"; "no systematic investigation" is qualified by naming exactly what
*has* been tested. A broad unqualified gap claim is an invitation for a referee to supply the
counterexample.

### Stating the aim
`Here, we report X.` / `In this work, we ...` / `In this paper, we report a combined X and Y study of Z.` / `Our goal in the present work is to answer the following question: [question]` / `In the present study, X is combined with Y to ...`

> "In this paper, we report a combined experimental and theoretical study of the stability of bulk nanobubbles." — Ma-2022, Intro
> "Our goal in the present work is to answer the following question: Can superstable nanobubbles interact with nanoparticles, akin to froth flotation?" — Zhang-2016, Intro
> "Here we demonstrate the ability of bulk nanobubbles to interact with gold nanoparticles." — Zhang-2016, Intro
> "In this paper, the interaction between bulk NBs and lipid Langmuir monolayers using the LB technique is studied for the first time." — LB-2024, Intro
> "Using MD, in this work we perform heterogeneous bubble growth simulations of nanoscale vapour bubbles." — Sullivan-2023, Intro
> "In the present study, Langmuir Blodgett (LB) technique is combined with AFM, to visualize the imprints of NBs on anionic, cationic and zwitterionic lipid films deposited on glass-slide substrates." — LB-2024, Intro
> "Molecular dynamics (MD) simulations offer a powerful tool for obtaining such insight." — Kubelka-JCIS, Intro

`In this work/study/research` opens 6+ sentences per paper — it is the corpus's normal aim marker,
not a tic. `Here, we ...` is used for the sharpest single claim.

### Stating the hypothesis (JCIS structured style)
`We hypothesize that X, but Y.`

> "We hypothesize that a small amount of oil stabilizes the NBs, but bulk oil causes NB dissolution due to higher solubility of the gas in oil." — Kubelka-JCIS, Abstract

---

## 3. Methods

### Materials and provenance
`X (purity, supplier) was used as the Y.` / `X (supplier, country) was used as the solvent in all experiments.` / `X was used as the gas source for Y.`

> "High-purity heptane (≥99%, Sigma-Aldrich) was used as the model oil." — Kubelka-JCIS, Methods
> "Nitrogen (Airgas, 99% purity) was used as the gas source for the NB generation." — Khairy-2025, Methods
> "NBs were generated using a commercial NB generator (Moleaer, Inc.)." — Kubelka-JCIS, Methods
> "All stock solutions and nanobubble suspensions were prepared using DI water." — Ma-2022, Methods

### Procedure (passive, past)
The corpus runs `was/were` + past participle at 4.29 per 1,000 words. Methods is where passive
voice is correct and expected: the agent is irrelevant, the operation is the point.

> "After generation, NB solutions were collected and stored in 250 mL glass bottles." — Khairy-2025, Methods
> "Measurements were performed under ambient conditions using a standard cell (Malvern Instruments)." — Khairy-2025, Methods
> "The zeta potential was calculated by the Smoluchowski model [69]." — Ma-2022, Methods
> "Surface pressure of monolayers was measured with the use of a platinum Wilhelmy plate." — LB-2024, Methods
> "Scans of AFM were performed in order to collect the surface topography of the deposited films." — LB-2024, Results
> "The simulation was performed using periodic boundary conditions (PBC) in all three directions." — Abolfath-2024, Results
> "The simulation data were analyzed using Gromacs utility programs and MATLAB scripts written in house." — Kubelka-JCIS, Methods

### Replication and controls
`To confirm the reproducibility of the results, N measurements were performed for each scenario.` / `The measurement was repeated N times on M samples.` / `Only X without detectable levels of Y were used.`

> "To confirm the reproducibility of the results, two measurements were performed for each scenario." — Kubelka-JCIS, Methods
> "The measurement was repeated five times on two samples." — Ma-2022, Methods
> "For each tested sample, the measurement was repeated six times with 10 s delay between them." — Ma-2022, Methods
> "Only the aqueous solutions without detectable levels of contaminant were used." — Ma-2022, Methods
> "All measurements were made 30 min after the nanobubble samples were generated." — Ma-2022, Methods
> "The solution conductivity was measured to confirm the accuracy of the salt concentration." — Hewage-2021, Intro

### Owning a modelling choice
`X was invoked to account for Y by ...` / `It was assumed that X could be used without significant error.` / `In this research, X is assumed to equal Y.` / `To avoid confusion between the two, X is referred to as Y.`

> "Electronic continuum correction (ECC) was invoked to account for water polarizability by scaling all ion charges by 0.75 [46]." — Kubelka-JCIS, Methods
> "Therefore, it was assumed that Smoluchowisk's approximation could be used without significant error." — Meegoda-2019, Methods
> "In this research, the thickness of the Stern layer is assumed as equal one hydrated ion radius." — Meegoda-2019, Intro
> "To avoid confusion between the two, it is often referred to as a non-evaporating layer (NEL) [23]." — Sullivan-2023, Intro

Every simplifying assumption in the corpus is stated as a decision with a reason attached. An
unexplained assumption is what a referee attacks first.

### Declaring a scope restriction inside Methods
`For X, the range was restricted to between A and B due to Y.`

> "For the direct generation experiments, the pH range was restricted to between 4 and 10 due to equipment limitations, as extreme pH values may cause potential damage to the system components." — Khairy-2025, Methods

---

## 4. Results

### Pointing at evidence
The corpus uses 176 distinct figure-pointing constructions. Vary them; do not open six consecutive
paragraphs with "Figure N shows".

`Figure N presents X.` / `The results are summarized in Figure N and in Table N.` / `X is shown in Figure N.` / `The corresponding distributions are plotted in Figure N.` / `A typical case is shown in Fig. N.` / `In Fig. N(a), we illustrate X.` / `The AFM image and the line profile are shown in Fig. N.` / `This resulted in N experimental sets, as summarized in Table N.` / `X is illustrated in Fig. N.`

> "Figure 5 presents the time progression of the NB dissolution." — Kubelka-JCIS, Results
> "The results are summarized in Figure 3 and in the SI, Table S1." — Khairy-2025, Results
> "This resulted in seven experimental sets, as summarized in Table 1." — Khairy-2025, Methods
> "The size probability distribution function from DLS is plotted in Figure 1b." — Zhang-2016, Results
> "A typical case is shown in Fig. 1(d)." — Ma-2022, Results
> "In Fig. 2(a), we illustrate the typical diameter distribution of bulk nanobubbles generated in aqueous solutions with pH ranging from 3 to 12." — Ma-2022, Results
> "The formation mechanism of NB imprints on the ODA film is illustrated in Fig. 10." — LB-2024, Results
> "The results for all samples are summarized in Fig. 4." — Ma-2022, Results

### Reporting a number
`X was higher by about N units.` / `declined from ~A to ~B` / `the typical X ranged from A to B` / `A and B were X and Y, respectively` / `which is lower than the value of N measured in experiment`

> "The surface tension of the 1.2 M NaOH solution, however, was higher by about 4 mN/m." — Jungwirth-2006, Intro
> "If the density of the lighter particles is assumed as the gas density, the typical particle (nanobubble) diameter ranged from 100 to 200 nm." — Yasui-2019
> "The model predicts a critical rupture thickness of 75 nm, which is lower than the value of 110 nm measured in experiment." — Yoon-2000, Conclusions
> "Fig. 1c and d show the zeta potential just after generation and after 1 week, respectively." — Hewage-2021, Results
> "The simulation shows the shock front propagates initially with a speed higher than the speed of sound in water (1450 m/s)." — Abolfath-2024, Results
> "In particular, the solubility of nitrogen in hydrocarbons is several orders of magnitude higher than that in water [32]." — Kubelka-JCIS, Intro

`respectively` is the corpus's standard device for pairing lists with values — used heavily, and
correctly, always with matched ordering.

### Describing a trend
`X decreased with an increase in Y and a decrease in Z.` / `The addition of X leads to a reduction in Y and a rise in Z.` / `a similar trend is observed for both: X decreases slightly with the increase of Y` / `there appears to be a maximum at X for both A and B`

> "However, the magnitude of the zeta potential decreased with an increase in concentration and a decrease in pH value." — Hewage-2021, Results
> "The addition of any salt leads to a reduction in bubble number density and a rise in the mean bubble diameter." — Hewage-2021, Results
> "Nevertheless, a similar trend is observed for both: db decreases slightly with the increase of bubble concentration." — Ma-2022, Results
> "In addition, there appears to be a maximum at pH 8 for both high- and low-concentration samples." — Khairy-2025, Results

### Moving from one experiment to the next
`Having established X, we next examined Y.` / `To test whether X, we ...` / `We now turn to explore X by monitoring Y over a Z period.` / `Finally, we explore X.` / `Turning to X, ...`

> "We now turn to explore the stability of nanobubbles that exist in electrolytic-aqueous solutions with various pH by monitoring their properties (N b ; db and f) over a 24-h period." — Ma-2022, Results
> "Finally, we explore the properties of the oil layers with the dissolved N2, as would follow after either the NB dissolution (Figures 4, 5) or fusion with the oil (Figure 6)." — Kubelka-JCIS, Results
> "We now address whether or not the nanobubbles in suspension interact with the Au nanoparticles in suspension." — Zhang-2016, Results

### Light interpretation (the ceiling inside a pure Results section)
`consistent with X` / `indicating that X` / `suggesting that X` / `which is consistent with Y` / `again paralleling Y` / `This indicates that X.`

> "Again, the size is consistent with the NTA measured bulk NBs diameter." — LB-2024, Results
> "This finding indicates the absence of strong attraction between the two particles, which is contradictory to the predictions from the classical DLVO theory." — JCIS-2015, Results
> "This indicates that for highly charged bubbles equating the zeta potential with the surface potential may not be permit table." — Ma-2022, Results
> "This parallels earlier experimental results [4,5], and is consistent with the similar lowering of the water surface tension [29–31]." — Kubelka-JCIS, Results

---

## 5. Discussion

### Proposing a mechanism
`This is likely the result of the competition between two processes: first, X, and second, Y.` / `We therefore interpret X as Y.` / `We interpret this new peak as X.` / `The energy cost for X depends on Y and is governed by Z.` / `X can be understood intuitively: Y.` / `At the basis of this phenomenon is X.`

> "We interpret this new peak as a combination/agglomeration of nanobubble and nanoparticle." — Zhang-2016, Results
> "This can be understood intuitively: for such cavitation-based birth, more energy creates more nucleation sites in bulk water." — Ma-2022, Results
> "The energy cost for the bubble formation depends on the interfacial area and is governed by the bubble's surface tension." — Hewage-2021, Results
> "The balance between attraction and repulsion depends on the surface charge characteristics that are governed by material type and solution chemistry." — JCIS-2015, Intro
> "The large drop in energy upon ion hydration is thus the reason for the preference of the ions for the aqueous bulk." — Jungwirth-2006, Intro
> "Consequently, the stability of bulk nanobubbles is significantly improved by a mechanism of accumulation of charge at the interface." — Alheshibri-2021, Intro

### Attributing an observation
`X may be attributed to Y.` / `X can be attributed to the fact that Y.` / `This is due to Z.` / `X may arise from an interplay between Y and Z.` / `X is principally attributed to Y.`

> "The formation of holes may be attributed to the special structure of DPPC" — LB-2024, Results
> "The discrepancy may be attributed to the hydrodynamic fluctuation of wetting films." — Yoon-2000, Conclusions
> "The greater NB size at this pH may arise from an interplay between the NB surface F" — Khairy-2025, Results
> "This is due to no firmly attached water molecule layer, unlike in clay/silica particles." — Meegoda-2019, Intro

### Isolating the governing variable
`Comparing X at a common Y isolates the role of A, whereas comparing Z at matched W isolates the role of B.` / `Consequently, it is A, rather than B or C, that governs D.` / `This means that X does not play a major role in Y.`

> "This means that pre-existing nanobubbles do not play a major role in nanoparticle−nanobubble interactions." — Zhang-2016, Conclusions
> "This conclusively rules out any electrostatic mechanism in those particular systems." — Attard-2003, Intro
> "Therefore, it is unlikely that electrical forces are responsible for the rupture of wetting films." — Yoon-2000, Intro

### Agreeing with prior work
`Our results are consistent with X [refs].` / `X is in good agreement with the data reported previously [ref].` / `in reasonable agreement with` / `Those findings are consistent with the results presented here.` / `A agrees well with those computed from B`

> "The interaction energies as calculated using the classical DLVO are in good agreement with the attachment characteristics observed by zeta potential distribution analysis." — JCIS-2015, Results
> "Over the pH range from 2.5 to 10.5, the alumina particles showed a clear isoelectric point (iep) of pH 9.4, in good agreement with the data reported previously [41]." — JCIS-2015, Results
> "Those findings are consistent with the experimental results presented here." — Hewage-2021, Conclusions
> "Hewage and Meegoda [33] showed that the internal pressures from the equation of state agree well with those computed from the stress tensor data." — Kubelka-JCIS, Results
> "The NB decay due to oil is consistent with our previous experiments which utilized layers of NBs and oil without agitation [4]." — Kubelka-JCIS, Results
> "These changes are consistent with the coalescence and Ostwald ripening,[ref] whereby the gas from the smaller NBs diffuses through the solution and is absorbed by the larger NBs." — Khairy-2025, Results

**Calibration point.** The corpus distinguishes *consistent with* from *supports* from *confirms*
and does so deliberately, most explicitly here:

> "The organic material therefore stabilizes the NB, and in this sense our results are consistent with the aspects of one of the leading theories for the stabilization of NBs - the dynamic equilibrium model [23,28]." — Kubelka-JCIS, Results

"consistent with aspects of" is the honest formulation when a result is compatible with a theory
but does not test it. Prefer it to "supports" whenever the experiment could not have falsified the
theory.

### Disagreeing with prior work
`This trend contrasts sharply with that of X [refs], where Y.` / `This contrasts with the findings of X et al., who observed Y.` / `This is in contrast to X, where Y.` / `in qualitative disagreement with Z` / `The only consequence of this discrepancy would be W, not V.`

> "This contrasts with the findings of Nirmalkar et al.,[ref] who observed different behavior in their experimental ..." — Khairy-2025, Results
> "This is in contrast to the NBs generated directly in saline solutions, where the generation time and thus the initial NB concentration had little impact on the NB stability (Figure 8a)." — Khairy-2025, Results
> "The only consequence of this discrepancy would be quantitative overestimation of the rate and, possibly, relative contribution of this process." — Kubelka-JCIS, Results
> "Indeed, they show a disagreement of a factor of two with experimental results." — Sullivan-2023, Intro
> "On the other hand, it seems at odds with the distributions in Figure S9b, where the peaks of heptane and N2 at the water edge align (at z ≃ 9 nm)." — Kubelka-JCIS, Results

The last two moves are the mark of a confident writer: name the disagreement, then bound its
consequences. "The only consequence of this discrepancy would be X, not Y" defuses a referee
objection before it is raised.

### Confronting expectation against observation
`While X may indeed cause Y, there is no detectable Z.` / `Conceptually, it is also not clear why X.` / `It does not seem plausible that X.` / `there seems to be no obvious reason why X`

> "While the excess heptane at the interface (Figures 2b, 3b) may indeed cause the depletion of water from the NB surface, there is no detectable N2 accumulation around the heptane." — Kubelka-JCIS, Results
> "Conceptually, it is also not clear why organic material, albeit hydrophobic, should lead to any additional depletion of water in its vicinity over likewise hydrophobic N2." — Kubelka-JCIS, Results
> "However, it is unclear to what extent the level of nanomaterials affects the formation of armored nanobubbles." — Alheshibri-2021, Intro

### Hedging (choose the rung the evidence earns)

```
surmise < speculate < suggest < indicate < imply < is consistent with
        < support < show < establish < demonstrate < confirm
```

Corpus rates: `may/might/could` 2.15/1,000; `suggest*` 0.91; `indicat*` 0.79; `show(n)` 3.04;
`demonstrat*` 0.41; `confirm*` 0.36. Hedges outnumber strong claims roughly two to one.

`may be X` / `is likely to X` / `appears to X` / `seems to X` / `presumably` / `we can only surmise that X` / `We speculate that X.` / `it is plausible to assume that X` / `cannot be ruled out` / `there is a good possibility that X`

> "We speculate that this is the result of the missing surface charge needed for their stabilization." — Ma-2022, Results
> "The reason for the reduced IFT, however, remains unclear, and we can only surmise that it is a consequence of partial separation of weakly miscible phases: N2, oil, and water." — Kubelka-JCIS, Conclusions
> "Thus, it is plausible to assume that the TS's are instantaneously created following the passage of charged particles." — Abolfath-2024, Results
> "However, there is a good possibility that those negative charges may be (HCO3)− ions due to dissolved CO2 in the air." — Meegoda-2019, Results
> "Presumably, the more highly charged bubbles are prevented from coalescing and growing laterally." — Attard-2003, Intro
> "The effect is relatively small, however, and seems to vanish as more organic material is added (Figure 2a)." — Kubelka-JCIS, Results
> "Nevertheless, the segregation of ions at the air/solution interface seems to be at least semiquantitatively described." — Jungwirth-2006, Intro
> "One possibility may be that the chemical potential of the gas is reduced by van der Waals interactions with the solid." — Attard-2003, Intro

`confirm` is reserved in the corpus for direct verification — a control that came out clean, a
measurement that closed a loop. Do not use it for "our data are compatible with our idea".

### Admitting a limitation without collapsing
`X may also contribute to Y [ref], but we cannot directly quantify this effect.` / `Further investigation is necessary to explain X.` / `A systematic investigation of X falls outside the scope of the present study.` / `Unfortunately, the current study was not able to discern X.`

> "Bursting of the NBs upon colliding with the oil (Figure 6) may also contribute to the IFT reduction [31], but we cannot directly quantify this effect." — Kubelka-JCIS, Results
> "Further investigation is necessary to explain this phenomenon." — Kubelka-JCIS, Conclusions
> "Unfortunately, the current study was not able to discern this latter attachment mechanism." — JCIS-2015, Results
> "While our results have provided prima facie evidence of ion adsorption stabilizing bulk nanobubbles, more experimental validation is needed to test the nanobubbles generated by other methods." — Ma-2022, Results
> "It is clear that further work is required to more fully understand these systems, in particular on the problem of nanobubble nucleation and nanobubble–nanoparticle interactions at the submicron scale." — Alheshibri-2021, Abstract

Note the shape: the limitation is stated in one clause and bounded in the next. It is never a
paragraph of apology, and it never appears without the surrounding claim still standing.

### Plain declarative after qualification
After a hedged passage, the corpus lands on a short unhedged sentence. This rhythm — long
qualified sentence, then a short flat one — is what makes the argument feel earned.

> "By contrast, the bulk oil depletes the NBs, as indicated by both experiments and simulations." — Kubelka-JCIS, Conclusions
> "We have shown that bulk nanobubble solutions interact with nanoparticles." — Zhang-2016, Conclusions

---

## 6. Implications (hedged extrapolation)

`X is expected to Y.` / `X could enable Y.` / `The ability of X to Y opens the door for Z.` / `These findings have important implications for W.` / `X may open up an in-depth understanding of Y.`

> "The ability of nanobubbles to interact with nanoparticles opens the door for enhanced scavenging through different separation technologies, as well as surface modification." — Zhang-2016, Conclusions
> "Nanobubbles thus provide a potential cleaning mechanism that can be free from detergents and other chemical agents." — Zhang-2016, Conclusions
> "Since bulk NBs have a much larger volume compared with the mo lecular size of ODA, the presence NBs at the interface is expected to give a large right shift of the isotherm." — LB-2024, Results
> "This suggests that while salting-out effects may enhance initial nucleation at moderate to high salinity, the long-term electrostatic screening and EDL compression ultimately reduce the long-term NB stability more severely as the salt content increases." — Khairy-2025, Results

Application claims stay on the low rungs throughout: *may*, *could*, *is expected to*, *opens the
door for*. A laboratory result is never upgraded to a field claim.

---

## 7. Conclusions

`In summary, we have reported X.` / `We have shown that X.` / `Overall, these findings provide W, emphasizing X and demonstrating Y.` / `In this respect, the results are consistent with Z [refs].` / `For the former, the results suggest X.`

> "In summary, we have reported an extensive experimental study to probe the stability of bulk nanobubbles in aqueous electrolyte solutions with various levels of pH and ionic strengths." — Ma-2022, Conclusions
> "In summary, nanobubbles in pure water are negatively charged, and with increased concentration of electrolyte, the magnitude of the zeta potential decreases." — Hewage-2021, Conclusions
> "Overall, these findings provide important lessons for utilizing NBs in practical applications, emphasizing the importance of generation conditions over postgeneration adjustments and demonstrating, overall, that neutral pH and low salt environments appear optimal for NB utilization." — Khairy-2025, Conclusions
> "In this respect, the results are consistent with the dynamic equilibrium theory of Yasui [23,28], according to which the NBs are stabilized by hydrophobic material covering 50% or more of their surface." — Kubelka-JCIS, Conclusions
> "For the former, the results suggest that hydrocarbon impurities may contribute to NB stabilization by lowering interfacial tension (IFT) with the surrounding water and, consequently, internal pressure [23]." — Kubelka-JCIS, Conclusions
> "In summary, NBs generated under high salt conditions, despite initially appearing more stable, experience faster degradation compared to the addition of salt after the generation." — Khairy-2025, Results

Note that `In summary` is also used *mid-paper*, to close a long Results subsection before moving
on. That is a good habit and it is under-used in most drafts.

### Leaving something open
`The reason for X, however, remains unclear.` / `X is identified as an important direction for future work.` / `Moreover, future experiments should strive to reveal X.`

> "Moreover, future experiments should strive to reveal the underlying mechanism of thermodynamic stability of isolated nanobubbles." — Ma-2022, Results
> "Thus, all that remains to be explored are the structural and dynamical consequences of specific interactions between ions and water molecules within the inhomogeneous interfacial region." — Jungwirth-2006, Intro

---

## 8. Abstract

Two shapes appear in the corpus.

**Structured (JCIS Hypothesis / Methods / Findings)** — each heading gets 2–4 sentences.
The Hypothesis block states the application context, then the tension, then a falsifiable claim:

> "We hypothesize that a small amount of oil stabilizes the NBs, but bulk oil causes NB dissolution due to higher solubility of the gas in oil." — Kubelka-JCIS, Abstract
> "Molecular dynamics (MD) simulations were used to uncover the underlying mechanisms of oil-NB interactions." — Kubelka-JCIS, Abstract

**Unstructured (Langmuir / PLoS / Chem. Rev.)** — the Cuntz-2010 abstract is the model of the form
and worth reading in full for its architecture: importance → gap → `Here we propose` → method →
what it yields → what it means. Its gap sentence is one line:

> "Nevertheless, no formalism has yet been described which can capture the general features of neuronal branching." — Cuntz-2010, Abstract

and its aim sentence immediately answers it:

> "Here we propose such a formalism, which is derived from the expression of dendritic arborizations as locally optimized graphs." — Cuntz-2010, Abstract

The `Nevertheless, no X has yet been described. Here we propose such an X ...` pairing is the
tightest gap-to-aim transition in the corpus. Steal the shape, not the words.

---

## 9. Response to reviewers

The corpus contains one full referee correspondence (Kubelka-JCIS). Its register: thank, then
answer with data, then state exactly what changed in the manuscript.

- We sincerely thank the Editor and the Reviewers for their careful examination of our manuscript and for the constructive comments, which have substantially improved the quality of the work.
- We thank the reviewer for the suggestion. We have conducted a new set of experiments and ...
- We thank the Reviewer for raising this point, which allows us to clarify X and to reinforce it with additional data.
- We thank the reviewer for this sharp and valid observation. We agree that X. The statement has been revised to correctly attribute ...
- X was advanced not as an unsupported assumption but as a hypothesis grounded in both the literature and our own measurements.
- We recognize, nevertheless, that X, so that A was not isolated as the governing variable from those experiments alone. To show that A is indeed the key factor, we performed an additional series of experiments ...
- We respectfully disagree, however, that X. The mechanistic explanation presented in the manuscript is directly grounded in and fully consistent with the quantitative data already provided.
- [For a scenario the referee proposes:] A quantitative argument shows the effect is negligible: [back-of-envelope estimate with every parameter deliberately exaggerated in the referee's favour].
- [For an unexplained feature:] We examined each of the known temperature-dependent properties [each with its magnitude over the range]; all vary smoothly and monotonically, so none can account for the abrupt threshold. To confirm the feature is genuine rather than an artifact, we repeated the measurement (Figure R1) ... We have therefore chosen to retain the candid statement that we have no definitive explanation, while now framing it explicitly as an open question.
- A systematic investigation of X falls outside the scope of the present study and is identified as an important direction for future work. [plus one acknowledging sentence added to the manuscript]
- The following additions were made to the text: (Section N, page N) "..."
- The apparent conflict arose from extrapolating a [different-regime] literature result to our system; to remove the inconsistency, we have deleted the corresponding passage and added [a model/figure] to the SI.

An observation from that correspondence worth generalising: the authors' strongest replies concede
the referee's *premise* and then show it does not reach the conclusion. They never simply assert
that the referee is wrong.

---

## 10. Frames that do not appear in this corpus

Do not use these. Each was searched for and found at or near zero frequency in 76,000 words of
published prose in this field.

- "In recent years, X has attracted significant/considerable attention."
- "It is important to note that ..." (1 occurrence) — use `Note that`
- "It is worth noting that ..." (3) — use `Note that`
- "Additionally, ..." (4) — use `In addition` or nothing
- "plays a pivotal role" (1 use of *pivotal* anywhere)
- "This study aims to shed light on ..."
- "X holds great promise for ..."
- "Our findings underscore the importance of ..." (1 use of *underscore*)
- "delve into", "the realm of", "the landscape of", "a robust framework" — **zero** occurrences
- "This paper is organized as follows" — absent; the corpus signposts locally instead
- Any sentence of the form "Not only X, but also Y" used for emphasis rather than genuine addition
- Tricolons for rhythm ("faster, cheaper, and more reliable") where only two items are real
