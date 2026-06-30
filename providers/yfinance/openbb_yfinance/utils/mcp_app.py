"""Yahoo Finance MCP server: a streamable-http subprocess, reverse-proxied
through the OpenBB API so the Workspace connects on the API's own host/port.
"""

import threading
import uuid
from typing import Any

from fastapi import Depends
from starlette.requests import Request


def _list_live_tvchart_targets() -> list[dict[str, Any]]:
    try:
        from openbb_yfinance.utils import tvchart_native
    except Exception:
        return []

    targets: list[dict[str, Any]] = []
    charts = getattr(tvchart_native, "_LIVE_CHARTS", [])
    for index, item in enumerate(charts):
        if not isinstance(item, (list, tuple)) or not item:
            continue
        app = item[0]

        inline_widgets = getattr(app, "_inline_widgets", {}) or {}
        chart_ids = getattr(app, "_obb_chart_ids_by_widget", {}) or {}
        app_chart_id = str(getattr(app, "_obb_chart_id", "") or "")
        if inline_widgets:
            for label in inline_widgets:
                targets.append(
                    {
                        "instance_index": index,
                        "widget_id": str(label),
                        "chart_id": str(
                            chart_ids.get(str(label)) or app_chart_id or ""
                        ),
                        "app_label": str(getattr(app, "label", "") or ""),
                    }
                )
        else:
            app_label = str(getattr(app, "label", "") or "")
            if app_label:
                targets.append(
                    {
                        "instance_index": index,
                        "widget_id": app_label,
                        "chart_id": app_chart_id,
                        "app_label": app_label,
                    }
                )

    return targets


def _latest_tvchart_target(widget_id: str = "") -> tuple[Any | None, str]:
    try:
        from openbb_yfinance.utils import tvchart_native
    except Exception:
        return None, ""

    for app, _streamer in reversed(getattr(tvchart_native, "_LIVE_CHARTS", [])):
        inline_widgets = getattr(app, "_inline_widgets", {}) or {}
        if widget_id:
            target = inline_widgets.get(widget_id)
            if target is not None:
                return target, widget_id
            if getattr(app, "label", "") == widget_id:
                return app, widget_id
            continue

        if inline_widgets:
            items = list(inline_widgets.items())
            if items:
                label, target = items[-1]
                return target, str(label)
        return app, str(getattr(app, "label", "") or "")

    return None, ""


def _latest_tvchart_chart_id(widget_id: str = "") -> str:  # noqa: PLR0911
    try:
        from openbb_yfinance.utils import tvchart_native
    except Exception:
        return ""

    for app, _streamer in reversed(getattr(tvchart_native, "_LIVE_CHARTS", [])):
        inline_widgets = getattr(app, "_inline_widgets", {}) or {}
        chart_ids = getattr(app, "_obb_chart_ids_by_widget", {}) or {}
        app_chart_id = str(getattr(app, "_obb_chart_id", "") or "")

        if widget_id:
            if widget_id in chart_ids:
                return str(chart_ids.get(widget_id) or "")
            if widget_id in inline_widgets:
                return app_chart_id
            if getattr(app, "label", "") == widget_id:
                return app_chart_id
            continue

        if inline_widgets:
            labels = list(inline_widgets.keys())
            if labels:
                return str(chart_ids.get(str(labels[-1])) or app_chart_id)
        if app_chart_id:
            return app_chart_id

    return ""


def _resolved_tvchart_data(
    event_type: str, data: dict[str, Any] | None = None, widget_id: str = ""
) -> dict[str, Any]:
    payload = dict(data or {})
    if event_type.startswith("tvchart:") and "chartId" not in payload:
        chart_id = _latest_tvchart_chart_id(widget_id)
        if chart_id:
            payload["chartId"] = chart_id
    return payload


def _tvchart_event_payload(
    event_type: str, data: dict[str, Any] | None = None, widget_id: str = ""
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "widget_id": widget_id,
        "data": data or {},
    }


