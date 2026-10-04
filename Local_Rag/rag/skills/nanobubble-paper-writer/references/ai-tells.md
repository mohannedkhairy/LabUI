# AI Tells: The Complete Avoidance Catalogue

This is the authoritative, standalone list of vocabulary, punctuation, constructions, and tonal habits that mark prose as machine-written. It is deliberately self-contained so it can be lifted into other skills or handed to any AI agent. `house-style.md` carries a condensed version; where the two differ, this file governs.

Why it matters: reviewers and editors increasingly distrust prose carrying these fingerprints, and in science that distrust is corrosive. Large-scale analyses of the post-2022 literature (including one covering more than 15 million PubMed abstracts) identified a measurable surge in a specific set of "style words" that now function as LLM markers. Most of these tells are also simply bad technical writing (vague, unfalsifiable, promotional), so removing them makes the prose more precise, not just less suspicious. The goal is not camouflage; it is the genuine article.

## 0. What the corpus actually contains

The lists below are not impressions. Every word in the banned list was searched for across ~76,000 words of published prose from the reference corpus (see `corpus.md`). Frequencies per 1,000 words:

| Word or construction | Occurrences in 76,000 words | Rate |
|---|---|---|
| `robust`, `delve`, `realm`, `landscape`, `tapestry`, `testament`, `showcase`, `multifaceted`, `intricate`, `meticulous` | **0** | 0.00 |
| `pivotal` | 1 | 0.01 |
| `underscore` | 1 | 0.01 |
| `It is important to note` | 1 | 0.01 |
| `leverage` | 2 | 0.03 |
| `It is worth noting` | 3 | 0.04 |
| `Importantly` | 3 | 0.04 |
| em dash `—` | **4** | 0.05 |
| `Notably` | 4 | 0.05 |
| `Additionally` | 4 | 0.05 |
| `novel` | 7 | 0.09 |
| `Interestingly` | 10 | 0.13 |
| `plays a … role` | 10 | 0.13 |
| `Nevertheless` / `Nonetheless` | 16 | 0.21 |
| `Consequently` | 18 | 0.24 |
| `Moreover` | 22 | 0.29 |
| `Furthermore` | 24 | 0.32 |
| `significant(ly)` | 49 | 0.64 |
| semicolon `;` | 74 | 0.97 |
| `However` | 127 | 1.67 |
| `Thus` / `Therefore` / `Hence` | 182 | 2.40 |

Read the table as budgets. A 6,000-word manuscript sits at roughly 8 % of these totals: about ten `However`s, fourteen inference connectives, two `Moreover`s, **zero** `Additionally`s, **zero** em dashes, six semicolons. The em dash line is the sharpest single discriminator available — four instances in 76,000 words of real publication prose against the many-per-page rate typical of machine drafts.

## 1. Punctuation and format tells

- **The em-dash used as a rhythm device.** The single most recognizable visual tell. Rewrite with a comma, parentheses, a colon, or two sentences. Numeric and page ranges keep the en-dash (10–100 nm, pp. 4–7); a minus sign is a minus sign. If a draft contains more than one or two em-dashes per page, it will read as machine output regardless of anything else.
- No emoji, no exclamation marks, ever.
- No bolded inline-header lists inside running prose ("**Stability:** the bubbles were..."). Paper sections are continuous argument, not lecture notes.
- No Title-Case Headings unless the journal requires them.
- No decorative bullet lists where the journal expects prose; scientific argument is paragraphs.
- Uniform paragraph lengths and uniform sentence lengths across a whole section read as generated. Vary both deliberately; a short declarative sentence after two long ones is a feature.

## 2. Vocabulary: banned outright (figurative filler with no place in technical prose)

delve, dive into, tapestry, realm, landscape (figurative), navigate/navigating (figurative), journey (figurative), unlock, unleash, harness, leverage (buzzword; "use" or "employ"), empower, foster (figurative), bolster, endeavor, garner, showcase, spotlight, shed light on, illuminate (figurative), pave the way, underscore, testament (as in "a testament to"), game-changing, cutting-edge, groundbreaking, state-of-the-art (as praise), transformative, revolutionary, seamless, vibrant, multifaceted, holistic, paradigm shift, ever-evolving, rapidly evolving (as a curtain-raiser), myriad, plethora, akin to, amidst, burgeoning, at the forefront, in the realm of, aforementioned, elucidate (prefer "explain", "identify", "determine"), utilize (prefer "use"), plays a crucial/vital/key/pivotal role (name the role instead), cannot be overstated, holds great promise, opens new avenues, sets the stage for, next-generation (as hype).

