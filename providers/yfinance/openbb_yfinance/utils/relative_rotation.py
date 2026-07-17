"""Relative Rotation Graph widget: openbb_technical math, served via PyWry components."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)
_ERROR_MESSAGE = "Unable to compute the relative rotation graph."

_BRIDGE_JS = Path(__file__).resolve().parent.parent / "assets" / "rrg_bridge.js"
_SEARCH_JS = Path(__file__).resolve().parent.parent / "assets" / "rrg_search.js"
_UI_JS = Path(__file__).resolve().parent.parent / "assets" / "rrg_ui.js"
_SEARCH_CSS = Path(__file__).resolve().parent.parent / "assets" / "rrg_search.css"
_TOOLBAR_CSS = Path(__file__).resolve().parent.parent / "assets" / "rrg_toolbar.css"

GRAPH_WIDGET_ID = "yfinance_rrg_obb"
STUDY_WIDGET_ID = "yfinance_rrg_study_data_obb"
RATIOS_WIDGET_ID = "yfinance_rrg_ratios_obb"
MOMENTUM_WIDGET_ID = "yfinance_rrg_momentum_obb"

_LIVE_RRG: list = []
_STATE: dict[str, dict] = {}
_MAX_LIVE = 16

SPDRS = [
    "XLB",
    "XLC",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XHB",
    "XLU",
    "XLV",
    "XLY",
    "XLRE",
]

_FIGURE_CONFIG = {
    "scrollZoom": True,
    "displaylogo": False,
    "responsive": True,
    "displayModeBar": False,
}

_STUDIES = ("price", "volume", "volatility")
_DESCRIPTIONS = {
    "symbols": "Symbols to plot against the benchmark. Comma-separated; click the magnifier to search.",
    "benchmark": "The symbol every other symbol is measured against. Defaults to SPY.",
    "date": "Last date of the study. Leave empty for the most recent data.",
    "study": "Series the relative strength is computed on: closing price, volume, or realized volatility.",
    "window": "Rolling window, in bars of the selected interval, for realized volatility.",
    "trading_periods": "Periods per year to annualize volatility (252 day, 52 week, 12 month).",
    "long_period": "RS-Ratio lookback in bars of the selected interval (about one year).",
    "short_period": "RS-Momentum lookback in bars of the selected interval (about one month).",
    "rrg-submit": "Re-fetch prices for the symbols, benchmark and end date above.",
    "show_tails": "Trace each symbol's path over time and enable the animation.",
    "tail_periods": "Number of intervals in the tail. Also the number of animation frames.",
    "tail_interval": "Spacing of each step in the tail. Changing this resets Periods to that interval's default.",
}

_TAIL_INTERVALS = ("day", "week", "month")
_TAIL_PERIODS = {"day": 60, "week": 30, "month": 24}
_TRADING_DAYS_PER_WEEK = 5
_INTERVAL_FREQ = {"week": "W", "month": "ME"}
_INTERVAL_FACTOR = {"day": 1, "week": 5, "month": 21}
_PERIOD_DEFAULTS = {
    "day": {
        "long_period": 252,
        "short_period": 21,
        "window": 21,
        "trading_periods": 252,
    },
    "week": {"long_period": 52, "short_period": 4, "window": 4, "trading_periods": 52},
    "month": {"long_period": 12, "short_period": 1, "window": 3, "trading_periods": 12},
}
_PERIOD_KEYS = ("long_period", "short_period", "window", "trading_periods")

_QUADRANT_EDGE = 1e6
_DARK_PAPER = "rgba(0,0,0,0)"
_DARK_SURFACE = "rgba(15,17,23,1)"
_DARK_GRID = "rgba(255,255,255,0.08)"
_DARK_ZEROLINE = "rgba(255,255,255,0.35)"
_DARK_AXIS = "rgba(255,255,255,0.25)"
_DARK_TICK = "#aaa"
_DARK_AXIS_TITLE = "#ccc"
_DARK_INK = "#e0e0e0"

_DARK_QUADRANT = {
    "lightgreen": "rgba(34,197,94,0.26)",
    "lightblue": "rgba(56,139,253,0.26)",
    "lightpink": "rgba(244,63,94,0.28)",
    "lightyellow": "rgba(250,204,21,0.22)",
}
_DARK_LABELS = {
    "Leading": "#4ade80",
    "Weakening": "#facc15",
    "Lagging": "#fb7185",
    "Improving": "#60a5fa",
}
_LIGHT_LABELS = {
    "Leading": "darkgreen",
    "Weakening": "goldenrod",
    "Lagging": "red",
    "Improving": "blue",
}
_MARGIN = {"l": 60, "r": 60, "b": 50, "t": 60, "pad": 0}


def parse_symbols(symbols: Any) -> list[str]:
    """Normalize a delimited string or a sequence into an upper-cased list."""
    if isinstance(symbols, str):
        items = [s.upper() for s in re.split(r"[,;\s]+", symbols.strip())]
    else:
        items = [str(s).strip().upper() for s in (symbols or [])]
    seen: dict[str, None] = {}
    for s in items:
        if s:
            seen.setdefault(s, None)
    return list(seen)


def default_inputs() -> dict[str, Any]:
    """Return the default sidebar inputs."""
    return {
        "symbols": list(SPDRS),
        "benchmark": "SPY",
        "study": "price",
        "date": None,
        **_PERIOD_DEFAULTS["week"],
        "show_tails": True,
        "tail_periods": _TAIL_PERIODS["week"],
        "tail_interval": "week",
    }


def coerce_inputs(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce loosely-typed component/query params into a clean inputs dict. The
    calculation periods default to the interval's own defaults, so an interval carries
    its own momentum/volatility windows unless the user overrides them.
    """
    base = default_inputs()
    tail_interval = str(raw.get("tail_interval") or base["tail_interval"]).lower()
    if tail_interval not in _TAIL_INTERVALS:
        tail_interval = "week"
    periods = _PERIOD_DEFAULTS[tail_interval]

    def _int(key: str, fallback: dict) -> int:
        try:
            return int(float(raw[key]))
        except (KeyError, TypeError, ValueError):
            return fallback[key]

    def _bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    symbols = (
        parse_symbols(raw.get("symbols")) if raw.get("symbols") else base["symbols"]
    )
    study = str(raw.get("study") or base["study"]).lower()
    date = str(raw.get("date") or "").strip() or None
    return {
        "symbols": symbols or base["symbols"],
        "benchmark": str(raw.get("benchmark") or base["benchmark"]).strip().upper(),
        "study": study if study in _STUDIES else "price",
        "date": date,
        "long_period": _int("long_period", periods),
        "short_period": _int("short_period", periods),
        "window": _int("window", periods),
        "trading_periods": _int("trading_periods", periods),
        "show_tails": _bool(raw.get("show_tails", base["show_tails"])),
        "tail_periods": _int("tail_periods", base),
        "tail_interval": tail_interval,
    }


