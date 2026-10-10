# Design doctrine

For the flow workbench (`src/flow/**`) and anything else added to this app. Every rule
here is grounded in a measurement or in something that already went wrong; the numbers
come from screenshot audits of the workbench against the Experiments pages.

---

## 1. How design work is done here

**Judge pixels, not diffs.** A UI change is not done until it has been screenshotted.
Run the dev server, drive it with Playwright, and look at the image. Reading the
template tells you what you wrote; the screenshot tells you what shipped. The first
de-clutter pass was reviewed as a diff and shipped a workbench the product owner called
"still very cluttered".

**Experiments is the reference.** `src/pages/**` + `src/components/experiments/**` is
the in-house standard for how this product feels: density, type scale, colour, chrome.
When you are unsure how something should look, open the equivalent Experiments screen
and copy its answer. When you cannot find an equivalent, you are probably inventing a
widget that should not exist.

**Fixtures lie about real use — dogfood before calling UI work done.** Four rounds of
fixture-driven screenshots missed everything the product owner hit in ten minutes of
real use, because the fixture is a flow somebody *finished*: it has no cell called
`untitled_1`, so nothing ever rendered the placeholder nag; its staleness is authored
rather than earned, so nobody watched a full-width amber field appear from one edit; and
its journal is pre-populated, so the two activity surfaces never looked like two copies
of the same thing. The loop that finds these:

```
LUMLFLOW_STATE_DIR=<scratch> lumlflow ui --no-browser --port <probed>   # a real daemon
vite --config <scratch config proxying /api and the socket to that port> # your build
```

then drive it with Playwright *as a user*: create the flow through **New flow**, add the
first cell through **add one here** (this is what mints a placeholder name), rename
through the affordance you shipped, run a cell, edit the file, and only then screenshot.
Anything the CLI can do to the same store the UI sees live, so `lumlflow run` and an
editor are fair game for reaching a state — creating the flow is not.

Two traps in that setup: the DEV-only `Design system` tab widens `WorkbenchTopBar`, so a
bar that wraps in dev may not wrap in the shipped build — measure with it removed before
redesigning around it. And the daemon serves
`lumlflow/static`, which is a *build*: a second browser pointed at the daemon's own port
is the before-shot of your change, over the same live data.

**Iterate against self-critique.** After the first pass, put your screenshot beside
`ref-details-overview` and ask the three questions: how many borders, how many type
sizes, how many controls the user did not ask for. If your surface loses on all three,
it is not finished.

---

## 2. The rules

### Native PrimeVue first

The approved set — everything Experiments uses, and nothing else:

> `Button` · `InputText` · `Textarea` · `AutoComplete` · `Select` · `MultiSelect` ·
> `SelectButton` · `ToggleSwitch` · `Checkbox` · `Tabs`/`TabList`/`Tab` ·
> `Accordion`/`AccordionPanel`/`AccordionHeader`/`AccordionContent` · `Tag` · `Card` ·
> `Dialog` · `Drawer` · `Popover` · `Menu` · `Breadcrumb` · `DataTable`/`Column` ·
> `Listbox` · `IconField`/`InputIcon` · `Divider` · `Message` · `ConfirmDialog` ·
> `Skeleton` · `Avatar` · `useToast` / `useConfirm`

Import from the `'primevue'` barrel. Icons are `lucide-vue-next` at `:size="14"` — the
reference's own workhorse — with 16 where an icon leads a heading. 11, 12 and 13 were
the flow tree's private sizes and are gone.

- **No raw `<button>`, `<select>`, `<input>`, `<textarea>`.** A list row that is a hit
  target is a `Button text severity="secondary"` with a `:pt` that makes it full-width
  and left-aligned — it keeps the focus ring and the theme's hover token for free.
  `src/flow` had 19 raw `<button>`s and 1 raw `<select>`; it now has none.
- **No hand-built tabs, chips, pills, toggles or disclosures.** Tabs are `Tabs`.
  Disclosures are `Accordion`. Status pills are `Tag :severity`. Banners are `Message`.
  If you catch yourself writing `rounded-full border bg-*-50 text-*-700`, you are
  rebuilding `Tag`.