def _emit_to_live_target(
    event_type: str, data: dict[str, Any] | None = None, widget_id: str = ""
) -> dict[str, Any]:
    payload = _tvchart_event_payload(
        event_type, _resolved_tvchart_data(event_type, data, widget_id), widget_id
    )
    target, resolved_widget_id = _latest_tvchart_target(widget_id)
    if target is None:
        return {
            "ok": True,
            "dispatched": False,
            "event": payload,
            "note": "No live chart target was available in this process.",
        }

    if resolved_widget_id and not payload["widget_id"]:
        payload["widget_id"] = resolved_widget_id
    try:
        target.emit(payload["event_type"], payload["data"])
    except Exception as exc:
        return {
            "ok": False,
            "dispatched": False,
            "event": payload,
            "error": str(exc),
        }

    return {
        "ok": True,
        "dispatched": True,
        "event": payload,
    }


def _api_prefix() -> str:
    try:
        from openbb_core.app.service.system_service import SystemService

        return SystemService().system_settings.api_settings.prefix or ""
    except Exception:
        return ""


def _api_tvchart_bridge_url() -> str:
    import os

    public_mcp = os.environ.get("OPENBB_YFINANCE_MCP_PUBLIC_URL", "").strip()
    if public_mcp:
        return f"{public_mcp.rstrip('/')}/tvchart/emit"

    host = os.environ.get("OPENBB_YFINANCE_MCP_PUBLIC_HOST", "127.0.0.1")
    port = os.environ.get("OPENBB_API_PORT", "6900")
    prefix = _api_prefix()
    return f"http://{host}:{port}{prefix}/yfinance/mcp/tvchart/emit"


def _emit_via_api_bridge(
    event_type: str, data: dict[str, Any] | None = None, widget_id: str = ""
) -> dict[str, Any]:
    import json
    import urllib.error
    import urllib.request

    payload = _tvchart_event_payload(
        event_type, _resolved_tvchart_data(event_type, data, widget_id), widget_id
    )
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310
        _api_tvchart_bridge_url(),
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=2.5) as resp:  # noqa: S310
            response_text = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        return {
            "ok": False,
            "dispatched": False,
            "event": payload,
            "error": f"Bridge request failed: {exc}",
        }

    try:
        bridge_result = json.loads(response_text)
    except Exception:
        bridge_result = {
            "ok": False,
            "dispatched": False,
            "event": payload,
            "error": "Bridge returned non-JSON payload.",
        }
    if isinstance(bridge_result, dict):
        bridge_result.setdefault("event", payload)
    return bridge_result


def _emit_or_envelope(
    event_type: str, data: dict[str, Any] | None = None, widget_id: str = ""
) -> dict[str, Any]:
    local = _emit_to_live_target(event_type, data, widget_id)
    if local.get("dispatched"):
        return local

    bridged = _emit_via_api_bridge(event_type, data, widget_id)
    if isinstance(bridged, dict) and bridged.get("dispatched"):
        return bridged

    payload = _tvchart_event_payload(event_type, data, widget_id)
    bridge_error = ""
    if isinstance(bridged, dict):
        bridge_error = str(bridged.get("error") or "")
    note = "No live chart target was available; returning event envelope for client dispatch."
    if bridge_error:
        note = f"{note} Bridge error: {bridge_error}"
    return {
        "ok": True,
        "dispatched": False,
        "event": payload,
        "note": note,
    }


def _await_local_tvchart_event(
    event_type: str,
    widget_id: str = "",
    timeout: float = 3.0,
    token: str = "",
) -> dict[str, Any] | None:
    target, resolved_widget_id = _latest_tvchart_target(widget_id)
    if target is None or not hasattr(target, "on"):
        return None

    gate = threading.Event()
    box: dict[str, Any] = {}

    def _handler(data: dict[str, Any] | None = None, *_args: Any) -> None:
        if token:
            context = (data or {}).get("context") if isinstance(data, dict) else None
            if not isinstance(context, dict) or context.get("mcpToken") != token:
                return
        box["data"] = data or {}
        gate.set()

    try:
        target.on(event_type, _handler)
    except Exception:
        return None

    wait_seconds = max(0.05, float(timeout))
    if not gate.wait(wait_seconds):
        return None

    return {
        "event_type": event_type,
        "widget_id": resolved_widget_id or widget_id,
        "data": box.get("data", {}),
    }


def _confirm_state(
    widget_id: str = "",
    chart_id: str = "",
    timeout: float = 3.0,
) -> dict[str, Any] | None:
    token = uuid.uuid4().hex
    payload: dict[str, Any] = {"context": {"mcpToken": token}}
    if chart_id:
        payload["chartId"] = chart_id
    request = _emit_or_envelope("tvchart:request-state", payload, widget_id)
    if not request.get("dispatched"):
        return None
    return _await_local_tvchart_event(
        "tvchart:state-response",
        widget_id=widget_id,
        timeout=timeout,
        token=token,
    )


