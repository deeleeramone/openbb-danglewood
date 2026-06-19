"""Field/value catalog that drives the interactive screener-builder iframe."""

from typing import Any

_STRING_FIELDS = {"region", "ticker", "primary_sector"}

_CATEGORY_LABELS = {
    "eq_fields": "Classification",
    "price": "Price & Performance",
    "valuation": "Valuation",
    "profitability": "Profitability",
    "income_statement": "Income Statement",
    "balance_sheet": "Balance Sheet",
    "cash_flow": "Cash Flow",
    "leverage": "Leverage",
    "liquidity": "Liquidity",
    "trading": "Trading",
    "short_interest": "Short Interest",
    "esg": "ESG",
    "fundamentals": "Fundamentals",
    "feesandexpenses": "Fees & Expenses",
    "historicalperformance": "Historical Performance",
    "keystats": "Key Stats",
    "morningstar_rating": "Morningstar",
    "portfoliostatistics": "Portfolio Statistics",
    "purchasedetails": "Purchase Details",
    "trailingperformance": "Trailing Performance",
}

_FIELD_LABELS = {
    "altmanzscoreusingtheaveragestockinformationforaperiod.lasttwelvemonths": "Altman Z-Score (LTM)",
    "annualreportgrossexpenseratio": "Gross Expense Ratio",
    "annualreportnetexpenseratio": "Net Expense Ratio",
    "annualreturnnavy1": "1Y Return (NAV)",
    "annualreturnnavy1categoryrank": "1Y Return Category Rank (NAV)",
    "annualreturnnavy3": "3Y Return (NAV)",
    "annualreturnnavy5": "5Y Return (NAV)",
    "avgdailyvol3m": "Avg Daily Volume (3M)",
    "basicepscontinuingoperations.lasttwelvemonths": "Basic EPS, Continuing Ops (LTM)",
    "beta": "Beta",
    "bookvalueshare.lasttwelvemonths": "Book Value / Share (LTM)",
    "capitalexpenditure.lasttwelvemonths": "Capital Expenditure (LTM)",
    "cashfromoperations.lasttwelvemonths": "Cash from Operations (LTM)",
    "cashfromoperations1yrgrowth.lasttwelvemonths": "Cash from Operations 1Y Growth (LTM)",
    "categoryname": "Category",
    "consecutive_years_of_dividend_growth_count": "Consecutive Years of Dividend Growth",
    "currentratio.lasttwelvemonths": "Current Ratio (LTM)",
    "days_to_cover_short.value": "Days to Cover Short",
    "dayvolume": "Volume",
    "dilutedeps1yrgrowth.lasttwelvemonths": "Diluted EPS 1Y Growth (LTM)",
    "dilutedepscontinuingoperations.lasttwelvemonths": "Diluted EPS, Continuing Ops (LTM)",
    "ebit.lasttwelvemonths": "EBIT (LTM)",
    "ebitda.lasttwelvemonths": "EBITDA (LTM)",
    "ebitda1yrgrowth.lasttwelvemonths": "EBITDA 1Y Growth (LTM)",
    "ebitdainterestexpense.lasttwelvemonths": "EBITDA / Interest Expense (LTM)",
    "ebitdamargin.lasttwelvemonths": "EBITDA Margin (LTM)",
    "ebitinterestexpense.lasttwelvemonths": "EBIT / Interest Expense (LTM)",
    "environmental_score": "Environmental Score",
    "eodprice": "Close Price",
    "eodvolume": "EOD Volume",
    "epsgrowth.lasttwelvemonths": "EPS Growth (LTM)",
    "esg_score": "ESG Score",
    "exchange": "Exchange",
    "fiftytwowkpercentchange": "52-Week % Change",
    "forward_dividend_per_share": "Forward Dividend / Share",
    "forward_dividend_yield": "Forward Dividend Yield",
    "fundfamilyname": "Fund Family",
    "fundnetassets": "Net Assets",
    "governance_score": "Governance Score",
    "grossprofit.lasttwelvemonths": "Gross Profit (LTM)",
    "grossprofitmargin.lasttwelvemonths": "Gross Profit Margin (LTM)",
    "highest_controversy": "Highest Controversy",
    "industry": "Industry",
    "initialinvestment": "Min Initial Investment",
    "intradaymarketcap": "Market Cap",
    "intradayprice": "Price",
    "intradaypricechange": "Price Change",
    "lastclose52weekhigh.lasttwelvemonths": "52-Week High (Last Close)",
    "lastclose52weeklow.lasttwelvemonths": "52-Week Low (Last Close)",
    "lastclosemarketcap.lasttwelvemonths": "Market Cap (Last Close)",
    "lastclosemarketcaptotalrevenue.lasttwelvemonths": "Market Cap / Revenue (Last Close)",
    "lastclosepriceearnings.lasttwelvemonths": "P/E (Last Close)",
    "lastclosepricetangiblebookvalue.lasttwelvemonths": "Price / Tangible Book (Last Close)",
    "lastclosetevebit.lasttwelvemonths": "TEV / EBIT (Last Close)",
    "lastclosetevebitda.lasttwelvemonths": "TEV / EBITDA (Last Close)",
    "lastclosetevtotalrevenue.lasttwelvemonths": "TEV / Revenue (Last Close)",
    "leveredfreecashflow.lasttwelvemonths": "Levered Free Cash Flow (LTM)",
    "leveredfreecashflow1yrgrowth.lasttwelvemonths": "Levered FCF 1Y Growth (LTM)",
    "ltdebtequity.lasttwelvemonths": "LT Debt / Equity (LTM)",
    "marketcapitalvaluelong": "Market Cap",
    "morningstar_economic_moat": "Morningstar Economic Moat",
    "morningstar_last_close_price_to_fair_value": "Price / Fair Value (Morningstar)",
    "morningstar_moat_trend": "Morningstar Moat Trend",
    "morningstar_rating": "Morningstar Rating",
    "morningstar_rating_change": "Morningstar Rating Change",
    "morningstar_rating_updated_time": "Morningstar Rating Updated",
    "morningstar_stewardship": "Morningstar Stewardship",
    "morningstar_uncertainty": "Morningstar Uncertainty",
    "netdebtebitda.lasttwelvemonths": "Net Debt / EBITDA (LTM)",
    "netepsbasic.lasttwelvemonthsnetepsdiluted.lasttwelvemonths": "Net EPS, Basic & Diluted (LTM)",
    "netincome1yrgrowth.lasttwelvemonths": "Net Income 1Y Growth (LTM)",
    "netincomeis.lasttwelvemonths": "Net Income (LTM)",
    "netincomemargin.lasttwelvemonths": "Net Income Margin (LTM)",
    "operatingcashflowtocurrentliabilities.lasttwelvemonths": "Operating Cash Flow / Current Liabilities (LTM)",
    "operatingincome.lasttwelvemonths": "Operating Income (LTM)",
    "pctheldinsider": "% Held by Insiders",
    "pctheldinst": "% Held by Institutions",
    "peer_group": "Peer Group",
    "pegratio_5y": "PEG Ratio (5Y)",
    "peratio.lasttwelvemonths": "P/E Ratio (LTM)",
    "percentchange": "% Change",
    "performanceratingoverall": "Performance Rating",
    "pricebookratio.quarterly": "Price / Book (Q)",
    "primary_sector": "Primary Sector",
    "quarterendtrailingreturnytd": "YTD Return (Quarter End)",
    "quarterlyrevenuegrowth.quarterly": "Quarterly Revenue Growth (Q)",
    "quickratio.lasttwelvemonths": "Quick Ratio (LTM)",
    "region": "Region",
    "returnonassets.lasttwelvemonths": "Return on Assets (LTM)",
    "returnonequity.lasttwelvemonths": "Return on Equity (LTM)",
    "returnontotalcapital.lasttwelvemonths": "Return on Total Capital (LTM)",
    "riskratingoverall": "Risk Rating",
    "sector": "Sector",
    "short_interest.value": "Short Interest",
    "short_interest_percentage_change.value": "Short Interest % Change",
    "short_percentage_of_float.value": "Short % of Float",
    "short_percentage_of_shares_outstanding.value": "Short % of Shares Outstanding",
    "social_score": "Social Score",
    "ticker": "Ticker",
    "totalassets.lasttwelvemonths": "Total Assets (LTM)",
    "totalcashandshortterminvestments.lasttwelvemonths": "Total Cash & Short-Term Investments (LTM)",
    "totalcommonequity.lasttwelvemonths": "Total Common Equity (LTM)",
    "totalcommonsharesoutstanding.lasttwelvemonths": "Total Common Shares Outstanding (LTM)",
    "totalcurrentassets.lasttwelvemonths": "Total Current Assets (LTM)",
    "totalcurrentliabilities.lasttwelvemonths": "Total Current Liabilities (LTM)",
    "totaldebt.lasttwelvemonths": "Total Debt (LTM)",
    "totaldebtebitda.lasttwelvemonths": "Total Debt / EBITDA (LTM)",
    "totaldebtequity.lasttwelvemonths": "Total Debt / Equity (LTM)",
    "totalequity.lasttwelvemonths": "Total Equity (LTM)",
    "totalrevenues.lasttwelvemonths": "Total Revenue (LTM)",
    "totalrevenues1yrgrowth.lasttwelvemonths": "Total Revenue 1Y Growth (LTM)",
    "totalsharesoutstanding": "Total Shares Outstanding",
    "trailing_3m_return": "3M Return",
    "trailing_ytd_return": "YTD Return",
    "turnoverratio": "Turnover Ratio",
    "unleveredfreecashflow.lasttwelvemonths": "Unlevered Free Cash Flow (LTM)",
}

