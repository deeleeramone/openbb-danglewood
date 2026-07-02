"""HKEX Company Filings fetcher (CompanyFilings standard model).

Maps the hkexnews.hk title-search results to OpenBB's CompanyFilings schema.
Each filing PDF is one row; ``report_url`` points to the actual document.
"""

from __future__ import annotations

import asyncio
from datetime import (
    date as dateType,
    datetime,
)
from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.company_filings import (
    CompanyFilingsData,
    CompanyFilingsQueryParams,
)
from pydantic import Field

from openbb_hkex.utils.client import (
    disclosure_search_sync,
    find_stock_id,
    symbol_widget_config,
)

FormGroup = Literal[
    "all",
    "annual",
    "interim",
    "quarterly",
    "esg",
    "financials",
    "announcements",
    "circulars",
    "listing_docs",
    "monthly_returns",
    "proxy",
    "buyback",
    "constitutional",
    "takeovers",
    "debt",
    "etf_info",
]

_FORM_GROUP_CODES: dict[str, tuple[str | None, str | None]] = {
    "all": (None, None),
    "annual": ("40000", "40100"),
    "interim": ("40000", "40200"),
    "quarterly": ("40000", "40300"),
    "esg": ("40000", "40400"),
    "financials": ("40000", None),
    "announcements": ("10000", None),
    "circulars": ("20000", None),
    "listing_docs": ("30000", None),
    "monthly_returns": ("51500", None),
    "proxy": ("52000", None),
    "buyback": ("50000", None),
    "constitutional": ("54000", None),
    "takeovers": ("55000", None),
    "debt": ("70000", None),
    "etf_info": ("80000", None),
}


class HkexCompanyFilingsQueryParams(CompanyFilingsQueryParams):
    """HKEX Company Filings query."""

    symbol: str | None = Field(
        default=None,
        description="HKEX stock code.",
        json_schema_extra=symbol_widget_config(),
    )
    form_group: FormGroup = Field(
        default="all",
        description="Filing category. 'all' returns everything; the rest filter "
        "by HKEX disclosure taxonomy (annual = Annual Report, interim = "
        "Interim/Half-Year Report, esg = ESG Information, "
        "announcements = Announcements and Notices, etc.).",
    )
    start_date: dateType | None = Field(
        default=None,
        description="Filter for filings released on or after this date "
        "(default: 1999-04-01, the earliest hkexnews retains).",
    )
    end_date: dateType | None = Field(
        default=None,
        description="Filter for filings released on or before this date (default: today).",
    )
    title: str | None = Field(
        default=None, description="Keyword filter on the filing title."
    )
    limit: int | None = Field(
        default=None,
        description="Cap on rows returned. None returns the full result set "
        "from hkexnews (typically up to ~100 per query).",
    )


class HkexCompanyFilingsData(CompanyFilingsData):
    """HKEX Company Filings data."""

    title: str | None = Field(default=None, description="Title of the filing.")
    stock_code: str | None = Field(
        default=None,
        description="HKEX stock code(s) the filing was released under. "
        "Multiple codes (e.g. '00005 / 80005') indicate dual-counter listings.",
    )
    stock_name: str | None = Field(
        default=None, description="Issuer's short name as it appears on hkexnews."
    )
    category: str | None = Field(
        default=None,
        description="HKEX disclosure category — Tier 1 + Tier 2 subcategories.",
    )
    file_size: str | None = Field(
        default=None,
        description="Human-readable file size as reported by hkexnews (e.g. '4MB').",
    )


class HkexCompanyFilingsFetcher(
    Fetcher[HkexCompanyFilingsQueryParams, list[HkexCompanyFilingsData]]
):
    """HKEX Company Filings fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexCompanyFilingsQueryParams:
        """Transform the query parameters."""
        return HkexCompanyFilingsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexCompanyFilingsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        stock_id: str | None = None
        if query.symbol:
            hits = await find_stock_id(query.symbol)
            if not hits:
                hits = await find_stock_id(query.symbol, kind="inactive")
            if hits:
                wanted_code = query.symbol.lstrip("0")
                exact = [
                    h for h in hits if h.get("code", "").lstrip("0") == wanted_code
                ]
                stock_id = str((exact or hits)[0]["stockId"])

        t1_code, t2_code = _FORM_GROUP_CODES.get(query.form_group, (None, None))

        date_from = (query.start_date or dateType(1999, 4, 1)).strftime("%Y%m%d")
        date_to = (query.end_date or dateType.today()).strftime("%Y%m%d")

        rows = await asyncio.to_thread(
            disclosure_search_sync,
            stock_id,
            t1_code,
            t2_code,
            date_from,
            date_to,
            query.title or "",
        )
        if query.limit:
            rows = rows[: query.limit]
        return rows

    @staticmethod
    def transform_data(
        query: HkexCompanyFilingsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[HkexCompanyFilingsData]:
        """Transform the raw data into the model."""
        out: list[HkexCompanyFilingsData] = []
        for r in data:
            try:
                ts = datetime.strptime(r["release_time"], "%d/%m/%Y %H:%M")
            except (ValueError, KeyError):
                continue
            category_label = r.get("category") or ""
            report_type = None
            if "[" in category_label and "]" in category_label:
                report_type = category_label.split("[", 1)[1].rsplit("]", 1)[0]
                report_type = report_type.split("/")[0].strip() or None
            else:
                report_type = category_label.split("-", 1)[0].strip() or None
            out.append(
                HkexCompanyFilingsData(
                    filing_date=ts.date(),
                    report_type=report_type,
                    report_url=r.get("url", ""),
                    title=r.get("title"),
                    stock_code=r.get("stock_code"),
                    stock_name=r.get("stock_short_name"),
                    category=category_label or None,
                    file_size=r.get("size"),
                )
            )
        return out