def _confirm_indicators(
    widget_id: str = "",
    chart_id: str = "",
    timeout: float = 3.0,
) -> dict[str, Any] | None:
    token = uuid.uuid4().hex
    payload: dict[str, Any] = {"context": {"mcpToken": token}}
    if chart_id:
        payload["chartId"] = chart_id
    request = _emit_or_envelope("tvchart:list-indicators", payload, widget_id)
    if not request.get("dispatched"):
        return None
    return _await_local_tvchart_event(
        "tvchart:list-indicators-response",
        widget_id=widget_id,
        timeout=timeout,
        token=token,
    )


def _dispatch_with_settled_confirmation(
    event_type: str,
    data: dict[str, Any] | None = None,
    widget_id: str = "",
    confirm: bool = False,
    timeout: float = 3.0,
) -> dict[str, Any]:
    result = _emit_or_envelope(event_type, data, widget_id)
    if not confirm:
        return result

    out = dict(result)
    if not out.get("dispatched"):
        out["confirmed"] = False
        return out

    confirmation = _await_local_tvchart_event(
        "tvchart:data-settled", widget_id=widget_id, timeout=timeout
    )
    out["confirmed"] = confirmation is not None
    if confirmation is not None:
        out["confirmation"] = confirmation
    else:
        out["note"] = (
            "Event dispatched but no local data-settled confirmation was captured before timeout."
        )
    return out


