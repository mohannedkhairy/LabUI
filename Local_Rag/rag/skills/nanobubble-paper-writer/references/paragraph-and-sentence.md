# Paragraph and sentence craft

The mechanics below are what separates prose that a referee reads once from prose a referee reads
twice. They come from three craft sources in the corpus (`WS-Paragraph`, `WS-SentenceFlow`,
`WS-Precision`) plus Box's essay on parsimony, checked against what the research corpus actually
does. Apply them at revision time, not while drafting — trying to be precise in a first draft
stalls the draft.

---

## 1. The paragraph: one idea, three parts

**One idea per paragraph.** The test is mechanical: state the paragraph's topic in a single
sentence. If no single sentence covers everything in it, either split the paragraph, or the
paragraph has no point and should be rewritten from scratch.

**Context–Content–Conclusion.** A paragraph is a burger:

- **Topic sentence** (the top bun). States the paragraph's main point or names its topic. It gives
  the reader the frame *before* the details, so complex material lands in an existing slot instead
  of being held in suspension.
- **Body** (the filling). Evidence, numbers, reasoning, citations — the actual content.
- **Closing sentence** (the bottom bun). Summarises or concludes, and hands off to the next
  paragraph. **Optional** in short paragraphs on simple points; **required** whenever the body
  presents contrasting evidence, competing explanations, or anything the reader could come away
  from with the wrong take-home.

The consequence to exploit: if every paragraph opens with a real topic sentence, the first
sentences of a section read on their own as a summary of the section's argument. Test any draft
this way. Read only the opening sentence of each paragraph. If that sequence does not tell a
coherent story, the section is structurally broken, no matter how good the individual sentences
are.

**The failure mode.** Starting with details and only arriving at the point at the end. The reader
must hold everything unassigned until the payoff, which is exactly the cognitive load a complex
research topic cannot afford. If you find a paragraph whose point lands in the last sentence, move
that sentence to the front and see whether the paragraph improves. It usually does.

**Length.** The corpus median is 76 words and 4 sentences (IQR 39–127). A paragraph past ~180
words is almost always two paragraphs.

---

## 2. The sentence: one thought, old before new

**One thought per sentence.** Do not compress two propositions into one sentence for the sake of
brevity. When the reader finishes a sentence having forgotten its beginning, split it. The corpus
median is 23 words; anything past ~40 should be inspected and usually broken in two.

**Old information in the topic position.** The first few words of a sentence set the frame the
reader uses to interpret the rest. Never open a sentence with something introduced for the first
time — the reader has to hold it, unattached, until the sentence explains it. Opening with
something already established creates the connection to the preceding text that readers experience
as flow. This is why 20 % of corpus sentences open with `The` and 5 % with `This`.

**New information in the stress position.** What comes last is what is emphasised and what is
remembered. Put the new term, the new value, the new claim at the end.

**The chaining rule that follows.** Introduce a concept at the *end* of one sentence, then make it
the *subject* of the next. Repeat. That is what given-new chaining is, and it produces a paragraph
that reads as one continuous movement rather than a list of true statements:

> An important strategy to increase agricultural production is to improve **soil fertility**. In
> many agricultural soils, a major limiting factor for plant growth is **phosphorus**. **Phosphorus**
> is involved in essential metabolic pathways including photosynthesis, biological oxidation,
> nutrient uptake, energy transfer and cell division. — `WS-SentenceFlow`

**Fixing a sentence that will not work.** Decide what belongs in the topic position (something
familiar) and what belongs in the stress position (the new point), then arrange the middle. If a
sentence is the very first of an abstract or section, there is no prior text to chain from, so open
with the most familiar available concept rather than the most technical one.

---

## 3. Twelve precision rules

From `WS-Precision`, ordered as they are most often needed.

1. **Use simple sentence structures.** Long, multiply-embedded sentences hide the relationships
   between the objects in them. Split rather than nest.

