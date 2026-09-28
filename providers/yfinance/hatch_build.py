"""Hatchling build hook: generate the screener cache asset."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import (  # ty: ignore[unresolved-import]
    BuildHookInterface,
)

_ROOT = Path(__file__).resolve().parent
_CACHE_PATH = _ROOT / "openbb_yfinance" / "assets" / "screener_cache.json.xz"
_FORCE_ENV = "OPENBB_YFINANCE_FORCE_CACHE_REBUILD"


class YFinanceBuildHook(BuildHookInterface):
    """Materialize the screener cache before the wheel/sdist is built."""

    PLUGIN_NAME = "openbb-yfinance"

    def initialize(self, version: str, build_data: dict) -> None:
        """Generate the screener cache if it doesn't already exist."""
        self._build_screener_cache()

    def _build_screener_cache(self) -> None:
        force = os.environ.get(_FORCE_ENV, "").lower() in {"1", "true", "yes"}
        if _CACHE_PATH.exists() and not force:
            return
        sys.path.insert(0, str(_ROOT))
        try:
            from openbb_yfinance.utils.screener_cache import build_screener_cache

            build_screener_cache()
            sys.stderr.write("yfinance screener cache: generated.\n")
        except Exception as exc:  # noqa: BLE001 - never fail the build on a network error
            sys.stderr.write(f"yfinance screener cache: skipped ({exc}).\n")
