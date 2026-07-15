# LUML Design System

Design system for **LUML** — an open-source MLOps/LLMOps platform for managing the complete machine learning lifecycle (experiments, model registry, deployments, and client-side compute). Built by Dataforce Solutions.

> Tagline: **"A unified end-to-end AIOps platform — helping data scientists to build, manage and deploy AI solutions with ease."**

## Product landscape

LUML is a single product with multiple surfaces. The platform is organized around four core concepts (see `_source/` for the full definitions lifted from the project README):

- **Organizations** — root logical boundary; governs users, quotas, and storage.
- **Orbits** — project workspaces inside an Organization. "Orbit" because data & compute orbit around the workspace but aren't owned by it.
- **Satellites** — externally hosted compute nodes paired to LUML, which pull work from a queue and run it on user infrastructure.
- **Buckets** — cloud storage connected at the Organization level; file transfers happen client-side, never through LUML servers.

### Modules (the user-facing product surfaces)
| Module | Purpose |
|---|---|
| **Registry** | Centralized model versioning & artifact management (uses native `.luml` container format). |
| **Experiment Snapshots** | Structured logging of ML experiment runs + metrics / parameters / charts. |
| **LLM Tracing / Evals** | Visibility into LLM execution flow, prompt/response, latency, tokens, cost. |
| **Deployments** | Bind a registry artifact to a Satellite and expose a callable endpoint. |
| **Express Tasks** | AutoML + no-code LLM prompt optimization (Tabular Classification/Regression, Prompt Fusion, Notebooks, Forecasting). |
| **Notebooks** | In-browser JupyterLite (WASM Python, no backend). |
| **Data Agent** | Agent-driven data exploration. |

### Primary product surfaces for this design system
1. **Web app (`app.luml.ai`)** — the main authenticated workspace. Vue 3 + PrimeVue + custom theme tokens. This is the biggest UI surface.
2. **Marketing site (`luml.ai`)** — brand landing; hero/feature tiles visible in the GitHub README.
3. **Docs site (`docs.luml.ai`)** — Docusaurus-based.

The UI kit in this design system covers surface #1 (the app) only. Marketing/docs are out of scope unless a future iteration requests them.

---

## Sources consulted
- **Codebase**: `luml-ai/luml` on GitHub
  - `frontend/src/assets/theme/{light,dark}-theme.css` — 2,300-line auto-generated token set (PrimeVue-style `--p-*` variables) from Figma-derived JSON tokens. Original tokens in `frontend/tokens/`.
  - `frontend/src/assets/base.css`, `main.css`, `null.css` — global styles.
  - `frontend/src/components/layout/{LayoutHeader,LayoutSidebar}.vue` — app shell.
  - `frontend/src/components/ui/*` — UI primitives (buttons wrap `d-button` from PrimeVue; cards/inputs/toggles/etc).
  - `frontend/src/pages/*.vue` — HomePage (Express Tasks picker), SignIn, OrbitRegistry, OrbitDeployments, etc.
  - `frontend/src/assets/img/` — logos, task icons, provider icons, auth-service icons (all copied into `assets/`).
- **Brand imagery**: `Dataforce-Solutions/static_assets` — hero illustrations and feature panels (copied into `assets/screenshots/`).
- **Public README & docs**: `luml-ai/luml/README.md`, `luml-ai/luml/docs/`

No Figma was attached — tokens come from the committed Figma-token JSON that Style Dictionary compiles into the theme CSS.

---

## Content fundamentals

**Voice.** Matter-of-fact, technical, no hype. The product README describes mechanics ("the Satellite polls for new tasks, retrieves them, and runs them in its own environment") not benefits. UI copy is short, imperative, verb-first.

**Tone & person.** Third-person for concepts ("An Orbit is a project workspace"), second-person for direct instruction ("Pick a Machine Learning Task", "Welcome to LUML", "In order to use the inference URL, please authorize with your API key"). No "we" in product UI.

**Casing.**
- Sentence case for everything: buttons ("Sign in", "Create collection", "Create deployment"), titles ("Pick a Machine Learning Task"), nav items ("Express tasks", "Data Agent", "Deployments").
- Title Case reserved for proper nouns (the LUML domain concepts): **Organization, Orbit, Satellite, Bucket, Registry, Deployment, Collection, Experiment Snapshot**. These are always capitalized in prose.
- Machine names (tasks) use Title Case: "Tabular Classification", "Prompt Optimization", "Time Series Forecasting".

**Emoji.** Used in the GitHub README for section headers (🔬 📦 🚀 🔒 🏢 🌍 🧩) but **not** in the product UI. The app uses Lucide icons throughout instead. Don't introduce emoji into UI designs.

**Unicode ornaments.** The GitHub README uses `──────── ✨ Key Features ────────` decorative bars. Useful in marketing / docs headers; never in UI.