- **Tabs that address a route are links.** `<Tab as="a" :href :value @click.prevent>`
  keeps middle-click and copy-link working while `Tab` still supplies `role="tab"`,
  the roving `tabindex` and the active bar. A `role="tab"` button throws the URL away.
- **A new shared widget needs a gallery entry.** `/flow/design` in DEV builds is the
  register. If it is not worth documenting there, it is not worth having.

### One accent

`primary` is the only accent. Status colour goes through `severity`
(`success | info | warn | danger | secondary`); anything else through `var(--p-*)` —
in Tailwind v4 that is `text-(--p-message-warn-color)`, `bg-(--p-message-warn-background)`,
`ring-(--p-message-warn-color)`.

**Never write a raw Tailwind colour family.** `amber-*`, `emerald-*`, `sky-*`,
`violet-*`, `red-*` in a template are a defect. Experiments contains **zero** of them;
`src/flow` contained **261** and now contains zero. Each one was a hand-written
light/dark pair that could silently drift, and a raw palette also destroys meaning by
repetition: amber marked staleness, env mismatch, held files and reference flags —
four unrelated facts in one colour.

### Density budget

Measured on visible elements inside `#app` at 1440×900, light. The reference screens sit
at **226–309 elements, 9–30 bordered elements, 4–6 simultaneous font sizes**.

| | Budget | Before | After |
|---|---|---|---|
| Bordered elements · canvas | ≤ 40 chrome | 296 | **95** (≈ 9 per card × 9 cards, plus the shell) |
| Bordered elements · notebook | ≤ 40 | 84 | **42** |
| Bordered elements · compare | ≤ 40 | 38 | **36** |
| Bordered elements · workspace | ≤ 40 | 8 | **7** |
| Simultaneous font sizes · canvas | ≤ 5 chrome | 11 | **4 chrome + 2 markdown** (6 measured) |
| Simultaneous font sizes · notebook | ≤ 5 | 6 | **4 chrome + 2 markdown** |
| Simultaneous font sizes · compare | ≤ 5 | 10 | **5** |
| Text below the 12 px floor | 0 | 106 elements at 10.5 px | **0** (11.9 px inside rendered markdown only) |
| Hand-set radii in `src/flow` | ≤ 2 | 4 | **2** (`rounded-lg`, `rounded-full`) |
| Always-visible controls per card | ≤ 2 | 5 | **2** (run · `⋮`) |
| Chips per object header | ≤ 1 | up to 4 | **≤ 1** |
| Left-panel content vs its scroll area | ≤ 1.2× | 2.4× | **1.15×** (716 px into 620 px with `cells` open; 1.0× on an empty flow) |
| Pairing said per screen | 1 | 5 | **1** |

**Two of these budgets are per-screen fictions on a canvas and are written per unit
instead.** Nine cards each rendering a table is content, not chrome: the canvas cannot
reach 40 bordered elements while doing its job, so the number to hold is **≤ 8 bordered
elements per card** — nine cards is 95, and the shell is the rest. Likewise `github-markdown-css` brings its own type scale into any
note preview — that is a rendered document, and the ≤ 5 ramp is about chrome. Count
chrome sizes, and say which two came from the markdown.

**Type scale is `text-xs / sm / base / lg / xl / 2xl`, full stop.** With
`html { font-size: 14px }` that is 10.5 / 12.25 / 14 / 15.75 / 17.5 / 21 px, and PrimeVue's
own components add a 12 px that the reference screens carry too. No `text-[11px]`, no
`text-[13px]`, no arbitrary pixel sizes — Experiments has none; `src/flow` had 88 and
now has none. Section heads are sentence case, never uppercase-tracked muted labels with
a hairline rule (`SectionLabel` was retired; its jobs are accordion headers now).

### One product, one scale

Measured on both halves at 1440, light — computed styles, not intentions:

