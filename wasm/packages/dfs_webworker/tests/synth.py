"""Deterministic synthetic series for forecasting tests."""

import numpy as np
import pandas as pd


def dates(n: int, freq: str = "MS", start: str = "2020-01-01") -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.date_range(start, periods=n, freq=freq)]


def seasonal(
    n: int,
    seed: int = 0,
    level: float = 100.0,
    slope: float = 1.0,
    amp: float = 15.0,
    period: int = 12,
    noise: float = 3.0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return level + slope * t + amp * np.sin(2 * np.pi * t / period) + rng.normal(0, noise, n)


def trend(
    n: int, seed: int = 1, level: float = 10.0, slope: float = 2.0, noise: float = 1.0
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return level + slope * t + rng.normal(0, noise, n)


def records(date_list: list[str], **cols: np.ndarray) -> list[dict]:
    return [
        {"date": date_list[i], **{k: float(v[i]) for k, v in cols.items()}}
        for i in range(len(date_list))
    ]