**Button copy examples.** "Sign in", "Sign up", "Log in", "Next", "Create collection", "Create deployment", "Create secret", "Add new Deployment". Prefer `<verb>` or `<verb> <noun>`. Use "next" (lowercase) inside task-card CTAs specifically.

**Empty-state copy example.** "Add new Deployment / Instantly deploy models in a single click."

**Toast/banner example.** "In order to use the inference URL, please authorize with your API key" — full sentence, period optional.

**Error copy.** Short; form-level: "Form is invalid". Field-level messages come from the resolver (zod).

**Task descriptions** (homepage) are a single sentence, feature + payoff:
> "Predict categories from table-structured data — ideal for tasks like customer segmentation, product classification, or fraud detection."

Em-dash is used as the break. Tooltips expand with an additional sentence of technical nuance.

---

## Visual foundations

### Palette
- **Brand blue** `#2673fd` — primary actions, links, active nav, focus rings. Not a gradient blue; pure saturated blue on white.
- **Slate neutrals** — full Tailwind-Slate ramp from `#f8fafc` (surface-50) to `#0a0a0a` (surface-950). Body text is `#334155` (slate-700), muted is `#64748b` (slate-500).
- **Content background** is `#f8fafc` (not pure white). Cards sit on top in pure white with a very soft shadow.
- **Semantic colors** follow Tailwind conventions: success `#22c55e`, info `#0ea5e9`, warn `#f97316`, danger `#ef4444`, help `#a855f7`. Each has a light tint pair used in tags/messages (e.g. success tag is `#dcfce7` bg / `#15803d` fg).
- **Signature gradient** — only appears on the default avatar and hero artwork: `linear-gradient(226deg, #add8fb 28%, #dfa3f0 98.72%)` (light blue → lavender-pink). Dark mode uses a three-stop variant with `#2673fd → #828bf7 → #dfa3f0`. Use sparingly; never on buttons or cards.

### Type
- **Inter** at weights 100–900 (loaded from Google Fonts in `main.css`). System fallbacks: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto.
- Base size `16px` (desktop), `14px` below 768px (`html { font-size: 14px }` media query).
- Weights used: 400 (body, tag), 500 (button, title, menu-link), 600 (section label, submenu label), 700 (badge). No italics anywhere.
- **Main title** (h1): 24px / 500 / lh 1.25 / tracking -0.48px. This tracking value shows up consistently — it's the distinctive thing about LUML's headings.
- **Card title**: 17.5px / 500.
- **Body**: 14px / 400 / lh 1.5.
- **Badge**: 10.5px / 700, all-caps not used.

### Spacing & sizing
- Grid built on a 3.5px step (PrimeVue convention): 3.5, 7, 10.5, 14, 17.5, 24, 32, 40.
- Card body padding: **17.5px**. Form-field padding: **24px × 12px**. Modal padding: **17.5px**. Popover padding: **10.5px**.
- Header is **64px** tall. Sidebar: **180px** open / **67px** closed.
- Buttons: default 35px tall, 20/10 padding, 7px icon gap.

### Radii
- 4px — menu items (subtle)
- 6px — content cards, tags, badges, inputs when small
- 8px — buttons, inputs (default), github-pill in sidebar
- 12px — cards & modals (the "chunky" radius)
- 28px — rounded buttons (pill) — used on the big primary CTA on sign-in

### Backgrounds
- No full-bleed imagery inside the app. Content areas are solid `surface-50`.
- **Auth pages** are the one exception: the right-hand "form-bg.webp" panel is a full-bleed illustration with the signature blue→lavender gradient on it. The hero illustrations in marketing (see `assets/screenshots/hero-light.png`) use a purple/blue angled gradient backdrop with white UI screenshots floating on it.
- No repeating patterns, no noise/grain, no hand-drawn illustrations.

### Shadows & elevation
Very restrained. Two tiers:
- **Card/input shadow** — `0px 1px 2px 0px #1212170d` on inputs; the bespoke `--card-shadow` on cards is a five-stop curve that reads almost flat (mostly 0-opacity stops; visible as `0px 1px 3px rgba(28, 43, 64, 0.02)`).
- **Popover/modal** — `0px 4px 6px -1px #0000001a, 0px 2px 4px -2px #0000001a` (popover), stronger for modals.
No glow/colored shadows. No inner shadows.

### Borders
- 1px, `#e2e8f0` (slate-200) almost everywhere — dividers, card edges, input borders.
- Sidebar right edge, header bottom edge, and tab rail underline all use the same `--p-divider-border-color`.
- Active tab: 2px solid `--p-primary-color` (the brand blue) bottom border.
- No colored left-border accent cards (avoid that AI-slop trope).

