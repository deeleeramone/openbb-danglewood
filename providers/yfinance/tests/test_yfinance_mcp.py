from types import SimpleNamespace

from openbb_yfinance.utils import mcp_app


def test_mcp_tvchart_emit_payload_rejects_non_tvchart_event():
    result = mcp_app.mcp_tvchart_emit_payload(
        {"event_type": "grid:update-data", "data": {}, "widget_id": "w1"}
    )
    assert result["ok"] is False
    assert result["dispatched"] is False
    assert "tvchart:" in result["error"]


def test_emit_to_live_target_dispatches_inline_widget(monkeypatch):
    class _Target:
        def __init__(self):
            self.events = []

        def emit(self, event, data):
            self.events.append((event, data))

    target = _Target()
    app = SimpleNamespace(_inline_widgets={"w1": target}, label="app-main")

    from openbb_yfinance.utils import tvchart_native

    monkeypatch.setattr(tvchart_native, "_LIVE_CHARTS", [(app, None)], raising=False)

    result = mcp_app._emit_to_live_target("tvchart:undo", {}, "w1")
    assert result["ok"] is True
    assert result["dispatched"] is True
    assert target.events == [("tvchart:undo", {})]


def test_emit_or_envelope_uses_bridge_when_local_unavailable(monkeypatch):
    monkeypatch.setattr(
        mcp_app,
        "_emit_to_live_target",
        lambda event_type, data, widget_id: {
            "ok": True,
            "dispatched": False,
            "event": {
                "event_type": event_type,
                "widget_id": widget_id,
                "data": data,
            },
        },
    )
    monkeypatch.setattr(
        mcp_app,
        "_emit_via_api_bridge",
        lambda event_type, data, widget_id: {
            "ok": True,
            "dispatched": True,
            "event": {
                "event_type": event_type,
                "widget_id": widget_id,
                "data": data,
            },
        },
    )

    result = mcp_app._emit_or_envelope("tvchart:time-range", {"value": "1Y"}, "")
    assert result["ok"] is True
    assert result["dispatched"] is True
    assert result["event"]["event_type"] == "tvchart:time-range"


def test_mcp_tvchart_emit_payload_dispatches(monkeypatch):
    monkeypatch.setattr(
        mcp_app,
        "_emit_to_live_target",
        lambda event_type, data, widget_id: {
            "ok": True,
            "dispatched": True,
            "event": {
                "event_type": event_type,
                "widget_id": widget_id,
                "data": data,
            },
        },
    )

    result = mcp_app.mcp_tvchart_emit_payload(
        {
            "event_type": "tvchart:symbol-search",
            "data": {"query": "MSFT", "autoSelect": True},
            "widget_id": "w1",
        }
    )
    assert result["ok"] is True
    assert result["dispatched"] is True
    assert result["event"]["widget_id"] == "w1"


def test_list_live_tvchart_targets_collects_inline_widget_ids(monkeypatch):
    from openbb_yfinance.utils import tvchart_native

    app = SimpleNamespace(
        label="app-main",
        _inline_widgets={"w1": object(), "w2": object()},
        _obb_chart_ids_by_widget={"w1": "cid-1", "w2": "cid-2"},
        _obb_chart_id="cid-app",
    )
    monkeypatch.setattr(tvchart_native, "_LIVE_CHARTS", [(app, None)], raising=False)

    targets = mcp_app._list_live_tvchart_targets()
    ids = {t["widget_id"] for t in targets}
    assert ids == {"w1", "w2"}
    by_id = {t["widget_id"]: t["chart_id"] for t in targets}
    assert by_id["w1"] == "cid-1"
    assert by_id["w2"] == "cid-2"


def test_emit_to_live_target_injects_resolved_chart_id(monkeypatch):
    class _Target:
        def __init__(self):
            self.events = []

        def emit(self, event, data):
            self.events.append((event, data))

    target = _Target()
    app = SimpleNamespace(
        _inline_widgets={"w1": target},
        _obb_chart_ids_by_widget={"w1": "cid-1"},
        _obb_chart_id="cid-app",
        label="app-main",
    )

    from openbb_yfinance.utils import tvchart_native

    monkeypatch.setattr(tvchart_native, "_LIVE_CHARTS", [(app, None)], raising=False)

    result = mcp_app._emit_to_live_target("tvchart:undo", {}, "w1")
    assert result["ok"] is True
    assert result["dispatched"] is True
    assert target.events == [("tvchart:undo", {"chartId": "cid-1"})]


