"""Yahoo Finance MCP server: a streamable-http subprocess, reverse-proxied
through the OpenBB API so the Workspace connects on the API's own host/port.
"""

from typing import Any

from fastapi import Depends
from starlette.requests import Request


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
            " issuer/style universe with the screener."
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
        rows = await YFinanceEquityScreenerFetcher.fetch_data(params, {})
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
    import aiohttp
    from starlette.responses import JSONResponse, StreamingResponse

    ensure_mcp_subprocess()
    if not await _await_ready():
        return JSONResponse({"error": "MCP server failed to start"}, status_code=503)

    session = aiohttp.ClientSession()
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
