# Proposals

## Problem

Dataset artifacts in the SDK cannot carry an HTML documentation card. Model artifacts already support this via `ModelReference.add_model_card()`, which embeds a self-contained HTML file into the `.tar` artifact. Users who want to document a dataset — describing its schema, provenance, statistics, or visualizations — have no equivalent mechanism.

## Solution

Rename `ModelCardBuilder` to `CardBuilder` (the name no longer implies it is model-only), keep `ModelCardBuilder` as a re-exported alias so existing code continues to work. Move the class into a new `luml.card` package; `model_card` becomes a pure backward-compat shim. Add `add_dataset_card(html_content: str | CardBuilder)` to `DatasetReference`, mirroring the existing `ModelReference.add_model_card()` API exactly. The same builder class produces the HTML; only the storage tag and zip filename differ. A one-line frontend regex update makes the existing Card tab detect and display dataset cards transparently.

## Why This Approach

- Renames the builder to the more accurate `CardBuilder`; the alias keeps backward compatibility with no migration burden.
- Purely additive otherwise: no existing method signatures change.
- The Card tab display logic in the frontend (`CardView.vue`) already handles generic HTML cards for any artifact type; only card _detection_ needs updating.

---

# Design

## SDK changes

### Move `_append_metadata` to `DiskReference`

`_append_metadata` currently lives on `ModelReference` in `sdk/python/sdk/luml/artifacts/model.py`. Both `ModelReference` and `DatasetReference` inherit from `DiskReference` (`_base.py`). Move `_append_metadata` to `DiskReference` so both subclasses can call it without duplication.

Signature (unchanged from current implementation):

```python
def _append_metadata(
    self,
    idx: str | None,
    tags: list[str],
    payload: dict[str, Any],
    data: list[FileMap],
    prefix: str | None = None,
) -> None: ...
```

### `DatasetReference.add_dataset_card()`

Add to `sdk/python/sdk/luml/artifacts/dataset/_reference.py`:

```python
def add_dataset_card(self, html_content: str | CardBuilder) -> None:
    if not isinstance(html_content, str):
        if isinstance(html_content, CardBuilder):
            html_content = html_content.build()
        else:
            msg = "html_content must be a string or CardBuilder instance"
            raise TypeError(msg)

    tag = "dataforce.studio::dataset_card:v1"

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("index.html", html_content)

    zip_buffer.seek(0)
    file = MemoryFile(zip_buffer.read())

    self._append_metadata(
        idx=None,
        tags=[tag],
        payload={},
        prefix=tag,
        data=[FileMap(file=file, remote_path="dataset_card.zip")],
    )
```

Tag: `dataforce.studio::dataset_card:v1`
Archive entry name: `dataset_card.zip` (contains `index.html`)
Resulting tar path: `meta_artifacts/dataforce.studio~c~~c~dataset_card~c~v1~~et~~{uuid}/dataset_card.zip`

### Imports needed in `_reference.py`

```python
import io
import zipfile
from luml.artifacts._base import FileMap, MemoryFile
from luml.model_card.builder import CardBuilder
```

### New `card/` package — canonical home for `CardBuilder`

Create `sdk/python/sdk/luml/card/` as a new package:

- `sdk/python/sdk/luml/card/builder.py` — move the `CardBuilder` class here (renamed from `ModelCardBuilder`). Update its internal import of templates to use `luml.card.templates`.
- `sdk/python/sdk/luml/card/templates.py` — move `get_html_template`, `plot_container`, `plotly_container`, `table_container`, `image_container`, `get_default_css` here from `model_card/templates.py`.
- `sdk/python/sdk/luml/card/__init__.py`:
  ```python
  from luml.card.builder import CardBuilder
  __all__ = ["CardBuilder"]
  ```

### `model_card/` becomes a backward-compat shim

- `sdk/python/sdk/luml/model_card/builder.py`:
  ```python
  from luml.card.builder import CardBuilder
  ModelCardBuilder = CardBuilder
  __all__ = ["ModelCardBuilder"]
  ```
- `sdk/python/sdk/luml/model_card/templates.py`:
  ```python
  from luml.card.templates import *  # noqa: F401, F403
  ```
- `sdk/python/sdk/luml/model_card/__init__.py`:
  ```python
  from luml.model_card.builder import ModelCardBuilder
  __all__ = ["ModelCardBuilder"]
  ```

