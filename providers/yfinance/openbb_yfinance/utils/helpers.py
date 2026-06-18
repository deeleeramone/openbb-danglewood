"""Yahoo Finance helpers module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from openbb_core.provider.utils.errors import EmptyDataError

from openbb_yfinance.utils.references import INTERVALS, MONTHS, PERIODS

if TYPE_CHECKING:
    from datetime import date  # noqa
    from pandas import DataFrame


MONTH_MAP = {
    "F": "01",
    "G": "02",
    "H": "03",
    "J": "04",
    "K": "05",
    "M": "06",
    "N": "07",
    "Q": "08",
    "U": "09",
    "V": "10",
    "X": "11",
    "Z": "12",
}

PREDEFINED_SCREENERS = [
    "aggressive_small_caps",
    "day_gainers",
    "day_losers",
    "growth_technology_stocks",
    "most_actives",
    "most_shorted_stocks",
    "small_cap_gainers",
    "undervalued_growth_stocks",
    "undervalued_large_caps",
    "conservative_foreign_funds",
    "high_yield_bond",
    "portfolio_anchors",
    "solid_large_growth_funds",
    "solid_midcap_growth_funds",
    "top_mutual_funds",
]

SCREENER_FIELDS = [
    "symbol",
    "quoteType",
    "shortName",
    "regularMarketPrice",
    "regularMarketChange",
    "regularMarketChangePercent",
    "regularMarketVolume",
    "regularMarketOpen",
    "regularMarketDayHigh",
    "regularMarketDayLow",
    "regularMarketPreviousClose",
    "fiftyDayAverage",
    "twoHundredDayAverage",
    "fiftyTwoWeekHigh",
    "fiftyTwoWeekLow",
    "marketCap",
    "sharesOutstanding",
    "epsTrailingTwelveMonths",
    "forwardPE",
    "epsForward",
    "bookValue",
    "priceToBook",
    "trailingAnnualDividendYield",
    "trailingPE",
    "ytdReturn",
    "trailingThreeMonthReturns",
    "annualReturnNavY3",
    "annualReturnNavY5",
    "netExpenseRatio",
    "yieldTTM",
    "netAssets",
    "openInterest",
    "currency",
    "exchange",
    "exchangeTimezoneName",
    "earnings_date",
]


def _screen_via_post(
    quote_type: str,
    query_node: dict,
    sort_field: str,
    sort_asc: bool,
    offset: int,
    size: int,
) -> dict:
    """Run a screen for a quote type yfinance has no query class for.

    yfinance's ``screen`` only stamps ``quoteType`` for EQUITY, MUTUALFUND and
    ETF. INDEX and FUTURE share the same request shape, so the body is posted
    directly to the screener endpoint with operators normalised to the
    upper-case form Yahoo expects.
    """
    from json import dumps

    from yfinance.data import YfData
    from yfinance.screener.screener import _SCREENER_URL_

    def _normalize(node: dict) -> dict:
        operator = str(node.get("operator", "")).upper()
        operands = node.get("operands") or []
        if operands and isinstance(operands[0], dict):
            return {"operator": operator, "operands": [_normalize(o) for o in operands]}
        if operator == "IS-IN":
            field, values = operands[0], list(operands[1:])
            if len(values) == 1:
                return {"operator": "EQ", "operands": [field, values[0]]}
            return {
                "operator": "OR",
                "operands": [
                    {"operator": "EQ", "operands": [field, v]} for v in values
                ],
            }
        return {"operator": operator, "operands": operands}

    body = {
        "offset": int(offset),
        "size": int(size),
        "sortField": sort_field or "percentchange",
        "sortType": "ASC" if sort_asc else "DESC",
        "quoteType": quote_type,
        "query": _normalize(query_node),
        "userId": "",
        "userIdType": "guid",
    }
    params = {
        "corsDomain": "finance.yahoo.com",
        "formatted": "false",
        "lang": "en-US",
        "region": "US",
    }
    response = YfData(session=None).post(
        _SCREENER_URL_,
        data=dumps(body, separators=(",", ":"), ensure_ascii=False),
        params=params,
    )
    response.raise_for_status()
    return response.json()["finance"]["result"][0]


async def get_custom_screener(
    body: dict[str, Any],
    limit: int | None = None,
    keep_illiquid: bool = False,
):
    """Run a custom screener with the yfinance ``screen`` API.

    The ``body`` keeps the Yahoo screener-request shape (quoteType, sortField,
    sortType and an AND-combined list of operand dicts), which is translated
    into an ``EquityQuery``/``FundQuery``/``ETFQuery`` and paginated. ``INDEX``
    and ``FUTURE`` have no yfinance query class, so their request body is posted
    directly to the screener endpoint. When ``keep_illiquid`` is set, rows that
    merely carry a price are kept (ETFs, funds, indices and futures have no
    intraday volume), otherwise a row needs both a change and a volume.
    """
    import asyncio

    from openbb_core.provider.utils.helpers import safe_fromtimestamp
    from pytz import timezone
    from yfinance import EquityQuery, ETFQuery, FundQuery, screen

    query_classes = {
        "EQUITY": EquityQuery,
        "MUTUALFUND": FundQuery,
        "ETF": ETFQuery,
    }
    quote_type = str(body.get("quoteType") or "EQUITY").upper()
    sort_field = body.get("sortField") or "percentchange"
    sort_asc = str(body.get("sortType") or "DESC").upper() != "DESC"

    query_node = body.get("query") or {}
    if not (query_node.get("operands") or []):
        return []

    direct = quote_type in ("INDEX", "FUTURE")
    if not direct:
        query_cls: Any = query_classes.get(quote_type, EquityQuery)

        def _to_query(node: dict):
            operator = str(node.get("operator", "")).lower()
            node_operands = node.get("operands") or []
            if operator in ("and", "or"):
                sub = [_to_query(item) for item in node_operands]
                return sub[0] if len(sub) == 1 else query_cls(operator, sub)
            return query_cls(operator, node_operands)

        query = _to_query(query_node)

    results: list = []
    offset = 0
    page = 250
    total: int | None = None

    while True:
        size = page if limit is None else min(page, max(1, limit - len(results)))
        if direct:
            response = await asyncio.to_thread(
                _screen_via_post,
                quote_type,
                query_node,
                sort_field,
                sort_asc,
                offset,
                size,
            )
        else:
            response = await asyncio.to_thread(
                screen,
                query,
                offset=offset,
                size=size,
                sortField=sort_field,
                sortAsc=sort_asc,
            )
        quotes = (response or {}).get("quotes") or []
        if total is None:
            total = (response or {}).get("total")
        if not quotes:
            break
        results.extend(quotes)
        if limit is not None and len(results) >= limit:
            break
        offset += len(quotes)
        if (total is not None and offset >= total) or len(quotes) < size:
            break

    if not results:
        raise EmptyDataError("No data found for the screener.")

    output: list = []
    seen: set = set()
    for item in results:
        symbol = item.get("symbol")
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        tz = item.get("exchangeTimezoneName")
        earnings_date = (
            safe_fromtimestamp(item["earningsTimestamp"], timezone(tz)).strftime(
                "%Y-%m-%d %H:%M:%S%z"
            )
            if item.get("earningsTimestamp") and tz
            else None
        )
        item["earnings_date"] = earnings_date
        result = {k: item.get(k, None) for k in SCREENER_FIELDS}
        if keep_illiquid:
            if result.get("regularMarketPrice") is not None:
                output.append(result)
        elif result.get("regularMarketChange") and result.get("regularMarketVolume"):
            output.append(result)

    return output[:limit] if limit is not None else output


async def get_defined_screener(
    name: str | None = None,
    body: dict[str, Any] | None = None,
    limit: int | None = None,
    all_fields: bool = False,
):
    """Run a predefined Yahoo screener by its ``scrId``.

    Any predefined ``scrId`` is accepted (Yahoo validates it), including the
    private-company markets. With ``all_fields`` every returned field is kept;
    otherwise the quote is normalized to the common screener columns.
    """
    import asyncio

    from openbb_core.provider.utils.helpers import safe_fromtimestamp
    from pytz import timezone
    from yfinance import screen

    count = 250 if not limit else min(250, max(1, limit))
    response = await asyncio.to_thread(screen, name, count=count)
    results = (response or {}).get("quotes") or []

    if not results:
        raise EmptyDataError("No data found for the predefined screener.")

    output: list = []
    seen: set = set()
    for item in results:
        sym = item.get("symbol")
        if not sym or sym in seen:
            continue
        seen.add(sym)
        tz = item.get("exchangeTimezoneName")
        item["earnings_date"] = (
            safe_fromtimestamp(item["earningsTimestamp"], timezone(tz)).strftime(
                "%Y-%m-%d %H:%M:%S%z"
            )
            if item.get("earningsTimestamp") and tz
            else None
        )
        if all_fields:
            output.append(item)
        else:
            result = {k: item.get(k, None) for k in SCREENER_FIELDS}
            if result.get("regularMarketChange") and result.get("regularMarketVolume"):
                output.append(result)

    if not output:
        raise EmptyDataError("No data found for the predefined screener.")

    return output[:limit] if limit is not None else output


async def attach_price_sparklines(
    records: list[dict],
    period: str = "1mo",
    interval: str = "1d",
) -> list[dict]:
    """Attach a ``price_history`` close series to each record for sparklines.

    Uses a single batched ``yfinance.download`` for every symbol, so the cost is
    one request rather than one per row.
    """
    import asyncio

    from yfinance import download

    symbols = [r["symbol"] for r in records if r.get("symbol")]
    if not symbols:
        return records

    data = await asyncio.to_thread(
        download,
        symbols,
        period=period,
        interval=interval,
        progress=False,
        auto_adjust=True,
    )
    if data is None or data.empty or "Close" not in data:
        return records

    closes = data["Close"]
    single = closes.ndim == 1
    for record in records:
        symbol = record.get("symbol")
        if single:
            series = closes
        elif symbol in closes.columns:
            series = closes[symbol]
        else:
            continue
        values = [round(float(v), 4) for v in series.dropna().tolist()]
        record["price_history"] = values or None

    return records


async def enrich_fund_metadata(
    records: list[dict],
    quote_types: tuple[str, ...] = ("ETF", "MUTUALFUND"),
) -> list[dict]:
    """Merge the full ``Ticker.info`` metadata into ETF and mutual-fund rows.

    Yahoo's screener returns only quote columns; ETFs and funds carry a much
    larger metadata universe (category, family, expense ratio, net assets,
    trailing returns, ratings, ...) available only per symbol.
    """
    import asyncio

    from yfinance import Ticker

    targets = [
        record
        for record in records
        if str(record.get("quoteType", "")).upper() in quote_types
        and record.get("symbol")
    ]
    if not targets:
        return records

    infos = await asyncio.gather(
        *(
            asyncio.to_thread(lambda s: Ticker(s).get_info(), record["symbol"])
            for record in targets
        )
    )
    for record, info in zip(targets, infos, strict=False):
        if isinstance(info, dict):
            record.update(info)

    return records


def get_expiration_month(symbol: str) -> str:
    """Get the expiration month for a given symbol."""
    month = symbol.split(".", maxsplit=1)[0][-3]
    year = "20" + symbol.split(".", maxsplit=1)[0][-2:]
    return f"{year}-{MONTH_MAP[month]}"


def get_futures_data() -> DataFrame:
    """Return the dataframe of the futures csv file."""
    from pathlib import Path  # noqa
    from pandas import read_csv  # noqa

    return read_csv(Path(__file__).resolve().parent / "futures.csv")


def get_futures_symbols(symbol: str) -> list:
    """Return the active futures contract chain for a continuation root.

    yfinance has no public futures-chain accessor, so this drives the library's
    own ``quoteSummary`` ``futuresChain`` module fetch (the data behind Yahoo's
    ``/quote/<symbol>/futures`` page) for the exact, dated contracts.
    """
    from yfinance import Ticker

    root = symbol.upper()
    ticker_symbol = root if root.endswith("=F") else f"{root}=F"
    try:
        result = Ticker(ticker_symbol)._quote._fetch(modules=["futuresChain"])
    except Exception:
        return []

    if not isinstance(result, dict):
        return []
    nodes = (result.get("quoteSummary") or {}).get("result") or []
    if not nodes:
        return []
    chain = (nodes[0] or {}).get("futuresChain") or {}
    return chain.get("futures") or []


async def get_futures_quotes(symbols: list) -> DataFrame:
    """Get the current futures quotes for a list of symbols."""
    import os  # noqa
    from contextlib import (
        contextmanager,
        redirect_stderr,
        redirect_stdout,
        suppress,
    )  # noqa
    from aiohttp import ClientError  # noqa
    from openbb_yfinance.models.equity_quote import YFinanceEquityQuoteFetcher  # noqa
    from pandas import DataFrame  # noqa

    @contextmanager
    def suppress_all_output():
        with (
            open(os.devnull, "w") as devnull,
            redirect_stdout(devnull),
            redirect_stderr(devnull),
        ):
            yield

    with suppress_all_output(), suppress(ClientError):
        fetcher = YFinanceEquityQuoteFetcher()
        data = await fetcher.fetch_data(
            params={"symbol": ",".join(symbols)}, credentials={}
        )

    df = DataFrame([d.model_dump() for d in data])  # ty: ignore[unresolved-attribute]
    prices = df[["symbol", "bid", "ask", "prev_close"]].copy()
    prices["price"] = round((prices.ask + prices.bid) / 2, 2)
    prices["price"] = prices.price.fillna(prices.prev_close)
    prices["expiration"] = [get_expiration_month(symbol) for symbol in prices.symbol]

    return prices[["expiration", "price"]]


async def get_historical_futures_prices(
    symbols: list, start_date: date, end_date: date
):
    """Get historical futures prices for the list of symbols."""
    from openbb_yfinance.models.equity_historical import (  # noqa
        YFinanceEquityHistoricalFetcher,
    )

    fetcher = YFinanceEquityHistoricalFetcher()

    return await fetcher.fetch_data(
        params={
            "symbol": ",".join(symbols),
            "start_date": start_date,
            "end_date": end_date,
        },
        credentials={},
    )


async def get_futures_curve(symbol: str, date: str | list | None = None) -> DataFrame:
    """Get the futures curve for a given symbol.

    Parameters
    ----------
    symbol: str
        Symbol to get futures for
    date: str | None
        Optional historical date to get curve for

    Returns
    -------
    DataFrame
        DataFrame with futures curve
    """
    from datetime import date as dateType, datetime  # noqa
    from dateutil.relativedelta import relativedelta  # noqa
    from pandas import Categorical, DataFrame, DatetimeIndex, to_datetime  # noqa

    futures_symbols = get_futures_symbols(symbol)
    today = datetime.today().date()
    dates: list = []
    if date:
        if isinstance(date, dateType):
            date = date.strftime("%Y-%m-%d")
        if isinstance(date, list) and isinstance(date[0], dateType):
            date = [d.strftime("%Y-%m-%d") for d in date]
        dates = date.split(",") if isinstance(date, str) else date
        dates = sorted([to_datetime(d).date() for d in dates])

    if futures_symbols and (not date or len(dates) == 1 and dates[0] >= today):
        futures_quotes = await get_futures_quotes(futures_symbols)
        return futures_quotes

    if dates and futures_symbols:
        historical_futures_prices = await get_historical_futures_prices(
            futures_symbols, dates[0], dates[-1]
        )
        df = DataFrame([d.model_dump() for d in historical_futures_prices])
        df = df.set_index("date").sort_index()
        df.index = df.index.astype(str)
        df.index = DatetimeIndex(df.index)
        dates_list = DatetimeIndex(dates)
        symbols = df.symbol.unique().tolist()
        expiration_dict = {symbol: get_expiration_month(symbol) for symbol in symbols}
        df = (
            df.reset_index()
            .pivot(columns="symbol", values="close", index="date")
            .copy()
        )
        df = df.rename(columns=expiration_dict)
        df.columns.name = "expiration"

        nearest_dates = [df.index.asof(date) for date in dates_list]

        df = df[df.index.isin(nearest_dates)]

        df = df.fillna("N/A").replace("N/A", None)

        flattened_data = df.reset_index().melt(
            id_vars="date", var_name="expiration", value_name="price"
        )
        flattened_data = flattened_data.sort_values("date")
        flattened_data["expiration"] = Categorical(
            flattened_data["expiration"],
            categories=sorted(list(expiration_dict.values())),
            ordered=True,
        )
        flattened_data = flattened_data.sort_values(
            by=["date", "expiration"]
        ).reset_index(drop=True)
        flattened_data["date"] = flattened_data["date"].dt.strftime("%Y-%m-%d")

        return flattened_data

    if not futures_symbols:
        import os  # noqa
        from contextlib import contextmanager, redirect_stderr, redirect_stdout  # noqa

        futures_data = get_futures_data()
        try:
            exchange = futures_data[futures_data["Ticker"] == symbol][
                "Exchange"
            ].values[0]
        except IndexError as exc:
            raise ValueError(f"Symbol {symbol} was not found.") from exc

        futures_index: list = []
        futures_curve: list = []
        futures_date: list = []
        historical_curve: list = []
        if dates:
            dates = [d.strftime("%Y-%m-%d") for d in dates]
            dates_list = DatetimeIndex(dates)

        i = 0
        empty_count = 0

        @contextmanager
        def suppress_all_output():
            with (
                open(os.devnull, "w") as devnull,
                redirect_stdout(devnull),
                redirect_stderr(devnull),
            ):
                yield

        with suppress_all_output():
            while empty_count < 12:
                future = today + relativedelta(months=i)
                future_symbol = (
                    f"{symbol}{MONTHS[future.month]}{str(future.year)[-2:]}.{exchange}"
                )
                data = yf_download(future_symbol)
                if data.empty:
                    empty_count += 1
                else:
                    empty_count = 0
                    if dates:
                        data = data.set_index("date").sort_index()
                        data.index = DatetimeIndex(data.index)
                        nearest_dates = [data.index.asof(date) for date in dates_list]
                        data = data[data.index.isin(nearest_dates)]
                        data.index = data.index.strftime("%Y-%m-%d")
                        for dt in dates:
                            try:
                                historical_curve.append(data.loc[dt, "close"])
                                futures_date.append(dt)
                                futures_index.append(future.strftime("%Y-%m"))
                            except KeyError:
                                historical_curve.append(None)
                    else:
                        futures_index.append(future.strftime("%Y-%m"))
                        futures_curve.append(
                            data.query("close.notnull()")["close"].values[-1]
                        )

                i += 1

        if not futures_index:
            raise EmptyDataError()

        if historical_curve:
            df = DataFrame(
                {
                    "date": futures_date,
                    "price": historical_curve,
                    "expiration": futures_index,
                }
            )
            df["expiration"] = Categorical(
                df["expiration"],
                categories=sorted(list(set(futures_index))),
                ordered=True,
            )
            df = df.sort_values(by=["date", "expiration"]).reset_index(drop=True)
            if len(df.date.unique()) == 1:
                df = df.drop(columns=["date"])

            return df

    return DataFrame({"price": futures_curve, "expiration": futures_index})


def yf_download(
    symbol: str,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    interval: INTERVALS = "1d",
    period: PERIODS | None = None,
    prepost: bool = False,
    actions: bool = False,
    progress: bool = False,
    ignore_tz: bool = True,
    keepna: bool = False,
    repair: bool = False,
    rounding: bool = False,
    group_by: Literal["ticker", "column"] = "ticker",
    adjusted: bool = False,
    **kwargs: Any,
) -> DataFrame:
    """Get yFinance OHLC data for any ticker and interval available."""
    from datetime import datetime, timedelta  # noqa
    from pandas import DataFrame, concat, to_datetime
    import yfinance as yf

    symbol = symbol.upper()
    _start_date = start_date
    intraday = False
    if interval in ["60m", "1h"]:
        period = "2y" if period in ["5y", "10y", "max"] else period
        _start_date = None
        intraday = True

    if interval in ["2m", "5m", "15m", "30m", "90m"]:
        _start_date = (datetime.now().date() - timedelta(days=58)).strftime("%Y-%m-%d")
        intraday = True

    if interval == "1m":
        period = "5d"
        _start_date = None
        intraday = True

    if adjusted is False:
        kwargs.update(dict(auto_adjust=False, back_adjust=False, period=period))

    session = kwargs.pop("session", None)
    if session and hasattr(session, "proxies") and session.proxies:
        kwargs["proxy"] = session.proxies

    try:
        data = yf.download(
            tickers=symbol,
            start=_start_date,
            end=None,
            interval=interval,
            prepost=prepost,
            actions=actions,
            progress=progress,
            ignore_tz=ignore_tz,
            keepna=keepna,
            repair=repair,
            rounding=rounding,
            group_by=group_by,
            threads=False,
            **kwargs,
        )
        if hasattr(data.index, "tz") and data.index.tz is not None:
            data = data.tz_convert(None)

    except ValueError as exc:
        raise EmptyDataError() from exc

    tickers = symbol.split(",")
    if len(tickers) == 1:
        if hasattr(data.columns, "levels"):
            try:
                if symbol in data.columns.get_level_values(0):
                    data = data[symbol]
                elif symbol in data.columns.get_level_values(1):
                    data = data.xs(symbol, level=1, axis=1)
            except (KeyError, IndexError):
                pass
    elif len(tickers) > 1:
        _data = DataFrame()
        for ticker in tickers:
            temp = data[ticker].copy().dropna(how="all")
            if len(temp) > 0:
                temp["symbol"] = ticker
                temp = temp.reset_index().rename(
                    columns={"Date": "date", "Datetime": "date", "index": "date"}
                )
                _data = concat([_data, temp])
        if not _data.empty:
            index_keys = ["date", "symbol"] if "symbol" in _data.columns else "date"
            _data = _data.set_index(index_keys).sort_index()
            data = _data

    if data.empty:
        raise EmptyDataError()

    if hasattr(data.columns, "levels") and len(data.columns.names) > 1:
        data.columns = [
            col[0] if isinstance(col, tuple) else col for col in data.columns
        ]

    data = data.reset_index()
    data = data.rename(columns={"Date": "date", "Datetime": "date", "index": "date"})
    data["date"] = data["date"].apply(to_datetime)
    data = data[data["Open"] > 0]

    if start_date is not None:
        data = data[data["date"] >= to_datetime(start_date)]
    if (
        end_date is not None
        and start_date is not None
        and to_datetime(end_date) > to_datetime(start_date)
    ):
        data = data[
            data["date"]
            <= (to_datetime(end_date) + timedelta(days=1 if intraday is True else 0))
        ]
    if intraday is True:
        data["date"] = data["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        data["date"] = data["date"].dt.strftime("%Y-%m-%d")
    if adjusted is False:
        data = data.drop(columns=["Adj Close"])
    data.columns = data.columns.str.lower().str.replace(" ", "_").to_list()

    for col in ["dividends", "capital_gains", "stock_splits"]:
        if col in data.columns and data[col].sum() == 0:
            data = data.drop(columns=[col])

    return data


def df_transform_numbers(data: DataFrame, columns: list) -> DataFrame:
    """Replace abbreviations of numbers with actual numbers."""
    multipliers = {"M": 1e6, "B": 1e9, "T": 1e12}

    def replace_suffix(x, suffix, multiplier):
        return float(str(x).replace(suffix, "")) * multiplier if suffix in str(x) else x

    for col in columns:
        if col == "% Change":
            data[col] = data[col].astype(str).str.replace("%", "").astype(float) / 100
        else:
            for suffix, multiplier in multipliers.items():
                data[col] = data[col].apply(replace_suffix, args=(suffix, multiplier))

    return data
