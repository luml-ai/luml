<a id="luml_api.utils.progress"></a>

# luml_api.utils.progress

<a id="luml_api.utils.progress.PrintProgressHandler"></a>

## PrintProgressHandler Objects

```python
class PrintProgressHandler(BaseProgressHandler)
```

Handles and displays progress updates for a file upload process.

This class provides visual feedback during the file upload process
by printing a progress bar to the console. It tracks the progress
of chunks uploaded, displays an indicative progress bar and
percentage, and signals the completion of the upload.

**Attributes**:

- `_file_name` _str_ - The name of the file currently being uploaded.
- `_description_shown` _bool_ - Indicates whether the file upload description has already been displayed.

<a id="luml_api.utils.progress.PrintProgressHandler.on_chunk"></a>

#### on_chunk

```python
def on_chunk(uploaded: int, total: int) -> None
```

Handles progress updates for file upload by processing
chunks and printing a progress bar.

**Arguments**:

- `uploaded` _int_ - The number of bytes that have been uploaded so far.
- `total` _int_ - The total number of bytes to be uploaded.

