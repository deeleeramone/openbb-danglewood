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

        chart_ids = getattr(app, "_obb_chart_ids_by_widget", {}) or {}
        app_chart_id = str(getattr(app, "_obb_chart_id", "") or "")
        inline_widgets = getattr(app, "_inline_widgets", {}) or {}
        app_label = str(getattr(app, "label", "") or "")
        # _show() records every chart in _obb_chart_ids_by_widget for browser
        # (Workspace iframe) and inline widgets alike; _inline_widgets is only
        # populated for inline/Jupyter, so a browser widget would otherwise be
        # invisible here. Fall back to the inline registry / app label.
        labels = list(chart_ids) or list(inline_widgets) or (
            [app_label] if app_label else []
        )
        for label in labels:
            chart_id = str(chart_ids.get(str(label)) or app_chart_id or "")
            targets.append(
                {
                    "instance_index": index,
                    "widget_id": chart_id or str(label),
                    "chart_id": chart_id,
                    "app_label": app_label or str(label),
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
        chart_ids = getattr(app, "_obb_chart_ids_by_widget", {}) or {}
        app_chart_id = str(getattr(app, "_obb_chart_id", "") or "")
        if widget_id:
            target = inline_widgets.get(widget_id)
            if target is not None:
                return target, widget_id
            # This chart, addressed by chart id, widget label, or app label. A
            # browser (Workspace iframe) chart is emitted to via the app itself.
            if (
                widget_id == app_chart_id
                or widget_id in chart_ids
                or widget_id in chart_ids.values()
                or getattr(app, "label", "") == widget_id
            ):
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
            if widget_id == app_chart_id or widget_id in chart_ids.values():
                return widget_id
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
    data = data or {}
    # The client dispatches the event by widget_id; for a tvchart the routing id
    # is the chart id. Carry it as the widget_id when the caller didn't give one
    # (resolves only where the live chart is visible — the chart's process).
    if not widget_id and event_type.startswith("tvchart:"):
        widget_id = str(data.get("chartId") or _latest_tvchart_chart_id())
    return {
        "event_type": event_type,
        "widget_id": widget_id,
        "data": data,
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


def _api_tvchart_targets_url() -> str:
    return _api_tvchart_bridge_url().rsplit("/emit", 1)[0] + "/targets"


def _list_targets_via_bridge() -> list[dict[str, Any]]:
    """List live targets from the chart's process (the API server) over HTTP.

    tvchart tools run in the MCP subprocess, whose ``_LIVE_CHARTS`` is always
    empty; the charts live in the API process, so ask it directly.
    """
    import json
    import urllib.error
    import urllib.request

    req = urllib.request.Request(_api_tvchart_targets_url(), method="GET")  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=2.5) as resp:  # noqa: S310
            result = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError):
        return []
    if isinstance(result, dict) and isinstance(result.get("targets"), list):
        return result["targets"]
    return []


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

    # Prefer the bridge's event: it is built in the chart's process, so it
    # carries the resolved chart id as widget_id. Only rebuild here (MCP process,
    # where the chart isn't visible) as a last resort.
    bridge_error = ""
    bridged_event = None
    if isinstance(bridged, dict):
        bridge_error = str(bridged.get("error") or "")
        bridged_event = bridged.get("event")
    payload = bridged_event or _tvchart_event_payload(event_type, data, widget_id)
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


async def _extract_emit_payload(request: Request) -> dict:
    """Parse the emit body into a plain dict.

    The OpenBB router wraps endpoints as commands and deep-copies their kwargs;
    a raw starlette ``Request`` recurses under deepcopy (RecursionError → 500),
    so the JSON body is pulled out via this dependency (like the reverse proxy)
    rather than taken as an endpoint argument.
    """
    import json

    try:
        payload = json.loads(await request.body() or b"{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


async def mcp_tvchart_emit(
    payload: dict = Depends(_extract_emit_payload),
) -> Any:
    """Handle the bridge HTTP request that emits a tvchart event."""
    from starlette.responses import JSONResponse

    if not payload:
        return JSONResponse(
            {"ok": False, "error": "Invalid or empty JSON payload"}, status_code=400
        )
    try:
        result = mcp_tvchart_emit_payload(payload)
    except Exception as exc:  # noqa: BLE001 - never 500; the resolved chart id still helps the client dispatch
        data = payload.get("data")
        result = {
            "ok": True,
            "dispatched": False,
            "event": _tvchart_event_payload(
                str(payload.get("event_type") or ""),
                data if isinstance(data, dict) else {},
                str(payload.get("widget_id") or ""),
            ),
            "error": f"emit failed: {exc}",
        }
    status = 200 if result.get("ok") else 400
    return JSONResponse(result, status_code=status)


async def mcp_tvchart_targets() -> Any:
    """Bridge endpoint (runs in the chart's process): list live tvchart targets."""
    from starlette.responses import JSONResponse

    targets = _list_live_tvchart_targets()
    return JSONResponse({"ok": True, "count": len(targets), "targets": targets})


def _list_live_rrg_targets() -> list[dict[str, Any]]:
    try:
        from openbb_yfinance.utils import relative_rotation
    except Exception:
        return []

    targets: list[dict[str, Any]] = []
    for index, item in enumerate(getattr(relative_rotation, "_LIVE_RRG", [])):
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        meta = item[1] if isinstance(item[1], dict) else {}
        widget_id = str(meta.get("widget_id") or "")
        if not widget_id:
            continue
        targets.append({"instance_index": index, "widget_id": widget_id})
    return targets


def _latest_rrg_target(widget_id: str | None = None) -> tuple[Any | None, str | None]:
    try:
        from openbb_yfinance.utils import relative_rotation
    except Exception:
        return None, None

    for item in reversed(getattr(relative_rotation, "_LIVE_RRG", [])):
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        widget = item[0]
        meta = item[1] if isinstance(item[1], dict) else {}
        wid = str(meta.get("widget_id") or "")
        if not wid:
            continue
        if widget_id:
            if wid == widget_id:
                return widget, wid
            continue
        return widget, wid
    return None, None


def _rrg_event_payload(
    event_type: str,
    data: dict[str, Any] | None = None,
    widget_id: str | None = None,
) -> dict[str, Any]:
    if not widget_id:
        _target, widget_id = _latest_rrg_target()
    return {"event_type": event_type, "widget_id": widget_id, "data": data or {}}


def _emit_rrg_to_live_target(
    event_type: str,
    data: dict[str, Any] | None = None,
    widget_id: str | None = None,
) -> dict[str, Any]:
    target, resolved_widget_id = _latest_rrg_target(widget_id)
    payload = _rrg_event_payload(event_type, data or {}, widget_id or resolved_widget_id)
    if target is None:
        return {
            "ok": True,
            "dispatched": False,
            "event": payload,
            "note": "No live RRG target was available in this process.",
        }
    if resolved_widget_id and not payload["widget_id"]:
        payload["widget_id"] = resolved_widget_id
    try:
        target.emit(payload["event_type"], payload["data"])
    except Exception as exc:
        return {"ok": False, "dispatched": False, "event": payload, "error": str(exc)}
    return {"ok": True, "dispatched": True, "event": payload}


def _api_rrg_bridge_url() -> str:
    import os

    public_mcp = os.environ.get("OPENBB_YFINANCE_MCP_PUBLIC_URL", "").strip()
    if public_mcp:
        return f"{public_mcp.rstrip('/')}/rrg/emit"
    host = os.environ.get("OPENBB_YFINANCE_MCP_PUBLIC_HOST", "127.0.0.1")
    port = os.environ.get("OPENBB_API_PORT", "6900")
    return f"http://{host}:{port}{_api_prefix()}/yfinance/mcp/rrg/emit"


def _api_rrg_targets_url() -> str:
    return _api_rrg_bridge_url().rsplit("/emit", 1)[0] + "/targets"


def _list_rrg_targets_via_bridge() -> list[dict[str, Any]]:
    import json
    import urllib.error
    import urllib.request

    req = urllib.request.Request(_api_rrg_targets_url(), method="GET")  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=2.5) as resp:  # noqa: S310
            result = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError):
        return []
    if isinstance(result, dict) and isinstance(result.get("targets"), list):
        return result["targets"]
    return []