2. **Use active voice where the performer matters.** Especially in the Abstract and Discussion, the
   reader must be able to tell whether a result is yours or someone else's. `A strong correlation
   was found` hides that; `We found a strong correlation` does not. Passive is still correct in
   Methods, where the agent is irrelevant. The corpus does both, deliberately.

3. **Include linking words for signposting.** A logical relation the reader has to infer is a
   relation half the readers will get wrong. `These spikes are mediated by calcium electrogenesis
   and are fundamentally different from ...` becomes `**However**, these spikes are mediated by
   calcium electrogenesis and are **therefore** fundamentally different from ...`. Note that this
   rule and the connective budget in `phrase-bank.md` §0 are not in conflict: use a connective when
   there is a real relation to signal, never as filler.

4. **Be cautious with pronouns.** `it`, `this`, `they`, `its` are ambiguous far more often than
   authors believe. Replace with a specific pro-form: `this energy`, `this radiation`, `these
   bubbles`. A bare `This` opening a sentence should almost always become `This X`.

5. **Choose words carefully; there are no true synonyms.** *shows*, *indicates*, *demonstrates*,
   *illustrates*, *suggests* are not interchangeable — they sit on different rungs of the evidential
   ladder (see `phrase-bank.md` §5).

6. **Omit unnecessary details.** Decide the message first, then keep only the details that serve it.
   `It becomes increasingly recognized that ...` earns its place only if the recency is the point.

7. **Include redundant information where it aids comprehension.** The mirror of rule 6. For your
   central message, or for a term your target readership may not share, restate it in different
   words: `Ephaptic transmission is capacitive: there is no transmembrane current flow, but the
   charge is redistributed on the intra- and extracellular surfaces of membranes.` The clause after
   the colon is redundant for a physicist and essential for a biologist.

8. **Delete unnecessary words.** Watch for doubling (`absolutely essential`) and for `very`, which
   weakens rather than strengthens. `It seems possible that there might exist ...` stacks three
   hedges to say one thing.

9. **Use qualifiers to fine-tune, not to soften.** `At least two qualitatively different X` is more
   precise than `two X`. That is a qualifier doing work. `Somewhat higher` usually is not.

10. **In comparisons, state both terms.** `The compound has a boiling point similar to water`
    compares a temperature to a substance. Write `similar to that of water`. `The probe contained
    more leukocytes than saliva` says something the author almost certainly did not mean. Precision
    and brevity trade off here; choose precision.

11. **Avoid strings of nouns.** `DSE un-inoculated and inoculated plant root samples` hides which
    noun modifies which. Unpack it: `samples from plant roots inoculated and not inoculated with
    DSEs`.

12. **Avoid garden-path sentences.** Sentences that are grammatically correct but send the reader
    down a dead end on first reading. Authors cannot detect these in their own text, because they
    already know the intended parse. The tell is a sentence you have to re-read to hear correctly.

---

## 4. Parsimony and selective worry (Box)

Box's essay supplies two habits of mind that show up as prose decisions.

**All models are wrong; some are useful.** State a model's simplifying assumptions plainly and then
argue its usefulness, rather than defending the assumptions as if they were true. In practice this
means the honest formulation `our results are consistent with aspects of [theory]` rather than
`our results prove [theory]`, and an explicit sentence naming what the model does *not* capture.

> "Since all models are wrong the scientist cannot obtain a "correct" one by excessive elaboration." — Box-1976

**Worry selectively.**

> "Since all models are wrong the scientist must be alert to what is importantly wrong." — Box-1976

"I t is inappropriate to be concerned about mice when there are tigers abroad," as Box puts it in
the next line. Applied to writing: a Limitations passage that lists every conceivable caveat at equal
weight tells the referee you cannot tell which ones matter. Name the one or two assumptions that
could actually overturn the conclusion, quantify their likely effect, and let the rest go.

**Overelaboration is a tell.**

> "Just as the ability to devise simple but evocative models is the signature of the great scientist so overelaboration and overparameterization is often the mark of mediocrity." — Box-1976

The same is true of prose: a sentence carrying four qualifiers, or a Discussion that
proposes three mechanisms with equal enthusiasm, signals that the author has not decided what they
believe. Commit, then hedge at the level the evidence supports.

---

## 5. Revision order

Higher-order concerns first, lower-order last. Revising sentence rhythm before the argument is
settled wastes the work.

1. **Argument.** Does the section fulfil its contract? Is the claim actually supported?
2. **Structure.** One idea per paragraph; topic sentences; do the paragraph openers read as a
   summary?
3. **Cohesion.** Given-new chaining across sentences; connectives reflecting real relations.
4. **Precision.** The twelve rules above.
5. **Register.** Connective budget, hedging ladder, banned vocabulary (`ai-tells.md`).
6. **Consistency.** Symbols, units, abbreviations, figure numbers, tense.

Then, and only then, read the whole thing aloud once. Sentences that cannot be read aloud in one
breath are the ones to split.
