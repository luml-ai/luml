import pytest

from luml_api.utils.progress import BaseProgressHandler, PrintProgressHandler


class _RecordingHandler(BaseProgressHandler):
    def __init__(self) -> None:
        self.chunks: list[tuple[int, int]] = []
        self.finished = False

    def on_chunk(self, uploaded: int, total: int) -> None:
        self.chunks.append((uploaded, total))

    def finish(self) -> None:
        self.finished = True


def test_base_update_accumulates_and_calls_on_chunk() -> None:
    handler = _RecordingHandler()
    handler.start("model.fnnx", total=100)

    handler.update(30)
    handler.update(20)

    assert handler.chunks == [(30, 100), (50, 100)]


def test_base_start_resets_progress() -> None:
    handler = _RecordingHandler()
    handler.start("a", total=10)
    handler.update(5)
    handler.start("b", total=20)

    handler.update(4)

    assert handler.chunks[-1] == (4, 20)


def test_print_handler_shows_description_once(capsys: pytest.CaptureFixture) -> None:
    handler = PrintProgressHandler()
    handler.start("model.fnnx", total=100)

    handler.update(50)
    handler.update(50)

    out = capsys.readouterr().out
    assert out.count('Processing file "model.fnnx"...') == 1


def test_print_handler_partial_bar(capsys: pytest.CaptureFixture) -> None:
    handler = PrintProgressHandler()
    handler.start("model.fnnx", total=100)

    handler.update(50)

    out = capsys.readouterr().out
    assert "50.0%" in out
    assert ">" in out  # partial bar uses the arrow head


def test_print_handler_full_bar(capsys: pytest.CaptureFixture) -> None:
    handler = PrintProgressHandler()
    handler.start("model.fnnx", total=100)

    handler.update(100)

    out = capsys.readouterr().out
    assert "100.0%" in out
    assert "[" + "=" * 30 + "]" in out


def test_print_handler_zero_total_skips_bar(capsys: pytest.CaptureFixture) -> None:
    handler = PrintProgressHandler()
    handler.start("model.fnnx", total=0)

    handler.update(0)

    out = capsys.readouterr().out
    assert 'Processing file "model.fnnx"...' in out
    assert "%" not in out


def test_print_handler_no_filename_skips_description(
    capsys: pytest.CaptureFixture,
) -> None:
    handler = PrintProgressHandler()
    handler.start("", total=100)

    handler.update(50)

    out = capsys.readouterr().out
    assert "Processing file" not in out
    assert "50.0%" in out


def test_print_handler_finish_prints_newline(capsys: pytest.CaptureFixture) -> None:
    handler = PrintProgressHandler()

    handler.finish()

    assert capsys.readouterr().out == "\n"
