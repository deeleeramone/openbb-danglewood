import inspect

import pytest

from openbb_yfinance.utils import (
    mcp_app,
    relative_rotation as rr,
)


class _Widget:
    def __init__(self):
        self.events = []

    def emit(self, event, data):
        self.events.append((event, data))


def test_parse_symbols_dedup_upper():
    assert rr.parse_symbols("xlk, xlf; xlk aapl") == ["XLK", "XLF", "AAPL"]
    assert rr.parse_symbols(["spy", "SPY", "qqq"]) == ["SPY", "QQQ"]


def test_coerce_inputs_defaults():
    ci = rr.coerce_inputs({})
    assert ci["symbols"] == rr.SPDRS
    assert ci["benchmark"] == "SPY"
    assert ci["study"] == "price"
    assert ci["date"] is None


def test_coerce_inputs_types():
    ci = rr.coerce_inputs(
        {
            "symbols": "aapl,msft",
            "study": "VOLATILITY",
            "show_tails": "true",
            "long_period": "100",
            "date": "2024-01-01",
        }
    )
    assert ci["symbols"] == ["AAPL", "MSFT"]
    assert ci["study"] == "volatility"
    assert ci["show_tails"] is True
    assert ci["long_period"] == 100
    assert ci["date"] == "2024-01-01"


def test_coerce_inputs_bad_study_falls_back():
    assert rr.coerce_inputs({"study": "bogus"})["study"] == "price"


def test_rows_replaces_nan_with_none():
    import pandas as pd

    df = pd.DataFrame(
        {"a": [1.0, float("nan")]},
        index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
    )
    df.index.name = "date"
    rows = rr._rows(df)
    assert rows[0] == {"date": "2024-01-01", "a": 1.0}
    assert rows[1]["a"] is None


def test_build_toolbar_uses_pywry_components():
    toolbar = rr._build_toolbar(rr.default_inputs())
    ids: list = []

    def collect(items):
        for item in items:
            cid = getattr(item, "component_id", None)
            if cid:
                ids.append(cid)
            children = getattr(item, "children", None)
            if children:
                collect(children)

    collect(toolbar.items)
    for cid in ("symbols", "benchmark", "study", "long_period", "short_period",
                "window", "trading_periods", "show_tails", "tail_periods", "tail_interval"):
        assert cid in ids
    assert any(getattr(item, "label", "") == "Fetch Data" for item in toolbar.items)


def test_every_input_has_hover_text():
    toolbar = rr._build_toolbar(rr.default_inputs())
    described: dict = {}

    def collect(items):
        for item in items:
            cid = getattr(item, "component_id", None)
            if cid:
                described[cid] = getattr(item, "description", "")
            collect(getattr(item, "children", None) or [])

    collect(toolbar.items)
    for cid, text in rr._DESCRIPTIONS.items():
        assert described.get(cid) == text, f"{cid} has no hover text"


def test_ui_backfills_tooltips_pywry_drops():
    # pywry 2.0.5 DateInput/Div never emit data-tooltip, so the client fills them in
    js = rr._UI_JS.read_text(encoding="utf-8")
    assert "data-tooltip" in js
    assert "tooltips" in js


def test_rrg_bridge_declares_three_table_widgets():
    js = rr._BRIDGE_JS.read_text(encoding="utf-8")
    for wid in (rr.STUDY_WIDGET_ID, rr.RATIOS_WIDGET_ID, rr.MOMENTUM_WIDGET_ID):
        assert wid in js
    assert "openbb-connect" in js
    assert "openbb-data" in js


def test_rrg_bridge_pushes_tables_over_ws_without_workspace_refresh():
    js = rr._BRIDGE_JS.read_text(encoding="utf-8")
    assert 'window.pywry.on("rrg:data"' in js
    assert "openbb:widget-params:update" not in js


def test_rrg_search_modal_reuses_tvchart_dialog():
    js = rr._SEARCH_JS.read_text(encoding="utf-8")
    css = rr._SEARCH_CSS.read_text(encoding="utf-8")
    for cls in ("tv-settings-overlay", "tv-symbol-search-panel", "tv-compare-search-input", "tv-compare-result-row"):
        assert cls in js
        assert cls in css
    assert "/search?query=" in js
    assert 'getElementById("symbols")' in js
    assert "--pywry-tvchart-panel-bg" in css
    assert "--pywry-bg-" not in css


