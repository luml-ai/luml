"""Terminal narration playback with a typing effect.

Narration files are plain text streamed line by line. Lines starting with
`@sleep <seconds>` pause playback instead of printing. All delays scale with
the speed factor (PRISMA_DEMO_SPEED env or --speed flag); 0 disables delays,
which keeps tests instant.
"""

import contextlib
import os
import random
import sys
import time
from pathlib import Path

from luml_prisma.demo.scenario import PlaybackConfig

_SPEED_ENV_VAR = "PRISMA_DEMO_SPEED"
_SLEEP_DIRECTIVE = "@sleep "


def resolve_speed(cli_value: float | None = None) -> float:
    if cli_value is not None:
        return max(cli_value, 0.0)
    raw = os.environ.get(_SPEED_ENV_VAR, "").strip()
    if not raw:
        return 1.0
    try:
        return max(float(raw), 0.0)
    except ValueError:
        return 1.0


def _sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _emit(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def play_line(line: str, config: PlaybackConfig, speed: float) -> None:
    char_delay = config.char_delay_ms / 1000 * speed
    for ch in line:
        _emit(ch)
        _sleep(char_delay)
    _emit("\n")
    jitter = random.uniform(0, config.jitter_ms / 1000) if config.jitter_ms else 0.0
    _sleep((config.line_delay_ms / 1000 + jitter) * speed)


def play_narration(path: Path, config: PlaybackConfig, speed: float) -> None:
    for line in path.read_text().splitlines():
        if line.startswith(_SLEEP_DIRECTIVE):
            with contextlib.suppress(ValueError):
                _sleep(float(line[len(_SLEEP_DIRECTIVE):]) * speed)
            continue
        play_line(line, config, speed)
