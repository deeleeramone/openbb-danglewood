"""Bundled OpenBB Workspace app (apps.json) for the Yahoo Finance widgets."""

from pathlib import Path

_APPS_JSON = Path(__file__).resolve().parent.parent / "assets" / "apps.json"

# Namespaces whose commands are served by a first-party OpenBB router when its
# extension is installed, and by this hybrid (under ``/yfinance/<namespace>``)
# when it is not. The Workspace derives a command's widget id from its route, so
# the same widget is ``<namespace>_<command>`` with the extension installed and
# ``yfinance_<namespace>_<command>`` without it.
_CONDITIONAL_NAMESPACES = (
    "equity",
    "etf",
    "derivatives",
    "index",
    "crypto",
    "currency",
    "news",
    "economy",
)


def _installed_namespaces() -> dict[str, bool]:
    """Return each conditional namespace mapped to whether its extension is installed."""
    from openbb_yfinance import (
        CRYPTO_INSTALLED,
        CURRENCY_INSTALLED,
        DERIVATIVES_INSTALLED,
        ECONOMY_INSTALLED,
        EQUITY_INSTALLED,
        ETF_INSTALLED,
        INDEX_INSTALLED,
        NEWS_INSTALLED,
    )

    return {
        "equity": EQUITY_INSTALLED,
        "etf": ETF_INSTALLED,
        "derivatives": DERIVATIVES_INSTALLED,
        "index": INDEX_INSTALLED,
        "crypto": CRYPTO_INSTALLED,
        "currency": CURRENCY_INSTALLED,
        "news": NEWS_INSTALLED,
        "economy": ECONOMY_INSTALLED,
    }


def _remap_widget_id(widget_id: str, installed: dict[str, bool]) -> str:
    """Prefix a standard-form widget id with ``yfinance_`` when its namespace's
    extension is absent, matching the route the hybrid router serves.

    Widget ids already in the ``yfinance_`` form (the explicit ``yfinance_*_obb``
    widgets, or an already-prefixed id) are left untouched.
    """
    if widget_id.startswith("yfinance_"):
        return widget_id
    namespace = widget_id.split("_", 1)[0]
    if namespace in installed and not installed[namespace]:
        return f"yfinance_{widget_id}"
    return widget_id


def build_yfinance_apps() -> list[dict]:
    """Return the curated Yahoo Finance Workspace app from ``assets/apps.json``.

    Widget ids are stored in their first-party (standard) form. Any widget whose
    namespace extension is not installed is rewritten to the ``yfinance_`` form
    the hybrid router serves, so the app resolves in both install states.
    """
    import json

    try:
        apps = json.loads(_APPS_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    installed = _installed_namespaces()
    for app in apps:
        for tab in (app.get("tabs") or {}).values():
            for widget in tab.get("layout") or []:
                widget_id = widget.get("i")
                if isinstance(widget_id, str):
                    widget["i"] = _remap_widget_id(widget_id, installed)
    return apps