_SUFFIX_LABELS = [
    (".lasttwelvemonths", " (LTM)"),
    (".quarterly", " (Q)"),
    (".value", ""),
    ("_5y", " (5Y)"),
]


def _field_label(field: str) -> str:
    """Return a human-friendly label for a raw screener field."""
    if field in _FIELD_LABELS:
        return _FIELD_LABELS[field]
    base, suffix = field, ""
    for token, repl in _SUFFIX_LABELS:
        if base.endswith(token):
            base, suffix = base[: -len(token)], repl
            break
    base = base.replace("_", " ").replace(".", " ")
    return (base[:1].upper() + base[1:] + suffix).strip()


_ASSET_TYPES = [
    {"value": "equity", "label": "Equity"},
    {"value": "etf", "label": "ETF"},
    {"value": "fund", "label": "Mutual Fund"},
    {"value": "index", "label": "Index"},
    {"value": "future", "label": "Future"},
]

_OPERATORS = {
    "number": [
        {"value": "gt", "label": "greater than"},
        {"value": "gte", "label": "greater or equal"},
        {"value": "lt", "label": "less than"},
        {"value": "lte", "label": "less or equal"},
        {"value": "btwn", "label": "between"},
    ],
    "enum": [
        {"value": "eq", "label": "is"},
        {"value": "is-in", "label": "is any of"},
    ],
    "text": [{"value": "eq", "label": "is"}],
}

