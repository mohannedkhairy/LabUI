# The reference corpus

Everything quantitative in this skill — connective budgets, sentence-length targets, hedging
ratios, the banned-word list, and every attested exemplar in `phrase-bank.md` — was measured from
the documents below. When a rule in this skill states a number, that number came from here, not
from an impression of how scientific writing sounds.

## Composition

Twenty documents. After stripping front matter, reference lists, figure captions, table debris,
equation fragments, and publisher furniture, and after de-duplicating a manuscript that appeared
twice in one file, the mined text is **~76,000 words of running research prose in 3,059 sentences**
from the fifteen research documents, plus **~7,000 words** from five craft sources that were
analysed for rules rather than for phrases.

## Source keys

Keys used in `phrase-bank.md` exemplar attributions.

### Research corpus (mined for phrases and register statistics)

| Key | Paper |
|---|---|
| `Attard-2003` | P. Attard, *Nanobubbles and the hydrophobic attraction*, Adv. Colloid Interface Sci. **104** (2003) 75–91 |
| `Yoon-2000` | R.-H. Yoon, *The role of hydrodynamic and surface forces in bubble–particle interaction*, Int. J. Miner. Process. **58** (2000) 129–143 |
| `Jungwirth-2006` | P. Jungwirth, D. J. Tobias, *Specific Ion Effects at the Air/Water Interface*, Chem. Rev. **106** (2006) 1259–1281 |
| `JCIS-2015` | *Studying bubble–particle interactions by zeta potential distribution analysis*, J. Colloid Interface Sci. **449** (2015) 399–408 |
| `Zhang-2016` | M. Zhang, J. R. T. Seddon, *Nanobubble−Nanoparticle Interactions in Bulk Solutions*, Langmuir (2016) |
| `Meegoda-2019` | J. N. Meegoda, S. Aluthgun Hewage, J. H. Batagoda, *Application of the Diffused Double Layer Theory to Nanobubbles*, Langmuir **35** (2019) 12100–12112 |
| `Yasui-2019` | K. Yasui, T. Tuziuti, W. Kanematsu, K. Kato, *Dynamic Equilibrium Model for a Bulk Nanobubble and a Microbubble Partly Covered with Hydrophobic Material*, Langmuir |
| `Hewage-2021` | S. Aluthgun Hewage, J. Kewalramani, J. N. Meegoda, *Stability of nanobubbles in different salts solutions*, Colloids Surf. A **609** (2021) 125669 |
| `Alheshibri-2021` | M. Alheshibri, A. Al Baroot, L. Shui et al., *Nanobubbles and nanoparticles*, Curr. Opin. Colloid Interface Sci. |
| `Ma-2022` | X. Ma, M. Li, P. Pfeiffer, J. Eisener, C.-D. Ohl et al., *Ion adsorption stabilizes bulk nanobubbles*, J. Colloid Interface Sci. **606** (2022) 1380–1394 |
| `Sullivan-2023` | P. Sullivan, D. Dockar, R. Enright, M. K. Borg, R. Pillai, *The role of surface wettability on the growth of vapour bubbles*, Int. J. Heat Mass Transf. **217** (2023) 124657 |
| `LB-2024` | *The effect of nanobubbles on Langmuir-Blodgett films*, J. Colloid Interface Sci. **669** (2024) 327–335 |
| `Abolfath-2024` | R. Abolfath, N. Afshordi, S. Rahvar, A. van Duin et al., *A molecular dynamics simulation of the abrupt changes in the thermodynamic properties of water after formation of nano-bubbles / nano-cavities induced by passage of charged particles*, arXiv:2403.05880 |
| `Kubelka-JCIS` | J. Kubelka, A. Taman, M. Piri, *Effect of Oil on Stability and Properties of Aqueous Nanobubbles: Experiments and Molecular Dynamics Simulations*, J. Colloid Interface Sci. (manuscript JCIS-25-17007 R3, **including the full referee correspondence**) |
| `Khairy-2025` | **M. Khairy**, J. Kubelka, M. Piri, *The Effects of Ionic Strength and pH on Nanobubble Electrostatic Stability in Saline Solutions*, Langmuir (2025) |

The last two are house papers and carry extra weight: `Khairy-2025` is the author's own published
work and `Kubelka-JCIS` is from the same group, submitted to the same target journal, with its
reviewer replies attached. When the corpus is internally divided about a convention, follow these
two.

### Craft sources (mined for rules, not phrases)