def test_tvchart_tools_include_target_discovery_tool():
    import inspect

    source = inspect.getsource(mcp_app)
    assert "def tvchart_list_targets(" in source


def test_tvchart_tool_docstrings_include_response_examples():
    import inspect

    source = inspect.getsource(mcp_app)
    for name in (
        "tvchart_send_event",
        "tvchart_symbol_search",
        "tvchart_change_interval",
        "tvchart_time_range",
        "tvchart_toggle_dark_mode",
        "tvchart_chart_type",
        "tvchart_compare",
        "tvchart_request_state",
        "tvchart_add_indicator",
        "tvchart_remove_indicator",
        "tvchart_list_indicators",
        "tvchart_show_indicators",
        "tvchart_show_settings",
        "tvchart_time_range_picker",
        "tvchart_log_scale",
        "tvchart_auto_scale",
        "tvchart_drawing_tool",
        "tvchart_undo",
        "tvchart_redo",
        "tvchart_screenshot",
        "tvchart_fullscreen",
    ):
        assert f"def {name}(" in source
    assert source.count("Example response:") >= 20


def test_tvchart_drawing_tool_rejects_invalid_mode():
    import inspect

    source = inspect.getsource(mcp_app)
    assert (
        "mode must be one of: cursor, crosshair, magnet, eraser, visibility, lock"
        in source
    )


def test_confirm_state_captures_local_state_response(monkeypatch):
    class _Target:
        def __init__(self):
            self.handlers = {}

        def on(self, event, callback):
            self.handlers[event] = callback

        def emit(self, event, data):
            if event == "tvchart:request-state":
                token = data.get("context", {}).get("mcpToken")
                cb = self.handlers.get("tvchart:state-response")
                if cb:
                    cb({"symbol": "AAPL", "context": {"mcpToken": token}})

    target = _Target()
    monkeypatch.setattr(
        mcp_app,
        "_latest_tvchart_target",
        lambda widget_id="": (target, widget_id or "w1"),
    )
    monkeypatch.setattr(
        mcp_app,
        "_emit_or_envelope",
        lambda event_type, data, widget_id: (
            target.emit(event_type, data)
            or {
                "ok": True,
                "dispatched": True,
                "event": {
                    "event_type": event_type,
                    "widget_id": widget_id,
                    "data": data,
                },
            }
        ),
    )

    confirmed = mcp_app._confirm_state(widget_id="w1", timeout=0.2)
    assert confirmed is not None
    assert confirmed["data"]["symbol"] == "AAPL"


def test_dispatch_with_settled_confirmation_returns_confirmed(monkeypatch):
    class _Target:
        def __init__(self):
            self.handlers = {}

        def on(self, event, callback):
            self.handlers[event] = callback

        def emit(self, event, data):
            if event == "tvchart:time-range":
                cb = self.handlers.get("tvchart:data-settled")
                if cb:
                    cb({"interval": "1D"})

    target = _Target()
    monkeypatch.setattr(
        mcp_app,
        "_latest_tvchart_target",
        lambda widget_id="": (target, widget_id or "w1"),
    )
    monkeypatch.setattr(
        mcp_app,
        "_emit_or_envelope",
        lambda event_type, data, widget_id: (
            target.emit(event_type, data)
            or {
                "ok": True,
                "dispatched": True,
                "event": {
                    "event_type": event_type,
                    "widget_id": widget_id,
                    "data": data,
                },
            }
        ),
    )

    result = mcp_app._dispatch_with_settled_confirmation(
        "tvchart:time-range",
        {"value": "1D"},
        "w1",
        confirm=True,
        timeout=0.2,
    )
    assert result["confirmed"] is True


def test_remaining_tvchart_tools_accept_confirm_timeout():
    import inspect

    for fn_name in (
        "tvchart_show_indicators",
        "tvchart_show_settings",
        "tvchart_time_range_picker",
        "tvchart_log_scale",
        "tvchart_auto_scale",
        "tvchart_drawing_tool",
        "tvchart_undo",
        "tvchart_redo",
        "tvchart_screenshot",
        "tvchart_fullscreen",
    ):
        source = inspect.getsource(mcp_app)
        block_start = source.find(f"def {fn_name}(")
        assert block_start >= 0
        block = source[block_start : block_start + 260]
        assert "confirm" in block
        assert "timeout" in block


def test_tvchart_list_indicators_defaults_confirm_true():
    import inspect

    source = inspect.getsource(mcp_app)
    start = source.find("def tvchart_list_indicators(")
    assert start >= 0
    block = source[start : start + 220]
    assert "confirm: bool = True" in block
