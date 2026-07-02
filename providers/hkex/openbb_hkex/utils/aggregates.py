"""Cached HKEX market-universe feeds and HSIC/CSIC classification."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from openbb_hkex.models._reference import scaled
from openbb_hkex.utils.client import call_widget

PROGRAMME_HKEX = "HKEX"
PROGRAMME_CONNECT = "Stock Connect"
PRIMARY_CCY = {PROGRAMME_HKEX: "HKD", PROGRAMME_CONNECT: "CNY"}

_TTL_SECONDS = 86_400  # one calendar day
_cache: dict[str, dict[str, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}


def _fresh(key: str) -> bool:
    entry = _cache.get(key)
    return bool(entry and (time.time() - entry["t"] < _TTL_SECONDS))


def _lock(key: str) -> asyncio.Lock:
    lock = _locks.get(key)
    if lock is None:
        lock = _locks[key] = asyncio.Lock()
    return lock


def _norm_row(r: dict, programme: str, venue: str) -> dict[str, Any]:
    """Normalize a screener row into a common universe record."""
    return {
        "symbol": str(r.get("sym") or "").zfill(5)
        if programme == PROGRAMME_HKEX
        else str(r.get("sym") or ""),
        "ric": r.get("ric"),
        "name": r.get("nm"),
        "programme": programme,
        "venue": venue,
        "currency": r.get("ccy"),
        "last_price": r.get("ls"),
        "change_pct": r.get("pc"),
        "pe": r.get("pe"),
        "dividend_yield": r.get("yld"),
        "market_cap": scaled(r.get("mktcap"), r.get("mktcap_u")),
        "turnover": scaled(r.get("am"), r.get("am_u")),
        "suspended": bool(r.get("suspend")),
    }


def is_rmb_counter(symbol: str) -> bool:
    """Return True for an HKEX RMB dual-trading counter (codes 80000-89999)."""
    try:
        return 80000 <= int(symbol) <= 89999
    except (TypeError, ValueError):
        return False


async def get_equity_universe() -> list[dict[str, Any]]:
    """Every HKEX-listed equity, tagged Main Board / GEM. Cached for a day."""
    if _fresh("equity"):
        return _cache["equity"]["v"]
    async with _lock("equity"):
        if _fresh("equity"):
            return _cache["equity"]["v"]
        rows: list[dict[str, Any]] = []
        for market, venue in (("MAIN", "Main Board"), ("GEM", "GEM")):
            data = await call_widget("getequityfilter", market=market, all="1")
            rows.extend(
                _norm_row(r, PROGRAMME_HKEX, venue)
                for r in data.get("stocklist", []) or []
            )
        _cache["equity"] = {"t": time.time(), "v": rows}
        return rows


async def get_ashare_universe() -> list[dict[str, Any]]:
    """Every Stock Connect eligible A-share (Shanghai / Shenzhen). Cached daily."""
    if _fresh("ashare"):
        return _cache["ashare"]["v"]
    async with _lock("ashare"):
        if _fresh("ashare"):
            return _cache["ashare"]["v"]
        data = await call_widget("getasharefilter", all="1")
        rows = [
            _norm_row(r, PROGRAMME_CONNECT, (r.get("exch") or "").title() or "Connect")
            for r in data.get("stocklist", []) or []
        ]
        _cache["ashare"] = {"t": time.time(), "v": rows}
        return rows


SECTOR_SERIES_SLUGS: list[str] = [
    s.strip()
    for s in os.environ.get("HKEX_SECTOR_SERIES_SLUGS", "industry,hsci").split(",")
    if s.strip()
]


async def get_sector_map() -> dict[str, dict[str, Any]]:
    """Map HKEX equity symbols to their Hang Seng sector (HSIC top level)."""
    if _fresh("sector"):
        return _cache["sector"]["v"]
    async with _lock("sector"):
        if _fresh("sector"):
            return _cache["sector"]["v"]

        # Local import to avoid a heavy import at module load.
        from openbb_hkex.utils.index_sources import (
            fetch_sector_membership,
        )

        out: dict[str, dict[str, Any]] = {}
        for slug in SECTOR_SERIES_SLUGS:
            try:
                members = await fetch_sector_membership(slug)
            except Exception:  # noqa: BLE001,S112 — try the next candidate slug
                continue
            if members:
                for m in members:
                    out.setdefault(m["symbol"].zfill(5), {"sector": m["sector"]})
                break

        _cache["sector"] = {"t": time.time(), "v": out}
        return out


async def prime_caches() -> None:
    """Best-effort background warm-up of the bulk feeds (call at startup).

    Two requests only — never crawls per-symbol.
    """
    try:  # noqa: SIM105 — explicit best-effort priming
        await asyncio.gather(get_equity_universe(), get_ashare_universe())
    except Exception:  # noqa: BLE001,S110 — priming is best-effort
        pass
