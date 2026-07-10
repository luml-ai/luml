---
sidebar_label: 'Terminal UI'
sidebar_position: 4
title: Terminal UI
---

# Terminal UI

:::warning Experimental

The terminal interface is **experimental**. Keyboard bindings, screens, and command-line flags may change between releases without a deprecation period. The browser interface (`lumlflow ui`) remains the primary way to use Flow.

:::

Flow includes a terminal interface for environments where a browser is impractical: remote machines over SSH, containers, or headless training servers. It reads the same local experiment store as the browser interface and exposes the same data — groups, experiments, metrics, traces, evaluation results, and attachments.

```bash
lumlflow tui
```

Without arguments, the store is resolved from the project configuration (`BACKEND_STORE_URI`), the same way `lumlflow ui` resolves it. The `--path` option points the interface at a specific store instead.

A training script can also be launched under the interface:

```bash
lumlflow tui train.py --epochs 10
```

The script runs as a child process against the same store. The interface attaches to the experiment the script creates and follows it live: log output, status, and metrics update as the run progresses. `Ctrl+C` targets the running script rather than the interface, so interrupting training does not tear down the UI. Arguments after the script name are passed through to the script.

## Navigation

Screens form a stack. `Enter` opens the focused item (a group, an experiment, a trace), and `Esc` or `q` returns to the previous screen. `Ctrl+←` and `Ctrl+→` move backward and forward through screen history, as in a browser. Arrow keys always move within the current screen — between table rows, chart cells, or tree nodes — and never change screens. On the home screen, where there is nothing to go back to, pressing `q` twice exits the application.

Key bindings are discoverable from three places. The footer lists the keys that apply to the current screen and, on the experiment view, to the active tab. `?` opens a searchable cheat-sheet of every binding, beginning with the ones available on the current screen. `:` opens a command palette that runs any action by name, including actions that have no key binding. The interface also responds to the mouse: rows, tabs, breadcrumb segments, and column headers are clickable.

Data refreshes automatically every two seconds. `r` forces an immediate refresh, `R` toggles auto-refresh, and the `--refresh-interval` and `--no-auto-refresh` flags set the initial behavior. The refresh interval can also be changed at runtime through the command palette.

## Screens

The screen hierarchy mirrors the browser interface: groups, the experiments of a group, and a detailed view per experiment, with trace and evaluation detail screens one level deeper.

The home screen lists experiment groups. `/` starts an incremental search and `s` opens the sort dialog; clicking a column header sorts by that column. The experiments list adds an advanced filter (`f`) that accepts the same expression syntax as the browser interface's search bar, for example `accuracy >= 0.8`, plus multi-select: `Space` marks experiments — the selection survives navigation across groups — and `c` opens a comparison of the marked runs with a parameter diff, a metric overlay chart, and evaluation scores side by side.

The experiment view mirrors the browser's [Experiment View](./experiment_view.md) as five tabs — Overview, Metrics, Traces, Evals, and Attachments — reachable by their first letter, by position (`1`–`5`), or by cycling with `Tab`. The Metrics tab renders one chart per metric; arrow keys move between charts and `Enter` zooms into one. Inside the zoom, `←`/`→` step to the adjacent metric, and `S`, `L`, and `X` toggle smoothing, log-scale, and the x-axis between step and elapsed time. The Attachments tab previews text files inline and saves any file to disk with `s`; the path prompt completes filesystem paths as you type.

## Publishing to LUML

Publishing follows the same [Registry](../../documentation/Modules/Registry/registry.md) flow as [Uploading to LUML](./uploading.md) in the browser: an API key gate, then Organization → Orbit → Collection selection. A key that is already configured is picked up automatically; otherwise the flow prompts for one and stores it for future publishes.

There are three entry points. `p` on an experiment — in the list or in the experiment view — publishes that experiment. `p` on a focused model row in the Overview tab publishes that single model, optionally embedding the experiment inside the model file. `u`, available on any screen, uploads an arbitrary artifact file from disk, the counterpart of the Registry's "add artifact" dialog.

## Key reference

The authoritative list is the `?` cheat-sheet inside the application. The keys below are global.

| Key | Action |
|-----|--------|
| `?` | Help cheat-sheet |
| `:` | Command palette |
| `Enter` | Open focused item |
| `Esc` / `q` | Back |
| `Ctrl+←` / `Ctrl+→` | Screen history |
| `/` | Search |
| `r` / `R` | Refresh / toggle auto-refresh |
| `p` | Publish experiment or model |
| `u` | Upload a file to LUML |
| `Ctrl+T` | Toggle dark/light theme |
| `Ctrl+C` | Quit |

## Limitations

The terminal interface does not yet match the browser feature for feature. Column customization on the experiments table is not available. Charts are drawn with terminal characters at correspondingly lower resolution. Inline image preview depends on the terminal's graphics support; terminals without it fall back to save-to-disk. Copying values (`y`) uses the OSC 52 escape sequence, which some terminals and multiplexers disable by default.
