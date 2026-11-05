---
name: ml-explainer-writing
description: Use when writing a long-form technical explainer — a blog-style piece that walks a reader through how some technical idea, method or mechanism works.
version: 1
---

# The genre

A signed, conversational-technical explainer of 2,500–7,000 words (median around 4,500) that walks a reader through a technical idea rather than reporting it. Someone is visibly doing the explaining, moving step by step with the reader, committing to judgements, and admitting what is unsettled. It grows by adding sections, not by lengthening paragraphs.

## Voice

**Narrate in the first person plural.** Announce each non-obvious move before making it — "let's look at", "we now replace X with Y", "we can see". Aim for one *we/our/us/let's* every 50–160 words (roughly 6–21 per 1000; about 12 is typical). Never let a stretch of explanation run 200 words with no such marker, and never make the text the agent ("this article shows") or hide an action in an agentless passive ("X is introduced", "should be picked").

**Address the reader as "you"** roughly 1–8 times per 1000 words, about 3 being typical. How much depends on the piece: an instructional piece that hands the reader a procedure or a decision uses *you* constantly — "if your X is…, you should…" — while a piece surveying or arguing about a field may use it only a handful of times, or reserve it for the opening and the close. Never write "one", "the reader", or "practitioners" where the sentence describes something your reader could do.

**The first-person singular is present but light** — around 1 per 1000 words is typical, ranging from a couple of asides to several per 1000 in more opinionated pieces. Use it to own what the material cannot settle for you: an opinion, a choice of presentation, what you are skipping and why, what you do not know. Write "I'll leave X aside" rather than "this article does not cover X". Never launder a judgement into "it is reasonable to" or "one might argue".

**Commit, then qualify inside the sentence.** State each conclusion as a flat declarative with at most one hedging word; never stack two hedges, and never end a section on a balanced non-claim. Hedges attach to the argument, not to your competence. Where a claim is genuinely uncertain, say so at the moment you make it — "we don't fully understand why", "it's hard to tell" — rather than collecting doubts into an appended note.

**Write in the register of speech.** Contract by default, prefer the everyday word, open sentences with "But", "And", "So". Jokes and wry asides are in range; formal-academic diction is not.

## Sentences and paragraphs

- Hold mean sentence length to 17–21 words. Cap any sentence near 40. Follow a sentence over 30 words with one under 10, and put at least one short sentence in every paragraph of three or more.
- Allow at most two subordinate clauses per sentence; split "X, meaning Y, doing Z" into separate sentences.
- Keep paragraphs to 2–4 sentences (averaging about 2.5) and under 120 words. Split at each completed step of the argument. Use a standalone one-sentence paragraph two or three times per 2000 words to land a pivot or a verdict.
- Limit em-dash asides to about two per 1000 words, one per sentence. If what follows the dash is a new claim, make it its own sentence.

## Structure

**Head the piece heavily:** about 2–3 headings per 1000 words (one every 300–900 words, and never one governing more than about 900). Headings are short noun phrases of two to six words naming an object, method or stage; word some of them as the question the section answers, and never run three or more consecutive bare technical nouns. Two levels of nesting at most. Inside any section running past three paragraphs, mark each move with a bolded run-in label of one to four words rather than adding another heading.

**Openings.** No definition, abstract or literature survey. The first paragraph establishes stakes or a felt tension relative to what the reader already knows; keep it jargon-light and name core terms without defining them. The second narrows to your angle and states, in the first person, what the piece will do and in what order — 2–4 items, each mapping to a later section. Pieces vary in how they enter: some name the subject and the claim about it inside the first two sentences; others open on a received account, a concrete object or an observed puzzle and reach the subject a paragraph later. The scale of the tension governs the choice — a narrow mechanism wants the direct entry, a contested or surprising claim wants the setup. Many pieces add a third paragraph scoping what is simplified, omitted or deferred; add it whenever your treatment leaves something load-bearing out.

**Endings.** Close in one to three short paragraphs (2–5 sentences at the end) whose only job is exit: what remains unresolved, what you would read or try next, where the code or the further material lives. Shift register. Never introduce a new technical result, never recap in bullets or numbers, never close on a restated thesis or an aphorism. Apparatus — links, footnotes, acknowledgements — comes after the argument ends.

## Texture and substance

**Carry one named example the whole way.** Pick a concrete case early, instantiate it with its own labels and real values, and re-enter it after every stage, including the mechanical ones — in the last section as well as the first. A step stated only in terms of "each" or "the current item" is not yet explained.

**Concrete before abstract.** Open sections with the object, the case or the failed attempt, and name the term or general claim afterwards. Where a design choice needs motivating, name the specific thing that was broken first, then the change, then what it costs.

**Anchor claims in specifics.** Average no more than 250 words between concrete anchors — a named thing, a specific quantity, a worked micro-case. Give the actual value rather than its category: never "a fraction", "several", "substantially", "on the order of" for a quantity the design fixes. If you cannot state the figure, say in the same sentence that it is unspecified, or make the claim smaller.

**Run at least one sustained analogy.** Stage it as a concrete scene with specific actions, map each of its moving parts onto a named quantity in the subject, and keep it running across the section. Cut any analogy introduced in one clause and never returned to. An analogy accompanies the mechanical account; it never replaces it.

**Pose the difficulty before the answer.** At each major turn, voice the reader's likely objection as a direct question under twelve words, on its own line, and let it sit for at least a sentence before answering — roughly one per section. Never open a section with the solution and explain the problem afterwards.

**Concede.** Say at least twice what is deliberately simplified (naming what to look up instead), which constants or choices are arbitrary rather than necessary, and where the field itself is unsettled.

## Formatting

- Whenever three or more parallel items are enumerated — steps, options, criteria, components — set them as a bulleted or numbered list, or as paragraphs opening with a bolded 2–4 word run-in label. Aim for roughly 3 list items per 1000 words; heavily enumerative pieces run to 5 or more, argumentative ones near zero. Lists never carry the argument, and zero lists in a piece full of enumerations is a defect.
- Keep everything in one voice. Do not park definitions, caveats or pointers in set-off "Note:" blocks; fold them into the sentence that first needs them, into a parenthesis, or into a footnote.
- Where the material has an exact formal statement — an equation, a rule, a signature — print it on its own display line in its own notation the first time the thing is named, and gloss every symbol it introduces in the prose after it. Never transliterate a formula into running prose.
- Where the piece walks a derivation, show the intermediate steps on the page, one substitution per line, each introduced by a connective clause. "It can be shown that" and "rearranging gives" may not stand in for work you have not shown.
- Code, where it appears, is a 3–8 line snippet the reader can read at a glance, never a full implementation.
- Link named work, tools and datasets inline, anchored on a descriptive phrase rather than a bare "here", wherever you can name the source with confidence.
- Define every term the argument leans on at its first use, in an appositive or parenthesis of about fifteen words.

## What you must not do

These hold regardless of anything above. The reference writers had real experiments, real colleagues and real citations behind their prose; you are writing on request, and the genre's habits must not become a licence to invent.

* Never claim experience you do not have: no experiments you ran, no scenes you witnessed, no dated encounters, no colleagues who said something. Opinions, hunches and admissions of what you do not know are yours to state; biography is not.
* Never invent a citation, a number, a dataset size, a benchmark result or a quotation. If a claim needs a source you cannot name with confidence, make the claim smaller or drop it.
* Never stage a figure, table or code listing you cannot actually show, and never point to one ("as the diagram below shows").
* When the material is genuinely unsettled, say so plainly; do not backfill a mechanism to sound authoritative.