def _quadrant_figure():
    import plotly.graph_objects as go

    return go.Figure(
        layout=go.Layout(
            shapes=[
                {"type": "rect", "fillcolor": "lightgreen", "line": {"color": "Black"}},
                {"type": "rect", "fillcolor": "lightpink"},
            ],
            annotations=[{"text": "Leading", "font": {"color": "darkgreen"}}],
        )
    )


def test_apply_theme_dark():
    fig = _quadrant_figure()
    rr._apply_theme(fig, "dark")
    layout = fig.layout
    assert layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert layout.plot_bgcolor == rr._DARK_SURFACE
    assert layout.font.color == rr._DARK_INK
    assert layout.shapes[0].fillcolor == rr._DARK_QUADRANT["lightgreen"]
    assert layout.shapes[1].fillcolor == rr._DARK_QUADRANT["lightpink"]
    assert layout.shapes[0].line.color == rr._DARK_ZEROLINE
    assert layout.annotations[0].font.color == rr._DARK_LABELS["Leading"]
    assert layout.xaxis.gridcolor == rr._DARK_GRID


def test_tails_never_trigger_a_refetch():
    base = rr.default_inputs()
    tails = {**base, "tail_periods": 52, "tail_interval": "week", "show_tails": True}
    assert rr._fetch_key(base) == rr._fetch_key(tails)


@pytest.mark.integration
def test_study_and_tails_emit_visibility_over_the_event_system():
    import asyncio

    from pywry import inline

    async def main():
        inline._state.server_loop = asyncio.get_running_loop()
        await rr.rrg_widget_html(theme="dark", symbols="XLK,XLF", benchmark="SPY")
        widget_id = list(rr._STATE)[-1]
        state = rr._STATE[widget_id]
        emitted: list = []
        state["widget"].emit = lambda event, data: emitted.append((event, data))
        on_input = inline._state.widgets[widget_id]["callbacks"]["rrg:input"]

        await asyncio.to_thread(on_input, {"componentId": "study", "value": "volatility"}, "rrg:input", widget_id)
        assert ("toolbar:set-value", {"componentId": "rrg-vol-group", "style": ""}) in emitted

        emitted.clear()
        await asyncio.to_thread(on_input, {"componentId": "show_tails", "value": False}, "rrg:input", widget_id)
        assert (
            "toolbar:set-value",
            {"componentId": "rrg-tail-group", "style": "display:none;"},
        ) in emitted

    asyncio.run(main())


def _group_style(inputs, component_id):
    toolbar = rr._build_toolbar(inputs)
    for item in toolbar.items:
        if getattr(item, "component_id", None) == component_id:
            return getattr(item, "style", None)
    raise AssertionError(f"{component_id} not in toolbar")


def test_volatility_group_hidden_unless_study_is_volatility():
    base = rr.default_inputs()
    assert _group_style(base, "rrg-vol-group") == "display:none;"
    assert _group_style({**base, "study": "volatility"}, "rrg-vol-group") == ""


def test_tails_are_on_by_default():
    assert rr.default_inputs()["show_tails"] is True


def test_day_is_a_tail_interval_with_its_own_period_default():
    assert "day" in rr._TAIL_INTERVALS
    assert rr.coerce_inputs({"tail_interval": "DAY"})["tail_interval"] == "day"
    # ~3 months of trading days, so a daily tail spans a comparable window
    assert rr._TAIL_PERIODS["day"] == 60


def test_backfill_covers_the_tail_for_every_interval():
    for interval, periods in rr._TAIL_PERIODS.items():
        weeks = rr._backfill_weeks(periods, interval)
        needed = {
            "day": periods / 5,
            "week": periods,
            "month": periods * 4,
        }[interval]
        assert weeks >= needed


