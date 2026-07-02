"""HKEX Equity Search fetcher (EquitySearch standard model)."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_search import (
    EquitySearchData,
    EquitySearchQueryParams,
)
from pydantic import Field

from openbb_hkex.models._reference import (
    HkexEquityReference,
    extract_reference,
)
from openbb_hkex.utils.client import call_widget, to_hk_symbol

SecurityType = Literal["EQTY", "ETP", "REIT", "DW", "CBBC", "INLINE", "BOND"]
SECURITY_TYPE_CHOICES: list[str] = list(SecurityType.__args__)  # type: ignore[attr-defined]

_MAX_ENRICH_CONCURRENCY = 8


class HkexEquitySearchQueryParams(EquitySearchQueryParams):
    """HKEX Equity Search query."""

    limit: int = Field(default=20, description="Max rows to fetch from the source.")
    type: SecurityType | None = Field(
        default=None,
        description="Filter by classification (EQTY / ETP / REIT / DW / CBBC / INLINE / BOND).",
        json_schema_extra={"choices": SECURITY_TYPE_CHOICES},
    )
    enrich: bool = Field(
        default=True,
        description="Enrich each match with full reference metadata "
        "(identifiers, classification, listing, fundamentals). Disable for a "
        "faster code/name-only lookup.",
    )


class _SearchStandard(EquitySearchData):
    symbol: str = Field(
        description="HKEX security code.",
        json_schema_extra={
            "x-widget_config": {
                "renderFn": "cellOnClick",
                "renderFnParams": {
                    "actionType": "groupBy",
                    "groupBy": {"paramName": "symbol", "valueField": "symbol"},
                },
            }
        },
    )
    type: str | None = Field(default=None, description="Security classification.")


class HkexEquitySearchData(HkexEquityReference, _SearchStandard):
    """HKEX Equity Search row."""


class HkexEquitySearchFetcher(
    Fetcher[HkexEquitySearchQueryParams, list[HkexEquitySearchData]]
):
    """HKEX Equity Search fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexEquitySearchQueryParams:
        """Transform the query parameters."""
        return HkexEquitySearchQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexEquitySearchQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        data = await call_widget(
            "getstocksearch", keyword=query.query or "", pre=query.limit
        )
        hits = data.get("stocklist", []) or []

        wanted = query.type.upper() if query.type else None
        hits = [
            h for h in hits if not wanted or (h.get("type") or "").upper() == wanted
        ]

        if not query.enrich:
            return hits

        sem = asyncio.Semaphore(_MAX_ENRICH_CONCURRENCY)

        async def _enrich(hit: dict) -> dict:
            merged = {
                "_sym": hit.get("sym"),
                "_nm": hit.get("nm"),
                "_type": (hit.get("type") or "").upper() or None,
            }
            async with sem:
                try:
                    resp = await call_widget(
                        "getequityquote", sym=to_hk_symbol(str(hit.get("sym") or ""))
                    )
                    quote = resp.get("quote") or {}
                except Exception:  # noqa: BLE001 — degrade to code/name on any error
                    quote = {}
            merged.update(quote)
            return merged

        return await asyncio.gather(*[_enrich(h) for h in hits])

    @staticmethod
    def transform_data(
        query: HkexEquitySearchQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexEquitySearchData]:
        """Transform the raw data into the model."""
        out: list[HkexEquitySearchData] = []
        for r in data:
            sym = str(r.get("_sym") or r.get("sym") or "")
            row: dict[str, Any] = {
                "symbol": sym.zfill(5),
                "name": r.get("nm") or r.get("nm_s") or r.get("_nm"),
                "type": r.get("_type") or (r.get("type") or "").upper() or None,
            }
            row.update(extract_reference(r))
            out.append(HkexEquitySearchData(**row))
        return out
