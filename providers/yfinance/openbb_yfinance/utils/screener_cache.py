"""Fund-profile cache for the screener's fund issuer/style dimensions.

Yahoo's screener ``fundfamilyname``/``categoryname`` valid-values are stale (they
miss renames such as State Street and include fund companies with no ETFs), and
``screen`` validates against them. The research-hub ``visualization`` endpoint
returns the current family and category as columns of the result, so a short
crumb-authed, paginated sweep of a region (walked in net-asset order until the
distinct families/categories stop growing) yields them without any per-symbol
calls. This module caches those distinct values so the dropdowns and screening
use real, current names instead of yfinance's stale tables.
"""

from __future__ import annotations

import lzma
import re
from pathlib import Path
from typing import Any

_CACHE_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "screener_cache.json.xz"
)

_FUND_QUOTE_TYPES = {"etf": "ETF", "fund": "MUTUALFUND"}
_SORT_FIELD = "fundnetassets"
_VISUALIZATION_URL = "https://query1.finance.yahoo.com/v1/finance/visualization"
_INCLUDE_FIELDS = ["ticker", "fundfamilyname", "categoryname"]


def _cell(value: Any) -> Any:
    """Unwrap a visualization cell that may be a scalar or a ``{raw, fmt}`` dict."""
    if isinstance(value, dict):
        return value.get("raw", value.get("value", value.get("fmt")))
    return value


def _visualization_page(
    quote_type: str, offset: int, size: int
) -> tuple[list[dict], int | None]:
    """Fetch one research-hub page of (symbol, family, category) records."""
    from json import dumps

    from yfinance.data import YfData

    body = {
        "offset": int(offset),
        "size": int(size),
        "sortType": "DESC",
        "sortField": _SORT_FIELD,
        "includeFields": _INCLUDE_FIELDS,
        "query": {
            "operator": "and",
            "operands": [{"operator": "eq", "operands": ["region", "us"]}],
        },
        "quoteType": quote_type,
        "topOperator": "and",
    }
    response = YfData(session=None).post(
        _VISUALIZATION_URL,
        data=dumps(body, separators=(",", ":"), ensure_ascii=False),
        params={"lang": "en-US", "region": "US", "corsDomain": "finance.yahoo.com"},
    )
    response.raise_for_status()
    document = response.json()["finance"]["result"][0]["documents"][0]
    columns = [column.get("id") for column in document.get("columns", [])]
    total = document.get("total")
    records = []
    for row in document.get("rows", []):
        cells = row if isinstance(row, dict) else dict(zip(columns, row))
        records.append(
            {
                "symbol": _cell(cells.get("ticker")),
                "family": _cell(cells.get("fundfamilyname")),
                "category": _cell(cells.get("categoryname")),
            }
        )
    return records, total


_MAX_PAGES = 40


def _name_tokens(name: str) -> frozenset[str]:
    """Return the significant lower-case word tokens of a family name."""
    return frozenset(re.sub(r"[^a-z0-9 ]", " ", name.lower()).split())


def _dedupe_variants(counts: dict[str, int]) -> dict[str, int]:
    """Drop family names that are token-subset variants of a higher-count family.

    Yahoo carries data-entry variants of the same issuer — e.g. "SPDR State Street
    Investment Management" (1 fund) beside "State Street Investment Management"
    (175). Walking names from most to least covered and rejecting any whose token
    set is a subset/superset of an already-kept name collapses each issuer to its
    canonical label while leaving genuine single-fund issuers (e.g. "Akre") in
    place, since those share tokens with nothing larger.
    """
    kept: list[frozenset[str]] = []
    out: dict[str, int] = {}
    for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        tokens = _name_tokens(name)
        if not tokens:
            continue
        if any(tokens <= other or other <= tokens for other in kept):
            continue
        kept.append(tokens)
        out[name] = count
    return out


def build_asset_cache(asset_type: str, max_pages: int = _MAX_PAGES) -> dict[str, Any]:
    """Count funds per current family/category for an asset type.

    Pages are walked in net-asset order up to ``max_pages`` (or the region total,
    whichever comes first). Keeping the per-name counts lets the dropdowns drop the
    single-fund data-entry variants Yahoo carries — e.g. a stray "SPDR State
    Street Investment Management" beside the real "State Street Investment
    Management" — and label each family with its coverage.
    """
    quote_type = _FUND_QUOTE_TYPES[asset_type]
    families: dict[str, int] = {}
    categories: dict[str, int] = {}
    offset = 0
    page = 250
    total: int | None = None
    pages = 0
    while pages < max_pages:
        records, page_total = _visualization_page(quote_type, offset, page)
        if total is None:
            total = page_total
        if not records:
            break
        for record in records:
            family = record["family"]
            if family:
                families[family] = families.get(family, 0) + 1
            category = record["category"]
            if category:
                categories[category] = categories.get(category, 0) + 1
        offset += len(records)
        pages += 1
        if (total is not None and offset >= total) or len(records) < page:
            break
    return {"families": _dedupe_variants(families), "categories": categories}


def build_screener_cache(
    asset_types: tuple[str, ...] = ("etf", "fund"),
) -> dict[str, Any]:
    """Build and persist the fund-profile cache for the given asset types."""
    import json

    cache = {asset: build_asset_cache(asset) for asset in asset_types}
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with lzma.open(_CACHE_PATH, "wt", encoding="utf-8") as handle:
        json.dump(cache, handle, separators=(",", ":"))
    return cache


def load_screener_cache() -> dict[str, Any]:
    """Return the bundled fund-profile cache, or an empty dict when absent."""
    import json

    if not _CACHE_PATH.exists():
        return {}
    try:
        with lzma.open(_CACHE_PATH, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, lzma.LZMAError):
        return {}


def family_counts(asset_type: str) -> dict[str, int]:
    """Return the cached canonical ``{family: fund count}`` map for an asset type."""
    families = (load_screener_cache().get(asset_type) or {}).get("families") or {}
    if isinstance(families, dict):
        return families
    return {name: 1 for name in families}  # tolerate an older list-shaped cache


def fund_families(asset_type: str) -> list[str]:
    """Return the cached canonical fund families for an asset type, sorted."""
    return sorted(family_counts(asset_type))


def fund_categories(asset_type: str) -> list[str]:
    """Return the cached current fund categories for an asset type, sorted."""
    categories = (load_screener_cache().get(asset_type) or {}).get("categories") or {}
    return sorted(categories)
