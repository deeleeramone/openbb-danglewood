"""Static Yahoo screener field metadata for the ``index`` and ``future`` quote types.

Captured from the Yahoo screener fields endpoint
(``/v1/finance/screener/instrument/{index,future}/fields``); the locale-specific
``ranking`` fields are omitted. yfinance ships no query class or field map for these
quote types, so the builder relies on this catalog together with a direct screener
POST (see :func:`openbb_yfinance.utils.helpers.get_custom_screener`). Enum value
options are reused from the yfinance ``*_SCREENER_EQ_MAP`` tables, which share these
field identifiers (region, sector, industry, exchange).
"""

EXTRA_SCREENER_FIELDS = {
    "future": {
        "keystats": [
            "avgdailyvol3m",
            "dayvolume",
            "eodprice",
            "fiftytwowkpercentchange",
            "intradayprice",
            "intradaypricechange",
            "open_interest",
            "percentchange",
        ],
        "profile": ["exchange", "region"],
    },
    "index": {
        "keystats": [
            "avgdailyvol3m",
            "dayvolume",
            "eodprice",
            "fiftytwowkpercentchange",
            "intradayprice",
            "intradaypricechange",
            "percentchange",
        ],
        "profile": ["exchange", "region"],
    },
}

EXTRA_ENUM_FIELDS = {
    "future": ["exchange", "region"],
    "index": ["exchange", "region"],
}

EXTRA_CATEGORY_LABELS = {
    "keystats": "Price & Volume",
    "profile": "Profile",
}

EXTRA_FIELD_LABELS = {
    "avgdailyvol3m": "Average Daily 3m Volume",
    "dayvolume": "Day Volume",
    "eodprice": "EOD Price",
    "exchange": "Exchange",
    "fiftytwowkpercentchange": "52 Week % Change",
    "intradayprice": "Intraday Price",
    "intradaypricechange": "Change",
    "open_interest": "Open Interest",
    "percentchange": "% Change",
    "region": "Region",
    "ticker": "Symbol",
}

EXTRA_NUMBER_FIELDS = frozenset(
    [
        "avgdailyvol3m",
        "dayvolume",
        "eodprice",
        "fiftytwowkpercentchange",
        "intradayprice",
        "intradaypricechange",
        "open_interest",
        "percentchange",
    ]
)
