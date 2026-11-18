# @luml/design-tokens

Shared design tokens (CSS variables) for all LUML web apps: `frontend`, `lumlflow/frontend`, `satellite/monitoring-ui` and the demo apps of `@luml/experiments` / `@luml/attachments`.

## Usage

```css
@import '@luml/design-tokens/index.css';
```

`index.css` includes both themes. They can also be imported separately:

| File | Selector |
|---|---|
| `@luml/design-tokens/light-theme.css` | `body` |
| `@luml/design-tokens/dark-theme.css` | `[data-theme='dark'] body` |

All variables are prefixed with `--p-` (e.g. `--p-surface-0`).

## Regenerating

Token sources live in `tokens/` and are synced from Figma. After updating them, run from the repository root:

```bash
npm run tokens
```

This builds `light-theme.css` and `dark-theme.css` with Style Dictionary (`build.mjs`) and formats them with Prettier. The generated files are committed.
