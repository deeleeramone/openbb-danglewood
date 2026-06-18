"""Yahoo Finance Fund Risk Model."""

from datetime import date as dateType
from typing import Any

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.descriptions import QUERY_DESCRIPTIONS
from pydantic import Field, field_validator


class YFinanceFundRiskQueryParams(QueryParams):
    """YFinance Fund Risk Query."""

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="The fund or ETF ticker symbol.")
    start_date: dateType | None = Field(
        default=None, description=QUERY_DESCRIPTIONS.get("start_date", "")
    )
    end_date: dateType | None = Field(
        default=None, description=QUERY_DESCRIPTIONS.get("end_date", "")
    )
    benchmark: str = Field(
        default="^GSPC",
        description="The benchmark symbol used to compute beta.",
    )
    risk_free_rate: float = Field(
        default=0.0,
        description="The annual risk-free rate used for the Sharpe ratio, as a decimal.",
    )

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def _to_upper(cls, v):
        """Convert symbol to uppercase."""
        return v.upper() if isinstance(v, str) else ",".join(v).upper()


class YFinanceFundRiskData(Data):
    """YFinance Fund Risk Data."""

    symbol: str = Field(description="The fund or ETF ticker symbol.")
    start_date: dateType | None = Field(
        default=None, description="Start date of the analysis window."
    )
    end_date: dateType | None = Field(
        default=None, description="End date of the analysis window."
    )
    volatility: float | None = Field(
        default=None, description="Annualized volatility of daily returns."
    )
    beta: float | None = Field(default=None, description="Beta versus the benchmark.")
    annualized_return: float | None = Field(
        default=None, description="Annualized return over the window."
    )
    sharpe_ratio: float | None = Field(default=None, description="The Sharpe ratio.")
    max_drawdown: float | None = Field(
        default=None, description="The maximum drawdown over the window."
    )
    benchmark: str | None = Field(
        default=None, description="The benchmark used to compute beta."
    )


class YFinanceFundRiskFetcher(
    Fetcher[YFinanceFundRiskQueryParams, list[YFinanceFundRiskData]]
):
    """Transform the query, extract and transform the data from Yahoo Finance."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceFundRiskQueryParams:
        """Transform the query."""
        from datetime import datetime

        from dateutil.relativedelta import relativedelta

        now = datetime.now().date()
        if params.get("start_date") is None:
            params["start_date"] = now - relativedelta(years=3)
        if params.get("end_date") is None:
            params["end_date"] = now
        return YFinanceFundRiskQueryParams(**params)

    @staticmethod
    def extract_data(
        query: YFinanceFundRiskQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Compute the risk statistics for each symbol."""
        from warnings import warn

        from numpy import sqrt
        from openbb_core.provider.utils.errors import EmptyDataError
        from pandas import to_datetime

        from openbb_yfinance.utils.helpers import yf_download

        symbols = [s.strip() for s in query.symbol.split(",") if s.strip()]

        bench = yf_download(
            symbol=query.benchmark,
            start_date=query.start_date,
            end_date=query.end_date,
            interval="1d",
            adjusted=False,
        )
        bench_ret = None
        if not bench.empty:
            bench_close = bench.set_index("date")["close"].astype(float)
            bench_close.index = to_datetime(bench_close.index)
            bench_ret = bench_close.pct_change().dropna()

        results: list[dict] = []
        for symbol in symbols:
            data = yf_download(
                symbol=symbol,
                start_date=query.start_date,
                end_date=query.end_date,
                interval="1d",
                adjusted=False,
            )
            if data.empty:
                warn(f"No price history found for {symbol}.")
                continue

            series = data.set_index("date")["close"].astype(float)
            series.index = to_datetime(series.index)
            returns = series.pct_change().dropna()
            if returns.empty:
                warn(f"Insufficient history to compute risk for {symbol}.")
                continue

            volatility = float(returns.std() * sqrt(252))
            cumulative = (1 + returns).cumprod()
            periods = len(returns)
            annualized_return = (
                float(cumulative.iloc[-1] ** (252 / periods) - 1) if periods else None
            )
            drawdown = cumulative / cumulative.cummax() - 1
            max_drawdown = float(drawdown.min())

            beta = None
            if bench_ret is not None and not bench_ret.empty:
                aligned = returns.to_frame("fund").join(
                    bench_ret.rename("bench"), how="inner"
                )
                if len(aligned) > 1:
                    var = aligned["bench"].var()
                    if var:
                        beta = float(aligned["fund"].cov(aligned["bench"]) / var)

            sharpe = (
                float((annualized_return - query.risk_free_rate) / volatility)
                if annualized_return is not None and volatility
                else None
            )

            results.append(
                {
                    "symbol": symbol,
                    "start_date": series.index.min().date(),
                    "end_date": series.index.max().date(),
                    "volatility": volatility,
                    "beta": beta,
                    "annualized_return": annualized_return,
                    "sharpe_ratio": sharpe,
                    "max_drawdown": max_drawdown,
                    "benchmark": query.benchmark,
                }
            )

        if not results:
            raise EmptyDataError("No risk statistics could be computed.")

        return results

    @staticmethod
    def transform_data(
        query: YFinanceFundRiskQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceFundRiskData]:
        """Transform the data."""
        return [YFinanceFundRiskData.model_validate(d) for d in data]