### States
- **Hover (interactive text/nav)**: background shifts to `surface-100` (`#f1f5f9`), text to `surface-800` (`#1e293b`). No scale.
- **Hover (primary button)**: background goes from `#2673fd` → `#2563eb` (one step darker).
- **Active/pressed**: one more step darker (`#1d4ed8`). No shrink transform.
- **Active nav**: white (`surface-0`) pill with the full `--card-shadow`, text goes to `surface-800`. In dark mode the pill is `surface-900` with white text.
- **Focus ring**: 1px ring, 2px offset, color = `--p-primary-color` on primary buttons (transparent ring on inputs — border changes to blue instead).
- **Transitions**: 0.3s for color/background/width on nav + sidebar. Inputs/buttons don't animate except on sidebar toggle rotation (180°).
- **Disabled**: `surface-400` foreground on transparent background; no darkening. Cursor default, no hover effects.

### Layout rules
- Fixed app chrome: header (64px) across the top, sidebar (180px) on the left. Content scrolls in the remaining space.
- Content padding: `padding-top: 32px` on every page's top-level wrapper. Section gaps are 36–44px; intra-section gaps 12–20px.
- Max-width: no explicit cap on content — it fills. Pages self-regulate via the list/card grid.

### Transparency, blur
- `--p-mask-background: #00000066` on modal overlays — classic 40% black, no blur.
- Message banners use 95%-opacity backgrounds (`#eff6fff2`, `#f0fdf4f2`) — near-solid but admit a whisper of page color.
- No backdrop-filter blur anywhere.

### Imagery vibe
Product screenshots in the marketing README are composited onto a vibrant blue-purple gradient with white card chrome floating at a 3-5° tilt. The screenshots themselves are **warm-neutral** (blue-leaning charts, slate text, white backgrounds). No sepia, no B&W, no grain, no vignettes.

### Animation
Minimal. No spring/bounce easings, no Framer-style big transitions. Just:
- 0.3s `transition: color, background-color, width` on nav
- 0.5s `transition: width` on header-icon enter/leave
- 180° rotate on the sidebar-toggle chevron

---

## Iconography

**Primary system: `lucide-vue-next`** (`^0.460.0`). Icons are rendered inline as Vue components at specific pixel sizes — usually `:size="14"` for menu/button icons, `:size="20"` for page-header icons. Stroke icons, 1.5px weight, no fill. Always use Lucide unless you're handling one of the dedicated illustrated SVGs below.

Seen in the code: `Zap, File, Orbit, BotMessageSquare, MessageCircleCode, Folders, Rocket, Satellite, ArrowLeftToLine, Github, Star, X, Menu, Plus, BellRing, Lock`.

In web artifacts, load from CDN:
```html
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
```
Or use the per-icon SVG endpoints at `https://unpkg.com/lucide-static@latest/icons/<name>.svg`.

**Illustrated SVGs (custom, in `assets/`)**:
- `logo-full-light.svg` / `logo-full-dark.svg` — full wordmark (120×40).
- `logo-mark.svg` — mark only.
- `logo-mobile.svg` — compact mark.
- `task-icons/` — 5 bespoke 3-color illustrations for homepage task cards (tabular-classification, tabular-regression, forecasting, conversational-qa, notebook). Flat, not iconographic; use as hero elements.
- `providers/` — brand marks for OpenAI, Ollama, GPT, plus auth providers (GitHub, Google, Microsoft).
- `icons/csv.svg` — file-type chip.

**No icon font, no sprite sheet.** Lucide is imported per-icon in Vue; in HTML mocks pull individual SVGs.

**No emoji in UI.** Use Lucide for anything iconographic. Emoji is fine in marketing/README context only.

**Unicode characters as icons**: not used. The only Unicode ornamentation is the `────────` bar in the GitHub README decorative headers.

---

## File index

Root-level:
- `README.md` — this file.
- `colors_and_type.css` — CSS variables + semantic classes. Drop-in for any HTML artifact.
- `SKILL.md` — skill manifest (for Claude Code / Agent Skills).

Folders:
- `assets/` — logos, task icons, provider icons, CSV icon, brand screenshots.
- `assets/screenshots/` — marketing hero + feature panels (PNG).
- `preview/` — one HTML card per token/component group (rendered in the Design System tab).
- `ui_kits/app/` — Vue-free HTML/JSX recreation of the LUML web app.
- `fonts/` — empty (Inter loaded from Google Fonts).
- `_source/` — raw imports from the luml-ai/luml repo for reference (theme CSS, logos, task-icons). **Not** a supported public surface; use the cleaned-up copies in `assets/` and `colors_and_type.css` instead.

---

## Caveats & known gaps
- **Figma not attached.** Tokens come from the Figma→JSON export committed to the repo; no design-file URL was shared. If the Figma becomes available, re-verify the tokens.
- **Fonts.** Inter is loaded from Google Fonts at runtime; `fonts/` is empty. If offline use is needed, vendor Inter's woff2 files in.
- **Dark mode** is in the token set and selectors (`[data-theme='dark']`) but the preview cards demonstrate light mode only.
- **Marketing / docs surfaces** aren't covered by a UI kit — only the web app.
- **Auth hero image** (`form-bg.webp`) was referenced in SignInPage but not extracted from the repo; the sign-in kit screen uses a brand-gradient block instead. Flag for a swap-in.