| Key | Source | What it contributes |
|---|---|---|
| `WS-Paragraph` | *Let's burger it! The art of paragraph writing*, Writing Scientist | One idea per paragraph; the Context–Content–Conclusion (topic sentence / body / closing sentence) structure; the one-sentence topic test |
| `WS-SentenceFlow` | *How to structure sentences for a better flow in your writing*, Writing Scientist | One thought per sentence; old information in the topic position; new information in the stress position; given-new chaining |
| `WS-Precision` | *How to write precisely*, Writing Scientist | The twelve precision rules (see `paragraph-and-sentence.md`) |
| `Box-1976` | G. E. P. Box, *Science and Statistics*, J. Am. Stat. Assoc. **71** (1976) 791–799 | Parsimony as a virtue; "worry selectively"; the model-is-wrong-but-useful framing; how to be candid about a model's limits without undermining it |
| `Cuntz-2010` | H. Cuntz, F. Forstner, A. Borst, M. Häusser, *One Rule to Grow Them All*, PLoS Comput. Biol. **6** (2010) e1000877 | Abstract architecture: importance → gap → `Here we propose` → method → yield → meaning |

## Measured register profile

Everything below is from the fifteen research documents.

**Sentence length (words).** p5 = 10, p25 = 17, **median = 23**, p75 = 31, p90 = 40, p95 = 47;
mean 24.8, sd 11.2. Distribution: 17 % under 15 words, 57 % between 15 and 30, 26 % over 30.
The variance matters as much as the median — a draft whose sentences all sit at 20–25 words reads
as machine-generated even when every sentence is correct.

**Paragraph length.** Median 76 words and 4 sentences; interquartile range 39–127 words.
Single-sentence paragraphs exist but are rare; paragraphs beyond ~180 words are rarer still.

**Voice.** `we` at 3.16/1,000 words and `our` at 1.12/1,000 — first-person plural is used freely,
not avoided. `was`/`were` + past participle at 4.29/1,000 — passive is the default for methods and
observations. The corpus mixes both without embarrassment: passive for what was done, active
first-person for what was decided, interpreted, or claimed.

**Hedging.** `may`/`might`/`could` 2.15/1,000; `suggest*` 0.91; `indicat*` 0.79; `show(n)` 3.04;
`demonstrat*` 0.41; `confirm*` 0.36; `likely` 0.22; `appears`/`seems` 0.47; `presumably` 0.13.
Hedges outnumber assertions of proof roughly two to one.

**Punctuation.** Semicolon 0.97/1,000. Em dash **0.05/1,000** — four occurrences in 76,000 words.
The em dash is effectively absent from this literature; the semicolon does its job.

**Sentence openers.** The 28 most common sentence-initial words, in order: *the* (645), *in* (200),
*this* (162), *for* (102), *however* (91), *we* (91), *it* (85), *a* (59), *as* (57), *these* (44),
*to* (38), *thus* (38), *therefore* (31), *here* (27), *they* (27), *one* (26), *at* (26),
*nanobubbles* (25), *when* (24), *furthermore* (23), *if* (22), *all* (22), *moreover* (21),
*our* (21), *on* (20), *with* (20), *hence* (19), *after* (17).

Two things follow. First, roughly a fifth of sentences open with `The` and another tenth with
`This` — the corpus chains through given information constantly, exactly as `WS-SentenceFlow`
prescribes. Second, connectives account for well under 10 % of sentence openings; the overwhelming
majority of sentences begin with a noun phrase carrying old information.

## Re-mining after adding papers

The corpus is a folder of PDFs. To extend it, add PDFs and re-run the pipeline:

1. `pdftotext -nopgbrk` each PDF.
2. Re-join wrapped lines, detect section headings on raw lines *before* joining paragraphs
   (headings are short standalone lines matching `^\d?\.?\s*(Introduction|Methods|Results|Discussion|Conclusions)$`),
   truncate at the reference list, drop paragraphs that are mostly digits or mathematical symbols,
   and de-duplicate on the first 120 characters.
3. Split into sentences with an abbreviation-aware splitter (`et al.`, `Fig.`, `e.g.`, `i.e.`,
   `cf.`, `approx.`, `Ref.`).
4. Recount the marker rates in `## Measured register profile` and update the budget table in
   `phrase-bank.md` §0.
5. Pull new exemplars by rhetorical-move regex, filter for OCR cleanliness, and add only sentences
   that appear verbatim in the source.

Any exemplar added to `phrase-bank.md` must be verified verbatim against its source file before it
is trusted. Elided inline citation numbers are marked `[ref]` / `[refs]`; nothing else may be
altered inside quotation marks.
