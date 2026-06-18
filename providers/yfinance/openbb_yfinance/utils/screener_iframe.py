"""Screener-builder iframe assembled from PyWry toolbar components."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_CSS = _ASSETS / "screener_builder.css"
_JS = _ASSETS / "screener_builder.js"

_RESULTS_GRID_ID = "ob-results-grid"
_RESULTS_WIDGET_ID = "yfinance_screener_results"
_CONFIG_WIDGET_ID = "yfinance_screener_config"

_FMT_PRICE = (
    "value == null || value === '' ? '' : "
    "Number(value).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})"
)
_FMT_COMPACT = (
    "value == null || value === '' ? '' : "
    "Intl.NumberFormat('en-US', {notation: 'compact', maximumFractionDigits: 2}).format(value)"
)
_FMT_PCT = "value == null || value === '' ? '' : Number(value).toFixed(2) + '%'"
_FMT_YIELD = (
    "value == null || value === '' ? '' : (Number(value) * 100).toFixed(2) + '%'"
)


def _num(field: str, header: str, fmt: str, width: int = 105) -> dict[str, Any]:
    """Build a right-aligned, formatted numeric AG Grid column definition."""
    return {
        "field": field,
        "headerName": header,
        "type": "numericColumn",
        "cellDataType": "number",
        "valueFormatter": fmt,
        "minWidth": width,
        "wrapText": False,
        "autoHeight": False,
    }


def _txt(field: str, header: str, width: int = 110, **extra: Any) -> dict[str, Any]:
    """Build a non-wrapping text AG Grid column definition."""
    return {
        "field": field,
        "headerName": header,
        "minWidth": width,
        "wrapText": False,
        "autoHeight": False,
        **extra,
    }


_COMMON_COLS: list[dict[str, Any]] = [
    _txt("symbol", "Symbol", 95, pinned="left"),
    _txt("shortName", "Name", 200),
    _txt("quoteType", "Type", 90),
    _num("regularMarketPrice", "Price", _FMT_PRICE),
    _num("regularMarketChange", "Change", _FMT_PRICE),
    _num("regularMarketChangePercent", "% Change", _FMT_PCT),
]

_TAIL_COLS: list[dict[str, Any]] = [
    _txt("currency", "Currency", 90),
    _txt("exchange", "Exchange", 100),
    _txt("exchangeTimezoneName", "Timezone", 150),
]

_EQUITY_COLS: list[dict[str, Any]] = [
    *_COMMON_COLS,
    _num("regularMarketVolume", "Volume", _FMT_COMPACT, 110),
    _num("marketCap", "Market Cap", _FMT_COMPACT, 120),
    _num("regularMarketOpen", "Open", _FMT_PRICE),
    _num("regularMarketDayHigh", "Day High", _FMT_PRICE),
    _num("regularMarketDayLow", "Day Low", _FMT_PRICE),
    _num("regularMarketPreviousClose", "Prev Close", _FMT_PRICE),
    _num("fiftyDayAverage", "50D Avg", _FMT_PRICE),
    _num("twoHundredDayAverage", "200D Avg", _FMT_PRICE),
    _num("fiftyTwoWeekHigh", "52W High", _FMT_PRICE),
    _num("fiftyTwoWeekLow", "52W Low", _FMT_PRICE),
    _num("sharesOutstanding", "Shares Out", _FMT_COMPACT, 120),
    _num("epsTrailingTwelveMonths", "EPS (TTM)", _FMT_PRICE),
    _num("forwardPE", "Fwd P/E", _FMT_PRICE),
    _num("epsForward", "EPS (Fwd)", _FMT_PRICE),
    _num("bookValue", "Book Value", _FMT_PRICE),
    _num("priceToBook", "P/B", _FMT_PRICE),
    _num("trailingAnnualDividendYield", "Div Yield", _FMT_YIELD),
    *_TAIL_COLS,
    _txt("earnings_date", "Earnings Date", 165),
]

_FUND_COLS: list[dict[str, Any]] = [
    *_COMMON_COLS,
    _num("ytdReturn", "YTD Return", _FMT_PCT, 110),
    _num("trailingThreeMonthReturns", "3M Return", _FMT_PCT, 110),
    _num("annualReturnNavY3", "3Y Return", _FMT_PCT, 110),
    _num("annualReturnNavY5", "5Y Return", _FMT_PCT, 110),
    _num("netExpenseRatio", "Expense Ratio", _FMT_PCT, 120),
    _num("yieldTTM", "Yield (TTM)", _FMT_PCT, 110),
    _num("netAssets", "Net Assets", _FMT_COMPACT, 120),
    _num("trailingPE", "P/E (TTM)", _FMT_PRICE),
    _num("fiftyTwoWeekHigh", "52W High", _FMT_PRICE),
    _num("fiftyTwoWeekLow", "52W Low", _FMT_PRICE),
    _num("fiftyDayAverage", "50D Avg", _FMT_PRICE),
    _num("twoHundredDayAverage", "200D Avg", _FMT_PRICE),
    *_TAIL_COLS,
]

_INDEX_COLS: list[dict[str, Any]] = [
    *_COMMON_COLS,
    _num("regularMarketOpen", "Open", _FMT_PRICE),
    _num("regularMarketDayHigh", "Day High", _FMT_PRICE),
    _num("regularMarketDayLow", "Day Low", _FMT_PRICE),
    _num("regularMarketPreviousClose", "Prev Close", _FMT_PRICE),
    _num("fiftyDayAverage", "50D Avg", _FMT_PRICE),
    _num("twoHundredDayAverage", "200D Avg", _FMT_PRICE),
    _num("fiftyTwoWeekHigh", "52W High", _FMT_PRICE),
    _num("fiftyTwoWeekLow", "52W Low", _FMT_PRICE),
    *_TAIL_COLS,
]

_FUTURE_COLS: list[dict[str, Any]] = [
    *_COMMON_COLS,
    _num("regularMarketVolume", "Volume", _FMT_COMPACT, 110),
    _num("openInterest", "Open Interest", _FMT_COMPACT, 120),
    _num("regularMarketOpen", "Open", _FMT_PRICE),
    _num("regularMarketDayHigh", "Day High", _FMT_PRICE),
    _num("regularMarketDayLow", "Day Low", _FMT_PRICE),
    _num("regularMarketPreviousClose", "Prev Close", _FMT_PRICE),
    _num("fiftyTwoWeekHigh", "52W High", _FMT_PRICE),
    _num("fiftyTwoWeekLow", "52W Low", _FMT_PRICE),
    *_TAIL_COLS,
]

_COLUMN_DEFS_BY_ASSET: dict[str, list[dict[str, Any]]] = {
    "equity": _EQUITY_COLS,
    "etf": _FUND_COLS,
    "fund": _FUND_COLS,
    "index": _INDEX_COLS,
    "future": _FUTURE_COLS,
}

_RESULT_COLUMN_DEFS: list[dict[str, Any]] = _EQUITY_COLS


def _category_options(catalog_fields: list[dict]) -> list:
    """Distinct {value, label} category options, ordered by label."""
    from pywry import Option

    seen: dict[str, str] = {}
    for field in catalog_fields:
        seen.setdefault(field["category"], field["category_label"])
    pairs = sorted(seen.items(), key=lambda kv: kv[1].lower())
    return [Option(label=label, value=value) for value, label in pairs]


def build_screener_content(theme: str = "dark", transport: str = "iframe"):
    """Build the shared screener-builder content, toolbars, modals and theme.

    The same component tree drives every surface; ``transport`` selects how the
    page fetches results: ``iframe`` calls the ``/run`` HTTP route and speaks the
    OpenBB iframe protocol, while ``bridge`` emits ``screener:run`` to a PyWry
    backend (native window or notebook) and renders the ``screener:results``
    reply.

    Returns
    -------
    tuple
        ``(HtmlContent, list[Toolbar], list[Modal], grid_theme)``.
    """
    from pywry import (
        Button,
        Div,
        HtmlContent,
        Modal,
        NumberInput,
        Option,
        Select,
        TabGroup,
        TextInput,
        Toolbar,
    )
    from pywry.grid import build_grid_config, build_grid_html

    from openbb_yfinance.utils.screener_catalog import build_screener_catalog
    from openbb_yfinance.utils.screener_presets import list_presets

    try:
        templates = list_presets()
    except Exception:  # noqa: BLE001 - templates are optional; never block the page
        templates = []

    grid_theme = "light" if str(theme).lower() == "light" else "dark"

    catalog = build_screener_catalog()
    asset_types = catalog["asset_types"]
    default_asset = asset_types[0]["value"]
    fields = catalog["fields"]
    sort_fields = catalog["sort_fields"]

    label_by_field = {
        asset: {field["field"]: field["label"] for field in entries}
        for asset, entries in fields.items()
    }
    sort_options = {
        asset: [
            {"value": fld, "label": label_by_field[asset].get(fld, fld)}
            for fld in sort_fields[asset]
        ]
        for asset in fields
    }
    preferred_sort = {
        "equity": "intradaymarketcap",
        "etf": "fundnetassets",
        "fund": "performanceratingoverall",
        "index": "percentchange",
        "future": "percentchange",
    }
    default_sort = {
        asset: (
            preferred_sort[asset]
            if preferred_sort.get(asset) in set(sort_fields[asset])
            else (sort_fields[asset][0] if sort_fields[asset] else "")
        )
        for asset in fields
    }

    grid_html = build_grid_html(
        build_grid_config(
            [],
            column_defs=_RESULT_COLUMN_DEFS,  # ty: ignore[invalid-argument-type]
            grid_id=_RESULTS_GRID_ID,
            theme=grid_theme,
            aggrid_theme="quartz",
            row_selection=False,
            pagination=True,
            pagination_page_size=50,
        )
    )

    body = (
        '<div class="ob-results">'
        '<div class="ob-filterbar" id="ob-filterbar"></div>'
        '<div class="ob-results-head">'
        '<span class="ob-results-title">Results</span>'
        '<span id="ob-results-status">Loading results…</span>'
        '<span id="ob-count" class="ob-count"></span>'
        "</div>"
        f'<div class="ob-grid-wrap">{grid_html}</div>'
        "</div>"
    )

    template_options = [Option(label="— Templates —", value="")] + [
        Option(label=t["label"], value=t["name"]) for t in templates
    ]
    templates_bar = Toolbar(
        position="top",
        class_name="ob-templates",
        items=[
            Select(
                component_id="ob-template",
                label="Template",
                event="screener:template-pick",
                searchable=True,
                options=template_options,
                selected="",
            ),
            Button(label="New", event="screener:template-new", variant="secondary"),
            Button(label="Save", event="screener:template-save", variant="secondary"),
            Button(
                label="Save As…",
                event="screener:template-saveas",
                variant="secondary",
            ),
            Button(
                label="Delete",
                event="screener:template-delete-click",
                variant="secondary",
            ),
        ],
    )

    actions = Toolbar(
        position="top",
        class_name="ob-actions",
        items=[
            TabGroup(
                component_id="ob-asset",
                event="screener:asset",
                options=[
                    Option(label=a["label"], value=a["value"]) for a in asset_types
                ],
                selected=default_asset,
            ),
            Button(
                label="+ Add Filter",
                event="screener:open-add-filter",
                variant="secondary",
            ),
            Select(
                component_id="ob-sort-field",
                label="Sort by",
                event="screener:sortfield",
                searchable=True,
                options=[
                    Option(label=o["label"], value=o["value"])
                    for o in sort_options[default_asset]
                ],
                selected=default_sort[default_asset],
            ),
            Select(
                component_id="ob-sort-type",
                label="Order",
                event="screener:sorttype",
                options=[
                    Option(label=s["label"], value=s["value"])
                    for s in catalog["sort_types"]
                ],
                selected="DESC",
            ),
            NumberInput(
                component_id="ob-limit",
                label="Limit",
                event="screener:limit",
                value=100,
                min=1,
            ),
            Button(label="Reset", event="screener:reset", variant="secondary"),
            Button(label="Apply", event="screener:apply", variant="primary"),
        ],
    )

    add_filter_modal = Modal(
        component_id="ob-add-filter",
        title="Add Filter",
        size="md",
        reset_on_close=False,
        items=[
            Div(
                component_id="ob-mf-join-row",
                class_name="ob-mf-join-row",
                children=[
                    Select(
                        component_id="ob-mf-join",
                        label="Join with previous",
                        event="screener:mf-join",
                        options=[
                            Option(label="AND", value="and"),
                            Option(label="OR", value="or"),
                        ],
                        selected="and",
                    ),
                ],
            ),
            Select(
                component_id="ob-mf-category",
                label="Category",
                event="screener:mf-category",
                searchable=True,
                options=_category_options(fields[default_asset]),
            ),
            Select(
                component_id="ob-mf-field",
                label="Filter",
                event="screener:mf-field",
                searchable=True,
                options=[],
            ),
            Select(
                component_id="ob-mf-operator",
                label="Condition",
                event="screener:mf-operator",
                options=[],
            ),
            Div(
                class_name="ob-mf-value-wrap",
                content='<div id="ob-mf-value" class="ob-mf-value"></div>',
            ),
            Button(label="Add filter", event="screener:add-filter", variant="primary"),
        ],
    )

    save_template_modal = Modal(
        component_id="ob-save-template",
        title="Save Template",
        size="sm",
        reset_on_close=False,
        items=[
            TextInput(
                component_id="ob-save-name",
                label="Template name",
                event="screener:save-name",
                placeholder="my_screen",
            ),
            Div(
                class_name="ob-modal-hint",
                content="Saved as an .ini preset in your presets directory. "
                "Filters are AND-joined.",
            ),
            Button(label="Save", event="screener:template-do-save", variant="primary"),
        ],
    )

    delete_template_modal = Modal(
        component_id="ob-delete-template",
        title="Delete Template",
        size="sm",
        reset_on_close=False,
        items=[
            Div(
                class_name="ob-modal-hint",
                content='<span id="ob-delete-msg">Delete this template?</span>',
            ),
            Button(
                label="Delete",
                event="screener:template-do-delete",
                variant="primary",
            ),
        ],
    )

    content = HtmlContent(
        html=body,
        inline_css=_CSS.read_text(encoding="utf-8"),
        json_data={
            "assetTypes": asset_types,
            "defaultAsset": default_asset,
            "fields": fields,
            "operators": catalog["operators"],
            "sortOptions": sort_options,
            "defaultSort": default_sort,
            "theme": theme,
            "transport": transport,
            "addFilterModalId": "ob-add-filter",
            "saveModalId": "ob-save-template",
            "deleteModalId": "ob-delete-template",
            "templateSelectId": "ob-template",
            "templates": templates,
            "resultsGridId": _RESULTS_GRID_ID,
            "resultsWidgetId": _RESULTS_WIDGET_ID,
            "configWidgetId": _CONFIG_WIDGET_ID,
            "resultColumns": [
                {"field": c["field"], "label": c["headerName"]}
                for c in _RESULT_COLUMN_DEFS
            ],
            "columnDefsByAsset": _COLUMN_DEFS_BY_ASSET,
        },
        init_script=_JS.read_text(encoding="utf-8"),
    )
    return (
        content,
        [templates_bar, actions],
        [add_filter_modal, save_template_modal, delete_template_modal],
        grid_theme,
    )


@lru_cache(maxsize=4)
def build_screener_builder_html(theme: str = "dark") -> str:
    """Return the screener-builder iframe page built from PyWry components.

    Every screenable field becomes a PyWry toolbar component (searchable
    multi-select, min/max number, or text). The toolbar carries the asset-type
    tabs, sort controls and the apply/reset actions; the page speaks the OpenBB
    iframe protocol and emits the full configuration on apply.
    """
    from pywry.models import ThemeMode, WindowConfig
    from pywry.templates import build_html

    content, toolbars, modals, grid_theme = build_screener_content(
        theme, transport="iframe"
    )
    config = WindowConfig(
        title="OpenBB - Yahoo Finance Screener Builder",
        theme=ThemeMode.LIGHT if grid_theme == "light" else ThemeMode.DARK,
        enable_aggrid=True,
        aggrid_theme="quartz",
    )
    return build_html(
        content,
        config,
        window_label="yfinance_screener_builder",
        toolbars=toolbars,
        modals=modals,
    )