def _backfill_weeks(tail_periods: int, tail_interval: str) -> int:
    backfill = 156
    if tail_interval == "day":
        needed = -(-tail_periods // _TRADING_DAYS_PER_WEEK)
    elif tail_interval == "month":
        needed = tail_periods * 4
    else:
        needed = tail_periods
    return max(backfill, needed)


def _rows(frame: Any) -> list[dict]:
    out = frame.reset_index()
    if "date" in out.columns:
        out["date"] = out["date"].astype(str)
    records = out.to_dict("records")
    for row in records:
        for key, value in row.items():
            if isinstance(value, float) and math.isnan(value):
                row[key] = None
    return records


def _style_controls(fig: Any, dark: bool) -> None:
    for menu in fig.layout.updatemenus or ():
        menu.bgcolor = "#333" if dark else "#eee"
        menu.bordercolor = "#666" if dark else "#ccc"
        menu.borderwidth = 1
        menu.font = {"color": "#fff" if dark else "#333", "size": 13}
    for slider in fig.layout.sliders or ():
        if slider.currentvalue:
            slider.currentvalue.font = {"size": 14, "color": "#ccc" if dark else "#333"}
        slider.font = {"color": "#aaa" if dark else "#555", "size": 11}
        slider.activebgcolor = "#666" if dark else "#aaa"
        slider.bgcolor = "#333" if dark else "#ddd"
        slider.bordercolor = "#555" if dark else "#bbb"
        slider.tickcolor = "#666" if dark else "#ccc"


def _template_layout(dark: bool) -> dict:
    axis = (
        {
            "gridcolor": _DARK_GRID,
            "zerolinecolor": _DARK_ZEROLINE,
            "linecolor": _DARK_AXIS,
            "tickfont": {"color": _DARK_TICK},
            "title": {"font": {"color": _DARK_AXIS_TITLE}},
        }
        if dark
        else {
            "gridcolor": "rgba(0,0,0,0.1)",
            "zerolinecolor": "rgba(0,0,0,0.4)",
            "linecolor": "rgba(0,0,0,0.3)",
            "tickfont": {"color": "#555"},
            "title": {"font": {"color": "#444"}},
        }
    )
    return {
        "paper_bgcolor": _DARK_PAPER if dark else "rgba(255,255,255,1)",
        "plot_bgcolor": _DARK_SURFACE if dark else "rgba(255,255,255,1)",
        "font": {"color": _DARK_INK if dark else "#333"},
        "xaxis": dict(axis),
        "yaxis": dict(axis),
    }


def _figure_config() -> dict:
    """PyWry strips ``plot_bgcolor``/``paper_bgcolor``/``colorway``/font+axis colors off the
    layout and applies its own theme template, so the colors have to ride in the per-theme
    templates it deep-merges on top.
    """
    from pywry import PlotlyConfig

    return PlotlyConfig(
        scroll_zoom=True,
        responsive=True,
        display_logo=False,
        display_mode_bar=False,
        template_dark={"layout": _template_layout(True)},
        template_light={"layout": _template_layout(False)},
    ).model_dump(by_alias=True, exclude_none=True, exclude_defaults=True)


def _apply_theme(fig: Any, theme: str) -> None:
    dark = str(theme).lower() != "light"
    axis = (
        {
            "gridcolor": _DARK_GRID,
            "zerolinecolor": _DARK_ZEROLINE,
            "linecolor": _DARK_AXIS,
            "title_font": {"color": _DARK_AXIS_TITLE},
            "tickfont": {"color": _DARK_TICK},
        }
        if dark
        else {
            "gridcolor": "rgba(0,0,0,0.1)",
            "zerolinecolor": "rgba(0,0,0,0.4)",
            "linecolor": "rgba(0,0,0,0.3)",
            "title_font": {"color": "#444"},
            "tickfont": {"color": "#555"},
        }
    )
    fig.update_layout(
        autosize=True,
        height=None,
        margin=dict(**_MARGIN),
        paper_bgcolor="rgba(0,0,0,0)" if dark else "rgba(255,255,255,1)",
        plot_bgcolor=_DARK_SURFACE if dark else "rgba(255,255,255,1)",
        font={"color": _DARK_INK if dark else "#333"},
        title_font={"color": _DARK_INK if dark else "#222"},
        xaxis=dict(axis),
        yaxis=dict(axis),
    )
    labels = _DARK_LABELS if dark else _LIGHT_LABELS
    for note in fig.layout.annotations or ():
        if note.text in labels:
            note.font.color = labels[note.text]
    for shape in fig.layout.shapes or ():
        quadrant = shape.fillcolor in _DARK_QUADRANT
        if quadrant:
            # the axes are aspect-locked, so a resize widens the range past a
            # data-sized rect and bares the background behind the quadrant.
            if shape.x0 == 0:
                shape.x1 = _QUADRANT_EDGE
            elif shape.x1 == 0:
                shape.x0 = -_QUADRANT_EDGE
            if shape.y0 == 0:
                shape.y1 = _QUADRANT_EDGE
            elif shape.y1 == 0:
                shape.y0 = -_QUADRANT_EDGE
        if dark:
            if shape.line and shape.line.color == "Black":
                shape.line.color = _DARK_ZEROLINE
            if quadrant:
                shape.fillcolor = _DARK_QUADRANT[shape.fillcolor]
                shape.opacity = 1.0
    _style_controls(fig, dark)


def _fetch_key(inputs: dict) -> tuple:
    return (
        tuple(inputs["symbols"]),
        inputs["benchmark"],
        inputs["date"],
    )


async def _fetch_prices(inputs: dict, backfill: int | None = None) -> list:
    from openbb_core.provider.abstract.annotated_result import AnnotatedResult
    from pandas import to_datetime

    from openbb_yfinance.models.equity_historical import (
        YFinanceEquityHistoricalFetcher,
    )

    if backfill is None:
        backfill = _backfill_weeks(inputs["tail_periods"], inputs["tail_interval"])
    end = to_datetime(inputs["date"]) if inputs["date"] else datetime.now()
    start_date = (end - timedelta(weeks=backfill)).date()
    end_date = end.date()
    symbols, benchmark = inputs["symbols"], inputs["benchmark"]
    tickers = symbols + ([benchmark] if benchmark not in symbols else [])
    fetched = await YFinanceEquityHistoricalFetcher.fetch_data(
        {
            "symbol": ",".join(tickers),
            "start_date": start_date,
            "end_date": end_date,
            "interval": "1d",
        },
        {},
    )
    return (fetched.result or []) if isinstance(fetched, AnnotatedResult) else fetched


def _relative_rotation(prices: list, inputs: dict) -> Any:
    from openbb_technical.relative_rotation import (
        RelativeRotation,
        RelativeRotationData,
    )

    data: list = prices
    if inputs["study"] == "volume":
        # yfinance volume is int64; the RS math writes floats back into the pivoted
        # column, which pandas rejects. Feed float volume instead.
        data = []
        for row in prices:
            item = row.model_dump() if hasattr(row, "model_dump") else dict(row)
            if item.get("volume") is not None:
                item["volume"] = float(item["volume"])
            data.append(item)

    factor = _INTERVAL_FACTOR[inputs["tail_interval"]]
    rr = RelativeRotation(
        data=data,
        benchmark=inputs["benchmark"],
        study=inputs["study"],
        long_period=inputs["long_period"] * factor,
        short_period=max(1, inputs["short_period"] * factor),
        window=max(2, inputs["window"] * factor),
        trading_periods=inputs["trading_periods"] if factor == 1 else 252,
    )
    return RelativeRotationData.model_validate(rr.__dict__)


def _rs_frames(res: Any, inputs: dict) -> tuple:
    """Return the (RS-Ratio, RS-Momentum) frames for the interval. Daily uses the
    RelativeRotation output directly; week/month resample its price series and re-run the
    extension's ``process_data`` with the interval's own periods (a month's short period is
    1), so the momentum is a genuine interval momentum, not daily values sampled off.
    """
    from openbb_core.app.utils import basemodel_to_df

    interval = inputs["tail_interval"]
    if interval == "day":
        return (
            basemodel_to_df(res.rs_ratios, index="date"),
            basemodel_to_df(res.rs_momentum, index="date"),
        )

    from openbb_technical.relative_rotation import process_data
    from pandas import to_datetime

    freq = _INTERVAL_FREQ[interval]
    symbols_data = basemodel_to_df(res.symbols_data, index="date")
    benchmark_data = basemodel_to_df(res.benchmark_data, index="date")
    symbols_data.index = to_datetime(symbols_data.index)
    benchmark_data.index = to_datetime(benchmark_data.index)
    symbols_data = symbols_data.resample(freq).last().dropna(how="all")
    benchmark_data = benchmark_data.resample(freq).last().dropna(how="all")
    ratios, momentum = process_data(
        symbols_data,
        benchmark_data,
        long_period=inputs["long_period"],
        short_period=inputs["short_period"],
    )
    momentum = momentum.dropna()
    ratios = ratios.reindex(momentum.index)
    return ratios, momentum


def _tables(res: Any, ratios_df: Any, momentum_df: Any) -> dict:
    from openbb_core.app.utils import basemodel_to_df

    study_df = basemodel_to_df(res.symbols_data, index="date").join(
        basemodel_to_df(res.benchmark_data, index="date")
    )
    return {
        "study_data": _rows(study_df),
        "rs_ratios": _rows(ratios_df),
        "rs_momentum": _rows(momentum_df),
    }


def _figure(ratios_df: Any, momentum_df: Any, inputs: dict, theme: str) -> dict:
    from openbb_charting.charts.relative_rotation import (
        create_rrg_with_tails,
        create_rrg_without_tails,
    )
    from pandas import to_datetime

    if inputs["show_tails"]:
        fig = create_rrg_with_tails(
            ratios_df,
            momentum_df,
            inputs["study"],
            inputs["benchmark"],
            inputs["tail_periods"],
            inputs["tail_interval"],
        )
    else:
        chart_date = to_datetime(inputs["date"]).date() if inputs["date"] else None
        fig = create_rrg_without_tails(
            ratios_df, momentum_df, inputs["benchmark"], inputs["study"], chart_date
        )
    _apply_theme(fig, theme)
    figure = fig.to_plotly_json()
    figure["config"] = _figure_config()
    return figure


async def _compute(inputs: dict, theme: str, cached: dict | None = None) -> dict:
    if not inputs["symbols"]:
        raise ValueError("At least one symbol is required.")
    key = _fetch_key(inputs)
    needed = _backfill_weeks(inputs["tail_periods"], inputs["tail_interval"])
    reusable = (
        cached
        and cached.get("fetch_key") == key
        and cached.get("prices")
        and cached.get("backfill", 0) >= needed
    )
    if reusable:
        prices = cached["prices"]
        needed = cached["backfill"]
    else:
        prices = await _fetch_prices(inputs, needed)

    def _build() -> tuple:
        res = _relative_rotation(prices, inputs)
        ratios_df, momentum_df = _rs_frames(res, inputs)
        return (
            res,
            _figure(ratios_df, momentum_df, inputs, theme),
            _tables(res, ratios_df, momentum_df),
        )

    res, figure, tables = await asyncio.to_thread(_build)
    return {
        "prices": prices,
        "fetch_key": key,
        "backfill": needed,
        "figure": figure,
        "tables": tables,
        "symbols": list(res.symbols),
        "benchmark": inputs["benchmark"],
        "study": inputs["study"],
    }


async def compute_rrg(theme: str = "dark", **raw: Any) -> dict[str, Any]:
    """Compute the RRG figure and the Study Data, RS-Ratio and RS-Momentum tables."""
    result = await _compute(coerce_inputs(raw), theme)
    tables = result["tables"]
    return {
        "figure": result["figure"],
        "study_data": tables["study_data"],
        "rs_ratios": tables["rs_ratios"],
        "rs_momentum": tables["rs_momentum"],
        "symbols": result["symbols"],
        "benchmark": result["benchmark"],
        "study": result["study"],
    }


def _vis(show: bool) -> str:
    return "" if show else "display:none;"


def _build_toolbar(inputs: dict) -> Any:
    from pywry import (
        Button,
        Checkbox,
        DateInput,
        Div,
        NumberInput,
        Option,
        Select,
        TextInput,
        Toolbar,
    )

    def rule() -> Any:
        return Div(content="<hr class='sidebar-rule'>")

    def heading(text: str) -> Any:
        return Div(content=text, class_name="sidebar-heading")

    return Toolbar(
        position="left",
        collapsible=True,
        items=[
            TextInput(
                component_id="symbols",
                label="Symbols",
                event="rrg:input",
                value=",".join(inputs["symbols"]),
                description=_DESCRIPTIONS["symbols"],
            ),
            TextInput(
                component_id="benchmark",
                label="Benchmark",
                event="rrg:input",
                value=inputs["benchmark"],
                description=_DESCRIPTIONS["benchmark"],
            ),
            DateInput(
                component_id="date",
                label="Target End Date",
                event="rrg:input",
                value=inputs["date"] or "",
                description=_DESCRIPTIONS["date"],
            ),
            rule(),
            Select(
                component_id="study",
                label="Study",
                event="rrg:input",
                options=[Option(label=s.capitalize(), value=s) for s in _STUDIES],
                selected=inputs["study"],
                description=_DESCRIPTIONS["study"],
            ),
            Div(
                component_id="rrg-vol-group",
                style=_vis(inputs["study"] == "volatility"),
                children=[
                    heading("Volatility Annualization"),
                    Div(
                        style="display:flex;flex-direction:row;gap:8px;width:100%;",
                        children=[
                            NumberInput(
                                component_id="window",
                                label="Window",
                                event="rrg:input",
                                value=inputs["window"],
                                min=1,
                                max=500,
                                description=_DESCRIPTIONS["window"],
                            ),
                            NumberInput(
                                component_id="trading_periods",
                                label="Periods / Year",
                                event="rrg:input",
                                value=inputs["trading_periods"],
                                min=1,
                                max=1000,
                                description=_DESCRIPTIONS["trading_periods"],
                            ),
                        ],
                    ),
                ],
            ),
            rule(),
            heading("Momentum Periods"),
            Div(
                style="display:flex;flex-direction:row;gap:8px;width:100%;",
                children=[
                    NumberInput(
                        component_id="long_period",
                        label="Long",
                        event="rrg:input",
                        value=inputs["long_period"],
                        min=1,
                        max=1000,
                        description=_DESCRIPTIONS["long_period"],
                    ),
                    NumberInput(
                        component_id="short_period",
                        label="Short",
                        event="rrg:input",
                        value=inputs["short_period"],
                        min=1,
                        max=500,
                        description=_DESCRIPTIONS["short_period"],
                    ),
                ],
            ),
            rule(),
            Button(
                component_id="rrg-submit",
                label="Fetch Data",
                event="rrg:submit",
                variant="primary",
                style="width:100%;",
                description=_DESCRIPTIONS["rrg-submit"],
            ),
            rule(),
            Checkbox(
                component_id="show_tails",
                label="Show Tails",
                event="rrg:input",
                value=inputs["show_tails"],
                description=_DESCRIPTIONS["show_tails"],
            ),
            Div(
                component_id="rrg-tail-group",
                style=_vis(inputs["show_tails"]),
                children=[
                    Div(
                        style="display:flex;flex-direction:row;gap:8px;width:100%;",
                        children=[
                            NumberInput(
                                component_id="tail_periods",
                                label="Periods",
                                event="rrg:input",
                                value=inputs["tail_periods"],
                                min=1,
                                max=200,
                                description=_DESCRIPTIONS["tail_periods"],
                            ),
                            Select(
                                component_id="tail_interval",
                                label="Interval",
                                event="rrg:input",
                                options=[
                                    Option(label=t.capitalize(), value=t)
                                    for t in _TAIL_INTERVALS
                                ],
                                selected=inputs["tail_interval"],
                                description=_DESCRIPTIONS["tail_interval"],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _island(
    tables: dict | None,
    error: str | None,
    theme: str,
    frames: list | None = None,
) -> str:
    payload = {
        "tableWidgetIds": {
            "study_data": STUDY_WIDGET_ID,
            "rs_ratios": RATIOS_WIDGET_ID,
            "rs_momentum": MOMENTUM_WIDGET_ID,
        },
        "data": tables,
        "error": error,
        "theme": theme,
        # PyWry's plotly init calls newPlot(data, layout, config) with no frames,
        # so the animation is added client-side from here.
        "frames": frames or [],
        # PyWry applies the per-theme template at init, then its theme pass re-merges
        # without it and the base template wins back; re-seeded client-side.
        "templates": {
            "dark": {"layout": _template_layout(True)},
            "light": {"layout": _template_layout(False)},
        },
        # pywry 2.0.5 DateInput/Div drop `description` instead of emitting data-tooltip.
        "tooltips": _DESCRIPTIONS,
    }
    return json.dumps(payload, default=str)


def _recompute(widget_id: str) -> None:
    state = _STATE.get(widget_id)
    if not state:
        return
    widget = state["widget"]
    inputs = coerce_inputs(state["inputs"])
    from pywry import inline as _inline

    loop = getattr(_inline._state, "server_loop", None)
    if loop is None or loop.is_closed():
        return

    needed = _backfill_weeks(inputs["tail_periods"], inputs["tail_interval"])
    refetching = _fetch_key(inputs) != state.get("fetch_key") or needed > state.get(
        "backfill", 0
    )
    widget.emit("rrg:status", {"loading": True, "fetching": refetching})

    async def _work() -> None:
        try:
            result = await _compute(inputs, state["theme"], cached=state)
        except Exception:
            _logger.exception("RRG recompute failed")
            widget.emit("rrg:status", {"error": _ERROR_MESSAGE})
            return
        state["prices"] = result["prices"]
        state["fetch_key"] = result["fetch_key"]
        state["backfill"] = result["backfill"]
        state["inputs"] = inputs
        figure = result["figure"]
        widget.emit(
            "plotly:update-figure",
            {"figure": figure, "config": figure.get("config") or {}},
        )
        widget.emit("rrg:data", {"data": result["tables"]})
        widget.emit("rrg:status", {"loading": False})

    future = asyncio.run_coroutine_threadsafe(_work(), loop)
    with contextlib.suppress(Exception):
        future.result(timeout=45)


def _callbacks(widget_id: str) -> dict:
    def on_input(data: dict, _event: str, _label: str) -> None:
        state = _STATE.get(widget_id)
        if not state or not isinstance(data, dict):
            return
        component_id = data.get("componentId")
        if not component_id:
            return
        raw = dict(state["inputs"])
        raw["symbols"] = ",".join(raw["symbols"])
        raw[component_id] = data.get("value")
        if component_id == "tail_interval":
            interval = str(data.get("value")).lower()
            raw["tail_periods"] = _TAIL_PERIODS.get(interval, raw["tail_periods"])
            raw.update(_PERIOD_DEFAULTS.get(interval, {}))
        merged = coerce_inputs(raw)
        state["inputs"] = merged

        widget = state["widget"]
        if component_id == "tail_interval":
            widget.emit(
                "toolbar:set-values",
                {"values": {k: merged[k] for k in ("tail_periods", *_PERIOD_KEYS)}},
            )
        if component_id == "study":
            widget.emit(
                "toolbar:set-value",
                {
                    "componentId": "rrg-vol-group",
                    "style": _vis(merged["study"] == "volatility"),
                },
            )
        elif component_id == "show_tails":
            widget.emit(
                "toolbar:set-value",
                {
                    "componentId": "rrg-tail-group",
                    "style": _vis(merged["show_tails"]),
                },
            )

        if _fetch_key(merged) == state.get("fetch_key"):
            _recompute(widget_id)

    def on_submit(_data: dict, _event: str, _label: str) -> None:
        _recompute(widget_id)

    def on_set_inputs(data: dict, _event: str, _label: str) -> None:
        state = _STATE.get(widget_id)
        if not state or not isinstance(data, dict):
            return
        raw = dict(state["inputs"])
        raw["symbols"] = ",".join(raw["symbols"])
        merged = coerce_inputs({**raw, **data})
        state["inputs"] = merged
        state["widget"].emit(
            "toolbar:set-values",
            {
                "values": {
                    "symbols": ",".join(merged["symbols"]),
                    "benchmark": merged["benchmark"],
                    "study": merged["study"],
                    "date": merged["date"] or "",
                    "long_period": merged["long_period"],
                    "short_period": merged["short_period"],
                    "window": merged["window"],
                    "trading_periods": merged["trading_periods"],
                    "show_tails": merged["show_tails"],
                    "tail_periods": merged["tail_periods"],
                    "tail_interval": merged["tail_interval"],
                }
            },
        )
        state["widget"].emit(
            "rrg:inputs", {"study": merged["study"], "show_tails": merged["show_tails"]}
        )
        if data.get("recompute", True):
            _recompute(widget_id)

    return {
        "rrg:input": on_input,
        "rrg:submit": on_submit,
        "rrg:set-inputs": on_set_inputs,
        "rrg:recompute": lambda *_a: _recompute(widget_id),
    }


def _register_live(widget: Any, widget_id: str) -> None:
    _LIVE_RRG.append((widget, {"widget_id": widget_id}))
    while len(_LIVE_RRG) > _MAX_LIVE:
        old_id = _LIVE_RRG.pop(0)[1].get("widget_id")
        _STATE.pop(old_id, None)


async def rrg_widget_html(theme: str = "dark", **raw: Any) -> str:
    """Return the live RRG widget HTML: a PyWry Toolbar sidebar + Plotly figure."""
    from pywry import inline as _inline
    from pywry.inline import (
        InlineWidget,
        _generate_widget_token,
        generate_plotly_html,
    )

    from openbb_yfinance.utils.pywry_server import bind_loop, ensure_pywry_mounted

    ensure_pywry_mounted()
    bind_loop()

    inputs = coerce_inputs(raw)
    widget_id = f"rrg_{uuid.uuid4().hex[:12]}"
    token = _generate_widget_token(widget_id)

    tables: dict | None = None
    error: str | None = None
    prices: list = []
    fetch_key: tuple = ()
    backfill: int = 0
    figure: dict = {"data": [], "layout": {}, "config": _figure_config()}
    try:
        result = await _compute(inputs, theme)
        figure, tables = result["figure"], result["tables"]
        prices, fetch_key = result["prices"], result["fetch_key"]
        backfill = result["backfill"]
    except Exception:
        _logger.exception("RRG initial render failed")
        error = _ERROR_MESSAGE

    frames = figure.get("frames") or []
    html = generate_plotly_html(
        json.dumps({k: v for k, v in figure.items() if k != "frames"}),
        widget_id,
        "OpenBB - Relative Rotation",
        "light" if str(theme).lower() == "light" else "dark",
        toolbars=[_build_toolbar(inputs)],
        token=token,
    )
    extra = (
        f"<style>{_TOOLBAR_CSS.read_text(encoding='utf-8')}</style>"
        f"<style>{_SEARCH_CSS.read_text(encoding='utf-8')}</style>"
        + f"<script>window.__obbRrg = {_island(tables, error, theme, frames)};</script>"
        + f"<script>{_BRIDGE_JS.read_text(encoding='utf-8')}</script>"
        + f"<script>{_SEARCH_JS.read_text(encoding='utf-8')}</script>"
        + f"<script>{_UI_JS.read_text(encoding='utf-8')}</script>"
    )
    html = (
        html.replace("</body>", f"{extra}</body>", 1)
        if "</body>" in html
        else html + extra
    )

    widget = InlineWidget(
        html=html, widget_id=widget_id, browser_only=True, token=token
    )
    _STATE[widget_id] = {
        "widget": widget,
        "inputs": inputs,
        "theme": theme,
        "prices": prices,
        "fetch_key": fetch_key,
        "backfill": backfill,
    }
    for event, callback in _callbacks(widget_id).items():
        with contextlib.suppress(Exception):
            widget.on(event, callback)
    with contextlib.suppress(Exception):
        _register_live(widget, widget_id)
    _inline  # noqa: B018 - imported for its side-effect of registering the widget loop

    return html
