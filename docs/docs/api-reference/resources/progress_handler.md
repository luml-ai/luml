<a id="luml_api.utils.progress"></a>

# luml\_api.utils.progress

<a id="luml_api.utils.progress.BaseProgressHandler"></a>

## BaseProgressHandler Objects

```python
class BaseProgressHandler(ABC)
```

Base class for handling progress updates during upload/download processes.

This abstract base class provides a framework for tracking progress of
an upload or download operation.

<a id="luml_api.utils.progress.BaseProgressHandler.start"></a>

#### start

```python
def start(file_name: str, total: int) -> None
```

Called before upload / download starts.

<a id="luml_api.utils.progress.BaseProgressHandler.update"></a>

#### update

```python
def update(chunk_size: int) -> None
```

Called with each chunk's byte size. Accumulates and calls on_chunk.

<a id="luml_api.utils.progress.BaseProgressHandler.on_chunk"></a>

#### on\_chunk

```python
@abstractmethod
def on_chunk(uploaded: int, total: int) -> None
```

Called with cumulative uploaded and total bytes after each chunk.

<a id="luml_api.utils.progress.BaseProgressHandler.finish"></a>

#### finish

```python
@abstractmethod
def finish() -> None
```

Called when upload / download completes.

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
- `_description_shown` _bool_ - Indicates whether the file upload description
  has already been displayed.

<a id="luml_api.utils.progress.PrintProgressHandler.on_chunk"></a>

#### on\_chunk

```python
def on_chunk(uploaded: int, total: int) -> None
```

Handles progress updates for file upload by processing
chunks and printing a progress bar.

**Arguments**:

- `uploaded` _int_ - The number of bytes that have been uploaded so far.
- `total` _int_ - The total number of bytes to be uploaded.

