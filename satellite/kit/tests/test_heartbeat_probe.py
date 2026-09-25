import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from luml_heartbeat import (
    DEFAULT_HEARTBEAT_FILE,
    DEFAULT_INTERVAL_SECONDS,
    heartbeat_file_is_fresh,
    main,
    probe_settings,
)

from luml_satellite.declaration import SatelliteConfiguration
from luml_satellite.monitoring import heartbeat_file_is_fresh as exported_check


class TestHeartbeatProbe:
    def test_exits_zero_while_the_heartbeat_is_fresh(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        heartbeat = tmp_path / "heartbeat"
        heartbeat.touch()
        monkeypatch.setenv("MONITORING_HEARTBEAT_FILE", str(heartbeat))
        monkeypatch.setenv("MONITORING_INTERVAL_SEC", "10")

        with pytest.raises(SystemExit) as exit_info:
            main()

        assert exit_info.value.code == 0

    def test_exits_one_once_the_heartbeat_goes_stale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        heartbeat = tmp_path / "heartbeat"
        heartbeat.touch()
        stale = heartbeat.stat().st_mtime - 31
        os.utime(heartbeat, (stale, stale))
        monkeypatch.setenv("MONITORING_HEARTBEAT_FILE", str(heartbeat))
        monkeypatch.setenv("MONITORING_INTERVAL_SEC", "10")

        with pytest.raises(SystemExit) as exit_info:
            main()

        assert exit_info.value.code == 1

    def test_exits_one_when_the_worker_never_wrote_a_heartbeat(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MONITORING_HEARTBEAT_FILE", str(tmp_path / "missing"))
        monkeypatch.setenv("MONITORING_INTERVAL_SEC", "10")

        with pytest.raises(SystemExit) as exit_info:
            main()

        assert exit_info.value.code == 1

    @pytest.mark.parametrize("interval", ["", "   ", "not-a-number"])
    def test_falls_back_to_defaults_for_an_unusable_environment(self, interval: str) -> None:
        path, seconds = probe_settings({"MONITORING_INTERVAL_SEC": interval})

        assert path == DEFAULT_HEARTBEAT_FILE
        assert seconds == DEFAULT_INTERVAL_SECONDS

    def test_defaults_match_the_satellite_configuration(self) -> None:
        configuration = SatelliteConfiguration(SATELLITE_TOKEN="satellite-token")

        assert DEFAULT_HEARTBEAT_FILE == configuration.MONITORING_HEARTBEAT_FILE
        assert DEFAULT_INTERVAL_SECONDS == configuration.MONITORING_INTERVAL_SEC

    def test_the_monitoring_package_keeps_exporting_the_check(self) -> None:
        assert exported_check is heartbeat_file_is_fresh

    def test_the_probe_costs_no_satellite_imports(self) -> None:
        script = "import sys, luml_heartbeat; print('luml_satellite' in sys.modules)"

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout.strip() == "False"

    def test_the_installed_entry_point_answers_for_a_fresh_heartbeat(self, tmp_path: Path) -> None:
        executable = shutil.which("luml-monitoring-probe")
        assert executable is not None
        heartbeat = tmp_path / "heartbeat"
        heartbeat.touch()

        result = subprocess.run(
            [executable],
            env={
                **os.environ,
                "MONITORING_HEARTBEAT_FILE": str(heartbeat),
                "MONITORING_INTERVAL_SEC": "10",
            },
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr

    def test_the_wheel_ships_the_probe_module_and_entry_point(self, tmp_path: Path) -> None:
        uv = shutil.which("uv")
        if uv is None:
            pytest.skip("uv is not available to build the wheel")
        project = Path(__file__).resolve().parents[1]

        subprocess.run(
            [uv, "build", "--wheel", "--out-dir", str(tmp_path), str(project)],
            check=True,
            capture_output=True,
            text=True,
        )

        wheels = list(tmp_path.glob("*.whl"))
        assert len(wheels) == 1
        with zipfile.ZipFile(wheels[0]) as wheel:
            names = wheel.namelist()
            entry_points = next(
                wheel.read(name).decode() for name in names if name.endswith("entry_points.txt")
            )
        assert "luml_heartbeat.py" in names
        assert "luml-monitoring-probe = luml_heartbeat:main" in entry_points
