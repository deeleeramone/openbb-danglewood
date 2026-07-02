# openbb-hkex

OpenBB Platform provider extension for **Hong Kong Exchange** open data.

No API key needed — wraps the public `hkexwidget` JSONP endpoints, the daily
`ListOfSecurities.xlsx` master file, and the hkexnews.hk disclosure search.

Every command lives under its own `obb.hkex.*` namespace. The extension never
injects into the shared OpenBB namespaces (`equity` / `index` / `derivatives`),
so installing it alongside other providers is safe and collision-free.

## Install

```bash
pip install -e .
openbb-build   # only required for the Python `obb.` interface
```

## What you get

All commands are under `obb.hkex.*`:

```python
from openbb import obb

# Securities — reference, quote, profile, OHLCV (works for stocks, ETFs, REITs)
obb.hkex.search("tencent")                                   # search by name or code
obb.hkex.quote("00005")                                      # live quote (HSBC)
obb.hkex.info("00700")                                       # profile & listing details
obb.hkex.historical("00700", start_date="2026-04-01")        # daily OHLCV

# Indices — Hang Seng family + Stock Connect benchmarks
obb.hkex.index_snapshots(region="hk")                        # current index levels
obb.hkex.index_constituents("HSI")                           # constituents & weights

# Derivatives
obb.hkex.options_chains("HSI")                               # full chain, all expiries
obb.hkex.options_chains("TCH")                               # single-stock options (Tencent)
obb.hkex.futures_curve("HSI")                                # term structure
obb.hkex.futures_instruments("HSI")                          # listed contracts & metadata

# ETFs (use the HK-listed ETF code, e.g. 03037 = CSOP Hang Seng Index ETF)
obb.hkex.etf_holdings("03037")
obb.hkex.etf_nav("03037")
obb.hkex.etf_performance("03037")
obb.hkex.etf_tracking("03037")

# Reference & market structure
obb.hkex.securities_master(category="Real Estate Investment Trusts")
obb.hkex.securities_master(code="00700")
obb.hkex.derivative_products(category="Equity-Index")
obb.hkex.stock_derivatives(kind="options")                   # SSO ticker roster
obb.hkex.market_statistics(group_by="venue")                 # listed-universe aggregates
```

## Symbol conventions

| Endpoint | Symbol form | Example |
| --- | --- | --- |
| `quote` / `info` / `historical` / `search` / `etf_*` | 1–5 digit HKEX code (zero-padding optional), `XXXX.HK` also accepted | `700`, `00005`, `9988.HK` |
| `index_snapshots` | n/a | — |
| `index_constituents` | Hang Seng index code | `HSI`, `HSCEI`, `HSTECH` |
| `options_chains` / `futures_curve` / `futures_instruments` (index/FX/rate/commodity) | HKEX ATS code | `HSI`, `HHI`, `GDU`, `CUS` |
| `options_chains` (single-stock) | 3-letter ATS ticker | `TCH` (Tencent), `HKB` (HSBC) |

Run `obb.hkex.derivative_products()` or `obb.hkex.stock_derivatives()` to look up codes.

## Why HKEX is awkward (gotchas the extension handles for you)

- **Token**: the widget endpoints 403 without a `callback=` param and a session
  `token` scraped from any market-data HTML page. The token rotates and arrives
  pre-URL-encoded. Cached for 1h, auto-refreshed.
- **Option chains**: the API only returns 11 ATM strikes unless you pass
  `fr`/`to` *within* each expiry's listed strike range. `OptionsChains` probes
  every listed expiry, discovers each range, then fetches the full chain.
- **Disclosure search**: hkexnews is JSF-driven and needs a session cookie jar.
  The included template (`/search/titleSearchSearchPanel.html`) defines the real
  POST field names; the inline form on the visible page does not.
- **Stock options ≠ stock code**: SSOs/SSFs use a 3-letter HKEX ticker (e.g.
  `TCH` for Tencent), not the 5-digit code. Use `stock_derivatives` to map.

## OpenBB Workspace

The extension's router also serves the HKEX Workspace widgets (market statistics,
securities lookup with intraday sparklines, ticker cards, a TradingView advanced
chart over all equities/indices/futures, and the hkexnews filings viewer) and the
bundled app layout. They are mounted under `/hkex/*` whenever the extension is
served by `openbb-api`; no separate app process is required.

```bash
openbb-api
```

## Project structure

```
providers/hkex/
├── pyproject.toml
├── README.md
├── tests/                          # cassette-backed fetcher tests
└── openbb_hkex/
    ├── __init__.py                 # Provider() registration (hkex_provider)
    ├── hkex_router.py              # obb.hkex.* commands + Workspace widget routes
    ├── models/                     # Three-class fetchers per OpenBB model
    │   ├── equity_quote.py         │ equity_info.py    │ equity_search.py
    │   ├── equity_historical.py    │ index_snapshots.py │ index_historical.py
    │   ├── index_constituents.py   │ options_chains.py │ futures_curve.py
    │   ├── futures_historical.py   │ futures_instruments.py
    │   ├── etf_holdings.py         │ etf_nav.py        │ etf_performance.py
    │   ├── etf_tracking.py         │ securities_master.py
    │   ├── derivative_products.py  │ stock_derivatives.py
    │   ├── company_filings.py      │ market_turnover.py │ market_statistics.py
    │   └── _chart.py, _reference.py   # shared helpers
    ├── assets/apps.json            # bundled Workspace layout
    └── utils/                      # async client, data adapters, widget routes
        ├── client.py               │ aggregates.py     │ calendar.py
        ├── daily_report.py         │ etf_sources.py    │ index_sources.py
        ├── widgets.py              # Workspace widget routes (register_widgets)
        ├── udf.py                  # TradingView UDF datafeed routes
        └── apps.py                 # apps.json builder + widget-id remap
```