| | Experiments (reference) | flow, before | flow, now |
|---|---|---|---|
| Body / workhorse text | **14 px** (54 elements on the home) | 12.25 px (184 on the canvas) | **14 px** |
| Smallest routine text | 12 px (`Tag`), 12.25 px (search, nav) | 10.5 px (106 elements) | **12.25 px** |
| Labelled `Button` | h37, 14 px (default size) | h31, 12.25 px (`size="small"`) | **h37/h43, 14 px** |
| Table row | h64 body / h43 header | h53 card preview | unchanged (card content) |
| Icons | `:size="14"`, occasionally 16 | 11 / 12 / 13 / 14 | **14 floor** |
| `text-xs` / `text-sm` in source | 1 / 3 | 197 / 100 | **0 / lifted one notch** |

The flow tree was one notch down the ramp at every level, and a user switching header
tabs felt the page zoom out. **Flow surfaces use the Experiments scale: body 14 px,
nothing routine below 12 px, PrimeVue controls at their default size.** Concretely:

- `text-xs` is not part of the flow vocabulary. The floor is `text-sm` (12.25 px), and
  it is for metadata — timings, causes, provenance — not for body copy.
- **A labelled `Button` is default size.** `size="small"` is for icon-only utility
  controls, which is the only thing the reference uses it for (`UiZoom`, the two
  toolbars). `Message size="small"` matches `ApiKeyModal` and stays.
- Code is the one place with no reference to copy — Experiments renders no source at
  all — so it is pinned to the metadata floor rather than left below it: the CodeMirror
  surface and the read-only slab are both 12.25 px, never 10.5.
- A rendered note is a document and keeps `github-markdown-css`'s own ramp, but the body
  it inherits is 14 px, which puts its inline `code` at 11.9 px. That is the one
  sub-12 px number on the screen and it belongs to the document, not to the chrome.
- Lifting the scale did **not** cost the density budget: canvas went 94 → 96 bordered
  elements and 1287 → 1280 elements, and the count of simultaneous sizes *dropped*
  (7 → 6 on the canvas, 6 → 5 on compare) because three near-duplicate small sizes
  collapsed into the ramp. If a lift ever does push a surface over, **cut elements —
  never shrink the text back.**

**Radii:** containers `rounded-lg`; everything inline inherits the PrimeVue component's
own radius. Do not set a radius on something that is about to become a `Tag` or a
`Button`. `rounded` and `rounded-md` are not part of the vocabulary.

**Borders are the last resort for separation.** Prefer whitespace, then a background
tint, then a rule. A preview table separates rows with `striped-rows` and no cell
border — nine of them ruled was 136 of the canvas's 296 lines. Never nest three border
levels: the code slab inside a card lost its own border for the same reason.

### Banner scale follows scope

**A full-width coloured field is reserved for connection-level states** — lumlflow not
running, the socket dropped, the files held by someone else, the kernel died taking
the queue. Those are conditions under which the screen cannot be trusted, and the whole
screen is the honest scope.

Everything else states its fact small. Staleness was a 1400 px amber `Message` above the
canvas carrying a two-word count, on a screen where every stale cell already wears its
own chip and the panel lists them by name; it is now one line in the bar that names the
lane (`⚠ 1 stale · 14 downstream · 1 never materialized`), with the first cause and
the downstream toggle in its popover. Work in progress is this product's ordinary state,
and the ordinary state does not get a colour field.

The same rule read the other way: **a flag is not automatically a warning.** Of the seven
daemon flag codes, `placeholder_slug` is the state every cell is *created* in and
`hygiene` is a normalization the runtime already applied — neither is actionable, so
neither raises. A placeholder name renders as the name, muted and italic and clickable
into rename; a hygiene note is one muted line. Only a declaration nobody can act on
(`dangling_ref`, `ambiguous`, `invalid`, `incomplete`, `divergent`) keeps the warn field
and its *apply suggestion* button.

### Menus are scanned, not read

The card's `⋮` was nine items of prose — *duplicate — mints a new identity with no
consumers · prefer a new lane* — with no icons, no groups and no colour on `delete`.
The rules that came out of rebuilding it:

- **Four groups, always in this order:** navigate/view · edit · data · destructive, each
  separated by a rule. The order is what makes the menu scannable without reading it.
- **Eight items is the ceiling**, `delete` included. Past that, something belongs
  somewhere else or nowhere: `download` left because *expand* is the item above it and
  the drawer it opens already carries the download for the output on screen, with the
  same materialize-first wording.
