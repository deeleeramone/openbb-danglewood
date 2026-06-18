"""Yahoo Finance Fund Info Model."""

from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class YFinanceFundInfoQueryParams(QueryParams):
    """YFinance Fund Info Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The fund or ETF ticker symbol.")

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceFundInfoData(Data):
    """YFinance Fund Info Data."""

    symbol: str = Field(description="The fund or ETF ticker symbol.")
    category: str | None = Field(default=None, description="Morningstar category.")
    family: str | None = Field(default=None, description="The fund family.")
    legal_type: str | None = Field(default=None, description="The legal type of fund.")
    description: str | None = Field(
        default=None, description="A description of the fund."
    )
    annual_report_expense_ratio: float | None = Field(
        default=None,
        description="Annual report expense ratio.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    annual_report_expense_ratio_category: float | None = Field(
        default=None,
        description="Category average annual report expense ratio.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    annual_holdings_turnover: float | None = Field(
        default=None,
        description="Annual holdings turnover.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    annual_holdings_turnover_category: float | None = Field(
        default=None,
        description="Category average annual holdings turnover.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    total_net_assets: float | None = Field(
        default=None, description="Total net assets."
    )
    price_to_earnings: float | None = Field(
        default=None, description="Portfolio weighted average price-to-earnings ratio."
    )
    price_to_book: float | None = Field(
        default=None, description="Portfolio weighted average price-to-book ratio."
    )
    price_to_sales: float | None = Field(
        default=None, description="Portfolio weighted average price-to-sales ratio."
    )
    price_to_cashflow: float | None = Field(
        default=None, description="Portfolio weighted average price-to-cashflow ratio."
    )
    median_market_cap: float | None = Field(
        default=None, description="Median market capitalization of holdings."
    )
    three_year_earnings_growth: float | None = Field(
        default=None, description="Three year earnings growth of holdings."
    )
    bond_duration: float | None = Field(
        default=None, description="Average bond duration, in years."
    )
    bond_maturity: float | None = Field(
        default=None, description="Average bond maturity, in years."
    )
    bond_credit_quality: str | float | None = Field(
        default=None, description="Average bond credit quality."
    )


class YFinanceFundInfoFetcher(
    Fetcher[YFinanceFundInfoQueryParams, list[YFinanceFundInfoData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceFundInfoQueryParams:
        """Transform query params."""
        return YFinanceFundInfoQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceFundInfoQueryParams,
        credentials: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data from Yahoo Finance."""
        import asyncio
        from warnings import warn

        from openbb_core.provider.utils.errors import EmptyDataError

        from openbb_yfinance.utils.funds_helpers import get_funds_data

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]
        results: list[dict] = []

        def _df_value(df, label, column) -> Any:
            """Read a labelled value from a frame."""
            try:
                return df.loc[label, column]
            except Exception:
                return None

        def _fetch(symbol: str) -> dict | None:
            """Fetch one fund's profile data."""
            funds = get_funds_data(symbol)
            overview = funds.fund_overview or {}
            ops = funds.fund_operations
            equity = funds.equity_holdings
            bond = funds.bond_holdings
            fund_col = (
                ops.columns[0] if ops is not None and len(ops.columns) else symbol
            )
            eq_col = (
                equity.columns[0]
                if equity is not None and len(equity.columns)
                else symbol
            )
            bd_col = (
                bond.columns[0] if bond is not None and len(bond.columns) else symbol
            )
            record = {
                "symbol": symbol,
                "category": overview.get("categoryName"),
                "family": overview.get("family"),
                "legal_type": overview.get("legalType"),
                "description": funds.description or None,
                "annual_report_expense_ratio": _df_value(
                    ops, "Annual Report Expense Ratio", fund_col
                ),
                "annual_report_expense_ratio_category": _df_value(
                    ops, "Annual Report Expense Ratio", "Category Average"
                ),
                "annual_holdings_turnover": _df_value(
                    ops, "Annual Holdings Turnover", fund_col
                ),
                "annual_holdings_turnover_category": _df_value(
                    ops, "Annual Holdings Turnover", "Category Average"
                ),
                "total_net_assets": _df_value(ops, "Total Net Assets", fund_col),
                "price_to_earnings": _df_value(equity, "Price/Earnings", eq_col),
                "price_to_book": _df_value(equity, "Price/Book", eq_col),
                "price_to_sales": _df_value(equity, "Price/Sales", eq_col),
                "price_to_cashflow": _df_value(equity, "Price/Cashflow", eq_col),
                "median_market_cap": _df_value(equity, "Median Market Cap", eq_col),
                "three_year_earnings_growth": _df_value(
                    equity, "3 Year Earnings Growth", eq_col
                ),
                "bond_duration": _df_value(bond, "Duration", bd_col),
                "bond_maturity": _df_value(bond, "Maturity", bd_col),
                "bond_credit_quality": _df_value(bond, "Credit Quality", bd_col),
            }
            return record

        async def _get_one(symbol: str) -> None:
            try:
                record = await asyncio.to_thread(_fetch, symbol)
            except Exception as e:  # noqa: BLE001
                warn(f"Error getting fund info for {symbol}: {e}")
                return
            if record:
                results.append(record)

        await asyncio.gather(*(_get_one(s) for s in symbols))

        if not results:
            raise EmptyDataError("No fund data was found for the given symbol(s).")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceFundInfoQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceFundInfoData]:
        """Transform the data."""
        from pandas import isna

        cleaned: list[dict] = []
        for row in data:
            cleaned.append(
                {
                    k: (None if (not isinstance(v, str) and isna(v)) else v)
                    for k, v in row.items()
                }
            )
        return [YFinanceFundInfoData.model_validate(d) for d in cleaned]
