import os
import signal
import subprocess
import sys


def test_sigterm_stops_the_worker() -> None:
    script = """
import asyncio
import subprocess
import sys
from unittest.mock import patch
import main

class Worker:
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    def stop(self):
        self.process.terminate()
        self.process.wait(timeout=5)
        print('stopped', flush=True)

class Handler:
    conda_worker = Worker()
    def __init__(self):
        print('ready', flush=True)

with patch.object(main, 'ModelHandler', Handler):
    asyncio.run(main.main())
"""
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", script], stdout=subprocess.PIPE, text=True
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "ready"
        os.kill(process.pid, signal.SIGTERM)
        output, _ = process.communicate(timeout=10)
        assert "stopped" in output
        assert process.returncode == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_interrupted_initialization_stops_the_worker() -> None:
    from unittest.mock import Mock, patch

    import pytest

    from handlers.model_handler import ModelHandler

    worker = Mock()
    worker.start.side_effect = SystemExit(0)
    with (
        patch.object(ModelHandler, "_get_model_cache_dir"),
        patch.object(ModelHandler, "_get_or_extract_model", return_value="/model"),
        patch.object(ModelHandler, "_create_model_env", return_value={"manager": Mock()}),
        patch.object(ModelHandler, "_get_env_name", return_value="env"),
        patch.object(ModelHandler, "_get_model_data_for_worker", return_value={}),
        patch("handlers.model_handler.ModelCondaManager", return_value=worker),
        pytest.raises(SystemExit),
    ):
        ModelHandler()
    worker.stop.assert_called_once()