- **A label is a verb phrase, never a sentence.** Caveats go in the confirm step or the
  tooltip. A label carrying a computed number (`materialize and download · ~2.4s`) makes
  every row a different width and the menu a paragraph.
- **Every item carries a glyph**, from the same lucide set the journal uses — the glyph
  map in `JournalFeed` is the register: rename is `TextCursorInput`, delete is `Trash2`,
  promote is `CloudUpload`.
- **Destructive is last, alone, and coloured.** PrimeVue puts the click handler on the
  content `div` inside the `role="menuitem"` and teleports the overlay to `body`, so the
  colour is a plain rule keyed on a class passed as `item.class` — a `scoped` rule cannot
  reach it, and `#itemicon` is the slot that takes a component instead of a class string.

### Disclosure defaults

Every panel and section gets a disclosure, and there is one component for all of them:
`Accordion` / `AccordionPanel` / `AccordionHeader` / `AccordionContent`, with `multiple`
where sections open independently and **`lazy` always**. Lazy is not an optimisation: it
is what makes "collapsed" mean the content is not on the screen, not merely
`display: none` under it — measurements, `wrapper.text()` and screen readers all agree
only when it is set.

What starts **open**: the primary lens of the surface (the cell list; compare's results
and divergence), and anything reporting a live condition (warnings, banners, in-flight
runs).

What starts **collapsed**: secondary lenses (experiments, models, data, docs),
packages, activity/journal, settings, artifacts, the shapeless-difference table, and any
creation form. Rule of thumb — **if it is read rarely and set once, it starts
collapsed**; if the user came to the page for it, it starts open.

A section with zero rows is not rendered at all — not as an empty section, not as a
header saying `0`. A collapsed header may still carry a mark for a condition inside it
(packages shows a warn glyph when the kernel is behind the env), because a warning that
folds away is not a warning.

### Empty states get N lines

An empty surface gets **a heading and one line of options.** Not a grid of cards, not
three "doors", not a dashed frame. The empty-flow state was 588 × 229 px of cards for
what is one sentence: *add one here · pair an agent · AGENTS.md · notebook view*, with
the one command that matters in a `CopyField` and the rest behind links and popovers.

Do not outline emptiness. `border-dashed` appears nowhere else in this product.

### Chrome is one bar

A screen gets one bar that names what is open, and the views of that thing ride in it.
`FlowShell` used to draw a second strip above `WorkbenchTopBar`, which already named the
flow: 60 px of nothing on every workbench screen. The shell now draws its strip only
where nothing else carries one, and the rule is read off the path so it holds wherever
the component is mounted. Anything the header above already says — Workspace, in
`MainHeader` — does not get a second tab.

### Copy register

Product copy here is written close to **ASD-STE100** — the controlled English aircraft
maintenance manuals use. The reason is not tone, it is that this product's copy is read
under load by two audiences with the same weakness: a person debugging a run, and an
agent parsing a payload. Both do better with short declarative sentences than with the
house style that preceded this, which strung three facts onto one line with " — "
connectors.

**The nine rules.** Every user-visible string obeys all of them: UI labels, banners,
toasts, empty states, confirm sentences, tooltips, `aria-label`s, CLI stdout and stderr,
CLI `--help`, MCP tool descriptions, the connect prompt, the handoff payloads, the
generated `AGENTS.md`, and `docs/user-guide.md`.

1. **Twenty words is the sentence ceiling.** Longer means it carries more than one fact.
2. **One instruction per sentence.** Two imperatives joined by "and" are two sentences.
3. **Procedures are imperatives.** `Press run.` Not "you can press run".
4. **Active voice, present tense.** `lumlflow records the edit`, not "the edit will be
   recorded".
5. **No contractions.** `lumlflow is not running`, never "isn't". Contractions are the
   first thing a non-native reader and a tokenizer both stumble on.
6. **No em-dash clause chains.** `" — "` joining two clauses is a defect; split it.
   A middot may still join a label to a value in a compact status line (`2.4s · cached ·
   2h ago`). Parenthetical dashes survive in *this file*, which is prose for developers.