## 3. Vocabulary: permitted only in the literal, technical sense

- *crucial, critical, vital, essential, pivotal*: only when something is genuinely necessary and the sentence says why; otherwise delete the word.
- *robust*: only in its technical meaning (a robust estimator, robust to pH variation); never generic praise.
- *significant / significantly*: reserved strictly for statistical significance (test and p-value stated) or a quantified effect. Never a synonym for "large" or "considerable". In Results this rule is absolute.
- *novel*: only when the sentence states precisely what is new.
- *comprehensive, intricate, meticulous*: prefer plain words, or describe the actual thing.
- *confirm, establish, demonstrate, prove*: top rungs of the hedging ladder; use only when the evidence is direct (see phrase-bank.md). "Conclusively demonstrates/proves" invites rebuttal; this exact overreach has drawn published Comments in the nanobubble field, and referees of the house corpus asked for the same wording to be toned down.

## 4. Intensifier inflation (the draft-stage tell)

Machine-flavored drafts pile adjectival emphasis where a number should be: *remarkable longevity, exceptional tolerance, profound effect, dramatic decrease, tremendous potential, superior stability, striking improvement, highly effective, powerful benefit, significant advancement*. The repair is mechanical and always improves the sentence: replace the intensifier with the measured comparison. Not "exceptional tolerance to high salinity" but "retained 21 × 10^6 bubbles/mL after 30 days at 10 wt% NaCl, versus complete decay of the unbuffered system within 16 days". Budget: if more than two or three intensifiers survive in a manuscript, the register has drifted. Superlatives are earned by data, one at a time.

## 5. The emphasis-adverb budget

*Interestingly, Curiously, Notably, Remarkably, Importantly, Surprisingly, Strikingly, Crucially* as sentence openers are on every LLM style-word list, and stacked they are diagnostic. The house corpus does use them, so the rule is a ration, not a ban:

- Total budget of about three per manuscript, all varieties combined.
- Each must sit on a genuinely surprising, specific, quantitative observation (a sign reversal, an unexpected coincidence of two values, a five-fold disparity), never on routine findings and never as paragraph lubricant.
- Never two in adjacent paragraphs; never the same one twice.
- Test: delete the adverb; if nothing is lost, it stays deleted. If the surprise needs announcing, consider showing it instead ("the zeta potential reversed sign, from −11 ± 2 to +17 ± 1 mV").

## 6. Constructions to avoid

- **False contrast / negative parallelism**: "It is not just X, it is Y", "This is not merely X but Y", "Not because X, but because Y", "No X. No Y. Just Z." The shape of insight without its content. (Legitimate "not only X but also Y" with real content is allowed, at most once or twice.)
- **Corporate tricolons**, especially alliterative ("fast, flexible, and future-proof"). One genuine three-item list is fine; the rhythmic triple as a default cadence is a tell.
- **Copula avoidance**: "serves as", "stands as", "acts as" (unless a true proxy relation), "represents a", "constitutes a", "featuring", "boasting". Use plain "is", "has", "shows".
- **Strings of -ing summary clauses**: "..., highlighting..., underscoring..., reflecting..., demonstrating the importance of...". Rewrite as separate assertions or cut. One participial tail per page, maximum, and only when it adds content.
- **Vague attribution**: "studies show", "research suggests", "experts believe", "it is widely accepted". Every such claim carries a specific citation or it goes.
- **Throat-clearing openers**: "In recent years, there has been growing interest in...", "In today's rapidly evolving...", "With the advent of...", "When it comes to...", "At its core...". Open with substance. ("In recent years" with a specific cited development is acceptable; as a generic curtain-raiser it is not.)
- **Hedging boilerplate**: "It is worth noting that" and "It is important to note that" are tells when used as filler. The house corpus permits "It should (also) be noted that" at most once or twice per paper, only to flag a genuine caveat (e.g., a compositional complication the study did not cover); anywhere else, state the point directly.
- **Filler connectives**: "Moreover", "Furthermore", "Additionally" used as paragraph glue, and especially stacked. A connective earns its place only when it marks a real logical move; most sentences should connect through content alone. "In order to" is "to".
- **Symmetrical hedging templates**: "While X, it is also true that Y" repeated as a reflex. Real qualification is asymmetric; say which side the evidence favors.
- **Inflated segues**: "Building on these findings...", "Against this backdrop...", "With this in mind...". Usually deletable; paragraph order already does the work.
- **Boilerplate closers**: "In conclusion", "In summary" (allowed at most once, only if the venue expects it), "Taken together" as a reflex, "the future looks bright", "only time will tell", "further research is needed" (say which research), and the promotional ending stack ("underscore the importance", "sets the stage for future research", "leveraging X for next-generation applications"). End on the last substantive finding, the sharpest open question, or the specific next experiment.
- **Over-signposting and meta-commentary**: "This section discusses...", "As mentioned above..." as a crutch, "In what follows we will...". A roadmap paragraph at the end of a long Introduction is the one sanctioned home for forward references.
- **Chatbot residue**: "Certainly", "Great question", "I hope this helps", "Here is the revised section:", addressing the reader, or any commentary about the writing itself surviving into the manuscript.

