"""Shared helpers for the HKEX ``getchartdata2`` price-chart feed."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

HKT = timezone(timedelta(hours=8))

_SOURCE: dict[str, tuple[int, int | None]] = {
    "1m": (1, None),
    "5m": (2, None),
    "15m": (2, 15),
    "30m": (2, 30),
    "1h": (5, None),
    "1d": (6, None),
    "1W": (7, None),
    "1M": (8, None),
    "1Q": (9, None),
}
_INTRADAY = {"1m", "5m", "15m", "30m", "1h"}
_MAX_PERIOD = 8

INTERVAL_CHOICES = ["1m", "5m", "15m", "30m", "1h", "1d", "1W", "1M", "1Q"]


def is_intraday(interval: str) -> bool:
    return interval in _INTRADAY


def chart_kwargs(interval: str) -> dict:
    span = _SOURCE[interval][0]
    return {"hchart": 1, "span": span, "int": _MAX_PERIOD if span >= 6 else 1}


def bar_datetime(ts_ms: float):
    return datetime.fromtimestamp(ts_ms / 1000, tz=HKT)


def maybe_resample(interval: str, bars: list) -> list:
    minutes = _SOURCE[interval][1]
    if not minutes:
        return bars
    bucket = minutes * 60_000
    grouped: dict[int, list] = {}
    order: list[int] = []
    for b in bars:
        if not b or len(b) < 5 or b[1] is None:
            continue
        start = (int(b[0]) // bucket) * bucket
        if start not in grouped:
            grouped[start] = []
            order.append(start)
        grouped[start].append(b)
    out: list = []
    for start in order:
        g = grouped[start]
        highs = [x[2] for x in g if len(x) > 2 and x[2] is not None]
        lows = [x[3] for x in g if len(x) > 3 and x[3] is not None]
        vols = [x[5] for x in g if len(x) > 5 and x[5] is not None]
        turns = [x[6] for x in g if len(x) > 6 and x[6] is not None]
        out.append(
            [
                start,
                g[0][1],
                max(highs) if highs else g[0][1],
                min(lows) if lows else g[0][1],
                g[-1][4],
                sum(vols) if vols else None,
                sum(turns) if turns else None,
            ]
        )
    return out
