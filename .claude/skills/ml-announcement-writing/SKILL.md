---
name: ml-announcement-writing
description: Use when writing a first-party announcement post — a launch, release, version, milestone, or shipped-capability roundup — published by the organization that built the thing.
version: 1
---

# Announcement writing

You are writing as the organization that shipped something, addressing a practitioner who already has a setup and a problem of their own. The piece announces, describes, and hands over: what it is, what it lets the reader do, where to get it. It is not an essay about the thing, and it never appraises its own material. Length runs 600–2,500 words, clustering at 1,000–1,600; add length by adding sections, lists, and cases of the same kind, never by developing one point further.

## Voice

**Speak in the first person plural as the team that did the work.** "We" owns every decision, launch, and measurement. Target 4–16 "we/our/us" per 1,000 words — about 11 is typical, roughly one every 90 words — with at least one in the opening sentence and one in the closing section. Never put your own organization's name in subject position ("Acme announces…") and never use "I" or "my".

**Address the reader as "you", cast as a practitioner with an owned problem** — "your team", "your pipeline", "your data". Rate varies with form: 8–26 per 1,000 words, median 17. A walkthrough or getting-started passage sits at the high end and carries imperatives; a piece that reports changes rather than guiding hands sits at the low end. Use "you" only for what the reader does, configures, or receives — never to narrate their past, their feelings, or their mistakes.

**Make claims flat and unhedged.** Cut "arguably", "we think", "probably", "it turns out". State what the thing does in the declarative present. Acknowledged limits range from none to one or two per piece; when you name one, give it a sentence, attach it to scope rather than to immaturity, and do not stage an objection and then answer it.

**Never appraise your own material.** Delete any sentence whose subject is the importance, cleverness, or unglamorousness of what you just wrote — "the real change here", "worth noticing", "this sounds minor but isn't", "less like X than Y". Delete any sentence that would survive unchanged on a different subject. Every paragraph must add a fact no earlier paragraph stated.

Use contractions in your own voice ("we're", "you'll", "don't").

## Structure

**Name the thing in the first sentence of the body**, in under 40 words, with what it is and who it is for. Open on the team and the act, not on the calendar: "We've added…", "We're shipping…", "Welcome our new release of…", "Our latest release brings…". Never open with "Today", "This week", "As of today" or any other time marker; a date belongs in the availability block, not in the lede. Problem framing comes after, not before, and takes at most a quarter of the piece; keep it to one compact paragraph or a run of flat assertions. Never open on a scene, an invented anecdote, a rhetorical question, or an aphorism.

A compressed preview after the lede is common: a labeled TL;DR line, or a bulleted inventory of 4–8 parts in the form **name** — what the reader gets, matched one-to-one to the sections that follow.

**Foreground anything the reader does with a coding agent.** When the brief describes how an agent reads, edits, runs or is set up against the product — an MCP entry, a printed guide, a CLI verb that mirrors a UI action, attribution of agent edits — that material is a headline capability, not an appendix. Name it in the lede or the TL;DR, give it its own entry in the preview inventory, give it its own section with subheadings where the brief supplies more than one mechanism, and tie at least one other capability back to it ("the checkpoint your agent reads first"). Never bury agent workflow under "also" or in the last paragraph before getting started. Facts about which harnesses are supported, which tools are exposed and what setup writes to disk still come only from the brief.

**Where you assert something is hard, give the cause in the same paragraph** — what property of the system produces the difficulty — before naming the remedy.

**Close on the reader's next action.** One to three sentences, carrying links: install it, read the docs, try it, tell us. Most pieces pair this with a forward-looking line, thanks to contributors, or a compressed restatement of the value. Endings never summarize the sections, never qualify earlier claims, never pose an open question, never end reflectively or on a metaphor. Two forms, governed by the piece: a single-subject announcement may restate its value in one clause before the ask; a catalog of independently shipped items stops at the last item and its ask, asserting no shared intent.

Where availability, pricing, editions, or event logistics appear, give them their own final block with labeled lines, each fact separate and each destination linked.

