"""HKEX Equity Quote fetcher (EquityQuote standard model)."""

from __future__ import annotations

import asyncio
from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_quote import (
    EquityQuoteData,
    EquityQuoteQueryParams,
)
from pydantic import Field

from openbb_hkex.utils.client import (
    call_widget,
    parse_int,
    parse_num,
    symbol_widget_config,
    to_hk_symbol,
)


class HkexEquityQuoteQueryParams(EquityQuoteQueryParams):
    """HKEX Equity Quote query.

    `symbol` accepts any of: `5`, `00005`, `0005.HK`, `00005.HK`. Multiple
    symbols may be passed as a comma-separated string.
    """

    symbol: str = Field(
        description="HKEX stock code(s). Multiple comma-separated codes allowed.",
        json_schema_extra=symbol_widget_config(multi=True),
    )


class HkexEquityQuoteData(EquityQuoteData):
    """HKEX Equity Quote data."""

    eps: float | None = Field(default=None, description="Earnings per share (TTM).")
    pe_ratio: float | None = Field(default=None, description="Price-to-earnings ratio.")
    dividend_yield: float | None = Field(
        default=None, description="Annualized dividend yield as a percentage."
    )
    amount_outstanding: float | None = Field(
        default=None, description="Total shares outstanding."
    )
    lot_size: int | None = Field(default=None, description="Trading board lot.")
    listing_date: str | None = Field(
        default=None, description="Date of listing on HKEX."
    )
    primary_exchange: str | None = Field(
        default=None, description="Primary listing venue."
    )
    last_update: str | None = Field(
        default=None, description="Source-reported quote timestamp."
    )


class HkexEquityQuoteFetcher(
    Fetcher[HkexEquityQuoteQueryParams, list[HkexEquityQuoteData]]
):
    """HKEX Equity Quote fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexEquityQuoteQueryParams:
        """Transform the query parameters."""
        return HkexEquityQuoteQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexEquityQuoteQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        codes = [to_hk_symbol(s) for s in symbols]
        results = await asyncio.gather(
            *(call_widget("getequityquote", sym=c) for c in codes),
            return_exceptions=True,
        )
        out: list[dict] = []
        for code, r in zip(codes, results):
            if isinstance(r, BaseException):
                continue
            q = r.get("quote") or {}
            if q:
                q["_input_symbol"] = code
                out.append(q)
        return out

    @staticmethod
    def transform_data(
        query: HkexEquityQuoteQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexEquityQuoteData]:
        """Transform the raw data into the model."""
        rows: list[HkexEquityQuoteData] = []
        for q in data:
            last = parse_num(q.get("ls"))
            prev = parse_num(q.get("hc"))
            change = parse_num(q.get("nc"))
            chg_pct = parse_num(q.get("pc"))
            rows.append(
                HkexEquityQuoteData(
                    symbol=q.get("ric") or q.get("_input_symbol", ""),
                    name=q.get("nm") or q.get("nm_l") or q.get("nm_s"),
                    exchange="HKEX",
                    asset_type=q.get("product_subtype") or "equity",
                    bid=parse_num(q.get("bd")),
                    ask=parse_num(q.get("as")),
                    last_price=last,
                    open=parse_num(q.get("op")),
                    high=parse_num(q.get("hi")),
                    low=parse_num(q.get("lo")),
                    prev_close=prev,
                    change=change,
                    change_percent=(chg_pct / 100) if chg_pct is not None else None,
                    year_high=parse_num(q.get("y_hi")) or parse_num(q.get("hi_5y")),
                    year_low=parse_num(q.get("y_lo")) or parse_num(q.get("lo_5y")),
                    eps=parse_num(q.get("eps")),
                    pe_ratio=parse_num(q.get("pe")),
                    dividend_yield=parse_num(q.get("div_yield")),
                    amount_outstanding=parse_num(q.get("amt_os")),
                    lot_size=parse_int(q.get("lot")),
                    listing_date=q.get("listing_date"),
                    primary_exchange=q.get("primaryexch"),
                    last_update=q.get("db_updatetime"),
                )
            )
        return rows
