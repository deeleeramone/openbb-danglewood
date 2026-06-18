"""Bundled OpenBB Workspace app (apps.json) for the Yahoo Finance widgets."""

from pathlib import Path

_APPS_JSON = Path(__file__).resolve().parent.parent / "assets" / "apps.json"


def build_yfinance_apps() -> list[dict]:
    """Return the curated Yahoo Finance Workspace app from ``assets/apps.json``.

    A focused Overview tab pairs the TradingView chart with the styled asset info,
    linked by the ``Symbol`` parameter group so selecting a symbol in the chart
    flows to every connected widget.
    """
    import json

    try:
        return json.loads(_APPS_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
