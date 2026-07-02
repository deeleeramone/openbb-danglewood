"""Bundled OpenBB Workspace app (apps.json) for the HKEX widgets."""

import json
from pathlib import Path

_APPS_JSON = Path(__file__).resolve().parent.parent / "assets" / "apps.json"

_GUARDED_WIDGETS = (
    ("quote", "equity_price_quote", "equity"),
    ("info", "equity_profile", "equity"),
    ("search", "equity_search", "equity"),
    ("historical", "equity_price_historical", "equity"),
    ("index_snapshots", "index_snapshots", "index"),
    ("index_constituents", "index_constituents", "index"),
    ("options_chains", "derivatives_options_chains", "derivatives"),
    ("futures_curve", "derivatives_futures_curve", "derivatives"),
)


def widget_id_remap(installed: dict[str, bool]) -> dict[str, str]:
    """Map each guarded HKEX widget id to its standard-namespace id, per install state."""
    return {
        f"hkex_{stem}_hkex_obb": f"{std}_hkex_obb"
        for stem, std, namespace in _GUARDED_WIDGETS
        if installed.get(namespace)
    }


def _installed() -> dict[str, bool]:
    from openbb_hkex import (
        DERIVATIVES_INSTALLED,
        EQUITY_INSTALLED,
        INDEX_INSTALLED,
    )

    return {
        "equity": EQUITY_INSTALLED,
        "index": INDEX_INSTALLED,
        "derivatives": DERIVATIVES_INSTALLED,
    }


def build_hkex_apps() -> list[dict]:
    """Load the bundled app and rewrite guarded widget ids to whichever namespace serves them."""
    apps = json.loads(_APPS_JSON.read_text(encoding="utf-8"))
    remap = widget_id_remap(_installed())
    if not remap:
        return apps
    for app in apps:
        for tab in (app.get("tabs") or {}).values():
            for widget in tab.get("layout") or []:
                wid = widget.get("i")
                if isinstance(wid, str) and wid in remap:
                    widget["i"] = remap[wid]
        for group in app.get("groups") or []:
            ids = group.get("widgetIds")
            if isinstance(ids, list):
                group["widgetIds"] = [remap.get(x, x) for x in ids]
    return apps
