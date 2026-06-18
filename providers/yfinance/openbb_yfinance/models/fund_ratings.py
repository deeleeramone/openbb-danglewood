"""Yahoo Finance Fund Ratings Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator

_FIXED_INCOME_KEYWORDS = (
    "bond",
    "income",
    "government",
    "treasury",
    "muni",
    "credit",
    "fixed",
    "mortgage",
)


class YFinanceFundRatingsQueryParams(QueryParams):
    """YFinance Fund Ratings Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The fund or ETF ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceFundRatingsData(Data):
    """YFinance Fund Ratings Data."""

    symbol: str = Field(description="The fund or ETF ticker symbol.")
    morningstar_overall_rating: int | None = Field(
        default=None, description="Morningstar overall rating (1-5 stars)."
    )
    morningstar_risk_rating: int | None = Field(
        default=None, description="Morningstar risk rating (1-5)."
    )
    category: str | None = Field(default=None, description="Morningstar category.")
    family: str | None = Field(default=None, description="The fund family.")
    legal_type: str | None = Field(default=None, description="The legal type of fund.")
    style_box: int | None = Field(
        default=None,
        description="Morningstar style-box cell position (1-9), numbered"
        + " left-to-right then top-to-bottom.",
    )
    style_box_type: str | None = Field(
        default=None, description="The style-box type ('equity' or 'fixed_income')."
    )
    style_box_label: str | None = Field(
        default=None, description="Human-readable style-box label."
    )
    style_box_size: str | None = Field(
        default=None,
        description="Equity style box market-cap row (Large, Mid, Small).",
    )
    style_box_investment_style: str | None = Field(
        default=None,
        description="Equity style box investment-style column (Value, Blend, Growth).",
    )
    style_box_credit_quality: str | None = Field(
        default=None,
        description="Fixed-income style box credit-quality row (High, Medium, Low).",
    )
    style_box_interest_rate_sensitivity: str | None = Field(
        default=None,
        description="Fixed-income style box interest-rate-sensitivity column"
        + " (Limited, Moderate, Extensive).",
    )
    style_box_url: str | None = Field(
        default=None, description="URL to the Morningstar style-box image."
    )


class YFinanceFundRatingsFetcher(
    Fetcher[YFinanceFundRatingsQueryParams, list[YFinanceFundRatingsData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceFundRatingsQueryParams:
        """Transform query params."""
        return YFinanceFundRatingsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceFundRatingsQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from Yahoo Finance."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError

        from openbb_yfinance.utils.funds_helpers import (
            get_fund_quote_summary,
            parse_raw,
            parse_style_box,
        )

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        def _is_fixed_income(top: dict, category: str | None) -> bool:
            """Determine whether the style box uses fixed-income axes."""
            stock = parse_raw(top.get("stockPosition"))
            bond = parse_raw(top.get("bondPosition"))
            if stock is not None or bond is not None:
                return (bond or 0) > (stock or 0)
            cat = (category or "").lower()
            return any(word in cat for word in _FIXED_INCOME_KEYWORDS)

        def _fetch(symbol: str) -> dict | None:
            """Parse ratings and the style box for one symbol."""
            summary = get_fund_quote_summary(
                symbol, ["defaultKeyStatistics", "fundProfile", "topHoldings"]
            )
            stats = summary.get("defaultKeyStatistics") or {}
            profile = summary.get("fundProfile") or {}
            top = summary.get("topHoldings") or {}
            overall = parse_raw(stats.get("morningStarOverallRating"))
            risk = parse_raw(stats.get("morningStarRiskRating"))
            category = profile.get("categoryName") or stats.get("category")
            style_box_url = profile.get("styleBoxUrl")
            box = parse_style_box(
                style_box_url, is_fixed_income=_is_fixed_income(top, category)
            )
            record = {
                "symbol": symbol,
                "morningstar_overall_rating": int(overall)
                if overall is not None
                else None,
                "morningstar_risk_rating": int(risk) if risk is not None else None,
                "category": category,
                "family": profile.get("family") or stats.get("fundFamily"),
                "legal_type": profile.get("legalType") or stats.get("legalType"),
                "style_box_url": style_box_url,
                **box,
            }
            if not any(
                record.get(k) is not None
                for k in (
                    "morningstar_overall_rating",
                    "morningstar_risk_rating",
                    "style_box",
                    "category",
                )
            ):
                return None
            return record

        async def _get_one(symbol: str) -> None:
            try:
                record = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting fund ratings for {symbol}: {e}")
                return
            if record:
                results.append(record)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError("No ratings were found for the given symbol(s).")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceFundRatingsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceFundRatingsData]:
        """Transform the data."""
        return [YFinanceFundRatingsData.model_validate(d) for d in data]
