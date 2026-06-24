# OpenBB Yahoo Finance Provider

This extension integrates [Yahoo! Finance](https://finance.yahoo.com/) into the OpenBB
Platform. It is a **hybrid extension** — a single package that registers as both:

- an `openbb_provider_extension`, contributing ~80 Yahoo Finance fetchers, and
- an `openbb_core_extension`, contributing a router with namespaced commands,
  interactive [PyWry](https://github.com/OpenBB-finance/pywry) widgets, a bundled
  OpenBB Workspace app, and an embedded MCP server.

Because of this, it works **standalone** (no other OpenBB data extensions required) and
also slots cleanly into a **full OpenBB Platform** install.

## Installation

```bash
pip install openbb-yfinance
```

Runtime dependencies: `openbb-core`, `yfinance`, `pywry`, and `fastmcp`.

## Hybrid registration

Fetchers register under their **standard** OpenBB model names when the companion
extension is installed, and fall back to namespaced **`Yf*` aliases** when it is not.
For example `EquityHistorical` is provided when `openbb-equity` is present, otherwise the
same fetcher registers as `YfEquityHistorical` and the bundled `equity` router exposes
the command. The companion extensions detected at import time are:

`openbb-equity`, `openbb-etf`, `openbb-derivatives`, `openbb-index`, `openbb-crypto`,
`openbb-currency`, `openbb-news`, and `openbb-economy`.

The matching router namespace (`equity`, `etf`, `derivatives`, `index`, `crypto`,
`currency`, `news`, `economy`) is only mounted when that companion extension is *absent*,
so the hybrid never collides with a first-party OpenBB extension.

## Data coverage

| Area | Examples |
| --- | --- |
| Equity | historical prices, quotes, company profile, balance sheet / income / cash flow, key metrics, key executives, share statistics, dividends, EPS history, company filings |
| Screening & movers | equity screener with INI presets — bundled movers/discovery presets (gainers, losers, most active, undervalued growth & large caps, aggressive small caps, growth tech) plus Yahoo's predefined screeners |
| Estimates | analyst recommendations, price target & consensus, earnings / revenue / growth estimates, EPS trend & revisions |
| Funds & ETFs | fund info, holdings, allocation, historical, performance, ratings, risk; ETF info & historical |
| Ownership | institutional / mutual fund / major holders, insider trading, insider purchases, insider roster |
| Sectors & industries | sector overview, top companies & funds, industries; industry overview, top performing & top growth |
| Derivatives | options chains, futures curve, futures historical |
| Index / Crypto / Currency | available indices & index historical, crypto historical, currency historical |
| Calendars | earnings, IPO, splits, economic calendar, per-company calendar |
| Other | symbol search, news (with full article body), private companies (Crunchbase data) |

## Router namespaces

Always mounted: `funds`, `estimates`, `ownership`, `sectors`, `industry`, plus the
top-level `search`, `news`, `private_companies`, and `company_calendar` commands.

Mounted only when the matching companion extension is **not** installed: `equity`,
`etf`, `derivatives`, `index`, `crypto`, `currency`, `news`, `economy`.

## Interactive widgets

The router ships [PyWry](https://github.com/OpenBB-finance/pywry)-powered, interactive
widgets that open as a native desktop window, render inline in a Jupyter notebook, or
serve as an iframe in the OpenBB Workspace (on a headless host the command returns the
iframe endpoint instead of opening a window):

- `obb.yfinance.tv_widget(...)` — TradingView chart backed by a live Yahoo Finance
  datafeed (`GET /yfinance/tv_widget/view`).
- `obb.yfinance.screener_builder(...)` — interactive screener builder that syncs results
  back to a Workspace table (`GET /yfinance/screener_builder/view`).
- Asset Info overview widget (`GET /yfinance/asset_info/view`) — a styled, live header
  summary that adapts to the asset type.

A curated Workspace app is served from `GET /yfinance/apps.json`.

## Embedded MCP server

A [FastMCP](https://github.com/jlowin/fastmcp) server is mounted at `/yfinance/mcp` with
tools for agents.

Core market-data tools:

- `search_symbols`
- `get_price_history`
- `get_quote`
- `get_company_profile`
- `run_screener`

TradingView chart control tools:

- Generic dispatch: `tvchart_send_event`
- Symbol/interval/view: `tvchart_symbol_search`, `tvchart_compare`,
  `tvchart_change_interval`, `tvchart_time_range`, `tvchart_time_range_picker`,
  `tvchart_request_state`
- Indicators: `tvchart_add_indicator`, `tvchart_remove_indicator`,
  `tvchart_list_indicators`, `tvchart_show_indicators`
- Chart options/actions: `tvchart_chart_type`, `tvchart_toggle_dark_mode`,
  `tvchart_log_scale`, `tvchart_auto_scale`, `tvchart_show_settings`,
  `tvchart_drawing_tool`, `tvchart_undo`, `tvchart_redo`, `tvchart_screenshot`,
  `tvchart_fullscreen`

Dispatch and confirmation behavior:

- TV tools emit `tvchart:*` events using PyWry's event system.
- Dispatch attempts local in-process emit first; when unavailable, it falls back to
  the API bridge endpoint `POST /yfinance/mcp/tvchart/emit`.
- Many mutation tools accept `confirm` + `timeout` and can wait for local
  `tvchart:data-settled` confirmation.
- State and indicator tools can return confirmed snapshots when local response
  events (`tvchart:state-response`, `tvchart:list-indicators-response`) are
  captured before timeout.

## Development

This package follows the OpenBB v5 packaging standard ([`hatchling`](https://hatch.pypa.io/)
build backend, [`uv`](https://docs.astral.sh/uv/) for installs, `ruff` + `ty` for
linting and type-checking). Dev tooling is provided by the `dev` dependency group
(`openbb-devtools`).

```bash
# from providers/yfinance
uv build --no-sources                 # build sdist + wheel
uv pip install --group dev            # install dev tooling
ruff check openbb_yfinance tests      # lint
ruff format --check openbb_yfinance tests
ty check openbb_yfinance              # type-check
pytest tests                          # unit tests
```

Tests replay recorded cassettes via `pytest-recorder` (markers `record_curl` and
`record_http`) so they run offline; tests marked `integration` make live calls to Yahoo
Finance and are excluded from CI.

This provider is developed and distributed from the
[openbb-danglewood](https://github.com/deeleeramone/openbb-danglewood) repository.