## Texture and substance

**Every capability gets a mechanism sentence**: what does the work, what is attached to what, at which step. If deleting that sentence leaves the paragraph saying the same thing, it isn't one. Then land the capability on a concrete consequence — what the reader no longer does, what now appears, what they can now answer. The recurring engine is a capability clause answered by a benefit clause ("so you can…", "which means…").

**Specificity comes from checkable particulars** — named systems, integrations, commands, flags, version strings, standards, partners — not from figuration. Budget at most one metaphor per 1,000 words, none in the opening paragraph or any heading; where you reach for one to explain a mechanism, state the mechanism instead.

Illustrations, where the material supports them, are a one-sentence hypothetical ("suppose your team…") attached to the mechanism it demonstrates, or a named case the brief supplies. Do not give an invented scenario its own paragraph. When the brief supplies a quotation from a named person, reproduce its wording, set it apart, and attribute it with name, role, and organization, with no clause interpreting how it reads.

Where the brief gives an exact API or command, show it as one fenced block of roughly 5–30 lines, cued by a short colon-terminated lead-in, with real argument values. Don't walk it through line by line; name one identifier from it in backticks in the sentence after. Use inline monospace for identifiers only. No equations, no tables.

## Formatting

**Any set of three or more parallel items goes in a bulleted list**, never a comma chain or a run of bold-led paragraphs. Dominant form: a bolded 2–6 word label, then a colon or dash, then a one-line gloss. Two to five lists per piece, three to eight items each, about 3–7 list items per 1,000 words — zero is a defect. Numbered lists are rare and short even for sequential steps.

**Link inline, densely, on the noun phrase itself** — every product, doc, repo, channel, and destination at first mention, roughly one link per 80–200 words. Never write a destination as bare text, never anchor on "here". There are no footnotes and no reference list.

**Headings are short literal noun phrases, two to seven words**, labeling the section rather than claiming anything; a reader scanning headings alone should be able to list what the thing does. Density is governed by form: a piece that runs as one continuous argument under ~1,500 words may use none, segmenting with bold run-in labels instead; a piece built from discrete capabilities or shipped items gives each its own heading, roughly one per 130–250 words, with one level of nesting where sections group. Across the corpus this lands at 0–8 headings per 1,000 words. The final heading is functional: availability, getting started, what's next, join us. At most one question heading.

**Paragraphs run 1–3 sentences**, averaging about two, 40–90 words, never past four; break at every change of subject. Single-sentence paragraphs are normal and carry emphasis. Mean sentence length sits at 18–22 words. Avoid runs of clipped fragments used for punch — a sentence under eight words must carry a new fact, and no paragraph ends on one as a kicker.

Cap em-dash asides at one per 400 words and never two in a paragraph. Bold load-bearing spans at roughly one per 150 words — list labels, a term at first definition, the sentence a skimmer must not miss — never on a name that should be a link. Italics only for terms being named.

## What you must not do

These hold regardless of anything above. The reference writers announced
products they had built, with real customers, real dates and real numbers
behind the prose; you are writing on request, and the genre's habits must not
become a licence to invent.

* Never invent a fact about the product: no feature, limit, integration,
  platform, pricing tier or availability date that the brief does not give
  you. If the brief is silent, leave it out or ask — do not fill the gap.
* Never invent a customer, a quote from a user or teammate, an adoption
  figure, a benchmark, a speed-up or a download count. Numbers come from the
  brief or do not appear.
* Never promise a roadmap item, a launch date or a venue the brief does not
  state; "coming soon" without a date is the most you may say on your own.
* Never stage a screenshot, demo, code sample or diagram you cannot actually
  show, and never point to one ("as the screenshot below shows"). A code
  sample is allowed only when the brief gives the exact API.
* Never name a competitor unless the brief does; when it does, compare on
  what the brief states, not on what you assume about the competitor.
* When something is still in preview, experimental or gated, say so plainly;
  do not round it up to "available today".
