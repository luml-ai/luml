import io
import logging
from unittest.mock import Mock

import pytest

from conda_manager import ModelCondaManager


@pytest.mark.parametrize("line_count", [0, 3, 10_000])
def test_worker_stderr_keeps_only_recent_lines_and_logs_at_info(
    line_count: int, caplog: pytest.LogCaptureFixture
) -> None:
    manager = ModelCondaManager("model-env", Mock(), "/model")
    lines = [f'INFO: 127.0.0.1 - "POST /compute HTTP/1.1" 200 OK #{i}' for i in range(line_count)]
    manager.process = Mock(stderr=io.StringIO("\n".join(lines)), poll=Mock(return_value=0))

    with caplog.at_level(logging.INFO, logger="conda_manager"):
        manager._monitor_stderr()

    assert list(manager._error_output) == lines[-manager.WORKER_LOGS_LINES :]
    assert [record.getMessage() for record in caplog.records] == [
        f"[conda_worker] {line}" for line in lines
    ]
    assert all(record.levelno == logging.INFO for record in caplog.records)


def test_failed_worker_reports_the_recent_stderr_in_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = ModelCondaManager("model-env", Mock(), "/model")
    lines = [f"worker line {i}" for i in range(100)]
    manager.process = Mock(
        stderr=io.StringIO("\n\n".join(f"  {line}  " for line in lines)),
        poll=Mock(return_value=7),
    )

    with caplog.at_level(logging.ERROR, logger="conda_manager"):
        manager._monitor_stderr()

    assert [record.getMessage() for record in caplog.records] == [
        "Conda worker process exited with code 7"
    ]
    with pytest.raises(RuntimeError) as error:
        manager._check_process_status()
    assert str(error.value).splitlines() == [
        "Conda worker process exited with code 7",
        *lines[-manager.WORKER_LOGS_LINES :],
    ]


def test_stderr_read_failure_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    manager = ModelCondaManager("model-env", Mock(), "/model")
    stream = Mock()
    stream.__iter__ = Mock(side_effect=OSError("closed stream"))
    manager.process = Mock(stderr=stream)

    with caplog.at_level(logging.ERROR, logger="conda_manager"):
        manager._monitor_stderr()

    assert caplog.messages == ["Error monitoring stderr: closed stream"]
