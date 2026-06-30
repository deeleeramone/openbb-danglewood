"""TradingView charts via PyWry's tvchart."""

import json
import uuid
from pathlib import Path
from typing import Any

from openbb_yfinance.utils.tvchart_datafeed import (
    SUPPORTED_RESOLUTIONS,
    BarCache,
    RealtimeStreamer,
    build_marquee,
    make_callbacks,
)

_LIVE_CHARTS: list = []

_BRIDGE_REGISTER_JS = (
    Path(__file__).resolve().parent.parent / "assets" / "tvchart_bridge_register.js"
)


def _show(app: Any, symbol: str, resolution: str, **show_kwargs: Any) -> Any:
    """Render the Yahoo Finance datafeed, live streamer, and marquee via PyWry's tvchart."""
    from pywry import ThemeMode
    from pywry.tvchart import build_tvchart_toolbars

    symbol = symbol.upper()
    cache = BarCache()
    streamer = RealtimeStreamer(app, cache)
    callbacks = make_callbacks(app, streamer, cache)

    def _on_theme_change(
        data: dict[str, Any], _event_type: str = "", _label: str = ""
    ) -> None:
        is_dark = (data.get("theme") or "dark").lower() != "light"
        app.theme = ThemeMode.DARK if is_dark else ThemeMode.LIGHT
        # Sync the chart's own dark-mode toggle (the toolbar slider) to the
        # Workspace theme; updating app.theme alone leaves the slider behind.
        app.emit("tvchart:toggle-dark-mode", {"value": is_dark})

    callbacks["pywry:update-theme"] = _on_theme_change

    toolbars = build_tvchart_toolbars(
        intervals=SUPPORTED_RESOLUTIONS,
        selected_interval=resolution,
        theme="light" if app.theme == ThemeMode.LIGHT else "dark",
    )
    marquee_toolbar, marquee_css = build_marquee(symbol)
    toolbars.insert(0, marquee_toolbar)

    chart_id = f"tvc_{uuid.uuid4().hex[:12]}"
    widget_label = f"tvw_{uuid.uuid4().hex[:12]}"

    widget = app.show_tvchart(
        use_datafeed=True,
        symbol=symbol,
        resolution=resolution,
        chart_id=chart_id,
        label=widget_label,
        title=f"OpenBB - Yahoo Finance TradingView Chart ({symbol})",
        chart_options={"timeScale": {"secondsVisible": False}},
        toolbars=toolbars,
        callbacks=callbacks,
        inline_css=marquee_css,
        **show_kwargs,
    )
    chart_ids = getattr(app, "_obb_chart_ids_by_widget", None)
    if not isinstance(chart_ids, dict):
        chart_ids = {}
    chart_ids[str(getattr(widget, "label", "") or widget_label)] = chart_id
    app._obb_chart_ids_by_widget = chart_ids
    app._obb_chart_id = chart_id
    _LIVE_CHARTS.append((app, streamer))
    return widget


def launch_tvchart(
    symbol: str = "AAPL",
    resolution: str = "1d",
    theme: str = "dark",
    width: int = 1280,
    height: int = 800,
) -> Any:
    """Open a TradingView chart and return the PyWry window handle."""
    from pywry import PyWry, ThemeMode

    theme_mode = ThemeMode.LIGHT if str(theme).lower() == "light" else ThemeMode.DARK
    app = PyWry(theme=theme_mode)
    return _show(app, symbol, resolution, width=width, height=height)


async def tvchart_widget_html(
    symbol: str = "AAPL", interval: str = "1d", theme: str = "dark"
) -> str:
    """Return PyWry's TradingView widget HTML for the Workspace iframe.

    PyWry's inline server is mounted onto the OpenBB API app, so the chart's
    datafeed WebSocket is served same-origin (no second server / port).
    """
    from pywry import PyWry, ThemeMode, WindowMode
    from pywry.inline import get_widget_html_async
    from pywry.toolbar import get_toolbar_script

    from openbb_yfinance.utils.pywry_server import bind_loop, ensure_pywry_mounted

    ensure_pywry_mounted()
    bind_loop()
    theme_mode = ThemeMode.LIGHT if str(theme).lower() == "light" else ThemeMode.DARK
    app = PyWry(mode=WindowMode.BROWSER, theme=theme_mode)
    widget = _show(app, symbol, interval)
    html = await get_widget_html_async(widget.label) or ""
    widget_id = str(getattr(widget, "label", "") or getattr(app, "label", "") or "")
    chart_id = (getattr(app, "_obb_chart_ids_by_widget", {}) or {}).get(
        widget_id
    ) or str(getattr(app, "_obb_chart_id", "") or "")
    bridge_state = json.dumps(
        {
            "widgetId": widget_id,
            "chartId": chart_id,
            "symbol": symbol.upper(),
            "interval": interval,
            "theme": theme,
        }
    )
    # generate_tvchart_html omits the toolbar handler script (marquee updates),
    # registers the datafeed dispatchers before window.pywry exists, and the WS
    # bridge's emit (unlike the native bridge) never fires local listeners.
    # Inject the toolbar script and a shim that re-registers the datafeed
    # dispatchers and makes emit dispatch locally so the chart toolbars work.
    extra = (
        f"<script>window.__obbTvChart = {bridge_state};</script>"
        + get_toolbar_script(with_script_tag=True)
        + f"<script>{_BRIDGE_REGISTER_JS.read_text(encoding='utf-8')}</script>"
    )
    return (
        html.replace("</body>", f"{extra}</body>", 1)
        if "</body>" in html
        else html + extra
    )
