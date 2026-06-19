"""Mount PyWry's inline widget server onto the OpenBB API application.

PyWry's TradingView datafeed runs over a WebSocket the browser opens at
``ws://<page-origin>/ws/<widget_id>``. Serving that endpoint from the OpenBB API
app itself — rather than a second uvicorn on another port — keeps it same-origin
with the iframe page and avoids the port-bind failures of a parallel server.
"""

import threading

_mounted = False
_lock = threading.Lock()


def ensure_pywry_mounted() -> None:
    """Attach PyWry's inline ``/ws`` and widget-lifecycle routes to the OpenBB app.

    Idempotent. Adds the routes to ``openbb_core.api.rest_api.app`` (the app the
    OpenBB API actually serves), starts the callback processor that handles
    inbound datafeed messages, and marks the inline server as running so
    ``InlineWidget`` never tries to launch its own uvicorn.
    """
    global _mounted  # noqa: PLW0603 - process-wide one-time mount
    if _mounted:
        return
    with _lock:
        if _mounted:
            return
        from openbb_core.api.rest_api import app as core_app
        from pywry import inline

        inline.get_server_app()
        pywry_app = inline._state.app
        if pywry_app is not None:
            existing = {getattr(route, "path", "") for route in core_app.router.routes}
            wanted = ("/ws/", "/register_widget", "/disconnect/")
            for route in pywry_app.routes:
                path = getattr(route, "path", "")
                if path.startswith(wanted) and path not in existing:
                    core_app.router.routes.append(route)

        threading.Thread(target=inline._process_callbacks, daemon=True).start()
        keeper = threading.Thread(target=threading.Event().wait, daemon=True)
        keeper.start()
        inline._state.server_thread = keeper
        _mounted = True


def bind_loop() -> None:
    """Bind PyWry's inline event loop to the running OpenBB API loop."""
    import asyncio

    from pywry import inline

    if inline._state.server_loop is None:
        inline._state.server_loop = asyncio.get_running_loop()
