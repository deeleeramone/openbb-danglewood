"""Yahoo Finance mutual fund & ETF analytics helpers."""

from typing import Any

_QUOTE_SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/"


def get_funds_data(symbol: str) -> Any:
    """Return the yfinance ``FundsData`` object for a fund or ETF symbol."""
    from yfinance import Ticker

    return Ticker(symbol).get_funds_data()


def compute_fund_performance(symbol: str) -> list[dict]:
    """Compute trailing and annual returns for a fund from its price history.

    yfinance does not implement Yahoo's ``fundPerformance`` module; per the
    library's own note, returns are derived from the dividend-adjusted price
    history instead.
    """
    from pandas import DateOffset, Timestamp

    from yfinance import Ticker

    history = Ticker(symbol).history(period="max", auto_adjust=True)
    if history is None or history.empty or "Close" not in history:
        return []
    close = history["Close"].dropna()
    if close.empty:
        return []
    close.index = close.index.tz_localize(None)

    end_date = close.index[-1]
    end_price = float(close.iloc[-1])
    rows: list[dict] = []

    windows = {
        "1m": DateOffset(months=1),
        "3m": DateOffset(months=3),
        "6m": DateOffset(months=6),
        "1y": DateOffset(years=1),
        "3y": DateOffset(years=3),
        "5y": DateOffset(years=5),
        "10y": DateOffset(years=10),
    }
    for period, offset in windows.items():
        prior = close[close.index <= end_date - offset]
        if prior.empty:
            continue
        start_price = float(prior.iloc[-1])
        if start_price <= 0:
            continue
        cumulative = end_price / start_price - 1
        years = (end_date - prior.index[-1]).days / 365.25
        annualized = (1 + cumulative) ** (1 / years) - 1 if years >= 1 else None
        rows.append(
            {
                "symbol": symbol,
                "measure": "trailing_return",
                "period": period,
                "cumulative_return": cumulative,
                "annualized_return": annualized,
            }
        )

    year_start = Timestamp(year=end_date.year, month=1, day=1)
    prior_ytd = close[close.index < year_start]
    if not prior_ytd.empty and float(prior_ytd.iloc[-1]) > 0:
        rows.append(
            {
                "symbol": symbol,
                "measure": "trailing_return",
                "period": "ytd",
                "cumulative_return": end_price / float(prior_ytd.iloc[-1]) - 1,
                "annualized_return": None,
            }
        )

    annual = close.resample("YE").last().pct_change().dropna()
    for timestamp, value in annual.items():
        rows.append(
            {
                "symbol": symbol,
                "measure": "annual_return",
                "period": str(timestamp.year),
                "cumulative_return": float(value),
                "annualized_return": None,
            }
        )

    return rows


def get_fund_quote_summary(symbol: str, modules: list[str]) -> dict:
    """Fetch raw Yahoo Finance ``quoteSummary`` modules for a symbol.

    Used for the Morningstar style box (``fundProfile`` ``styleBoxUrl``), which
    the yfinance ``FundsData`` object does not expose.

    Parameters
    ----------
    symbol : str
        The fund or ETF ticker symbol.
    modules : list[str]
        The quoteSummary module names to request.

    Returns
    -------
    dict
        The parsed ``quoteSummary.result[0]`` mapping, or an empty dict when
        no data is available.
    """
    from yfinance.data import YfData

    params = {
        "modules": ",".join(modules),
        "corsDomain": "finance.yahoo.com",
        "formatted": "false",
        "symbol": symbol,
    }
    response = YfData().get_raw_json(url=_QUOTE_SUMMARY_URL + symbol, params=params)

    if not isinstance(response, dict) or "quoteSummary" not in response:
        return {}
    result = response["quoteSummary"].get("result") or []
    if not result:
        return {}
    return result[0] or {}


def parse_raw(value: Any, default: Any = None) -> Any:
    """Unwrap a Yahoo ``{"raw": ...}`` value, returning *default* when missing."""
    if isinstance(value, dict):
        return value.get("raw", default)
    return value if value is not None else default


_EQUITY_SIZE = ("Large", "Mid", "Small")
_EQUITY_STYLE = ("Value", "Blend", "Growth")
_BOND_CREDIT = ("High", "Medium", "Low")
_BOND_SENSITIVITY = ("Limited", "Moderate", "Extensive")


def parse_style_box(style_box_url: str | None, is_fixed_income: bool = False) -> dict:
    """Parse a Morningstar style box from a Yahoo ``styleBoxUrl``.

    Parameters
    ----------
    style_box_url : str | None
        The Yahoo ``styleBoxUrl`` (e.g. ``.../3_0stylelargeeq5.gif``).
    is_fixed_income : bool
        When True, interpret the box with fixed-income axes.

    Returns
    -------
    dict
        Parsed style-box fields, or an empty dict when no box is available.
    """
    import re

    if not style_box_url:
        return {}
    match = re.search(r"(\d+)\.gif", style_box_url)
    if not match:
        return {}
    position = int(match.group(1))
    if not 1 <= position <= 9:
        return {}

    row = (position - 1) // 3
    column = (position - 1) % 3

    if is_fixed_income:
        credit = _BOND_CREDIT[row]
        sensitivity = _BOND_SENSITIVITY[column]
        return {
            "style_box": position,
            "style_box_type": "fixed_income",
            "style_box_credit_quality": credit,
            "style_box_interest_rate_sensitivity": sensitivity,
            "style_box_label": f"{credit} Credit Quality / {sensitivity} Sensitivity",
        }

    size = _EQUITY_SIZE[row]
    style = _EQUITY_STYLE[column]
    return {
        "style_box": position,
        "style_box_type": "equity",
        "style_box_size": size,
        "style_box_investment_style": style,
        "style_box_label": f"{size} {style}",
    }
