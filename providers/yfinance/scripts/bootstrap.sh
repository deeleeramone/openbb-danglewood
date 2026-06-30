#!/usr/bin/env bash
#
# bootstrap.sh — provision openbb-yfinance in a clean environment and run the
# Workspace API server or a native PyWry app.
#
# openbb-yfinance targets the unpublished v5 line of openbb-core/-charting/
# -platform-api. Two install modes:
#
#   --editable (default)  install the v5 packages from a local OpenBB checkout
#                         (source-live dev), plus openbb-yfinance editable.
#   --wheel               build the self-contained wheel (v5 sources vendored
#                         in) and install that — what gets published.
#
# After install the static `openbb` package is (re)built with `openbb-build`,
# using the SAME interpreter the package was installed into. Wheels have no
# post-install hook, so this script owns that step.
#
# Usage:
#   scripts/bootstrap.sh [options] [command]
#
# Commands:
#   server      (default)  serve the Platform API  (openbb-api)
#   screener               open the native Screener Builder window
#   tvchart [SYMBOL]       open the native TradingView chart window
#   bootstrap              install + openbb-build only, don't start anything
#
# Options:
#   --python <ver>      Python for the venv            (default: 3.11)
#   --venv <path>       venv location                  (default: <provider>/.venv)
#   --vendor-src <path> OpenBB v5 checkout             (default: auto-detect)
#   --editable          dev install (default)
#   --wheel             build + install the vendored wheel
#   --port <n>          server port                    (default: 6900)
#   --theme <dark|light> native-window theme           (default: dark)
#   --no-build          skip openbb-build
#   -h, --help          this help
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROVIDER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PYVER="3.11"
VENV="$PROVIDER_DIR/.venv"
VENDOR_SRC="${OPENBB_VENDOR_SRC:-}"
MODE="editable"
PORT="6900"
THEME="dark"
DO_BUILD=1
CMD="server"
SYMBOL="AAPL"

usage() { sed -n '2,46p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
    case "$1" in
        --python)     PYVER="$2"; shift 2 ;;
        --venv)       VENV="$2"; shift 2 ;;
        --vendor-src) VENDOR_SRC="$2"; shift 2 ;;
        --editable)   MODE="editable"; shift ;;
        --wheel)      MODE="wheel"; shift ;;
        --port)       PORT="$2"; shift 2 ;;
        --theme)      THEME="$2"; shift 2 ;;
        --no-build)   DO_BUILD=0; shift ;;
        -h|--help)    usage; exit 0 ;;
        server|screener|tvchart|bootstrap) CMD="$1"; shift ;;
        *)
            if [ "$CMD" = "tvchart" ]; then SYMBOL="$1"; shift
            else echo "unknown argument: $1" >&2; usage; exit 1; fi ;;
    esac
done

command -v uv >/dev/null 2>&1 || {
    echo "error: 'uv' is required — https://docs.astral.sh/uv/" >&2; exit 1; }

# Locate an OpenBB v5 checkout (needed to vendor the wheel or install editable).
if [ -z "$VENDOR_SRC" ]; then
    for c in "$PROVIDER_DIR/../../../OpenBB" "$HOME/github/OpenBB"; do
        if [ -d "$c/openbb_platform" ]; then VENDOR_SRC="$(cd "$c" && pwd)"; break; fi
    done
fi
if [ -z "$VENDOR_SRC" ] || [ ! -d "$VENDOR_SRC/openbb_platform" ]; then
    echo "error: OpenBB v5 checkout not found — pass --vendor-src <path>" >&2; exit 1
fi

echo "==> venv (python $PYVER) at $VENV"
uv venv --python "$PYVER" "$VENV"
PY="$VENV/bin/python"
[ -f "$PY" ] || PY="$VENV/Scripts/python.exe"  # Windows layout

if [ "$MODE" = "wheel" ]; then
    echo "==> building the self-contained wheel (vendoring v5 from $VENDOR_SRC)"
    rm -rf "$PROVIDER_DIR/dist"
    OPENBB_VENDOR_SRC="$VENDOR_SRC" uv build --wheel --no-sources "$PROVIDER_DIR"
    echo "==> installing the wheel"
    uv pip install --python "$PY" "$PROVIDER_DIR"/dist/openbb_yfinance-*.whl
else
    echo "==> installing v5 openbb-* (editable) from $VENDOR_SRC"
    uv pip install --python "$PY" \
        -e "$VENDOR_SRC/openbb_platform/core" \
        -e "$VENDOR_SRC/openbb_platform/obbject_extensions/charting" \
        -e "$VENDOR_SRC/openbb_platform/extensions/platform_api"
    echo "==> installing openbb-yfinance (editable, no vendoring)"
    OPENBB_VENDOR_SKIP=1 uv pip install --python "$PY" -e "$PROVIDER_DIR"
fi

if [ "$DO_BUILD" -eq 1 ]; then
    OBB_BUILD="$VENV/bin/openbb-build"
    [ -x "$OBB_BUILD" ] || OBB_BUILD="$VENV/Scripts/openbb-build.exe"
    if [ -x "$OBB_BUILD" ]; then
        echo "==> openbb-build"
        "$OBB_BUILD"
    else
        echo "==> openbb-build skipped (wheel ships the prebuilt static package)"
    fi
fi

case "$CMD" in
    bootstrap)
        echo "==> done. environment ready at $VENV"
        ;;
    server)
        APPS="$("$PY" -c "import openbb_yfinance,os;print(os.path.join(os.path.dirname(openbb_yfinance.__file__),'assets','apps.json'))")"
        echo "==> openbb-api on http://127.0.0.1:$PORT  (apps.json: $APPS)"
        exec "$PY" -m openbb_platform_api.main --port "$PORT" --apps-json "$APPS"
        ;;
    screener)
        echo "==> launching native Screener Builder ($THEME)"
        exec "$PY" -c "
from openbb_yfinance.utils import screener_native as s
s.launch_screener_builder(theme='$THEME')
s._APP.block()
"
        ;;
    tvchart)
        echo "==> launching native TradingView chart for $SYMBOL ($THEME)"
        exec "$PY" -c "
from pywry import PyWry, ThemeMode
from openbb_yfinance.utils.tvchart_native import _show
app = PyWry(theme=ThemeMode.LIGHT if '$THEME' == 'light' else ThemeMode.DARK)
_show(app, '$SYMBOL', '1d')
app.block()
"
        ;;
esac
