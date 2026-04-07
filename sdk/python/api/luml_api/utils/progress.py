from abc import ABC, abstractmethod


class BaseProgressHandler(ABC):
    """
    Base class for handling progress updates during upload/download processes.

    This abstract base class provides a framework for tracking progress of
    an upload or download operation.
    """

    _uploaded: int = 0
    _total: int = 0

    def start(self, file_name: str, total: int) -> None:
        """Called before upload / download starts."""
        self._uploaded = 0
        self._total = total

    def update(self, chunk_size: int) -> None:
        """
        Called with each chunk's byte size. Accumulates and calls on_chunk.
        """
        self._uploaded += chunk_size
        self.on_chunk(self._uploaded, self._total)

    @abstractmethod
    def on_chunk(self, uploaded: int, total: int) -> None:
        """
        Called with cumulative uploaded and total bytes after each chunk.
        """
        ...

    @abstractmethod
    def finish(self) -> None:
        """
        Called when upload / download completes.
        """


class PrintProgressHandler(BaseProgressHandler):
    """
    Handles and displays progress updates for a file upload process.

    This class provides visual feedback during the file upload process
    by printing a progress bar to the console. It tracks the progress
    of chunks uploaded, displays an indicative progress bar and
    percentage, and signals the completion of the upload.

    Attributes:
        _file_name (str): The name of the file currently being uploaded.
        _description_shown (bool): Indicates whether the file upload description
            has already been displayed.
    """

    def __init__(self) -> None:
        self._file_name = ""
        self._description_shown = False

    def start(self, file_name: str, total: int) -> None:
        super().start(file_name, total)
        self._file_name = file_name
        self._description_shown = False

    def on_chunk(self, uploaded: int, total: int) -> None:
        """
        Handles progress updates for file upload by processing
        chunks and printing a progress bar.

        Args:
            uploaded (int): The number of bytes that have been uploaded so far.
            total (int): The total number of bytes to be uploaded.
        """
        if not self._description_shown and self._file_name:
            print(f'Processing file "{self._file_name}"...')  # noqa: T201
            self._description_shown = True

        if total > 0:
            progress = (uploaded / total) * 100
            bar_length = 30
            filled_length = int(bar_length * uploaded // total)
            if filled_length >= bar_length:
                bar = "=" * bar_length
            else:
                bar = "=" * filled_length + ">" + " " * (bar_length - filled_length - 1)
            print(f"\r[{bar}] {progress:.1f}%", end="", flush=True)  # noqa: T201

    def finish(self) -> None:
        print()  # noqa: T201
