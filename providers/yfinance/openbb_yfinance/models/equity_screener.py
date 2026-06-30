"""YFinance Equity Screener Model."""

from typing import Any, Literal

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_screener import (
    EquityScreenerData,
    EquityScreenerQueryParams,
)
from openbb_core.provider.utils.country_utils import Country
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field, field_validator

from openbb_yfinance.utils.helpers import PREDEFINED_SCREENERS
from openbb_yfinance.utils.references import (
    COUNTRIES,
    EXCHANGES,
    INDUSTRIES,
    INDUSTRY_MAP,
    PEER_GROUPS,
    SECTOR_MAP,
    SECTORS,
    Exchanges,
    YFPredefinedScreenerData,
    get_industry_sector,
)
from openbb_yfinance.utils.screener_presets import get_bundled_presets

_PRESET_CHOICES = list(get_bundled_presets()) + PREDEFINED_SCREENERS


def _screener_eq_values(field: str) -> list[str]:
    """Return the sorted union of a Yahoo enum field's values across the ETF and fund maps."""
    try:
        from yfinance.const import ETF_SCREENER_EQ_MAP, FUND_SCREENER_EQ_MAP
    except Exception:  # noqa: BLE001
        return []
    values: set[str] = set()
    for mapping in (ETF_SCREENER_EQ_MAP, FUND_SCREENER_EQ_MAP):
        raw = mapping.get(field)
        if isinstance(raw, dict):
            for group in raw.values():
                values.update(str(v) for v in group)
        elif raw:
            values.update(str(v) for v in raw)
    return sorted(values)


def _fund_choices(field: str) -> list[str]:
    """Return current fund family/category choices from the build-time cache.

    Falls back to yfinance's stale enum maps only when the cache has not been
    generated, so the dropdowns offer values Yahoo actually matches today.
    """
    from openbb_yfinance.utils import screener_cache

    getter = (
        screener_cache.fund_families
        if field == "fundfamilyname"
        else screener_cache.fund_categories
    )
    values: set[str] = set()
    for asset_type in ("etf", "fund"):
        values.update(getter(asset_type))
    return sorted(values) if values else _screener_eq_values(field)


_FUND_ISSUERS = _fund_choices("fundfamilyname")
_FUND_STYLES = _fund_choices("categoryname")


def _match_choice(value: Any, choices: list[str], field: str) -> str:
    """Normalize an enum input to its canonical choice, matched case-insensitively."""
    text = str(value).strip()
    if text in choices:
        return text
    lowered = {c.lower(): c for c in choices}
    if text.lower() in lowered:
        return lowered[text.lower()]
    from difflib import get_close_matches

    hint = get_close_matches(text, choices, n=5)
    suggestion = f" Did you mean: {', '.join(hint)}?" if hint else ""
    raise ValueError(f"'{value}' is not a valid {field}.{suggestion}")


