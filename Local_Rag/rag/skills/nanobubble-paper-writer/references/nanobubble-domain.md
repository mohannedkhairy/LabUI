# Nanobubble Domain Primer

Purpose: make the prose technically fluent and the framing correct. This primer supplies background knowledge, standard terminology, the live controversies, and the canonical reference list. **Every specific number or citation taken from this file must still appear on the draft's verification list**; the user confirms against the original sources before submission. Where this primer and the user's sources disagree, the user's sources win, and the disagreement is flagged.

## 1. Definitions and typical scales

- **Surface (interfacial) nanobubbles**: gas-filled spherical caps at solid–liquid interfaces, first imaged by AFM around 2000. Typical heights of order 10–100 nm and lateral extents of order 100 nm to 1 μm, so they are far flatter than a hemisphere. Their nanoscopic contact angle is anomalous relative to the macroscopic Young angle; state the measurement convention explicitly whenever quoting an angle (through the gas vs. through the liquid), since both conventions circulate.
- **Bulk nanobubbles** (in parts of the literature, "ultrafine bubbles", the ISO term): spherical gas domains dispersed in the liquid bulk, diameter below 1 μm and typically reported around 100–200 nm, with number densities commonly in the 10^7–10^9 mL^-1 range and reported lifetimes of days to months.
- Common generation routes: hydrodynamic cavitation, acoustic (ultrasonic) cavitation, solvent exchange (ethanol–water is standard for surface nanobubbles), electrolysis, pressurization–depressurization cycling, membrane/porous injection, and spontaneous formation on mixing water with organic solvents (the last being the most artifact-prone; see §4).
- Reported properties frequently invoked in applications: negative zeta potential in pure water near neutral pH (values of roughly −20 to −40 mV are commonly reported), high gas–liquid interfacial area per volume, and claimed enhancement effects in flotation, cleaning, water treatment, aquaculture, and agriculture. Application claims vary widely in quality; cite specific measured effects, not the applications literature wholesale.

## 2. The stability paradox (the field's central tension)

Two pieces of classical physics make long-lived small bubbles surprising:

- **Young–Laplace**: the excess internal pressure is ΔP = 2γ/R for a spherical bubble of radius R and surface tension γ. With γ ≈ 0.072 N m^-1 for the air–water interface, a bubble of R = 100 nm carries ΔP ≈ 1.4 MPa, and R = 50 nm carries ≈ 2.9 MPa, i.e., tens of atmospheres.
- **Epstein–Plesset (1950)**: this elevated internal pressure drives gas out by diffusion; the predicted complete dissolution time for a sub-micron air bubble in air-saturated water is of order 1–100 μs.

Observed persistence over hours to months therefore contradicts the classical expectation by more than ten orders of magnitude. Every serious paper in the field positions itself relative to this paradox, and an Introduction that states it crisply, with the equation and an order-of-magnitude number, signals competence immediately.

## 3. Stability mechanisms: what is settled and what is not

**Surface nanobubbles: broadly settled.** The accepted resolution is **contact-line pinning combined with gas oversaturation** (Liu & Zhang 2014; Lohse & Zhang 2015a): pinning of the three-phase line at surface heterogeneities blocks the lateral shrinkage that dissolution would require, and a modest oversaturation ζ > 0 of dissolved gas balances the Laplace-driven outflux, yielding a stable equilibrium with sin θe = ζ L / Lc, where θe is the equilibrium contact angle, L the pinned footprint diameter, and Lc = 4γ/P0 a capillary length scale (P0 the ambient pressure). Molecular dynamics and later thermodynamic analyses support this picture. The earlier **dynamic-equilibrium** proposal (Brenner & Lohse 2008, gas influx at the contact line balancing outflux) and the **contaminant-film** proposal (Ducker 2009, an adsorbed film lowering surface tension and blocking transport) are now mainly of historical and cautionary interest, though contamination remains relevant as an experimental artifact. Note also that interfacial nanobubbles were shown to be *leaky* (German et al. 2014), which killed explanations based on an impermeable shell for pure systems.

