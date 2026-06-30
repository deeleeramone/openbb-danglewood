"""Hatchling build hook: screener cache + a self-contained, pre-built wheel.

openbb-yfinance targets the unpublished v5 line of ``openbb-core`` /
``openbb-charting`` / ``openbb-platform-api`` (it lives on the OpenBB ``v5``
branch, not PyPI). To ship an installable wheel this hook:

  1. vendors those three pure-Python packages under their real import names,
  2. installs them + this extension into a throwaway venv and runs
     ``openbb-build`` there (openbb-core ships the static-build ``openbb``
     package, so no meta package is involved),
  3. bundles the generated static ``openbb`` package too,

so a plain ``pip install`` of the wheel yields a working ``import openbb`` with
the yfinance commands — no post-install step, no v5 packages on PyPI.

Editable/dev installs set ``OPENBB_VENDOR_SKIP=1`` (see scripts/bootstrap.sh) to
install the real v5 packages instead; this also breaks the install-itself
recursion in step 2.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import (  # ty: ignore[unresolved-import]
    BuildHookInterface,
)

_ROOT = Path(__file__).resolve().parent
_CACHE_PATH = _ROOT / "openbb_yfinance" / "assets" / "screener_cache.json.xz"
_FORCE_ENV = "OPENBB_YFINANCE_FORCE_CACHE_REBUILD"

# Unpublished v5 openbb-* packages, bundled under their real import names.
# import-name -> path within an OpenBB monorepo checkout.
_VENDOR = {
    "openbb_core": "openbb_platform/core/openbb_core",
    "openbb_charting": "openbb_platform/obbject_extensions/charting/openbb_charting",
    "openbb_platform_api": "openbb_platform/extensions/platform_api/openbb_platform_api",
}
_VENDOR_ENV = "OPENBB_VENDOR_SRC"
_SKIP_ENV = "OPENBB_VENDOR_SKIP"


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


def _skip() -> bool:
    return os.environ.get(_SKIP_ENV, "").lower() in {"1", "true", "yes"}


class YFinanceBuildHook(BuildHookInterface):
    """Materialize the screener cache, vendor v5 openbb-*, and prebuild ``openbb``."""

    PLUGIN_NAME = "openbb-yfinance"

    def initialize(self, version: str, build_data: dict) -> None:
        """Generate the cache, then build the self-contained wheel payload."""
        self._tmp: str | None = None
        self._build_screener_cache()
        if self.target_name == "wheel" and not _skip():
            self._vendor_packages(build_data)

    def finalize(self, version: str, build_data: dict, artifact: str) -> None:
        """Remove the throwaway build venv once the wheel is written."""
        if getattr(self, "_tmp", None):
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None

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
        # Install the extension and run openbb-build, then bundle the result.
        openbb_pkg = self._build_static_openbb(root)
        force_include[str(openbb_pkg)] = "openbb"
        sys.stderr.write(f"vendored openbb (static) <- {openbb_pkg}\n")

    def _build_static_openbb(self, root: Path) -> Path:
        """Build the static ``openbb`` package in a throwaway venv and return its dir."""
        self._tmp = tempfile.mkdtemp(prefix="obb-yf-vendor-")
        venv = Path(self._tmp) / "venv"
        bindir = venv / ("Scripts" if os.name == "nt" else "bin")
        vpy = str(bindir / ("python.exe" if os.name == "nt" else "python"))

        def run(*cmd: str, env: dict | None = None) -> None:
            sys.stderr.write("  $ " + " ".join(cmd) + "\n")
            subprocess.run(cmd, check=True, env=env)  # noqa: S603

        run("uv", "venv", "--python", "3.11", str(venv))
        # openbb-core ships both `openbb_core` and the static-build `openbb`
        # package, so no meta package is needed. `--no-sources` bypasses the
        # OpenBB uv workspace so these install as real copies into the throwaway
        # venv — otherwise openbb-build would mutate the checkout's `openbb`.
        run("uv", "pip", "install", "--no-sources", "--python", vpy,
            str(root / "openbb_platform/core"))
        run(
            "uv", "pip", "install", "--no-sources", "--python", vpy,
            "-e", str(root / "openbb_platform/obbject_extensions/charting"),
            "-e", str(root / "openbb_platform/extensions/platform_api"),
        )
        # Install this extension (OPENBB_VENDOR_SKIP=1 → no nested vendoring).
        run("uv", "pip", "install", "--no-sources", "--python", vpy, str(_ROOT),
            env={**os.environ, _SKIP_ENV: "1"})
        # Generate the static `openbb` package from the installed extensions.
        run(vpy, "-m", "openbb_core.build")
        return Path(
            subprocess.check_output(  # noqa: S603
                [vpy, "-c", "import openbb,os;print(os.path.dirname(openbb.__file__))"],
                text=True,
            ).strip()
        )
