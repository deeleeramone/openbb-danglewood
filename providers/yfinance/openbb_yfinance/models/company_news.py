"""Yahoo Finance Company News Model."""

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.company_news import (
    CompanyNewsData,
    CompanyNewsQueryParams,
)
from pydantic import Field, field_validator


class YFinanceCompanyNewsQueryParams(CompanyNewsQueryParams):
    """YFinance Company News Query.

    Source: https://finance.yahoo.com/news/
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _symbol_mandatory(cls, v):
        """Symbol mandatory validator."""
        if not v:
            raise ValueError("Required field missing -> symbol")
        return v


class YFinanceCompanyNewsData(CompanyNewsData):
    """YFinance Company News Data."""

    source: str | None = Field(default=None, description="Source of the news article")


class YFinanceCompanyNewsFetcher(
    Fetcher[
        YFinanceCompanyNewsQueryParams,
        list[YFinanceCompanyNewsData],
    ]
):
    """Transform the query, extract and transform the data from the Yahoo Finance endpoints."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceCompanyNewsQueryParams:
        """Transform query params."""
        return YFinanceCompanyNewsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query,
        credentials=None,
        **kwargs,
    ) -> list[dict]:
        """Extract the raw data from YFinance and normalize to CompanyNewsData schema."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError
        from yfinance import Ticker

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        def _normalize_news_item(item: dict, sym: str) -> dict | None:
            """Flatten the response."""
            if not isinstance(item, dict):
                return None

            content = item.get("content")
            if not isinstance(content, dict):
                return None

            title = content.get("title") or content.get("summary")
            url = None
            ctu = content.get("clickThroughUrl")
            if isinstance(ctu, dict):
                url = ctu.get("url")
            if not url:
                can = content.get("canonicalUrl")
                if isinstance(can, dict):
                    url = can.get("url")
            if not url:
                url = content.get("previewUrl")

            date = content.get("pubDate") or content.get("displayTime")

            provider = content.get("provider")
            source = provider.get("displayName") if isinstance(provider, dict) else None
            summary = content.get("summary") or content.get("description") or ""

            if not (sym and title and url and date):
                return None

            normalized: dict[str, Any] = {
                "symbol": sym,
                "title": title,
                "url": url,
                "date": date,
                "source": source,
            }
            if summary:
                normalized["summary"] = summary
                normalized["text"] = summary

            if item.get("id"):
                normalized["id"] = item["id"]
            elif content.get("id"):
                normalized["id"] = content["id"]

            return normalized

        def _fetch_news(sym: str) -> list[dict]:
            """Fetch the data in a worker thread."""
            raw = Ticker(sym).get_news() or []
            out: list[dict] = []
            for item in raw:
                norm = _normalize_news_item(item, sym)
                if norm:
                    out.append(norm)
            return out

        async def get_one(sym: str) -> None:
            """Get the data for one ticker symbol."""
            try:
                items = await asyncio.to_thread(_fetch_news, sym)
            except Exception as e:
                warn(f"Error getting news for {sym}: {e}")
                return
            if items:
                results.extend(items)

        await asyncio.gather(*(get_one(sym) for sym in symbols))

        if not results:
            raise EmptyDataError("No data was returned for the given symbol(s)")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceCompanyNewsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceCompanyNewsData]:
        """Transform data."""
        return [YFinanceCompanyNewsData.model_validate(d) for d in data]