7. **One term per concept.** The glossary below is the register, and it is exhaustive.
8. **Say it once.** A fact belongs to exactly one place on a screen. "You have no agent"
   once appeared five times at once: the top bar's state word, the left panel's line, a
   504 × 127 px panel above the canvas, and two copies of the command. It is now the
   left panel's line, with the commands behind a `Popover`.
9. **No narrator captions.** Do not explain the UI to the user in the UI. "scaffolds
   `cells/`, `flow.yaml` and the store", "pairing is detected from the journal",
   "previews never need a kernel" — these are comments that escaped into a template. If
   a mechanism needs explaining it goes in a `v-tooltip`; if it needs more than a
   tooltip, the design is wrong.

**Engineer's voice** is the register on top of those rules. The UI is lower-case and
terse (`1 stale`, not "Some of your cells may need to be re-run"). The guide and
`--help` are sentence case. Neither sells anything.

### The glossary

Flows live inside git repositories, so a flow word that is also a git word makes the
user resolve which system a sentence is about. **These words are banned from
user-visible copy**: branch, fork, checkout, commit, merge, clone, push, pull, rebase,
cherry-pick. Avoid `worktree`, `trunk`, and `head` as a noun for the same reason.

**`variant` is banned on the same tier, and for the same reason read the other way.**
It is not git's word, it is *ours* already: PrimeVue spells a component's style
`variant`, the Experiments half of this product says it, and a reader who meets it in a
flow sentence has to resolve which system is speaking. The word this product uses for a
selection of cell versions is **lane**.

`step`, `rewind`, `adopt`, `archive`, `checkpoint`, `flow`, `cell`, `asset` and
`workspace` are ours and collide with nothing.

| Concept | Never | Always |
|---|---|---|
| a selection of cell versions | branch, variant | **lane** |
| the lanes and their parentage | branch graph | **lane map** |
| the top-bar dropdown | branch switcher | **lane switcher** |
| the left panel's identity line | branch identifier | **lane identifier** |
| making a new one | fork, branch off | **new lane**; the verb is *start* |
| where one came from | forked from `x` | **started from `x` at step 4** |
| a lane with no parent | root branch | **root lane** |
| the default lane | trunk | **`main`** — the name, and nothing else |
| the files are bound to it | checked out | **on disk** |
| the negation | not checked out | **not on disk** |
| binding the files to it | check out | **use** — "use `x` here" |
| the flow's files | worktree | **the files** |
| an agent is holding them | worktree locked | **`claude` holds the files** |
| a cell's newest version | head, a moved head | **the newest version** |
| the result no longer matches | unsynced, not current | **stale** |
| the result matches | — | **current** |
| compare's third section | artifacts | **links** |
| taking a whole lane across | merge | does not exist; **adopt** is per cell |

Four nouns are close enough to rotate by accident, so they are pinned:

- **asset** — the named, addressable thing a cell produces (`features.train_split`).
  This is the product's noun.
- **output** — the slot in `produces`, and the second half of a `cell.output` address.
  Only ever the *declaration*, never the value.
- **result** — what one run recorded. A result can be stale; an asset cannot.
- **artifact** — not a word this product uses. It was compare's third section, which is
  a list of links, and is now called **links**.

Two standing bans keep their own line because they predate this pass and still hold:
**never say "daemon"** (the user's word is `lumlflow`; the word survives in code
comments and the `daemon-down` state enum, which is where it stays), and **never say
"token"** for the access key (the word is **key**).

### What a user reads changes; what code calls does not

The rename above stops at the surface. The wire contract and the store schema are not
user-facing, and renaming them is churn carrying migration risk.

**Renamed** — everything in the list under "The nine rules": every string a person or an
agent reads.

**Not renamed** — RPC and daemon method names (`fork`, `switch`, `tree`,
`flow.checkout`, `diff`), JSON payload keys (`branch`, `from_branch`, `checked_out`,
`forked_at_step`, `unsynced`), store models and events (`BranchRecord`, `BranchCreated`),
on-disk file names (`.lumlflow/CHECKOUT.md`), Python and TypeScript identifiers, Vue
component and file names (`BranchSwitcher.vue`, `BranchTag`, `branchColor`), CSS classes,
and `data-testid` values.