_SORT_TYPES = [
    {"value": "DESC", "label": "Descending"},
    {"value": "ASC", "label": "Ascending"},
]


def _value_options(field: str, eq_map: dict) -> list[dict]:
    """Return {value, label} options for an enum field, labelling the country region."""
    raw = sorted(str(v) for v in eq_map[field])
    if field == "region":
        from openbb_core.provider.utils.country_utils import Country

        options = []
        for value in raw:
            try:
                options.append({"value": value, "label": str(Country(value).name)})
            except Exception:
                options.append({"value": value, "label": value.upper()})
        return sorted(options, key=lambda o: o["label"])
    return [{"value": value, "label": value} for value in raw]


def _fields_for(fields_map: dict, eq_map: dict) -> list[dict]:
    """Flatten a field map into catalog entries with type and enum values."""
    out: list[dict] = []
    for category in sorted(fields_map):
        category_label = _CATEGORY_LABELS.get(
            category, category.replace("_", " ").title()
        )
        for field in sorted(fields_map[category]):
            entry = {
                "field": field,
                "label": _field_label(field),
                "category": category,
                "category_label": category_label,
            }
            if field in eq_map:
                entry["type"] = "enum"
                entry["values"] = _value_options(field, eq_map)
            elif field in _STRING_FIELDS:
                entry["type"] = "text"
            else:
                entry["type"] = "number"
            out.append(entry)
    return out


def _extra_fields_for(asset: str) -> list[dict]:
    """Flatten the bundled index/future field metadata into catalog entries.

    yfinance ships no field map for the index and future quote types, so the
    metadata is bundled in :mod:`openbb_yfinance.utils.screener_extra_fields`;
    enum value options are reused from the yfinance ``*_SCREENER_EQ_MAP`` tables,
    which share the relevant field identifiers (region, sector, industry,
    exchange).
    """
    from openbb_yfinance.utils.screener_extra_fields import (
        EXTRA_CATEGORY_LABELS,
        EXTRA_ENUM_FIELDS,
        EXTRA_FIELD_LABELS,
        EXTRA_NUMBER_FIELDS,
        EXTRA_SCREENER_FIELDS,
    )
    from yfinance.const import (
        EQUITY_SCREENER_EQ_MAP,
        ETF_SCREENER_EQ_MAP,
        FUND_SCREENER_EQ_MAP,
    )

    eq_map: dict = {}
    for mapping in (EQUITY_SCREENER_EQ_MAP, ETF_SCREENER_EQ_MAP, FUND_SCREENER_EQ_MAP):
        eq_map.update(mapping)
    enum_fields = set(EXTRA_ENUM_FIELDS.get(asset, []))

    out: list[dict] = []
    for category in sorted(EXTRA_SCREENER_FIELDS[asset]):
        category_label = EXTRA_CATEGORY_LABELS.get(
            category, category.replace("_", " ").title()
        )
        for field in sorted(EXTRA_SCREENER_FIELDS[asset][category]):
            entry: dict[str, Any] = {
                "field": field,
                "label": EXTRA_FIELD_LABELS.get(field, _field_label(field)),
                "category": category,
                "category_label": category_label,
            }
            if field in enum_fields and field in eq_map:
                entry["type"] = "enum"
                entry["values"] = _value_options(field, eq_map)
            elif field in EXTRA_NUMBER_FIELDS:
                entry["type"] = "number"
            else:
                entry["type"] = "text"
            out.append(entry)
    return out


