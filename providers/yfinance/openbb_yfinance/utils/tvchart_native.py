"""TradingView charts via PyWry's tvchart."""

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
        theme_str = (data.get("theme") or "dark").lower()
        app.theme = ThemeMode.LIGHT if theme_str == "light" else ThemeMode.DARK

    callbacks["pywry:update-theme"] = _on_theme_change

    toolbars = build_tvchart_toolbars(
        intervals=SUPPORTED_RESOLUTIONS, selected_interval=resolution
    )
    marquee_toolbar, marquee_css = build_marquee(symbol)
    toolbars.insert(0, marquee_toolbar)

    widget = app.show_tvchart(
        use_datafeed=True,
        symbol=symbol,
        resolution=resolution,
        title=f"OpenBB - Yahoo Finance TradingView Chart ({symbol})",
        chart_options={"timeScale": {"secondsVisible": False}},
        toolbars=toolbars,
        callbacks=callbacks,
        inline_css=marquee_css,
        **show_kwargs,
    )
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
    html = await get_widget_html_async(widget.label)
    # generate_tvchart_html omits the toolbar handler script (marquee updates),
    # registers the datafeed dispatchers before window.pywry exists, and the WS
    # bridge's emit (unlike the native bridge) never fires local listeners.
    # Inject the toolbar script and a shim that re-registers the datafeed
    # dispatchers and makes emit dispatch locally so the chart toolbars work.
    extra = get_toolbar_script(with_script_tag=True) + (
        f"<script>{_BRIDGE_REGISTER_JS.read_text(encoding='utf-8')}</script>"
    )
    return (
        html.replace("</body>", f"{extra}</body>", 1)
        if "</body>" in html
        else html + extra
    )