def mcp_tvchart_emit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a tvchart emit payload and dispatch it to the live chart."""
    event_type = str(payload.get("event_type") or "")
    data = payload.get("data")
    widget_id = str(payload.get("widget_id") or "")

    if not event_type.startswith("tvchart:"):
        return {
            "ok": False,
            "dispatched": False,
            "event": _tvchart_event_payload(
                event_type, data if isinstance(data, dict) else {}, widget_id
            ),
            "error": "event_type must start with 'tvchart:'",
        }

    return _emit_to_live_target(
        event_type,
        data if isinstance(data, dict) else {},
        widget_id,
    )


async def mcp_tvchart_emit(request: Request) -> Any:
    """Handle the bridge HTTP request that emits a tvchart event."""
    from starlette.responses import JSONResponse

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            {"ok": False, "error": "Invalid JSON payload"}, status_code=400
        )
    if not isinstance(payload, dict):
        return JSONResponse(
            {"ok": False, "error": "Payload must be a JSON object"}, status_code=400
        )
    result = mcp_tvchart_emit_payload(payload)
    status = 200 if result.get("ok") else 400
    return JSONResponse(result, status_code=status)


def _build_mcp_server() -> Any:
    """Build the FastMCP server and register the Yahoo Finance tools."""
    from fastmcp import FastMCP

    mcp: Any = FastMCP(
        name="OpenBB Yahoo Finance",
        instructions=(
            "Tools for Yahoo Finance market data: symbol search, price history,"
            " quotes, company profiles, and a symbol screener. Use them to answer"
            " questions about the symbol shown on the TradingView chart, to look up"
            " new symbols, and to enumerate a region/exchange/sector/industry or fund"
            " issuer/style universe with the screener. TV chart control tools emit"
            " tvchart:* events with payloads aligned to PyWry's event system."
        ),
    )

    @mcp.tool
    def tvchart_list_targets() -> dict:
        """List active TradingView chart targets for multi-instance control.

        Returns ``{ok, count, targets}``, where each target includes
        ``widget_id`` and ``chart_id``.

        Example response:
        ``{"ok": True, "count": 2, "targets": [{"widget_id": "tvw_a1b2c3", "chart_id": "tvc_1a2b3c"}, {"widget_id": "tvw_d4e5f6", "chart_id": "tvc_4d5e6f"}]}``
        """
        targets = _list_live_tvchart_targets()
        return {
            "ok": True,
            "count": len(targets),
            "targets": targets,
        }

    @mcp.tool
    def tvchart_send_event(
        event_type: str,
        data: dict[str, Any] | None = None,
        widget_id: str = "",
    ) -> dict:
        """Emit a raw ``tvchart:*`` event.

        Returns a dictionary with fields ``ok`` (bool), ``dispatched`` (bool),
        and ``event`` containing ``{event_type, widget_id, data}``. When no live
        in-process chart is reachable, the tool attempts API-bridge dispatch and,
        if still unavailable, returns an event envelope with ``dispatched=false``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:undo", "widget_id": "", "data": {}}}``
        """
        if not event_type.startswith("tvchart:"):
            return {
                "ok": False,
                "dispatched": False,
                "error": "event_type must start with 'tvchart:'",
                "event": _tvchart_event_payload(event_type, data, widget_id),
            }
        return _emit_or_envelope(event_type, data, widget_id)

    @mcp.tool
    def tvchart_symbol_search(
        query: str,
        auto_select: bool = True,
        symbol_type: str = "",
        exchange: str = "",
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:symbol-search`` to drive the chart symbol picker.

        Response shape:
        ``{ok: bool, dispatched: bool, event: {event_type, widget_id, data}, note?: str, error?: str}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:symbol-search", "widget_id": "", "data": {"query": "MSFT", "autoSelect": true}}}``
        """
        payload: dict[str, Any] = {
            "query": query,
            "autoSelect": auto_select,
        }
        if symbol_type:
            payload["symbolType"] = symbol_type
        if exchange:
            payload["exchange"] = exchange
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            "tvchart:symbol-search",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_change_interval(
        value: str,
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:interval-change``.

        Response fields follow:
        ``{ok, dispatched, event{event_type, widget_id, data}, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:interval-change", "widget_id": "", "data": {"value": "1D"}}}``
        """
        payload: dict[str, Any] = {"value": value}
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            "tvchart:interval-change",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_time_range(
        value: str,
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:time-range``.

        Response fields:
        ``{ok, dispatched, event{event_type, widget_id, data}, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:time-range", "widget_id": "", "data": {"value": "1Y"}}}``
        """
        payload: dict[str, Any] = {"value": value}
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            "tvchart:time-range",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_toggle_dark_mode(
        value: bool,
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:toggle-dark-mode``.

        Response fields:
        ``{ok, dispatched, event{event_type, widget_id, data}, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:toggle-dark-mode", "widget_id": "", "data": {"value": true}}}``
        """
        payload: dict[str, Any] = {"value": value}
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            "tvchart:toggle-dark-mode",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_chart_type(
        value: str,
        series_id: str = "",
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:chart-type-change``.

        Response fields:
        ``{ok, dispatched, event{event_type, widget_id, data}, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:chart-type-change", "widget_id": "", "data": {"value": "Candles"}}}``
        """
        payload: dict[str, Any] = {"value": value}
        if series_id:
            payload["seriesId"] = series_id
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            "tvchart:chart-type-change",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_compare(
        query: str = "",
        auto_add: bool = True,
        symbol_type: str = "",
        exchange: str = "",
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:compare`` to add/open compare overlays.

        Response fields:
        ``{ok, dispatched, event{event_type, widget_id, data}, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:compare", "widget_id": "", "data": {"query": "SPY", "autoAdd": true}}}``
        """
        payload: dict[str, Any] = {
            "autoAdd": auto_add,
        }
        if query:
            payload["query"] = query
        if symbol_type:
            payload["symbolType"] = symbol_type
        if exchange:
            payload["exchange"] = exchange
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            "tvchart:compare",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_request_state(
        chart_id: str = "",
        context: dict[str, Any] | None = None,
        widget_id: str = "",
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:request-state`` for a chart state snapshot round-trip.

        Response fields:
        ``{ok, dispatched, event{event_type, widget_id, data}, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:request-state", "widget_id": "", "data": {}}}``
        """
        payload: dict[str, Any] = {}
        if chart_id:
            payload["chartId"] = chart_id
        if context is not None:
            payload["context"] = context
        result = _emit_or_envelope("tvchart:request-state", payload, widget_id)
        out = dict(result)
        if not out.get("dispatched"):
            out["confirmed"] = False
            return out
        confirmation = _confirm_state(
            widget_id=widget_id, chart_id=chart_id, timeout=timeout
        )
        out["confirmed"] = confirmation is not None
        if confirmation is not None:
            out["state"] = confirmation.get("data", {})
        else:
            out["note"] = (
                "State request dispatched but no local state-response was captured before timeout."
            )
        return out

    @mcp.tool
    def tvchart_add_indicator(
        name: str,
        period: int = 0,
        color: str = "",
        source: str = "",
        method: str = "",
        multiplier: float = 0.0,
        ma_type: str = "",
        offset: int = 0,
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = True,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:add-indicator``.

        Response fields:
        ``{ok, dispatched, confirmed?, confirmation?, indicators?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "confirmed": True, "event": {"event_type": "tvchart:add-indicator", "widget_id": "", "data": {"name": "RSI", "period": 14}}, "indicators": [{"seriesId": "ind_rsi_1", "name": "RSI"}]}``
        """
        payload: dict[str, Any] = {"name": name}
        if period > 0:
            payload["period"] = period
        if color:
            payload["color"] = color
        if source:
            payload["source"] = source
        if method:
            payload["method"] = method
        if multiplier:
            payload["multiplier"] = multiplier
        if ma_type:
            payload["maType"] = ma_type
        if offset:
            payload["offset"] = offset
        if chart_id:
            payload["chartId"] = chart_id
        result = _dispatch_with_settled_confirmation(
            "tvchart:add-indicator",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )
        if not confirm:
            return result
        out = dict(result)
        indicator_snapshot = _confirm_indicators(
            widget_id=widget_id,
            chart_id=chart_id,
            timeout=timeout,
        )
        if indicator_snapshot is not None:
            out["indicators"] = indicator_snapshot.get("data", {}).get("indicators", [])
        return out

    @mcp.tool
    def tvchart_remove_indicator(
        series_id: str,
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = True,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:remove-indicator``.

        Response fields:
        ``{ok, dispatched, confirmed?, confirmation?, indicators?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "confirmed": True, "event": {"event_type": "tvchart:remove-indicator", "widget_id": "", "data": {"seriesId": "ind_rsi_1"}}, "indicators": []}``
        """
        payload: dict[str, Any] = {"seriesId": series_id}
        if chart_id:
            payload["chartId"] = chart_id
        result = _dispatch_with_settled_confirmation(
            "tvchart:remove-indicator",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )
        if not confirm:
            return result
        out = dict(result)
        indicator_snapshot = _confirm_indicators(
            widget_id=widget_id,
            chart_id=chart_id,
            timeout=timeout,
        )
        if indicator_snapshot is not None:
            out["indicators"] = indicator_snapshot.get("data", {}).get("indicators", [])
        return out

    @mcp.tool
    def tvchart_list_indicators(
        chart_id: str = "",
        context: dict[str, Any] | None = None,
        widget_id: str = "",
        confirm: bool = True,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:list-indicators`` or return a confirmed local snapshot.

        Response fields:
        ``{ok, dispatched, confirmed?, indicators?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "confirmed": True, "event": {"event_type": "tvchart:list-indicators", "widget_id": "", "data": {}}, "indicators": [{"seriesId": "ind_rsi_1", "name": "RSI"}]}``
        """
        if confirm:
            snapshot = _confirm_indicators(
                widget_id=widget_id,
                chart_id=chart_id,
                timeout=timeout,
            )
            if snapshot is None:
                payload: dict[str, Any] = {}
                if chart_id:
                    payload["chartId"] = chart_id
                if context is not None:
                    payload["context"] = context
                result = _emit_or_envelope(
                    "tvchart:list-indicators", payload, widget_id
                )
                out = dict(result)
                out["confirmed"] = False
                out["note"] = (
                    "Indicator list request dispatched but no local list-indicators-response was captured before timeout."
                )
                return out
            return {
                "ok": True,
                "dispatched": True,
                "confirmed": True,
                "event": _tvchart_event_payload(
                    "tvchart:list-indicators", {}, widget_id
                ),
                "indicators": snapshot.get("data", {}).get("indicators", []),
            }
        payload: dict[str, Any] = {}
        if chart_id:
            payload["chartId"] = chart_id
        if context is not None:
            payload["context"] = context
        return _emit_or_envelope("tvchart:list-indicators", payload, widget_id)

    @mcp.tool
    def tvchart_show_indicators(
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:show-indicators``.

        Response fields:
        ``{ok, dispatched, confirmed?, confirmation?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:show-indicators", "widget_id": "", "data": {}}}``
        """
        payload: dict[str, Any] = {}
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            "tvchart:show-indicators",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_show_settings(
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:show-settings``.

        Response fields:
        ``{ok, dispatched, confirmed?, confirmation?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:show-settings", "widget_id": "", "data": {}}}``
        """
        payload: dict[str, Any] = {}
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            "tvchart:show-settings",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_time_range_picker(
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:time-range-picker``.

        Response fields:
        ``{ok, dispatched, confirmed?, confirmation?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:time-range-picker", "widget_id": "", "data": {}}}``
        """
        payload: dict[str, Any] = {}
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            "tvchart:time-range-picker",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_log_scale(
        value: bool,
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:log-scale``.

        Response fields:
        ``{ok, dispatched, confirmed?, confirmation?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:log-scale", "widget_id": "", "data": {"value": true}}}``
        """
        payload: dict[str, Any] = {"value": value}
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            "tvchart:log-scale",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_auto_scale(
        value: bool,
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:auto-scale``.

        Response fields:
        ``{ok, dispatched, confirmed?, confirmation?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:auto-scale", "widget_id": "", "data": {"value": true}}}``
        """
        payload: dict[str, Any] = {"value": value}
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            "tvchart:auto-scale",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_drawing_tool(
        mode: str,
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit one drawing-tool event from ``mode``.

        Modes: ``cursor``, ``crosshair``, ``magnet``, ``eraser``, ``visibility``, ``lock``.

        Response fields:
        ``{ok, dispatched, confirmed?, confirmation?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:tool-crosshair", "widget_id": "", "data": {}}}``
        """
        event_map = {
            "cursor": "tvchart:tool-cursor",
            "crosshair": "tvchart:tool-crosshair",
            "magnet": "tvchart:tool-magnet",
            "eraser": "tvchart:tool-eraser",
            "visibility": "tvchart:tool-visibility",
            "lock": "tvchart:tool-lock",
        }
        key = str(mode).strip().lower()
        event = event_map.get(key)
        if event is None:
            return {
                "ok": False,
                "dispatched": False,
                "error": "mode must be one of: cursor, crosshair, magnet, eraser, visibility, lock",
                "event": _tvchart_event_payload("", {}, widget_id),
            }
        payload: dict[str, Any] = {}
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            event,
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_undo(
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:undo``.

        Response fields:
        ``{ok, dispatched, confirmed?, confirmation?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:undo", "widget_id": "", "data": {}}}``
        """
        return _dispatch_with_settled_confirmation(
            "tvchart:undo",
            {},
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_redo(
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:redo``.

        Response fields:
        ``{ok, dispatched, confirmed?, confirmation?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:redo", "widget_id": "", "data": {}}}``
        """
        return _dispatch_with_settled_confirmation(
            "tvchart:redo",
            {},
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_screenshot(
        chart_id: str = "",
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:screenshot``.

        Response fields:
        ``{ok, dispatched, confirmed?, confirmation?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:screenshot", "widget_id": "", "data": {}}}``
        """
        payload: dict[str, Any] = {}
        if chart_id:
            payload["chartId"] = chart_id
        return _dispatch_with_settled_confirmation(
            "tvchart:screenshot",
            payload,
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def tvchart_fullscreen(
        widget_id: str = "",
        confirm: bool = False,
        timeout: float = 3.0,
    ) -> dict:
        """Emit ``tvchart:fullscreen``.

        Response fields:
        ``{ok, dispatched, confirmed?, confirmation?, event, note?, error?}``.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "tvchart:fullscreen", "widget_id": "", "data": {}}}``
        """
        return _dispatch_with_settled_confirmation(
            "tvchart:fullscreen",
            {},
            widget_id,
            confirm=confirm,
            timeout=timeout,
        )

    @mcp.tool
    def search_symbols(query: str, asset_type: str = "") -> list:
        """Search Yahoo Finance for ticker symbols by name or ticker."""
        from openbb_yfinance.utils.search_helpers import yf_symbol_search

        return yf_symbol_search(query, limit=25, asset_type=asset_type)

    @mcp.tool
    def get_price_history(symbol: str, interval: str = "1d") -> list:
        """Get OHLCV price history for a symbol."""
        from openbb_yfinance.utils.tvchart_datafeed import BarCache

        return BarCache().get(symbol, interval)

    @mcp.tool
    def get_quote(symbol: str) -> dict:
        """Get the latest price and key statistics for a symbol."""
        import yfinance as yf

        info = yf.Ticker(symbol).fast_info
        keys = (
            "last_price",
            "previous_close",
            "open",
            "day_high",
            "day_low",
            "year_high",
            "year_low",
            "market_cap",
            "shares",
            "currency",
            "exchange",
            "ten_day_average_volume",
            "fifty_day_average",
            "two_hundred_day_average",
        )
        out: dict = {"symbol": symbol.upper()}
        for key in keys:
            try:
                out[key] = info[key]
            except Exception:
                out[key] = None
        return out

    @mcp.tool
    def get_company_profile(symbol: str) -> dict:
        """Get the asset profile for a symbol (name, exchange, type, sector, etc.)."""
        from openbb_yfinance.utils.tvchart_datafeed import yf_symbol_info

        info = yf_symbol_info(symbol) or {}
        return {
            "symbol": symbol.upper(),
            "name": info.get("name"),
            "description": info.get("description"),
            "exchange": info.get("exchange"),
            "type": info.get("type"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "currency": info.get("currency_code"),
            "timezone": info.get("timezone"),
        }

    @mcp.tool
    async def run_screener(
        asset_type: str = "equity",
        exchange: str = "",
        region: str = "us",
        sector: str = "",
        industry: str = "",
        fund_issuer: str = "",
        fund_style: str = "",
        universe: bool = False,
        limit: int = 50,
    ) -> list:
        """Screen Yahoo Finance for symbols by dimension.

        Pull symbols for a region, exchange, asset type, sector, industry, fund
        issuer, or fund style. ``asset_type`` is one of equity, etf, fund, index,
        future. Set ``universe`` true to return every match without the default
        market-cap, price, and volume floors. ``region`` accepts a country code or
        'all'; ``exchange``/``sector``/``industry``/``fund_issuer``/``fund_style``
        are matched case-insensitively to their Yahoo Finance choices.
        """
        from openbb_yfinance.models.equity_screener import (
            YFinanceEquityScreenerFetcher,
        )

        params: dict = {
            "asset_type": asset_type,
            "universe": universe,
            "limit": limit,
        }
        for key, value in (
            ("exchange", exchange),
            ("country", region),
            ("sector", sector),
            ("industry", industry),
            ("fund_issuer", fund_issuer),
            ("fund_style", fund_style),
        ):
            if value:
                params[key] = value
        rows: Any = await YFinanceEquityScreenerFetcher.fetch_data(params, {})
        return [
            r.model_dump(exclude_none=True, exclude={"price_history"}) for r in rows
        ]

    return mcp


_MCP_HOST = "127.0.0.1"
_MCP_PATH = "/mcp"
_DEFAULT_MCP_PORT = 6922


def mcp_port() -> int:
    """Return the port the MCP subprocess listens on (``OPENBB_YFINANCE_MCP_PORT``)."""
    import os

    try:
        return int(os.environ.get("OPENBB_YFINANCE_MCP_PORT", str(_DEFAULT_MCP_PORT)))
    except ValueError:
        return _DEFAULT_MCP_PORT


def mcp_server_url() -> str:
    """Return the streamable-http URL the Workspace connects to."""
    return f"http://{_MCP_HOST}:{mcp_port()}{_MCP_PATH}"


def _port_open(host: str, port: int) -> bool:
    """Return True if something is already listening on host:port."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


_mcp_process: Any = None


def ensure_mcp_subprocess() -> None:
    """Launch the MCP server in its own process (idempotent).

    The streamable-http session manager must own its event loop and lifespan;
    mounting it inside the OpenBB API — whose lifespan it cannot extend — does not
    survive a real deployment, so it never finishes starting. Running it as a
    subprocess gives it a clean uvicorn lifecycle. The port-in-use guard keeps this
    safe when the API runs multiple workers.
    """
    global _mcp_process  # noqa: PLW0603 - process-wide singleton
    import atexit
    import os
    import subprocess
    import sys

    if _mcp_process is not None and _mcp_process.poll() is None:
        return
    port = mcp_port()
    if _port_open(_MCP_HOST, port):
        return  # already serving (this run or another worker)
    try:
        # Hand the child the parent's import paths so it can find the package even
        # in a dev checkout where it is path-injected rather than pip-installed.
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
        _mcp_process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "openbb_yfinance.utils.mcp_app",
                "--host",
                _MCP_HOST,
                "--port",
                str(port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        atexit.register(stop_mcp_subprocess)
    except Exception:
        _mcp_process = None


def stop_mcp_subprocess() -> None:
    """Terminate the MCP subprocess if this process started it."""
    global _mcp_process  # noqa: PLW0603 - process-wide singleton
    if _mcp_process is not None and _mcp_process.poll() is None:
        _mcp_process.terminate()
    _mcp_process = None


_FORWARD_REQ_HEADERS = {
    "accept",
    "content-type",
    "mcp-session-id",
    "mcp-protocol-version",
}
_DROP_RESP_HEADERS = {
    "content-length",
    "transfer-encoding",
    "connection",
    "content-encoding",
}


async def _await_ready(timeout: float = 10.0) -> bool:
    """Poll until the MCP subprocess is accepting connections."""
    import asyncio

    for _ in range(max(1, int(timeout / 0.2))):
        if _port_open(_MCP_HOST, mcp_port()):
            return True
        await asyncio.sleep(0.2)
    return False


async def _extract_mcp_request(request: Request) -> dict:
    """Pull plain values out of the request.

    The OpenBB router wraps endpoints as commands and deep-copies their kwargs;
    a starlette ``Request`` cannot be deep-copied (it recurses), so the proxy
    takes this plain dict via a dependency instead of the ``Request`` itself.
    """
    return {
        "method": request.method,
        "body": await request.body(),
        "headers": {
            k: v
            for k, v in request.headers.items()
            if k.lower() in _FORWARD_REQ_HEADERS
        },
        "query": dict(request.query_params),
    }


async def mcp_reverse_proxy(data: dict = Depends(_extract_mcp_request)) -> Any:
    """Proxy an MCP request to the local subprocess, streaming the response.

    Lets the Workspace connect at the OpenBB API's own host/port — the subprocess
    is an internal detail — while the subprocess still owns the streamable-http
    lifecycle that the in-process mount could not start. POST replies and the GET
    SSE stream are both forwarded; the session-id header is exposed so the browser
    client can carry the session.
    """
    import asyncio

    import aiohttp
    from starlette.responses import JSONResponse, StreamingResponse

    ensure_mcp_subprocess()
    if not await _await_ready():
        return JSONResponse({"error": "MCP server failed to start"}, status_code=503)

    session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=None)
    )
    try:
        upstream = await session.request(
            data["method"],
            mcp_server_url(),
            headers=data["headers"],
            data=data["body"] or None,
            params=data["query"],
        )
    except aiohttp.ClientError as exc:
        await session.close()
        return JSONResponse({"error": f"MCP proxy error: {exc}"}, status_code=502)

    out_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in _DROP_RESP_HEADERS
    }
    out_headers["access-control-expose-headers"] = "mcp-session-id, Mcp-Session-Id"

    async def _stream() -> Any:
        try:
            async for chunk in upstream.content.iter_any():
                yield chunk
        except (asyncio.CancelledError, asyncio.TimeoutError, aiohttp.ClientError):
            return
        finally:
            upstream.release()
            await session.close()

    return StreamingResponse(
        _stream(), status_code=upstream.status, headers=out_headers
    )


def _serve(host: str, port: int) -> None:
    """Run the FastMCP streamable-http server — the subprocess entry point."""
    import uvicorn
    from starlette.middleware.cors import CORSMiddleware

    mcp = _build_mcp_server()
    app = mcp.http_app(path=_MCP_PATH, json_response=True, transport="streamable-http")
    # The Workspace connects from the browser cross-origin; allow it and expose the
    # session-id header so the JS client can carry the session across requests.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id", "Mcp-Session-Id"],
    )
    _exit_when_orphaned()
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _exit_when_orphaned() -> None:
    """Exit if the parent API process goes away.

    The launcher cannot fire ``atexit`` when uvicorn SIGKILLs its workers on a
    reload, which would otherwise leave this server running forever. Polling the
    parent pid lets the subprocess clean itself up so reloads never accumulate
    abandoned MCP servers.
    """
    import os
    import threading
    import time

    parent = os.getppid()

    def _watch() -> None:
        while True:
            time.sleep(2)
            if os.getppid() != parent:  # reparented → the launcher died
                os._exit(0)

    threading.Thread(target=_watch, daemon=True).start()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=_MCP_HOST)
    parser.add_argument("--port", type=int, default=mcp_port())
    args = parser.parse_args()
    _serve(args.host, args.port)