def build_screener_catalog() -> dict:
    """Build the full field/value catalog for every screenable asset type."""
    from yfinance.const import (
        EQUITY_SCREENER_EQ_MAP,
        EQUITY_SCREENER_FIELDS,
        ETF_SCREENER_EQ_MAP,
        ETF_SCREENER_FIELDS,
        FUND_SCREENER_EQ_MAP,
        FUND_SCREENER_FIELDS,
    )

    fields = {
        "equity": _fields_for(EQUITY_SCREENER_FIELDS, EQUITY_SCREENER_EQ_MAP),
        "etf": _fields_for(ETF_SCREENER_FIELDS, ETF_SCREENER_EQ_MAP),
        "fund": _fields_for(FUND_SCREENER_FIELDS, FUND_SCREENER_EQ_MAP),
        "index": _extra_fields_for("index"),
        "future": _extra_fields_for("future"),
    }
    sort_fields = {
        asset: [
            f["field"]
            for f in entries
            if f["type"] == "number" or f["field"].endswith("price")
        ]
        for asset, entries in fields.items()
    }
    return {
        "asset_types": _ASSET_TYPES,
        "fields": fields,
        "operators": _OPERATORS,
        "sort_types": _SORT_TYPES,
        "sort_fields": sort_fields,
    }


_DEFAULT_OPERANDS = {
    "EQUITY": {"operator": "EQ", "operands": ["region", "us"]},
    "ETF": {"operator": "EQ", "operands": ["region", "us"]},
    "MUTUALFUND": {"operator": "GTE", "operands": ["performanceratingoverall", 1]},
    "INDEX": {"operator": "EQ", "operands": ["region", "us"]},
    "FUTURE": {"operator": "EQ", "operands": ["region", "us"]},
}

_DEFAULT_SORT_FIELDS = {
    "EQUITY": "intradaymarketcap",
    "ETF": "fundnetassets",
    "MUTUALFUND": "performanceratingoverall",
    "INDEX": "percentchange",
    "FUTURE": "percentchange",
}


def _filter_operand(item: dict) -> dict | None:
    """Translate one builder filter into a Yahoo screener leaf operand."""
    field = item.get("field")
    operator = str(item.get("operator", "")).lower()
    value = item.get("value")
    if not field or value in (None, "", []):
        return None
    if operator == "is-in":
        values = value if isinstance(value, list) else str(value).split(",")
        values = [v.strip() for v in values if str(v).strip()]
        return {"operator": "is-in", "operands": [field, *values]} if values else None
    if operator in ("gt", "gte", "lt", "lte"):
        return {"operator": operator.upper(), "operands": [field, float(value)]}
    if operator == "btwn" and isinstance(value, list) and len(value) == 2:
        return {
            "operator": "BTWN",
            "operands": [field, float(value[0]), float(value[1])],
        }
    return {"operator": "EQ", "operands": [field, value]}


def screener_body_from_config(config: dict) -> dict:
    """Translate a builder config into a Yahoo screener request body.

    The config shape is ``{type, limit, sort_field, sort_type, filters:[{field,
    operator, value, join}]}`` where ``operator`` is gt/gte/lt/lte/btwn/eq/is-in
    and ``join`` (``and``/``or``) joins a filter with everything before it,
    building a left-associative query tree. With no filters the body falls back to
    a US-market default so the screener returns the broad universe.
    """
    quote_types = {
        "equity": "EQUITY",
        "etf": "ETF",
        "fund": "MUTUALFUND",
        "mutualfund": "MUTUALFUND",
        "index": "INDEX",
        "future": "FUTURE",
    }
    quote_type = quote_types.get(str(config.get("type", "equity")).lower(), "EQUITY")

    leaves: list[tuple[str, dict]] = []
    for item in config.get("filters") or []:
        operand = _filter_operand(item)
        if operand is not None:
            join = "or" if str(item.get("join", "and")).lower() == "or" else "and"
            leaves.append((join, operand))

    if not leaves:
        query: dict = {"operator": "AND", "operands": [_DEFAULT_OPERANDS[quote_type]]}
    else:
        query = leaves[0][1]
        for join, operand in leaves[1:]:
            query = {"operator": join.upper(), "operands": [query, operand]}

    return {
        "offset": 0,
        "size": int(config.get("limit") or 100),
        "sortField": config.get("sort_field") or _DEFAULT_SORT_FIELDS[quote_type],
        "sortType": str(config.get("sort_type") or "DESC").upper(),
        "quoteType": quote_type,
        "query": query,
        "userId": "",
        "userIdType": "guid",
    }