def _emit_rrg_via_api_bridge(
    event_type: str,
    data: dict[str, Any] | None = None,
    widget_id: str | None = None,
) -> dict[str, Any]:
    import json
    import urllib.error
    import urllib.request

    payload = _rrg_event_payload(event_type, data or {}, widget_id)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310
        _api_rrg_bridge_url(),
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


def _emit_rrg_or_envelope(
    event_type: str,
    data: dict[str, Any] | None = None,
    widget_id: str | None = None,
) -> dict[str, Any]:
    local = _emit_rrg_to_live_target(event_type, data, widget_id)
    if local.get("dispatched"):
        return local

    bridged = _emit_rrg_via_api_bridge(event_type, data, widget_id)
    if isinstance(bridged, dict) and bridged.get("dispatched"):
        return bridged

    bridge_error = ""
    bridged_event = None
    if isinstance(bridged, dict):
        bridge_error = str(bridged.get("error") or "")
        bridged_event = bridged.get("event")
    payload = bridged_event or _rrg_event_payload(event_type, data, widget_id)
    note = "No live RRG target was available; returning event envelope for client dispatch."
    if bridge_error:
        note = f"{note} Bridge error: {bridge_error}"
    return {"ok": True, "dispatched": False, "event": payload, "note": note}


def mcp_rrg_emit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an RRG emit payload and dispatch it to the live widget."""
    event_type = str(payload.get("event_type") or "")
    data = payload.get("data")
    widget_id = payload.get("widget_id") or None

    if not event_type.startswith("rrg:"):
        return {
            "ok": False,
            "dispatched": False,
            "event": _rrg_event_payload(
                event_type, data if isinstance(data, dict) else {}, widget_id
            ),
            "error": "event_type must start with 'rrg:'",
        }

    return _emit_rrg_to_live_target(
        event_type, data if isinstance(data, dict) else {}, widget_id
    )


async def mcp_rrg_emit(payload: dict = Depends(_extract_emit_payload)) -> Any:
    """Handle the bridge HTTP request that emits an RRG event."""
    from starlette.responses import JSONResponse

    if not payload:
        return JSONResponse(
            {"ok": False, "error": "Invalid or empty JSON payload"}, status_code=400
        )
    try:
        result = mcp_rrg_emit_payload(payload)
    except Exception as exc:  # noqa: BLE001
        data = payload.get("data")
        result = {
            "ok": True,
            "dispatched": False,
            "event": _rrg_event_payload(
                str(payload.get("event_type") or ""),
                data if isinstance(data, dict) else {},
                payload.get("widget_id") or None,
            ),
            "error": f"emit failed: {exc}",
        }
    status = 200 if result.get("ok") else 400
    return JSONResponse(result, status_code=status)


async def mcp_rrg_targets() -> Any:
    """Bridge endpoint (runs in the API process): list live RRG targets."""
    from starlette.responses import JSONResponse

    targets = _list_live_rrg_targets()
    return JSONResponse({"ok": True, "count": len(targets), "targets": targets})


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
            " tvchart:* events with payloads aligned to PyWry's event system. Relative"
            " Rotation Graph (rrg_*) tools drive the RRG widget's sidebar (symbols,"
            " benchmark, study, momentum periods, tails) and recompute the graph."
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
        # Local list is empty in the MCP subprocess; the charts live in the API
        # process, so ask it over the bridge.
        targets = _list_live_tvchart_targets() or _list_targets_via_bridge()
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
        return [r.model_dump(exclude_none=True) for r in rows]

    @mcp.tool
    def rrg_list_targets() -> dict:
        """List active Relative Rotation Graph widgets to address by widget_id.

        Example response:
        ``{"ok": True, "count": 1, "targets": [{"instance_index": 0, "widget_id": "rrg_ab12cd34ef56"}]}``
        """
        targets = _list_live_rrg_targets() or _list_rrg_targets_via_bridge()
        return {"ok": True, "count": len(targets), "targets": targets}

    @mcp.tool
    def rrg_set_inputs(
        symbols: list[str] | str | None = None,
        benchmark: str | None = None,
        study: str | None = None,
        date: str | None = None,
        long_period: int | None = None,
        short_period: int | None = None,
        window: int | None = None,
        trading_periods: int | None = None,
        show_tails: bool | None = None,
        tail_periods: int | None = None,
        tail_interval: str | None = None,
        recompute: bool = True,
        widget_id: str | None = None,
    ) -> dict:
        """Set the RRG sidebar inputs and (by default) recompute the graph.

        Only the provided fields change. ``symbols`` accepts a list or a
        comma-separated string; ``study`` is price/volume/volatility;
        ``tail_interval`` is week/month. Leave ``widget_id`` unset to target the
        most-recent live RRG widget.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "rrg:set-inputs", "widget_id": "rrg_ab12cd34ef56", "data": {"study": "volatility", "recompute": True}}}``
        """
        data: dict[str, Any] = {}
        if symbols is not None:
            data["symbols"] = symbols
        for key, value in (
            ("benchmark", benchmark),
            ("study", study),
            ("date", date),
            ("long_period", long_period),
            ("short_period", short_period),
            ("window", window),
            ("trading_periods", trading_periods),
            ("show_tails", show_tails),
            ("tail_periods", tail_periods),
            ("tail_interval", tail_interval),
        ):
            if value is not None:
                data[key] = value
        data["recompute"] = bool(recompute)
        return _emit_rrg_or_envelope("rrg:set-inputs", data, widget_id)

    @mcp.tool
    def rrg_recompute(widget_id: str | None = None) -> dict:
        """Recompute the RRG with the widget's current sidebar inputs.

        Emits ``rrg:recompute``. Leave ``widget_id`` unset to target the
        most-recent live RRG widget.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "rrg:recompute", "widget_id": "rrg_ab12cd34ef56", "data": {}}}``
        """
        return _emit_rrg_or_envelope("rrg:recompute", {}, widget_id)

    @mcp.tool
    def rrg_send_event(
        event_type: str, data: dict | None = None, widget_id: str | None = None
    ) -> dict:
        """Emit an arbitrary ``rrg:*`` event to a Relative Rotation widget.

        ``event_type`` must start with ``rrg:``. Leave ``widget_id`` unset to
        target the most-recent live RRG widget.

        Example response:
        ``{"ok": True, "dispatched": True, "event": {"event_type": "rrg:recompute", "widget_id": "rrg_ab12cd34ef56", "data": {}}}``
        """
        if not str(event_type).startswith("rrg:"):
            return {
                "ok": False,
                "dispatched": False,
                "event": _rrg_event_payload(
                    str(event_type), data if isinstance(data, dict) else {}, widget_id
                ),
                "error": "event_type must start with 'rrg:'",
            }
        return _emit_rrg_or_envelope(
            event_type, data if isinstance(data, dict) else {}, widget_id
        )

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
