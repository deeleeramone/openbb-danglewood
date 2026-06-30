"""Shared options-chain loader and cache for the option views.

A symbol's chain is fetched and parsed once, then every view reads the cached
``OptionsChainsData`` object so the charts never refetch.
"""

from __future__ import annotations

from typing import Any

LOADED_SYMBOLS: dict[str, Any] = {}


async def load_symbol(symbol: str, update: bool = False) -> Any:
    """Return the cached ``OptionsChainsData`` for a symbol, loading it once.

    Raises ``OpenBBError`` (surfaced by the API as a proper HTTP error) when the
    ticker has no options chain.
    """
    from openbb_core.app.model.abstract.error import OpenBBError
    from openbb_core.provider.utils.errors import EmptyDataError

    symbol = symbol.upper()
    if symbol in LOADED_SYMBOLS and not update:
        return LOADED_SYMBOLS[symbol]

    from openbb_yfinance.models.options_chains import YFinanceOptionsChainsFetcher

    try:
        data = await YFinanceOptionsChainsFetcher.fetch_data({"symbol": symbol}, {})
    except (OpenBBError, EmptyDataError) as exc:
        raise OpenBBError(f"No options available for {symbol}.") from exc

    results = data.result if hasattr(data, "result") else data
    if results is None or not getattr(results, "expirations", None):
        raise OpenBBError(f"No options available for {symbol}.")

    LOADED_SYMBOLS[symbol] = results
    return results


def get_expirations(symbol: str) -> list[dict]:
    """Return the cached expiration choices for a symbol's dropdown."""
    results = LOADED_SYMBOLS.get(symbol.upper())
    if results is None:
        return []
    return [{"label": e, "value": e} for e in results.expirations]


def get_strikes(symbol: str) -> list[dict]:
    """Return the cached strike choices for a symbol's dropdown."""
    results = LOADED_SYMBOLS.get(symbol.upper())
    if results is None:
        return []
    underlying = results.underlying_price[0] if results.underlying_price else None
    choices: list[dict] = [{"label": "Nearest OTM", "value": None}]
    for strike in results.strikes:
        label = f"${str(strike).replace('.0', '')}"
        extra = (
            {"rightOfDescription": f"Underlying: ${underlying}"} if underlying else {}
        )
        choices.append({"label": label, "value": strike, "extraInfo": extra})
    return choices
