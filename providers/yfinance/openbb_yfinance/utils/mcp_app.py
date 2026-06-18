"""Yahoo Finance MCP server, mounted at ``/yfinance/mcp``."""

from typing import Any


def _build_mcp_server() -> Any:
    """Build the FastMCP server and register the Yahoo Finance tools."""
    from fastmcp import FastMCP

    mcp: Any = FastMCP(
        name="OpenBB Yahoo Finance",
        instructions=(
            "Tools for Yahoo Finance market data: symbol search, price history,"
            " quotes and company profiles. Use them to answer questions about the"
            " symbol shown on the TradingView chart and to look up new symbols."
        ),
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

    return mcp


class _LazyLifespanASGI:
    """Wrap an ASGI app and start its lifespan on first request."""

    def __init__(self, app: Any) -> None:
        import asyncio

        self._app = app
        self._ready = asyncio.Event()
        self._task: Any = None
        self._lock = asyncio.Lock()

    async def _runner(self) -> None:
        import asyncio

        async with self._app.lifespan(self._app):
            self._ready.set()
            await asyncio.Event().wait()

    async def _ensure(self) -> None:
        import asyncio

        if self._ready.is_set():
            return
        async with self._lock:
            if self._task is None:
                self._task = asyncio.create_task(self._runner())
        await self._ready.wait()

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            await self._ensure()
        await self._app(scope, receive, send)


def get_mcp_asgi_app() -> Any:
    """Return the Yahoo Finance MCP ASGI app, or None if unavailable."""
    try:
        mcp = _build_mcp_server()
        http_app = mcp.http_app(
            path="/",
            stateless_http=True,
            json_response=True,
            transport="streamable-http",
        )
        return _LazyLifespanASGI(http_app)
    except Exception:
        return None


def make_asgi_proxy(asgi_app: Any) -> Any:
    """Build a POST endpoint that proxies a JSON-RPC request to *asgi_app*."""
    from fastapi import Depends
    from starlette.requests import Request
    from starlette.responses import Response

    async def _extract(request: Request) -> dict:
        """Pull the plain body + headers out of the request."""
        return {
            "body": await request.body(),
            "headers": [
                (k, v)
                for k, v in request.scope.get("headers", [])
                if k.lower()
                in (
                    b"accept",
                    b"content-type",
                    b"mcp-session-id",
                    b"mcp-protocol-version",
                )
            ],
        }

    async def endpoint(data: dict = Depends(_extract)) -> Response:
        headers = data["headers"] or [
            (b"accept", b"application/json, text/event-stream"),
            (b"content-type", b"application/json"),
        ]
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": headers,
            "server": ("127.0.0.1", 80),
            "client": ("127.0.0.1", 0),
        }

        async def receive() -> dict:
            return {"type": "http.request", "body": data["body"], "more_body": False}

        messages: list = []

        async def send(message: dict) -> None:
            messages.append(message)

        await asgi_app(scope, receive, send)

        status = 200
        resp_headers: list = []
        out = b""
        for message in messages:
            if message["type"] == "http.response.start":
                status = message["status"]
                resp_headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                out += message.get("body", b"")

        clean = {
            k.decode(): v.decode()
            for k, v in resp_headers
            if k.lower() not in (b"content-length", b"transfer-encoding")
        }
        return Response(content=out, status_code=status, headers=clean)

    return endpoint
