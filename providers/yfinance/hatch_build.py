"""Hatchling build hook: screener cache + vendoring the unpublished v5 openbb-* deps.

The yfinance extension targets the v5 line of ``openbb-core``/``openbb-charting``/
``openbb-platform-api``, which is not on PyPI yet (it lives on the OpenBB ``v5``
branch). To ship an installable release candidate, those three pure-Python
packages are bundled into the wheel as top-level packages and dropped from
``[project.dependencies]`` (their third-party deps are folded in there instead).
"""

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

# Unpublished v5 openbb-* packages, bundled into the wheel under their real
# import names. import-name -> path within an OpenBB monorepo checkout.
_VENDOR = {
    "openbb_core": "openbb_platform/core/openbb_core",
    "openbb_charting": "openbb_platform/obbject_extensions/charting/openbb_charting",
    "openbb_platform_api": "openbb_platform/extensions/platform_api/openbb_platform_api",
}
_VENDOR_ENV = "OPENBB_VENDOR_SRC"


def _resolve_vendor_root() -> Path | None:
    """Locate an OpenBB checkout to vendor the v5 openbb-* packages from."""
    candidates: list[Path] = []
    env = os.environ.get(_VENDOR_ENV)
    if env:
        candidates.append(Path(env))
    candidates.append(_ROOT.parents[2] / "OpenBB")  # sibling checkout
    for cand in candidates:
        if cand and (cand / "openbb_platform").is_dir():
            return cand
    return None


class YFinanceBuildHook(BuildHookInterface):
    """Materialize the screener cache and vendor the v5 openbb-* packages."""

    PLUGIN_NAME = "openbb-yfinance"

    def initialize(self, version: str, build_data: dict) -> None:
        """Generate the cache, then bundle the v5 openbb-* sources into the wheel."""
        self._build_screener_cache()
        if self.target_name == "wheel":
            self._vendor_packages(build_data)

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

    def _vendor_packages(self, build_data: dict) -> None:
        root = _resolve_vendor_root()
        if root is None:
            raise RuntimeError(
                f"Cannot vendor the v5 openbb-* packages: set {_VENDOR_ENV} to an "
                "OpenBB checkout (the v5 branch), or place one beside this repo."
            )
        force_include = build_data.setdefault("force_include", {})
        for pkg, rel in _VENDOR.items():
            src = root / rel
            if not src.is_dir():
                raise RuntimeError(f"vendor source missing: {src}")
            force_include[str(src)] = pkg
            sys.stderr.write(f"vendored {pkg} <- {src}\n")