@pytest.mark.integration
def test_changing_interval_resets_periods_to_that_interval_default():
    import asyncio

    from pywry import inline

    async def main():
        inline._state.server_loop = asyncio.get_running_loop()
        await rr.rrg_widget_html(theme="dark", symbols="XLK,XLF", benchmark="SPY")
        widget_id = list(rr._STATE)[-1]
        state = rr._STATE[widget_id]
        emitted: list = []
        state["widget"].emit = lambda event, data: emitted.append((event, data))
        on_input = inline._state.widgets[widget_id]["callbacks"]["rrg:input"]

        await asyncio.to_thread(
            on_input, {"componentId": "tail_interval", "value": "month"}, "rrg:input", widget_id
        )
        assert state["inputs"]["tail_periods"] == rr._TAIL_PERIODS["month"]
        assert state["inputs"]["long_period"] == rr._PERIOD_DEFAULTS["month"]["long_period"]
        assert state["inputs"]["short_period"] == rr._PERIOD_DEFAULTS["month"]["short_period"]
        # the interval's params are pushed back to the UI, like tail_periods
        values = [d["values"] for e, d in emitted if e == "toolbar:set-values"]
        assert values
        pushed = values[0]
        assert pushed["tail_periods"] == rr._TAIL_PERIODS["month"]
        for key in rr._PERIOD_KEYS:
            assert pushed[key] == rr._PERIOD_DEFAULTS["month"][key]

    asyncio.run(main())


def test_tail_group_hidden_unless_show_tails():
    base = rr.default_inputs()
    assert _group_style(base, "rrg-tail-group") == ""
    assert _group_style({**base, "show_tails": False}, "rrg-tail-group") == "display:none;"


def test_rrg_ui_bridges_frames_and_loading():
    js = rr._UI_JS.read_text(encoding="utf-8")
    assert "rrg:status" in js
    assert "rrg-overlay" in js
    assert "addFrames" in js
    assert "deleteFrames" in js


def test_rrg_ui_shows_overlay_on_click_without_a_round_trip():
    # the overlay is raised locally on the interaction, not waiting for rrg:status
    js = rr._UI_JS.read_text(encoding="utf-8")
    assert "watchInteractions" in js
    assert 'addEventListener("click", onInteract, true)' in js
    assert "rrg-submit" in js


def test_apply_theme_light_leaves_quadrants():
    fig = _quadrant_figure()
    rr._apply_theme(fig, "light")
    layout = fig.layout
    assert layout.plot_bgcolor == "rgba(255,255,255,1)"
    assert layout.font.color == "#333"
    assert layout.shapes[0].fillcolor == "lightgreen"
    assert layout.annotations[0].font.color == "darkgreen"


def test_emit_rrg_resolves_empty_widget_id_to_real_id():
    rr._LIVE_RRG.clear()
    widget = _Widget()
    rr._LIVE_RRG.append((widget, {"widget_id": "rrg_deadbeef0001"}))
    try:
        res = mcp_app._emit_rrg_to_live_target("rrg:recompute", {}, None)
        assert res["dispatched"] is True
        assert res["event"]["widget_id"] == "rrg_deadbeef0001"
        assert widget.events == [("rrg:recompute", {})]
    finally:
        rr._LIVE_RRG.clear()


def test_rrg_event_payload_never_empty_string():
    rr._LIVE_RRG.clear()
    payload = mcp_app._rrg_event_payload("rrg:recompute", {}, None)
    assert payload["widget_id"] is None


def test_mcp_rrg_emit_payload_rejects_non_rrg_event():
    res = mcp_app.mcp_rrg_emit_payload(
        {"event_type": "tvchart:x", "data": {}, "widget_id": "rrg_x"}
    )
    assert res["ok"] is False
    assert "rrg:" in res["error"]


def test_list_live_rrg_targets_uses_real_widget_ids():
    rr._LIVE_RRG.clear()
    rr._LIVE_RRG.append((_Widget(), {"widget_id": "rrg_aaa"}))
    rr._LIVE_RRG.append((_Widget(), {"widget_id": "rrg_bbb"}))
    try:
        targets = mcp_app._list_live_rrg_targets()
        assert {t["widget_id"] for t in targets} == {"rrg_aaa", "rrg_bbb"}
        assert all(t["widget_id"] for t in targets)
    finally:
        rr._LIVE_RRG.clear()


def test_rrg_tools_registered():
    src = inspect.getsource(mcp_app)
    for name in ("rrg_list_targets", "rrg_set_inputs", "rrg_recompute", "rrg_send_event"):
        assert f"def {name}(" in src


def test_router_exposes_rrg_routes():
    import openbb_yfinance.yfinance_router as router

    assert hasattr(router, "rrg_page")
    assert hasattr(router, "rrg_data")
    assert hasattr(router, "rrg_search")