class YFinanceEquityScreenerQueryParams(EquityScreenerQueryParams):
    """YFinance Equity Screener Query."""

    __json_schema_extra__ = {
        "country": {
            "multiple_items_allowed": False,
            "choices": COUNTRIES,
        },
        "exchange": {
            "multiple_items_allowed": False,
            "choices": EXCHANGES,
        },
        "sector": {
            "multiple_items_allowed": False,
            "choices": list(SECTOR_MAP),
        },
        "industry": {
            "multiple_items_allowed": False,
            "choices": INDUSTRIES,
        },
        "preset": {
            "multiple_items_allowed": False,
            "choices": _PRESET_CHOICES,
        },
        "asset_type": {
            "multiple_items_allowed": False,
            "choices": ["equity", "etf", "fund", "index", "future"],
        },
        "fund_issuer": {
            "multiple_items_allowed": False,
            "choices": _FUND_ISSUERS,
        },
        "fund_style": {
            "multiple_items_allowed": False,
            "choices": _FUND_STYLES,
        },
    }

    asset_type: Literal["equity", "etf", "fund", "index", "future"] = Field(
        default="equity",
        description="Asset type to screen. Selects the Yahoo Finance query universe;"
        " 'fund' maps to mutual funds. Sector and industry apply to 'equity';"
        " fund_issuer and fund_style apply to 'etf' and 'fund'.",
    )
    universe: bool = Field(
        default=False,
        description="Pull every matching symbol for the given filters, bypassing the"
        " market-cap/price/volume floors and the liquidity filter. Use it to enumerate"
        " a full region/exchange/sector/industry/fund-issuer/fund-style universe."
        " Requires at least one filter.",
    )
    fund_issuer: str | None = Field(
        default=None,
        description="Filter funds and ETFs by fund family (issuer), e.g. 'Vanguard'.",
    )
    fund_style: str | None = Field(
        default=None,
        description="Filter funds and ETFs by category (style), e.g. 'Large Growth'.",
    )

    preset: str | None = Field(
        default=None,
        description="Screener preset to run — either a Yahoo Finance predefined"
        + " screener (e.g. 'most_actives', 'day_gainers', 'undervalued_large_caps')"
        + " or the name of a screener preset INI file. The user presets directory is"
        + " the 'OPENBB_YFINANCE_PRESETS_DIRECTORY' environment variable, or"
        + " 'yfinance_presets_directory' / '[yfinance] presets_directory' in"
        + " openbb.toml, defaulting to '<data_directory>/presets/yfinance/'. Bundled"
        + " presets are copied there on first use and any user preset of the same name"
        + " takes precedence. When set, the preset defines the full query and the other"
        + " filter parameters are ignored.",
    )
    config: str | None = Field(
        default=None,
        description="A JSON screener configuration built by the screener-builder"
        + " widget: {type, limit, sort_field, sort_type, filters:[{field, operator,"
        + " value}]}. When set, it defines the full query and the other filter"
        + " parameters are ignored.",
    )
    country: str | None = Field(
        default="us",
        description="Filter by country. Accepts ISO 3166-1 alpha-2 codes (e.g., 'US', 'DE'), "
        "alpha-3 codes (e.g., 'USA'), country names (e.g., 'United States'), or 'all' for all countries.",
    )
    exchange: Exchanges | None = Field(
        default=None,
        description="Filter by exchange.",
    )
    sector: SECTORS | None = Field(default=None, description="Filter by sector.")
    industry: str | None = Field(
        default=None,
        description="Filter by industry.",
    )
    mktcap_min: int | None = Field(
        default=500000000,
        description="Filter by market cap greater than this value. Default is 500M.",
    )
    mktcap_max: int | None = Field(
        default=None,
        description="Filter by market cap less than this value.",
    )
    price_min: float | None = Field(
        default=5,
        description="Filter by price greater than this value. Default is, 5",
    )
    price_max: float | None = Field(
        default=None,
        description="Filter by price less than this value.",
    )
    volume_min: int | None = Field(
        default=10000,
        description="Filter by volume greater than this value. Default is, 10K",
    )
    volume_max: int | None = Field(
        default=None,
        description="Filter by volume less than this value.",
    )
    beta_min: float | None = Field(
        default=None,
        description="Filter by a beta greater than this value.",
    )
    beta_max: float | None = Field(
        default=None,
        description="Filter by a beta less than this value.",
    )
    limit: int | None = Field(
        default=200,
        description="Limit the number of results returned. Default is, 200. Set to, 0, for all results.",
    )

    @field_validator("country", mode="before")
    @classmethod
    def _validate_country(cls, v):
        """Validate and normalize country input."""
        if v is None or v == "all":
            return v
        if isinstance(v, Country):
            country_code = v.alpha_2.lower()
        else:
            try:
                country_code = Country(v).alpha_2.lower()
            except ValueError:
                country_code = v.strip().lower()
        if country_code not in COUNTRIES:
            raise ValueError(
                f"Country '{v}' ({country_code.upper()}) is not supported by YFinance. "
                f"Valid options: {', '.join(sorted(COUNTRIES))}",
            )
        return country_code

    @field_validator("asset_type", mode="before")
    @classmethod
    def _validate_asset_type(cls, v):
        """Normalize asset-type synonyms to a canonical value."""
        if v is None:
            return "equity"
        text = str(v).strip().lower().replace(" ", "").replace("_", "")
        aliases = {
            "mutualfund": "fund",
            "mutualfunds": "fund",
            "funds": "fund",
            "etfs": "etf",
            "equities": "equity",
            "stock": "equity",
            "stocks": "equity",
            "indices": "index",
            "futures": "future",
        }
        return aliases.get(text, text)

    @field_validator("fund_issuer", mode="before")
    @classmethod
    def _validate_fund_issuer(cls, v):
        """Normalize and validate the fund issuer against the Yahoo fund-family choices."""
        return None if v is None else _match_choice(v, _FUND_ISSUERS, "fund_issuer")

    @field_validator("fund_style", mode="before")
    @classmethod
    def _validate_fund_style(cls, v):
        """Normalize and validate the fund style against the Yahoo category choices."""
        return None if v is None else _match_choice(v, _FUND_STYLES, "fund_style")


