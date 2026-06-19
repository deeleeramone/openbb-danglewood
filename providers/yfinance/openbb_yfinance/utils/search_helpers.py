"""Yahoo Finance symbol search helpers (yfinance Lookup)."""

from typing import Any

LOOKUP_METHODS: dict[str, str] = {
    "equity": "get_stock",
    "etf": "get_etf",
    "index": "get_index",
    "mutualfund": "get_mutualfund",
    "cryptocurrency": "get_cryptocurrency",
    "crypto": "get_cryptocurrency",
    "currency": "get_currency",
    "future": "get_future",
}

EXCHANGE_LABELS: dict[str, str] = {
    "NMS": "NASDAQ",
    "NGM": "NASDAQ",
    "NCM": "NASDAQ",
    "NASDAQGS": "NASDAQ",
    "NASDAQGM": "NASDAQ",
    "NASDAQCM": "NASDAQ",
    "NYQ": "NYSE",
    "NYSE": "NYSE",
    "NYSEARCA": "NYSE ARCA",
    "PCX": "NYSE ARCA",
    "NYSEAMERICAN": "NYSE AMEX",
    "ASE": "NYSE AMEX",
    "BTS": "CBOE BZX",
    "CBO": "CBOE",
    "OPR": "OTC",
    "PNK": "OTC Markets",
    "LSE": "LSE",
    "TSE": "TSE",
    "TSX": "TSX",
}


def yf_symbol_search(
    query: str,
    limit: int = 30,
    asset_type: str = "",
) -> list[dict[str, Any]]:
    """Search Yahoo Finance for symbols matching a query.

    Uses the yfinance ``Lookup`` API. An empty ``asset_type`` queries all types.

    Parameters
    ----------
    query : str
        The search term.
    limit : int
        Maximum number of results to return.
    asset_type : str
        Restrict to a single asset type. Empty queries all types.

    Returns
    -------
    list[dict[str, Any]]
        Normalized result documents.
    """
    from pandas import isna

    from yfinance import Lookup

    method_name = "get_all"
    if asset_type:
        method_name = LOOKUP_METHODS.get(asset_type.lower(), "get_all")

    try:
        frame = getattr(Lookup(query), method_name)(count=max(limit * 2, 50))
    except Exception:
        return []
    if frame is None or frame.empty:
        return []

    def _clean(value: Any) -> str:
        return "" if value is None or isna(value) else str(value)

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for symbol, row in frame.iterrows():
        sym = _clean(symbol)
        if not sym or sym in seen:
            continue
        seen.add(sym)
        short = _clean(row.get("shortName"))
        exch_code = _clean(row.get("exchange")).upper()
        items.append(
            {
                "symbol": sym,
                "name": short,
                "description": short,
                "exchange": EXCHANGE_LABELS.get(exch_code, _clean(row.get("exchange"))),
                "asset_type": (_clean(row.get("quoteType")) or "equity").lower(),
            }
        )
        if len(items) >= limit:
            break

    return items