def test_apps_json_has_relative_rotation_tab():
    from openbb_yfinance.utils.apps import build_yfinance_apps

    tabs = build_yfinance_apps()[0]["tabs"]
    assert "relative-rotation" in tabs
    ids = [w["i"] for w in tabs["relative-rotation"]["layout"]]
    assert ids == [rr.GRAPH_WIDGET_ID]


def test_apps_json_never_pre_places_connect_declared_widgets():
    from openbb_yfinance.utils.apps import build_yfinance_apps

    connect_only = {rr.STUDY_WIDGET_ID, rr.RATIOS_WIDGET_ID, rr.MOMENTUM_WIDGET_ID}
    placed = {
        w["i"]
        for app in build_yfinance_apps()
        for tab in app["tabs"].values()
        for w in tab["layout"]
    }
    assert not (placed & connect_only)


@pytest.mark.integration
def test_redraw_params_update_instantly_without_refetch():
    import asyncio

    from pywry import inline

    async def main():
        inline._state.server_loop = asyncio.get_running_loop()
        html = await rr.rrg_widget_html(theme="dark")
        assert "pywry.emit" in html
        assert "data-event" in html

        widget_id = list(rr._STATE)[-1]
        state = rr._STATE[widget_id]
        emitted: list = []
        state["widget"].emit = lambda event, _data: emitted.append(event)
        callbacks = inline._state.widgets[widget_id]["callbacks"]

        async def fire(event, payload):
            await asyncio.to_thread(callbacks[event], payload, event, widget_id)

        fetch_key = state["fetch_key"]
        await fire("rrg:input", {"componentId": "show_tails", "value": True})
        assert state["inputs"]["show_tails"] is True
        assert state["fetch_key"] == fetch_key
        assert "plotly:update-figure" in emitted

        emitted.clear()
        await fire("rrg:input", {"componentId": "symbols", "value": "XLK,XLF"})
        assert state["inputs"]["symbols"] == ["XLK", "XLF"]
        assert emitted == []

        emitted.clear()
        await fire("rrg:submit", {})
        assert "plotly:update-figure" in emitted

    asyncio.run(main())


@pytest.mark.integration
def test_tails_frames_reach_the_island_for_animation():
    import asyncio
    import json
    import re

    async def main():
        inputs = dict(rr.default_inputs())
        html = await rr.rrg_widget_html(
            theme="dark",
            symbols="XLK,XLF",
            benchmark="SPY",
            show_tails=True,
            tail_periods=inputs["tail_periods"],
        )
        match = re.search(r"window\.__obbRrg = (\{.*?\});</script>", html, re.S)
        island = json.loads(match.group(1))
        # PyWry drops frames, so they must ride along in the island for addFrames.
        assert len(island["frames"]) > 0

    asyncio.run(main())


@pytest.mark.integration
def test_interval_resamples_prices_and_scales_params_on_3yr_data():
    import asyncio

    import pandas as pd

    async def main():
        inputs = rr.coerce_inputs(
            {"show_tails": True, "symbols": "XLK,XLF,XLE", "benchmark": "SPY",
             "tail_interval": "month", "tail_periods": 24}
        )
        # ~3 years of daily data, not decades
        assert rr._backfill_weeks(24, "month") == 156
        prices = await rr._fetch_prices(inputs, 156)
        res = rr._relative_rotation(prices, inputs)
        ratios, _momentum = rr._rs_frames(res, inputs)
        # the RS-Ratio is genuinely monthly-spaced, computed on resampled prices
        step = pd.Series(pd.to_datetime(ratios.index)).diff().dt.days.median()
        assert 27 <= step <= 32

    asyncio.run(main())


@pytest.mark.integration
@pytest.mark.parametrize("study", ["price", "volume", "volatility"])
def test_every_study_computes(study):
    import asyncio

    out = asyncio.run(
        rr.compute_rrg(theme="dark", symbols="XLK,XLF", benchmark="SPY", study=study)
    )
    assert out["figure"]["data"]
    assert out["study"] == study


@pytest.mark.integration
def test_compute_rrg_live():
    import asyncio

    out = asyncio.run(rr.compute_rrg(symbols="XLK,XLF", benchmark="SPY"))
    assert out["figure"]["data"]
    assert out["study_data"] and out["rs_ratios"] and out["rs_momentum"]
    assert "SPY" in out["symbols"] + [out["benchmark"]]