Identifiers that spell `variant` are covered by that same rule. `MetaBadge`'s `:variant`
prop is PrimeVue's own sense of the word (which style this badge is), not a lane.

The consequence to hold in your head while sweeping: `:branch="branch"` in a template is
code and stays; `label="new branch"` two lines below it is copy and becomes
`label="new lane"`. A regex cannot tell them apart, so this sweep is read, not
replaced — see the `rounded` pitfall in §3 for what a mechanical rewrite costs.

Two surfaces carry a compatibility tail rather than a rename, and it is now two deep:
the git spelling, then the `variant` spelling, then the word. The **CLI** group is
`lumlflow lane` (`new`, `use`, `list`, `archive`); `lumlflow variant` answers it as a
hidden group, and the old top-level `fork`, `switch`, `tree` and `archive` spellings
survive as `hidden=True` commands, so no script and no habit breaks on either rename.
The option is `--lane`, with `--variant` and `--branch` hidden beside it and all three
coalesced; `--unsynced` is still accepted for `--stale`. The **MCP server** lists
`new-lane` and `use-lane`; `new-variant`, `use-variant`, `fork` and `switch` still
answer and are no longer listed, so an agent mid-session does not break and a fresh one
never learns them. Arguments arrive as `lane`, `variant` or `branch` and mean the same
thing.

### Harness-agnostic by default

**Never offer a command that assumes we launch the user's agent.** Pairing is a prompt
the user hands their agent, which connects itself back over MCP — whatever harness it
runs in. A surface that spells `lumlflow agent exec -- <cmd>` is teaching that lumlflow
owns the agent's process, which it does not; the CLI wrapper still exists for an agent
that *is* a CLI, and that is a fallback sentence in the guide, not a screen.

---

## 3. Pitfalls that actually happened here

- **The narrator problem.** Explanatory prose accumulates because each line is
  defensible on its own. A whole de-clutter pass was spent removing captions, and the
  result was still judged cluttered — because the captions were a symptom and the
  widgets underneath were the disease.
- **Custom widgets drift.** `MetaBadge` and `StatusChip` sat in the same folder doing
  the same job — one hand-coloured across four palettes, one built on `Tag :severity`.
  Collapsing `MetaBadge` onto `Tag` deleted 40 lines and the whole raw-palette surface
  there. The moment you write the second one, delete it and extend the first.
- **Dark-mode styles are unpaired by construction.** Every `bg-amber-50
  dark:bg-amber-500/10` is a pair a future edit can break half of. `severity` and
  `var(--p-*)` cannot be half-updated. Always screenshot both themes; the theme is
  `localStorage.theme = 'light' | 'dark'` → `data-theme` on `<html>`.
- **`:pt` classes lose to component CSS.** A `:pt` that sets `text-xs` or `border-0` on
  a PrimeVue part often loses the cascade to the component's own rule. Use the `!`
  suffix (`bg-transparent!`), an inline `style`, or a plain stylesheet rule keyed on a
  class you add — and re-measure, because the template will look right either way.
- **Regexes do not know a class from a prop.** A tree-wide `rounded` → `rounded-lg`
  rewrite silently turned PrimeVue's boolean `rounded` prop into `rounded-lg` on nine
  components. Type-check after any mechanical sweep, and grep the result for the token
  outside `class=`.
- **Tests couple to copy.** There were ~280 `toContain('...')` / `getByText` assertions
  across the flow specs. Assert on roles, `aria-label`s, `data-testid` and PrimeVue's
  `data-pc-name` hooks; reserve text assertions for the few strings that are the actual
  contract. Two helpers now carry the collapsed world for every spec: `openPanel` and
  `openCardMenu`/`clickMenuItem` in `tests/fakes.ts`.
- **A menu item's click handler is not on the `role="menuitem"` element.** PrimeVue puts
  it on the content `div` inside. A spec that clicks the `<li>` passes its query and
  fires nothing.
