"""HKEX Options Chains fetcher (OptionsChains standard model).

`symbol` is an HKEX derivatives **product code** (e.g. ``HSI``, ``HHI``, ``HTI``
for index products; or the 3-letter SSO ticker like ``TCH``, ``HKB`` — *not*
the 5-digit stock code). See `DERIVATIVE_PRODUCTS` and `stock_derivatives_list`.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.options_chains import (
    OptionsChainsData,
    OptionsChainsQueryParams,
)
from pydantic import Field

from openbb_hkex.models.futures_curve import DerivativeProductCode
from openbb_hkex.utils.calendar import (
    get_calendar,
    last_trading_day,
)
from openbb_hkex.utils.client import (
    DERIVATIVE_PRODUCTS,
    OPTION_UNDERLYINGS_ENDPOINT,
    call_widget,
    parse_int,
    parse_num,
    to_hk_symbol,
)
from openbb_hkex.utils.daily_report import (
    index_point_value,
    stock_option_settlements,
)

_CONTRACT_TYPE_MAP = {"standard": 1, "variant": 2}

_PRODUCT_TO_INDEX_RIC: dict[str, str] = {
    "HSI": ".HSI",
    "MHI": ".HSI",
    "PHS": ".HSI",
    "XHS": ".HSI",
    "HHI": ".HSCE",
    "MCH": ".HSCE",
    "PHH": ".HSCE",
    "XHH": ".HSCE",
    "HTI": ".HSTECH",
    "PTE": ".HSTECH",
}


async def _index_underlying_level(ric: str) -> float | None:
    """Return the current level of an index from the market-overview snapshot."""
    data = await call_widget("getmarketoverview")
    for i in data.get("indices") or []:
        if i.get("ric") == ric:
            return parse_num(i.get("ls")) or parse_num(i.get("hc"))
    return None


async def _stock_option_underlying(ats: str) -> tuple[int | None, float | None]:
    """Return (board_lot, current_price) for a single-stock option underlying."""
    roster = (await call_widget("getstockderivativeslist", type=2)).get("stocklist", [])
    sym = next(
        (r.get("sym") for r in roster if (r.get("cd") or "").upper() == ats.upper()),
        None,
    )
    if not sym:
        return None, None
    q = (await call_widget("getequityquote", sym=to_hk_symbol(str(sym)))).get(
        "quote", {}
    )
    price = parse_num(q.get("ls")) or parse_num(q.get("hc"))
    return parse_int(q.get("lot")), price


class HkexOptionsChainsQueryParams(OptionsChainsQueryParams):
    """HKEX Options Chains query.

    For single-stock options, pass the 3-letter ATS ticker as ``symbol``
    (the Literal validation is skipped for SSO codes — see
    `obb.hkex.stock_derivatives(kind='options')` to look one up).
    """

    symbol: DerivativeProductCode | str = Field(
        description="HKEX derivatives product code (e.g. HSI, HHI, HTI) or a "
        "3-letter single-stock option ticker (e.g. TCH for Tencent).",
        json_schema_extra={
            "hkex": {
                "x-widget_config": {
                    "type": "endpoint",
                    "optionsEndpoint": OPTION_UNDERLYINGS_ENDPOINT,
                    "style": {"popupWidth": 600},
                }
            }
        },
    )
    contract_type: Literal["standard", "variant"] = Field(
        default="standard",
        description="standard = standard contract; variant = flex/weekly where listed.",
        json_schema_extra={"choices": ["standard", "variant"]},
    )


class HkexOptionsChainsData(OptionsChainsData):
    """HKEX Options Chains data — list-of-lists OptionsChainsProperties shape."""

    point_value: list[float | None] = Field(
        default_factory=list,
        description="Currency value of one point/unit move per contract "
        "(e.g. HK$50 per HSI index point; HK$1 per share for stock options).",
    )
    point_value_currency: list[str | None] = Field(
        default_factory=list,
        description="Currency of the point value (HKD, USD, ...).",
    )


class HkexOptionsChainsFetcher(
    Fetcher[HkexOptionsChainsQueryParams, HkexOptionsChainsData]
):
    """HKEX Options Chains fetcher.

    Returns a single :class:`HkexOptionsChainsData` instance whose every field
    is a parallel list (one entry per (expiry, strike, call|put) row).
    """

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HkexOptionsChainsQueryParams:
        """Transform the query parameters."""
        return HkexOptionsChainsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: HkexOptionsChainsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Extract the data from the HKEX endpoints."""
        ats = query.symbol
        ctype = _CONTRACT_TYPE_MAP[query.contract_type]
        cons = (await call_widget("getoptioncontractlist", ats=ats, type=ctype)).get(
            "conlist", []
        )

        async def _fetch_one(con: dict) -> tuple[dict, dict]:
            probe = await call_widget(
                "getderivativesoption",
                ats=ats,
                type=ctype,
                con=con["id"],
            )
            lo = (probe.get("min") or "").replace(",", "")
            hi = (probe.get("max") or "").replace(",", "")
            if not (lo and hi):
                return con, probe
            full = await call_widget(
                "getderivativesoption",
                ats=ats,
                type=ctype,
                con=con["id"],
                fr=lo,
                to=hi,
            )
            return con, full

        results = await asyncio.gather(*(_fetch_one(c) for c in cons))
        await get_calendar()

        settle_map: dict[tuple, dict] = {}
        if ats in DERIVATIVE_PRODUCTS:
            contract_size: int | None = 1
            pv = await index_point_value(ats)
            point_value = pv["value"] if pv else None
            pv_ccy = pv["currency"] if pv else None
            ric = _PRODUCT_TO_INDEX_RIC.get(ats)
            underlying_lvl = await _index_underlying_level(ric) if ric else None
        else:
            contract_size, underlying_lvl = await _stock_option_underlying(ats)
            point_value = 1.0
            pv_ccy = "HKD"
            settle_map = await stock_option_settlements(ats)
            under = settle_map.get(("underlying",), {}).get("close")
            if under is not None:
                underlying_lvl = under

        # Report expiries grouped by (year, month) — used only as a fallback
        # for contract months beyond the published calendar horizon, and only
        # when that month has a single (unambiguous) expiry in the report.
        report_months: dict[tuple[int, int], list[date]] = {}
        for k in settle_map:
            if k[0] == "underlying":
                continue
            report_months.setdefault((k[0].year, k[0].month), [])
            if k[0] not in report_months[(k[0].year, k[0].month)]:
                report_months[(k[0].year, k[0].month)].append(k[0])

        exp_map: dict[str, date | None] = {}
        for con, _ in results:
            ltd = await last_trading_day(ats, con["id"])
            if ltd is None and len(con["id"]) >= 6:
                cand = report_months.get((int(con["id"][2:]), int(con["id"][:2])), [])
                ltd = cand[0] if len(cand) == 1 else None
            exp_map[con["id"]] = ltd

        econ = {
            "contract_size": contract_size,
            "point_value": point_value,
            "point_value_currency": pv_ccy,
            "underlying_price": underlying_lvl,
        }

        def _settle(ltd: date | None, strike: Any, side: str) -> dict:
            sk = parse_num(strike)
            if ltd is None or sk is None:
                return {}
            s = settle_map.get((ltd, round(sk, 3), side)) or {}
            return {f"_{k}": v for k, v in s.items()}

        flat: list[dict] = []
        for con, chain in results:
            ltd = exp_map[con["id"]]
            for row in chain.get("optionlist") or []:
                strike = row.get("strike")
                for side, key in (("call", "c"), ("put", "p")):
                    flat.append(
                        {
                            "con_id": con["id"],
                            "month": con["mon"],
                            "ltd": ltd,
                            "strike": strike,
                            "side": side,
                            **econ,
                            **_settle(ltd, strike, side),
                            **(row.get(key) or {}),
                        }
                    )
        return flat

    @staticmethod
    def transform_data(
        query: HkexOptionsChainsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> HkexOptionsChainsData:
        """Transform the raw data into the model."""
        n = len(data)
        out: dict[str, list] = {
            "underlying_symbol": [query.symbol] * n,
            "contract_symbol": [],
            "expiration": [],
            "strike": [],
            "option_type": [],
            "contract_size": [],
            "underlying_price": [],
            "point_value": [],
            "point_value_currency": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "bid": [],
            "ask": [],
            "last_trade_price": [],
            "volume": [],
            "open_interest": [],
            "implied_volatility": [],
        }
        for r in data:
            con_id = r["con_id"]
            ltd = r.get("ltd")
            if ltd is None:
                mm, yyyy = int(con_id[:2]), int(con_id[2:])
                ltd = date(yyyy, mm, 1)
            strike = parse_num(r.get("strike"))
            side = r["side"]
            out["contract_symbol"].append(
                f"{query.symbol}{con_id}{'C' if side == 'call' else 'P'}{int(strike) if strike else ''}"
            )
            out["expiration"].append(ltd)
            out["strike"].append(strike or 0.0)
            out["option_type"].append(side)
            out["contract_size"].append(r.get("contract_size"))
            out["underlying_price"].append(r.get("underlying_price"))
            out["point_value"].append(r.get("point_value"))
            out["point_value_currency"].append(r.get("point_value_currency"))
            out["open"].append(r.get("_open"))
            out["high"].append(r.get("_high"))
            out["low"].append(r.get("_low"))
            out["close"].append(r.get("_close"))
            out["bid"].append(parse_num(r.get("bd")))
            out["ask"].append(parse_num(r.get("as")))
            out["last_trade_price"].append(parse_num(r.get("ls")))
            live_vol = parse_int(r.get("vo"))
            out["volume"].append(live_vol if live_vol is not None else r.get("_volume"))
            out["open_interest"].append(parse_int(r.get("oi")))
            out["implied_volatility"].append(parse_num(r.get("iv")))
        return HkexOptionsChainsData(**out)  # ty: ignore[invalid-argument-type]
