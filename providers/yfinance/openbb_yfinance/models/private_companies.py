"""Yahoo Finance Private Companies Model."""

from datetime import date as dateType
from typing import Any, Literal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field

CATEGORY_SCR_IDS = {
    "highest_valuation": "HIGHEST_VALUATION_PRIVATE_COMPANY",
    "52_week_gainers": "52_WEEK_GAINERS_PRIVATE_COMPANY",
    "recently_funded": "RECENTLY_FUNDED_PRIVATE_COMPANY",
    "most_funded": "MOST_FUNDED_PRIVATE_COMPANY",
}


class YFinancePrivateCompaniesQueryParams(QueryParams):
    """YFinance Private Companies Query.

    Source: https://finance.yahoo.com/markets/private-companies/
    """

    category: Literal[
        "highest_valuation",
        "52_week_gainers",
        "recently_funded",
        "most_funded",
    ] = Field(
        default="highest_valuation",
        description="The private-companies market to retrieve.",
    )
    limit: int = Field(
        default=100, description="The maximum number of companies to return."
    )


class YFinancePrivateCompaniesData(Data):
    """YFinance Private Companies Data."""

    symbol: str = Field(description="The Yahoo private-company symbol (e.g. ANTH.PVT).")
    name: str | None = Field(default=None, description="The company name.")
    valuation: float | None = Field(
        default=None, description="The latest implied valuation."
    )
    funding_to_date: float | None = Field(
        default=None, description="The total funding raised to date."
    )
    latest_amount_raised: float | None = Field(
        default=None, description="The amount raised in the latest funding round."
    )
    latest_funding_date: dateType | None = Field(
        default=None, description="The date of the latest funding round."
    )
    latest_share_class: str | None = Field(
        default=None, description="The latest share class issued."
    )
    lead_investor: str | None = Field(
        default=None, description="The lead investor of the latest round."
    )
    total_funding_rounds: int | None = Field(
        default=None, description="The total number of funding rounds."
    )
    change_52_week: float | None = Field(
        default=None,
        description="The 52-week change in the indexed price.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 1},
    )
    price: float | None = Field(
        default=None, description="The latest indexed private-company price."
    )
    employees: int | None = Field(
        default=None, description="The number of full-time employees."
    )
    date_founded: dateType | None = Field(
        default=None, description="The date the company was founded."
    )
    sector: str | None = Field(default=None, description="The company sector.")
    industry: str | None = Field(default=None, description="The company industry.")
    city: str | None = Field(default=None, description="The headquarters city.")
    state: str | None = Field(default=None, description="The headquarters state.")
    country: str | None = Field(default=None, description="The headquarters country.")
    website: str | None = Field(default=None, description="The company website.")
    lead_executives: str | None = Field(
        default=None, description="Comma-separated lead executives and titles."
    )
    summary: str | None = Field(
        default=None, description="A short business summary of the company."
    )


class YFinancePrivateCompaniesFetcher(
    Fetcher[
        YFinancePrivateCompaniesQueryParams,
        list[YFinancePrivateCompaniesData],
    ]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> YFinancePrivateCompaniesQueryParams:
        """Transform query params."""
        return YFinancePrivateCompaniesQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinancePrivateCompaniesQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from Yahoo Finance."""
        import asyncio

        from openbb_core.provider.utils.errors import EmptyDataError
        from yfinance import Ticker, screen

        scr_id = CATEGORY_SCR_IDS[query.category]
        listing = await asyncio.to_thread(screen, scr_id, size=query.limit)
        quotes = (listing or {}).get("quotes") or []
        symbols = [q.get("symbol") for q in quotes if q.get("symbol")]
        if not symbols:
            raise EmptyDataError("No private companies were returned.")

        infos = await asyncio.gather(
            *(asyncio.to_thread(lambda s: Ticker(s).get_info(), sym) for sym in symbols)
        )
        return [
            {**(info or {}), "_rank": rank} for rank, info in enumerate(infos) if info
        ]

    @staticmethod
    def transform_data(
        query: YFinancePrivateCompaniesQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinancePrivateCompaniesData]:
        """Transform the data."""
        from datetime import datetime, timezone

        def _epoch_to_date(value: Any) -> dateType | None:
            if not isinstance(value, int | float):
                return None
            return datetime.fromtimestamp(value, tz=timezone.utc).date()

        def _iso_to_date(value: Any) -> dateType | None:
            if not isinstance(value, str):
                return None
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                return None

        out: list[YFinancePrivateCompaniesData] = []
        for info in sorted(data, key=lambda d: d.get("_rank", 0)):
            executives = ", ".join(
                f"{e.get('name')} ({e.get('title')})"
                for e in (info.get("executiveTeam") or [])
                if e.get("name")
            )
            out.append(
                YFinancePrivateCompaniesData.model_validate(
                    {
                        "symbol": info.get("symbol"),
                        "name": info.get("longName") or info.get("shortName"),
                        "valuation": info.get("latestImpliedValuation"),
                        "funding_to_date": info.get("fundingToDate"),
                        "latest_amount_raised": info.get("latestAmountRaised"),
                        "latest_funding_date": _epoch_to_date(
                            info.get("latestFundingDate")
                        ),
                        "latest_share_class": info.get("latestShareClass"),
                        "lead_investor": info.get("leadInvestor"),
                        "total_funding_rounds": info.get("totalFundingRounds"),
                        "change_52_week": info.get("fiftyTwoWeekChangePercent"),
                        "price": info.get("regularMarketPrice"),
                        "employees": info.get("fullTimeEmployees"),
                        "date_founded": _iso_to_date(info.get("dateFounded")),
                        "sector": info.get("sectorDisp") or info.get("sector"),
                        "industry": info.get("industryDisp") or info.get("industry"),
                        "city": info.get("city"),
                        "state": info.get("state"),
                        "country": info.get("country"),
                        "website": info.get("website") or info.get("companyURL"),
                        "lead_executives": executives or None,
                        "summary": info.get("longBusinessSummary")
                        or info.get("overview"),
                    }
                )
            )
        return out
