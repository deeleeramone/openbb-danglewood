"""Yahoo Finance Company Filings Model."""

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.company_filings import (
    CompanyFilingsData,
    CompanyFilingsQueryParams,
)
from pydantic import Field


class YFinanceCompanyFilingsQueryParams(CompanyFilingsQueryParams):
    """YFinance Company Filings Query.

    Source: https://finance.yahoo.com/quote/AAPL/sec-filings
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}


class YFinanceCompanyFilingsData(CompanyFilingsData):
    """YFinance Company Filings Data."""

    symbol: str | None = Field(default=None, description="The ticker symbol.")
    title: str | None = Field(default=None, description="The title of the filing.")


class YFinanceCompanyFilingsFetcher(
    Fetcher[YFinanceCompanyFilingsQueryParams, list[YFinanceCompanyFilingsData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceCompanyFilingsQueryParams:
        """Transform the query."""
        return YFinanceCompanyFilingsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceCompanyFilingsQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Return the raw data from the Yahoo Finance endpoint."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError

        from yfinance import Ticker

        symbols = [s.strip() for s in (query.symbol or "").split(",") if s.strip()]
        if not symbols:
            raise EmptyDataError("A symbol is required for company filings.")
        results: list[dict] = []

        def _fetch(symbol: str) -> list[dict]:
            filings = Ticker(symbol).get_sec_filings() or []
            rows: list[dict] = []
            for item in filings:
                if not isinstance(item, dict):
                    continue
                url = item.get("edgarUrl")
                if not url:
                    exhibits = item.get("exhibits")
                    if isinstance(exhibits, dict) and exhibits:
                        url = next(iter(exhibits.values()))
                if not item.get("date") or not url:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "filing_date": item.get("date"),
                        "report_type": item.get("type"),
                        "report_url": url,
                        "title": item.get("title"),
                    }
                )
            return rows

        async def _get_one(symbol: str) -> None:
            try:
                rows = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting filings for {symbol}: {e}")
                return
            results.extend(rows)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError("No filings were found for the given symbol(s).")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceCompanyFilingsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceCompanyFilingsData]:
        """Transform the data."""
        return [YFinanceCompanyFilingsData.model_validate(d) for d in data]