## 7. Tense and voice drift

Long machine-generated passages slide into a uniform present-tense summary gloss ("the findings demonstrate... the data reveal... this highlights..."). Keep the discipline: past tense for what this work did and found; present tense for standing facts, for what figures show, and for what the data now establish. Mixed active/passive as strong experimental papers use it; an all-passive or all-active section reads generated.

## 8. Substitution table (apply mechanically, then reread)

| Tell | Replace with |
| --- | --- |
| utilize | use |
| elucidate | explain / identify / determine |
| leverage (v.) | use / employ / exploit (only if literal) |
| showcase / spotlight | show / report |
| underscore / highlight (rhetorical) | show; or delete and let the fact stand |
| shed light on | explain / clarify / constrain |
| prior to / subsequent to | before / after |
| in order to | to |
| due to the fact that | because |
| a majority of / a number of | most / several (or the count) |
| it is worth noting that | (delete; state the point) |
| significantly (vague) | by N% / N-fold / the measured difference |
| dramatic(ally) | the number |
| exceptional / remarkable / profound | the quantitative comparison |
| plays a key role in | governs / controls / contributes N% of |
| novel | state precisely what is new |
| robust (vague) | specify: stable to what, over what range |
| — (rhythm em-dash) | comma / parentheses / colon / two sentences |

## 9. Pre-delivery scan (mechanical, do it every time)

Run every step. Steps 1–7 are pure pattern matching and take under a minute; run them as literal searches over the draft rather than by reading.

1. **Em dashes.** Search `—`. Budget for a full manuscript: 0–1. Rewrite each with a comma, parentheses, a colon, or a semicolon.
2. **Banned vocabulary.** Search each of: `delve|realm|landscape|tapestry|testament|showcase|underscore|pivotal|robust|holistic|multifaceted|intricate|meticulous|leverage|utilize|elucidate|shed light|pave the way|groundbreaking|cutting-edge|game-chang|transformative|seamless|myriad|plethora|burgeoning|at the forefront|holds great promise|opens new avenues|cannot be overstated`. Every hit is deleted or justified as literal-technical.
3. **Filler connectives.** Count `Additionally` (target: 0), `Moreover` + `Furthermore` (target: ≤4 combined), `However` (≤10 per 6,000 words). Any two filler connectives in adjacent sentences get one of them cut.
4. **Hedging boilerplate.** Search `It is worth noting|It is important to note|It should be noted`. Target ≤1 for the whole manuscript; replace with `Note that` or state the point directly.
5. **Emphasis adverbs.** Count sentence-initial `Interestingly|Notably|Remarkably|Importantly|Surprisingly|Strikingly|Crucially|Curiously`. Budget ~3 per manuscript, each on a specific quantitative surprise, never two in adjacent paragraphs.
6. **Participial tails.** Search `, highlighting|, underscoring|, reflecting|, demonstrating|, showcasing|, emphasizing|, suggesting that the`. Cut or convert to a separate assertion. One per page maximum.
7. **Intensifiers.** Search `exceptional|remarkable|profound|dramatic|superior|striking|highly effective|tremendous|substantial improvement`. Replace each with the measured comparison.
8. **`significant`.** Every occurrence must carry a test and a p-value, or a quantified effect. Otherwise replace with the number or delete.
9. **Vague attribution.** Search `studies (have )?show|research suggests|it is widely|experts|it is generally accepted`. Each needs a named source and a citation or it goes.
10. **Sentence-length variance.** Compute the word count of each sentence in one section. The corpus profile is median 23, IQR 17–31, with 17 % under 15 words and 26 % over 30. If the draft's sentences cluster in a narrow band, break some and merge others until the spread matches.
11. **Paragraph openers.** Read only the first sentence of each paragraph in a section, in order. That sequence must tell the section's argument. If it does not, the problem is structural, not lexical.
12. **The closing test.** Read the final paragraph of every section aloud; if it could close any paper in the field, rewrite it to close only this one.