**Bulk nanobubbles: not settled.** Candidate mechanisms, none consensus:

- **Electrostatic stabilization**: interfacial charge (commonly attributed to preferential OH^- adsorption in the field's discussions) opposing shrinkage and hindering coalescence; the quantitative sufficiency of measured zeta potentials is disputed.
- **Interfacial enrichment**: accumulation of ions or trace organics at the interface reducing the effective surface tension and hence the Laplace driving force (e.g., Zhang, Guo & Zhang 2020).
- **Diffusive shielding in clusters**: neighboring bubbles raising the local dissolved-gas concentration and slowing each other's dissolution (Weijs, Seddon & Lohse 2012); relevant at high number densities.
- **Stability analyses of charged bubbles** showing parameter windows in which shrinkage is arrested (Tan, An & Ohl 2020, "How bulk nanobubbles might survive").
- **Interfacial/thermal-fluctuation and skin models** of various kinds, more recent and less tested.

When writing, present these as candidates, attribute them, and never let the prose imply a resolved mechanism for bulk nanobubbles.

## 4. The existence controversy (bulk nanobubbles)

The sharpest dispute in the field is whether the long-lived nano-entities detected in "nanobubble water" are gas bubbles at all, or solid/supramolecular contaminant particles.

- The skeptical case: standard sizing techniques (NTA, DLS) count scatterers of any composition; organic contaminants at trace levels can produce stable nano-entities; ethanol–water mixing was shown to generate non-gaseous nanoparticles (Häbich et al. 2010; Alheshibri & Craig 2019); gas supersaturation by chemical reaction was reported not to produce detectable bulk nanobubbles (Alheshibri, Jehannin, Coleman & Craig 2019); and organic contamination was shown to matter directly (Eklund & Swenson 2018). Density-sensitive techniques such as resonant mass measurement, which can distinguish buoyant from dense particles, have been central to the skeptical program.
- The affirmative case: multi-technique batteries of indirect evidence (response to degassing, freeze–thaw, internal-pressure arguments, absence of signal in blanks) supporting a gaseous interior for entities produced by cavitation in clean systems (Nirmalkar, Pacek & Barigou 2018; Jadhav & Barigou 2020).
- The exchange to know: Jadhav & Barigou (Langmuir 2020) claimed their combined results provide conclusive proof; Rak & Sedlák (Langmuir 2020) published a Comment arguing the techniques lacked the sensitivity for that conclusion; Jadhav & Barigou (Langmuir 2021) responded, notably recalibrating the claim to "strong evidence" while noting that no direct technique combining spatial resolution with chemical sensitivity exists for these entities. That recalibration is itself a lesson in claim strength this skill should transmit.

Writing consequences: bulk-nanobubble papers must describe controls that discriminate gas from non-gas, must weigh the contamination alternative explicitly in the Discussion, and must calibrate identity claims to the indirectness of the evidence. Reviewers from either camp will read for exactly this.

## 5. Standard symbols and terms (keep consistent)

R (radius), γ (surface tension), ΔP (Laplace pressure), P0 (ambient pressure), ζ (gas oversaturation, ζ = c∞/cs − 1, with c∞ the bulk dissolved-gas concentration and cs saturation; beware collision with ζ-potential, define both explicitly if both appear), θ (contact angle, convention stated), L (pinned footprint), Lc = 4γ/P0, D (diffusion coefficient), kH (Henry's law constant). Terms: "nanobubble" vs. "ultrafine bubble" (ISO 20480 family uses the latter); "number density" (not "concentration" for counts); "zeta potential" with pH and ionic strength; "ultrapure water" with resistivity (18.2 MΩ·cm at 25 °C is the standard specification).

## 6. Canonical reference list (verify all details against the originals before citing)

Foundations and reviews:
- Epstein, P. S.; Plesset, M. S. On the stability of gas bubbles in liquid–gas solutions. J. Chem. Phys. 1950, 18, 1505–1509.
- Lohse, D.; Zhang, X. Surface nanobubbles and nanodroplets. Rev. Mod. Phys. 2015, 87, 981–1035. (The field's benchmark of expository writing.)
- Alheshibri, M.; Qian, J.; Jehannin, M.; Craig, V. S. J. A history of nanobubbles. Langmuir 2016, 32, 11086–11100.
- Zhou, L.; Wang, S.; Zhang, L.; Hu, J. Generation and stability of bulk nanobubbles: a review and perspective. Curr. Opin. Colloid Interface Sci. 2021, 53, 101439.
- Tan, B. H.; An, H.; Ohl, C.-D. Stability of surface and bulk nanobubbles. Curr. Opin. Colloid Interface Sci. 2021, 53, 101428.

Surface nanobubble stability:
- Brenner, M. P.; Lohse, D. Dynamic equilibrium mechanism for surface nanobubble stabilization. Phys. Rev. Lett. 2008, 101, 214505.
- Ducker, W. A. Contact angle and stability of interfacial nanobubbles. Langmuir 2009, 25, 8907–8910.
- Liu, Y.; Zhang, X. A unified mechanism for the stability of surface nanobubbles: contact line pinning and supersaturation. J. Chem. Phys. 2014, 141, 134702.
- German, S. R.; Wu, X.; An, H.; Craig, V. S. J.; Mega, T. L.; Zhang, X. Interfacial nanobubbles are leaky: permeability of the gas/water interface. ACS Nano 2014, 8, 6193–6201.
- Lohse, D.; Zhang, X. Pinning and gas oversaturation imply stable single surface nanobubbles. Phys. Rev. E 2015, 91, 031003(R).
- Maheshwari, S.; van der Hoef, M.; Zhang, X.; Lohse, D. Stability of surface nanobubbles: a molecular dynamics study. Langmuir 2016, 32, 11116–11122.

Bulk nanobubbles, existence and stability:
- Häbich, A.; Ducker, W.; Dunstan, D. E.; Zhang, X. Do stable nanobubbles exist in mixtures of organic solvents and water? J. Phys. Chem. B 2010, 114, 6962–6967.
- Weijs, J. H.; Seddon, J. R. T.; Lohse, D. Diffusive shielding stabilizes bulk nanobubble clusters. ChemPhysChem 2012, 13, 2197–2204.
- Nirmalkar, N.; Pacek, A. W.; Barigou, M. On the existence and stability of bulk nanobubbles. Langmuir 2018, 34, 10964–10973.
- Nirmalkar, N.; Pacek, A. W.; Barigou, M. Interpreting the interfacial and colloidal stability of bulk nanobubbles. Soft Matter 2018, 14, 9643–9656.
- Eklund, F.; Swenson, J. Stable air nanobubbles in water: the importance of organic contaminants. Langmuir 2018, 34, 11003–11009.
- Alheshibri, M.; Craig, V. S. J. Generation of nanoparticles upon mixing ethanol and water: nanobubbles or not? J. Colloid Interface Sci. 2019, 542, 136–143.
- Alheshibri, M.; Jehannin, M.; Coleman, V. A.; Craig, V. S. J. Does gas supersaturation by a chemical reaction produce bulk nanobubbles? J. Colloid Interface Sci. 2019, 554, 388–395.
- Jadhav, A. J.; Barigou, M. Bulk nanobubbles or not nanobubbles: that is the question. Langmuir 2020, 36, 1699–1708.
- Rak, D.; Sedlák, M. Comment on "Bulk nanobubbles or not nanobubbles: that is the question". Langmuir 2020, 36, 15618–15621.
- Jadhav, A. J.; Barigou, M. Response to "Comment on bulk nanobubbles or not nanobubbles: that is the question". Langmuir 2021, 37, 596–601.
- Tan, B. H.; An, H.; Ohl, C.-D. How bulk nanobubbles might survive. Phys. Rev. Lett. 2020, 124, 134503.
- Zhang, H.; Guo, Z.; Zhang, X. Surface enrichment of ions leads to the stability of bulk nanobubbles. Soft Matter 2020, 16, 5470–5477.