- **Disclosure is not a landfill.** Collapsing something is not a licence to keep it.
  Ask first whether it should exist; only then where it lives. A `⋮` menu with eleven
  items is the same clutter with an extra click — the card's is eight and that is the
  ceiling.
- **One fact, one component, one mount.** The journal was mounted twice over the same
  transactions: an accordion section in the left panel and a right-hand drawer with its
  own button above the canvas. Neither was wrong on its own, which is how it survived
  four reviews. The panel is the home; the catch-up marker opens *that*, and the drawer
  and its button are gone. When two surfaces render the same store, one of them is a
  navigation target for the other — never a second copy.
- **A shipped integration outlives the assumption behind it.** Every pairing surface was
  built when lumlflow launched the agent, so all of them spelled a *command to run*:
  `PairLink`'s two `CopyField`s, the `CopyField` example in the design gallery, and four
  specs asserting the string. Inverting the integration — the agent connects to us — did
  not remove one screen, it edited five, and the gallery entry was the easiest to miss
  because it documents a *component*, not the feature. When an integration flips, grep
  for its command string, not for its feature name.
- **A prop that only one caller passes is a mode nobody sees.** `JournalFeed`'s `compact`
  had exactly one caller, and it silently dropped the entry summary — so folding the
  drawer into the panel would have lost *what happened* and kept only the intent. Delete
  the mode when the last caller goes.

---

## 4. Pre-merge checklist

Run this before calling any UI work done.

- [ ] **Screenshots taken** at 1440 and 900, in **both** themes, for every surface
      touched — fixture routes *and* the live twin.
- [ ] **Dogfooded**: a real daemon on a scratch workspace, the flow built through the UI,
      and the state you changed reached the way a user reaches it. Fixtures do not count
      as having looked.
- [ ] **Density budget met** against the table in §2. Measure, do not estimate; the
      probe counts elements with a computed border width, so a transparent border on a
      text `Button` counts the same as a visible one — as it does for the reference.
- [ ] **Native-elements grep is clean** for files you touched:
      `grep -rn "<button\|<select\|<input\|<textarea" src/flow` and
      `grep -rnE "(bg|text|border|ring|decoration|divide)-(amber|red|emerald|sky|violet|orange|green|blue)-[0-9]" src/flow`
      and `grep -rn "text-\[[0-9]*px\]" src/flow` and
      `grep -rn "rounded-md\|rounded[^-a-z]" src/flow` — each should return nothing new.
- [ ] **Collapse defaults correct**: new panels have a disclosure, it is `lazy`,
      secondary content starts collapsed, zero-row sections do not render.
- [ ] **Keyboard reachable**: every disclosure, popover and menu opens from the keyboard
      and says what it opens (`aria-expanded`, `aria-haspopup`, `aria-controls`), with a
      spec that asserts it.
- [ ] **Said once**: no fact appears twice on the same screen, and no component is
      mounted twice over the same store.
- [ ] **Scale parity**: nothing routine below 12 px, body at 14 px, labelled buttons at
      the default size. `grep -rn "text-xs" src/flow` returns nothing.
- [ ] **Banner scale**: the full-width coloured field is a connection-level state, not a
      count.
- [ ] **No narrator captions**; no `daemon` in user-visible copy.
- [ ] **Copy standard met** for every string you touched: ≤ 20 words, one
      instruction per sentence, active voice, present tense, no contractions,
      no `" — "` joining two clauses.
- [ ] **Vocabulary clean.** `grep -rn " — " src/flow` returns only comments, and
      the glossary's banned words appear only as identifiers. The sweeps that
      hold this are `GIT_WORDS` in `tests/flow-workbench-ui.spec.ts` over
      rendered text, and `no_git_words` in `tests/daemon/helpers.py` over the
      CLI, `AGENTS.md`, the connect prompt, the handoff payloads and the MCP
      tool list. A new surface that renders copy gets added to one of them.
- [ ] **Guide quotes in sync**: `docs/user-guide.md` names sections, buttons and command
      strings by what the UI actually spells. The guide follows reality.
- [ ] **Gallery updated**: new or changed shared components have a `/flow/design` entry.
- [ ] **Gates pass**: `npm run type-check`, `npm run lint`, `npm test` from `frontend/`.