### `luml/__init__.py` exports

```python
from luml.card import CardBuilder
from luml.model_card import ModelCardBuilder  # backward-compat alias

__all__ = [
    ...
    "CardBuilder",
    "ModelCardBuilder",
    ...
]
```

All new internal usages (`model.py`, `_reference.py`, new tests) import from `luml.card`. The `model_card` shim is for callers who already use `ModelCardBuilder` or `from luml.model_card import ...`.

## Frontend changes

### `FnnxService.findHtmlCard()` — `frontend/src/lib/fnnx/FnnxService.ts:162`

Current regex:
```ts
/meta_artifacts\/dataforce\.studio~c~~c~[^/]+~c~v1~~et~~.+?\/model_card\.zip$|^card\.zip$/
```

Updated regex (also matches `dataset_card.zip`):
```ts
/meta_artifacts\/dataforce\.studio~c~~c~[^/]+~c~v1~~et~~.+?\/(?:model_card|dataset_card)\.zip$|^card\.zip$/
```

No other frontend changes needed:
- `isCardAvailable` in `index.vue:120-125` already uses `findHtmlCard` generically for all artifact types.
- `CardView.vue:setHtmlData()` already downloads and renders any HTML card zip regardless of artifact type.
- `ArtifactTabs.vue` already shows the Card tab for all artifacts (with `showCard: true`).

## Backward compatibility

- `ModelReference.add_model_card()` accepts `str | CardBuilder`; internally it will use `CardBuilder`. The old name `ModelCardBuilder` is an alias pointing to the same class, so callers passing a `ModelCardBuilder` instance continue to work without changes.
- The frontend regex is extended with `|dataset_card` inside a non-capturing group — existing `model_card.zip` paths continue to match.
- `DatasetReference` gets a new method; no existing methods change signatures.

## Tests

New test file: `sdk/python/sdk/tests/artifacts/test_dataset_card.py`

Mirrors the structure of `sdk/python/sdk/tests/test_model_card.py:180-253` (the `ModelReference` integration tests).

---

# Scenarios

## Scenario: Add dataset card from CardBuilder instance
**Given** a saved dataset tar file (created via `save_tabular_dataset` or `save_hf_dataset`)  
**And** a `CardBuilder` instance with heading and paragraph content  
**When** `dataset_ref.add_dataset_card(builder)` is called  
**Then** the tar file contains a file matching `meta_artifacts/dataforce.studio~c~~c~dataset_card~c~v1~~et~~.*/dataset_card\.zip`  
**And** that zip contains `index.html` with the built HTML content

## Scenario: Add dataset card from raw HTML string
**Given** a dataset `DatasetReference`  
**And** an HTML string `"<html><body>Dataset docs</body></html>"`  
**When** `dataset_ref.add_dataset_card(html_string)` is called  
**Then** the tar contains a `dataset_card.zip` entry in the expected meta path  
**And** the zip's `index.html` contains the original HTML string

## Scenario: Invalid type raises TypeError
**Given** a `DatasetReference`  
**When** `dataset_ref.add_dataset_card(12345)` is called  
**Then** a `TypeError` is raised with message containing `"must be a string or CardBuilder instance"`

## Scenario: Frontend detects dataset card
**Given** a dataset artifact whose `file_index` contains a key matching  
`meta_artifacts/dataforce.studio~c~~c~dataset_card~c~v1~~et~~abc123/dataset_card.zip`  
**When** `FnnxService.findHtmlCard(fileIndex)` is called  
**Then** the matching key is returned (not `undefined`)

## Scenario: Frontend does not detect model card under dataset card regex (no regression)
**Given** a model artifact whose `file_index` contains  
`meta_artifacts/dataforce.studio~c~~c~model_card~c~v1~~et~~abc123/model_card.zip`  
**When** `FnnxService.findHtmlCard(fileIndex)` is called  
**Then** the key is still returned (regex still matches `model_card.zip`)

## Scenario: Existing model card behavior is unchanged
**Given** a `ModelReference` with a card added via `add_model_card()`  
**When** the artifact is loaded in the frontend  
**Then** the Card tab is enabled and displays the HTML card as before  
**And** no regressions exist in tabular or prompt-optimization card display

## Scenario: Dataset without a card — Card tab disabled
**Given** a dataset artifact with no `dataset_card.zip` entry in `file_index`  
**When** the artifact detail page loads  
**Then** `isCardAvailable` is `false`  
**And** the Card tab is visible but disabled