class YFinanceEquityScreenerData(EquityScreenerData, YFPredefinedScreenerData):
    """YFinance Equity Screener Data."""

    symbol: str = Field(
        description="The ticker symbol.",
        json_schema_extra={
            "x-widget_config": {
                "renderFn": "cellOnClick",
                "renderFnParams": {
                    "actionType": "groupBy",
                    "groupBy": {"paramName": "symbol", "valueField": "symbol"},
                },
            }
        },
    )


class YFinanceEquityScreenerFetcher(
    Fetcher[YFinanceEquityScreenerQueryParams, list[YFinanceEquityScreenerData]],
):
    """YFinance Equity Screener Fetcher."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> YFinanceEquityScreenerQueryParams:
        """Transform query."""
        sector = params.get("sector")
        industry = params.get("industry")

        if industry and sector:
            sec = get_industry_sector(industry)
            if sec and sec != sector:
                choices = "\n    ".join(sorted(INDUSTRY_MAP[sector]))
                raise OpenBBError(
                    ValueError(
                        f"Industry {industry} does not belong to sector {sector}."
                        " Valid choices are:" + "\n\n    " + f"{choices}",
                    ),
                )
        elif industry and not sector:
            choices = "\n".join(INDUSTRIES)
            sector = get_industry_sector(industry)
            if not sector:
                raise OpenBBError(
                    ValueError(
                        f"Industry {industry} not found. Valid choices are:\n{choices}",
                    ),
                )
            _industry = INDUSTRY_MAP[sector][industry]

            if _industry not in PEER_GROUPS:
                params["sector"] = get_industry_sector(industry)

        return YFinanceEquityScreenerQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: YFinanceEquityScreenerQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the raw data."""
        from openbb_yfinance.utils.helpers import (
            enrich_fund_metadata,
            get_custom_screener,
            get_defined_screener,
        )

        if query.config:
            import json

            from openbb_yfinance.utils.screener_catalog import (
                screener_body_from_config,
            )

            try:
                cfg = json.loads(query.config)
            except (ValueError, TypeError) as exc:
                raise OpenBBError(
                    ValueError(f"Invalid screener config JSON: {exc}")
                ) from exc
            response = await get_custom_screener(
                body=screener_body_from_config(cfg),
                limit=query.limit
                if query.limit and query.limit not in (0, None)
                else None,
            )
            if not response:
                raise EmptyDataError("No results found for the configuration.")
            return await enrich_fund_metadata(response)

        if query.preset:
            from openbb_yfinance.utils.helpers import PREDEFINED_SCREENERS

            limit = (
                query.limit if query.limit and query.limit not in (0, None) else None
            )

            if query.preset in PREDEFINED_SCREENERS:
                response = await get_defined_screener(
                    name=query.preset,
                    limit=limit,
                    all_fields=True,
                )
                if not response:
                    raise EmptyDataError(
                        f"No results found for the predefined screener '{query.preset}'."
                    )
                return await enrich_fund_metadata(response)

            from openbb_yfinance.utils.screener_presets import (
                build_screener_body,
                get_preset_choices,
            )

            data_dir = (kwargs.get("preferences") or {}).get("data_directory")
            choices = get_preset_choices(data_dir)
            if query.preset not in choices:
                raise OpenBBError(
                    ValueError(
                        f"Preset '{query.preset}' not found. Valid choices are: "
                        + ", ".join(sorted(choices))
                    )
                )
            payload = build_screener_body(choices[query.preset])
            response = await get_custom_screener(
                body=payload,
                limit=limit,
            )
            if not response:
                raise EmptyDataError("No results found for the preset.")
            return await enrich_fund_metadata(response)

        operands: list = []

        quote_types = {
            "equity": "EQUITY",
            "etf": "ETF",
            "fund": "MUTUALFUND",
            "index": "INDEX",
            "future": "FUTURE",
        }
        quote_type = quote_types[query.asset_type]

        if query.exchange is not None:
            operands.append(
                {"operator": "eq", "operands": ["exchange", query.exchange.upper()]},
            )
            query.country = "all"

        if query.country and query.country != "all":
            operands.append({"operator": "EQ", "operands": ["region", query.country]})

        if query.asset_type == "equity":
            if query.sector is not None:
                sector = SECTOR_MAP[query.sector]
                operands.append({"operator": "EQ", "operands": ["sector", sector]})

            if query.industry is not None:
                sector = (
                    query.sector
                    if query.sector is not None
                    else get_industry_sector(query.industry)
                )
                industry = INDUSTRY_MAP[sector][query.industry]
                if industry in PEER_GROUPS:
                    operands.append(
                        {"operator": "EQ", "operands": ["peer_group", industry]},
                    )
                else:
                    operands.append(
                        {"operator": "EQ", "operands": ["industry", industry]}
                    )

        if query.asset_type in ("etf", "fund"):
            if query.fund_issuer is not None:
                operands.append(
                    {
                        "operator": "EQ",
                        "operands": ["fundfamilyname", query.fund_issuer],
                    }
                )
            if query.fund_style is not None:
                operands.append(
                    {"operator": "EQ", "operands": ["categoryname", query.fund_style]}
                )

        if not query.universe and query.asset_type == "equity":
            if query.mktcap_min is not None:
                operands.append(
                    {
                        "operator": "gt",
                        "operands": ["intradaymarketcap", query.mktcap_min],
                    },
                )

            if query.mktcap_max is not None:
                operands.append(
                    {
                        "operator": "lt",
                        "operands": ["intradaymarketcap", query.mktcap_max],
                    },
                )

            if query.price_min is not None:
                operands.append(
                    {"operator": "gt", "operands": ["intradayprice", query.price_min]},
                )

            if query.price_max is not None:
                operands.append(
                    {"operator": "lt", "operands": ["intradayprice", query.price_max]},
                )

            if query.volume_min is not None:
                operands.append(
                    {"operator": "gt", "operands": ["dayvolume", query.volume_min]},
                )

            if query.volume_max is not None:
                operands.append(
                    {"operator": "lt", "operands": ["dayvolume", query.volume_max]},
                )

            if query.beta_min is not None:
                operands.append(
                    {"operator": "gt", "operands": ["beta", query.beta_min]}
                )

            if query.beta_max is not None:
                operands.append(
                    {"operator": "lt", "operands": ["beta", query.beta_max]}
                )

        if not operands:
            raise OpenBBError(
                ValueError(
                    "Provide at least one filter (exchange, country, sector,"
                    " industry, fund_issuer, or fund_style) to run the screener."
                )
            )

        payload = {
            "offset": 0,
            "size": 100,
            "sortField": "percentchange",
            "sortType": "DESC",
            "quoteType": quote_type,
            "query": {
                "operands": operands,
                "operator": "AND",
            },
            "userId": "",
            "userIdType": "guid",
        }

        response = await get_custom_screener(
            body=payload,
            limit=query.limit if query.limit and query.limit not in (0, None) else None,
            keep_illiquid=query.universe,
        )

        if not response:
            raise EmptyDataError("No results found for the combination of filters.")

        return await enrich_fund_metadata(response)

    @staticmethod
    def transform_data(
        query: YFinanceEquityScreenerQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[YFinanceEquityScreenerData]:
        """Transform the data."""
        return [YFinanceEquityScreenerData(**d) for d in data]