## Scenario: Dataset with card — Card tab enabled and renders HTML
**Given** a dataset artifact whose `file_index` contains a valid `dataset_card.zip` path  
**When** the user navigates to the artifact detail page  
**Then** the Card tab is enabled  
**And** clicking it loads the HTML from the zip and renders it in the iframe

---

# Tasks

- [x] **Task 1: Create `card/` package, move `CardBuilder` and templates, wire `model_card/` as shim**
  - [x] Create `sdk/python/sdk/luml/card/` with `__init__.py`, `builder.py`, `templates.py`
  - [x] Move the builder class body from `model_card/builder.py` into `card/builder.py`, renaming the class to `CardBuilder`; update its import of templates to `from luml.card.templates import ...`
  - [x] Move all template functions from `model_card/templates.py` into `card/templates.py`
  - [x] Rewrite `model_card/builder.py` as a shim: `from luml.card.builder import CardBuilder; ModelCardBuilder = CardBuilder`
  - [x] Rewrite `model_card/templates.py` as a shim: `from luml.card.templates import *  # noqa: F401, F403`
  - [x] Rewrite `model_card/__init__.py` as a shim: `from luml.model_card.builder import ModelCardBuilder; __all__ = ["ModelCardBuilder"]`
  - [x] Update `card/__init__.py`: `from luml.card.builder import CardBuilder; __all__ = ["CardBuilder"]`
  - [x] Update `luml/__init__.py` to import `CardBuilder` from `luml.card` and `ModelCardBuilder` from `luml.model_card`; add `CardBuilder` to `__all__`
  - [x] Update `model.py` (`ModelReference.add_model_card`) to import `CardBuilder` from `luml.card.builder` instead of `luml.model_card.builder`; update type annotation in `add_model_card` to `str | CardBuilder`
  - [x] Verify existing `test_model_card.py` still passes without modification (it imports `ModelCardBuilder` via the alias)
  - [x] Run `pytest sdk/python/sdk/tests/` and confirm all tests pass

- [ ] **Task 2: Move `_append_metadata` to `DiskReference` and add `DatasetReference.add_dataset_card()`**
  - [ ] Move `_append_metadata` from `ModelReference` (`sdk/python/sdk/luml/artifacts/model.py`) to `DiskReference` (`sdk/python/sdk/luml/artifacts/_base.py`), keeping the method body identical; add the necessary imports (`io`, `tarfile`, `uuid`, `zipfile`) to `_base.py`
  - [ ] Remove `_append_metadata` from `ModelReference` (it now inherits from `DiskReference`)
  - [ ] Add `add_dataset_card(html_content: str | CardBuilder) -> None` to `DatasetReference` in `sdk/python/sdk/luml/artifacts/dataset/_reference.py`
  - [ ] Add required imports to `_reference.py`: `io`, `zipfile`, `FileMap`, `MemoryFile` from `luml.artifacts._base`, and `CardBuilder` from `luml.card.builder`
  - [ ] Write tests in `sdk/python/sdk/tests/artifacts/test_dataset_card.py` covering:
    - `add_dataset_card` with a `CardBuilder` instance — verify zip at expected tar path, `index.html` has correct HTML
    - `add_dataset_card` with a raw HTML string — same verification
    - `add_dataset_card` with an invalid type raises `TypeError` with message containing `"must be a string or CardBuilder instance"`
    - Verify `DatasetReference` still validates correctly after adding a card (`ref.validate()` returns `True`)
  - [ ] Run `pytest sdk/python/sdk/tests/` and confirm all tests pass

- [ ] **Task 3: Update frontend regex to detect dataset cards**
  - [ ] In `frontend/src/lib/fnnx/FnnxService.ts:162`, update the regex in `findHtmlCard()` from  
    `model_card\.zip` to `(?:model_card|dataset_card)\.zip`
  - [ ] Write unit tests (new file or add cases to an existing test file) verifying:
    - `findHtmlCard` returns the key when `file_index` contains a `dataset_card.zip` path
    - `findHtmlCard` still returns the key for existing `model_card.zip` paths (no regression)
    - `findHtmlCard` returns `undefined` when `file_index` has no matching entry
  - [ ] Run the frontend test suite and confirm all tests pass
