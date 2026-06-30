"""Unit tests for the tvchart datafeed core and iframe page (no network)."""

import pytest

from openbb_yfinance.utils.funds_helpers import parse_style_box
from openbb_yfinance.utils.screener_catalog import (
    build_screener_catalog,
    screener_body_from_config,
)
from openbb_yfinance.utils.screener_iframe import (
    build_screener_builder_html,
    build_screener_content,
    prune_empty_columns,
)
from openbb_yfinance.utils.screener_presets import (
    build_preset_template,
    build_screener_body,
    config_from_ini,
    config_to_ini,
    delete_preset,
    get_bundled_presets,
    list_presets,
    load_preset_config,
    resolve_user_presets_directory,
    sanitize_preset_name,
    save_preset,
    validate_config,
)
from openbb_yfinance.utils.tvchart_datafeed import (
    BarCache,
    aggregate_bars,
    is_24_7_market,
    normalize_resolution,
)


@pytest.mark.parametrize(
    "position, size, style",
    [
        (1, "Large", "Value"),
        (2, "Large", "Blend"),
        (3, "Large", "Growth"),
        (5, "Mid", "Blend"),
        (7, "Small", "Value"),
        (9, "Small", "Growth"),
    ],
)
def test_parse_style_box_equity(position, size, style):
    """Equity style-box positions map to the correct size/style labels."""
    url = f"https://s.yimg.com/lq/i/fi/3_0stylelargeeq{position}.gif"
    box = parse_style_box(url, is_fixed_income=False)
    assert box["style_box"] == position
    assert box["style_box_type"] == "equity"
    assert box["style_box_size"] == size
    assert box["style_box_investment_style"] == style
    assert box["style_box_label"] == f"{size} {style}"


@pytest.mark.parametrize(
    "position, credit, sensitivity",
    [
        (1, "High", "Limited"),
        (2, "High", "Moderate"),
        (7, "Low", "Limited"),
        (9, "Low", "Extensive"),
    ],
)
def test_parse_style_box_fixed_income(position, credit, sensitivity):
    """Fixed-income style-box positions map to credit/sensitivity labels."""
    url = f"https://s.yimg.com/lq/i/fi/3_0stylelargeeq{position}.gif"
    box = parse_style_box(url, is_fixed_income=True)
    assert box["style_box"] == position
    assert box["style_box_type"] == "fixed_income"
    assert box["style_box_credit_quality"] == credit
    assert box["style_box_interest_rate_sensitivity"] == sensitivity


def test_parse_style_box_invalid():
    """A missing or unparseable style-box URL yields an empty mapping."""
    assert parse_style_box(None) == {}
    assert parse_style_box("") == {}
    assert parse_style_box("https://example.com/no_number.png") == {}
    assert parse_style_box("https://s.yimg.com/lq/i/fi/3_0stylelargeeq0.gif") == {}


def test_normalize_resolution():
    """Resolution aliases and casing normalize to canonical keys."""
    assert normalize_resolution("60") == "1h"
    assert normalize_resolution("1D") == "1d"
    assert normalize_resolution("D") == "1d"
    assert normalize_resolution("1m") == "1m"
    assert normalize_resolution("unknown") == "1d"


def test_aggregate_bars():
    """Bars aggregate by grouping a fixed number of consecutive bars."""
    bars = [
        {"time": 0, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
        {"time": 60, "open": 1.5, "high": 3, "low": 1, "close": 2.5, "volume": 20},
        {"time": 120, "open": 2.5, "high": 4, "low": 2, "close": 3.5, "volume": 30},
    ]
    out = aggregate_bars(bars, 3)
    assert len(out) == 1
    bar = out[0]
    assert bar["open"] == 1
    assert bar["high"] == 4
    assert bar["low"] == 0.5
    assert bar["close"] == 3.5
    assert bar["volume"] == 60


def test_is_24_7_market():
    """A near-full-day regular window is detected as a 24/7 market."""
    assert is_24_7_market((0, 0, 1439, 1439)) is True
    assert is_24_7_market((240, 570, 960, 1200)) is False


def test_bar_cache_append_and_last():
    """The bar cache appends and reports the last bar time for cached series."""
    cache = BarCache()
    cache._cache[("TEST", "1m")] = [
        {"time": 60, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
    ]
    cache.append_bar(
        "TEST",
        "1m",
        {"time": 120, "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2},
    )
    assert cache.last_bar_time("TEST", "1m") == 120
    cache.append_bar(
        "TEST",
        "1m",
        {"time": 120, "open": 2, "high": 3, "low": 2, "close": 3, "volume": 5},
    )
    bars = cache.get("TEST", "1m")
    assert bars[-1]["high"] == 3
    assert len([b for b in bars if b["time"] == 120]) == 1


def test_screener_presets_bundled():
    """The bundled screener presets are discoverable by name."""
    choices = get_bundled_presets()
    assert "large_cap_value" in choices
    assert "top_etfs" in choices
    assert all(p.suffix == ".ini" for p in choices.values())
    # The reference template ships but is not a selectable choice.
    assert "_template" not in choices


def test_preset_template_covers_every_field():
    """The generated template lists every screenable field and parses as INI."""
    import configparser

    from yfinance.const import (
        EQUITY_SCREENER_FIELDS,
        ETF_SCREENER_FIELDS,
        FUND_SCREENER_FIELDS,
    )

    text = build_preset_template()
    all_fields: set[str] = set()
    for field_map in (
        EQUITY_SCREENER_FIELDS,
        ETF_SCREENER_FIELDS,
        FUND_SCREENER_FIELDS,
    ):
        for fields in field_map.values():
            all_fields |= set(fields)

    assert all_fields
    assert all(field in text for field in all_fields)

    parser = configparser.ConfigParser()
    parser.read_string(text)
    assert parser.sections() == ["screener", "filters"]


def test_screener_catalog():
    """The screener catalog exposes labelled fields and enum value options."""
    catalog = build_screener_catalog()
    assert {a["value"] for a in catalog["asset_types"]} == {
        "equity",
        "etf",
        "fund",
        "index",
        "future",
    }
    assert len(catalog["fields"]["equity"]) >= 80
    sector = next(f for f in catalog["fields"]["equity"] if f["field"] == "sector")
    assert sector["type"] == "enum"
    assert {"value": "Technology", "label": "Technology"} in sector["values"]
    region = next(f for f in catalog["fields"]["equity"] if f["field"] == "region")
    labels = {v["label"] for v in region["values"]}
    assert "United States" in labels  # country code -> name
    mktcap = next(
        f for f in catalog["fields"]["equity"] if f["field"] == "intradaymarketcap"
    )
    assert mktcap["type"] == "number"
    assert mktcap["label"] == "Market Cap"
    assert mktcap["category_label"] == "Price & Performance"
    fund_category = next(
        f for f in catalog["fields"]["fund"] if f["field"] == "categoryname"
    )
    assert fund_category["type"] == "enum"
    assert fund_category["values"]


def test_screener_catalog_index_future():
    """The catalog includes index and future fields from the bundled metadata."""
    catalog = build_screener_catalog()
    for asset in ("index", "future"):
        entries = catalog["fields"][asset]
        assert entries
        by_field = {e["field"]: e for e in entries}
        # region reuses the shared country vocabulary as an enum.
        assert by_field["region"]["type"] == "enum"
        assert any(v["label"] == "United States" for v in by_field["region"]["values"])
        # a numeric field is available to sort on.
        assert by_field["percentchange"]["type"] == "number"
        assert "percentchange" in catalog["sort_fields"][asset]
    idx_fields = {e["field"] for e in catalog["fields"]["index"]}
    assert "exchange" in idx_fields


def test_screener_body_from_config_index_future():
    """Index and future configs map to INDEX/FUTURE bodies with US defaults."""
    idx = screener_body_from_config({"type": "index", "filters": []})
    assert idx["quoteType"] == "INDEX"
    assert idx["query"]["operands"] == [
        {"operator": "EQ", "operands": ["region", "us"]}
    ]
    assert idx["sortField"] == "percentchange"

    fut = screener_body_from_config(
        {
            "type": "future",
            "limit": 10,
            "sort_field": "dayvolume",
            "sort_type": "DESC",
            "filters": [
                {"field": "region", "operator": "eq", "value": "us", "join": "and"},
                {"field": "percentchange", "operator": "gt", "value": 0, "join": "and"},
            ],
        }
    )
    assert fut["quoteType"] == "FUTURE"
    by_field = {op["operands"][0]: op for op in fut["query"]["operands"]}
    assert by_field["region"]["operands"] == ["region", "us"]
    assert by_field["percentchange"]["operator"] == "GT"


def test_screener_body_from_config():
    """A builder config translates into a valid Yahoo screener body."""
    config = {
        "type": "etf",
        "limit": 50,
        "sort_field": "fundnetassets",
        "sort_type": "DESC",
        "filters": [
            {"field": "fundnetassets", "operator": "gt", "value": 1000000000},
            {"field": "exchange", "operator": "is-in", "value": ["NMS", "PCX"]},
        ],
    }
    body = screener_body_from_config(config)
    assert body["quoteType"] == "ETF"
    assert body["size"] == 50
    by_field = {op["operands"][0]: op for op in body["query"]["operands"]}
    assert by_field["fundnetassets"]["operator"] == "GT"
    assert by_field["fundnetassets"]["operands"][1] == 1000000000.0
    assert by_field["exchange"]["operator"] == "is-in"
    assert by_field["exchange"]["operands"] == ["exchange", "NMS", "PCX"]


def test_screener_builder_html():
    """The builder iframe page is built from PyWry components and exports results."""
    html = build_screener_builder_html("dark")
    # Complete PyWry document with the bridge, toolbar handlers and dark theme.
    assert html.lower().startswith("<!doctype")
    assert "pywry-theme-dark" in html
    assert "initToolbarHandlers" in html
    # Filters are added via a modal, not a wall of field cards.
    assert "pywry-modal" in html
    assert 'data-event="screener:open-add-filter"' in html
    assert "ob-add-filter" in html
    assert 'data-event="screener:apply"' in html
    assert 'data-event="screener:asset"' in html
    # Template files: a picker plus new/save/save-as/delete and their modals.
    assert 'id="ob-template"' in html
    assert 'data-event="screener:template-pick"' in html
    assert 'data-event="screener:template-save"' in html
    assert 'data-event="screener:template-delete-click"' in html
    assert "ob-save-template" in html
    assert "ob-delete-template" in html
    # An AG Grid results table, themed to match the page.
    assert 'id="myGrid"' in html
    assert 'class="pywry-grid ag-theme-balham-dark"' in html
    assert "grid:update-data" in html
    # OpenBB iframe protocol with an exportable results sub-widget.
    assert "openbb-connect" in html
    assert "openbb:widget-params:update" in html
    assert "yfinance_screener_results" in html


def test_screener_builder_html_light_theme():
    """The light theme renders the light PyWry + AG Grid grid-div classes."""
    html = build_screener_builder_html("light")
    assert "pywry-theme-light" in html
    # The results grid div uses the light balham class (not the -dark variant).
    assert 'class="pywry-grid ag-theme-balham"' in html
    assert 'class="pywry-grid ag-theme-balham-dark"' not in html


def test_tvchart_widget_html_announces_workspace_bridge(monkeypatch):
    """The TradingView iframe announces itself to Workspace and exports symbol state."""
    import asyncio
    import sys
    from types import ModuleType, SimpleNamespace

    from openbb_yfinance.utils import tvchart_native

    fake_inline = ModuleType("pywry.inline")

    async def fake_get_widget_html_async(_label):
        return "<!doctype html><html><body>chart</body></html>"

    fake_inline.get_widget_html_async = fake_get_widget_html_async

    fake_toolbar = ModuleType("pywry.toolbar")
    fake_toolbar.get_toolbar_script = lambda with_script_tag=False: (
        "<script>toolbar</script>"
    )

    fake_pywry = ModuleType("pywry")
    fake_pywry.ThemeMode = SimpleNamespace(LIGHT="light", DARK="dark")
    fake_pywry.WindowMode = SimpleNamespace(BROWSER="browser")
    fake_pywry.PyWry = lambda *args, **kwargs: SimpleNamespace()

    fake_server = ModuleType("openbb_yfinance.utils.pywry_server")
    fake_server.bind_loop = lambda: None
    fake_server.ensure_pywry_mounted = lambda: None

    monkeypatch.setitem(sys.modules, "pywry", fake_pywry)
    monkeypatch.setitem(sys.modules, "pywry.inline", fake_inline)
    monkeypatch.setitem(sys.modules, "pywry.toolbar", fake_toolbar)
    monkeypatch.setitem(sys.modules, "openbb_yfinance.utils.pywry_server", fake_server)
    monkeypatch.setattr(
        tvchart_native,
        "_show",
        lambda app, symbol, resolution, **show_kwargs: SimpleNamespace(label="tvchart"),
    )

    html = asyncio.run(tvchart_native.tvchart_widget_html("AAPL", "1d", "dark"))
    assert "openbb-connect" in html
    assert "openbb-data" in html
    assert "window.__obbTvChart" in html
    assert "tvchart:symbol-search" in html


def test_screener_builder_run_rejects_bad_json_offline():
    """The results run route rejects malformed config JSON without a network call."""
    import asyncio
    import json as _json

    from openbb_yfinance.yfinance_router import screener_builder_run

    bad = asyncio.run(screener_builder_run(config="{not json"))
    assert bad.status_code == 400
    assert "Invalid config JSON" in _json.loads(bytes(bad.body))["error"]


def test_prune_empty_columns_drops_fully_empty_fields():
    rows = [
        {"symbol": "AAA", "shortName": "Alpha", "marketCap": None, "currency": "USD"},
        {"symbol": "BBB", "shortName": "Beta", "marketCap": None, "currency": ""},
    ]
    cols = [
        {"field": "symbol", "headerName": "Symbol"},
        {"field": "shortName", "headerName": "Name"},
        {"field": "marketCap", "headerName": "Market Cap"},
        {"field": "currency", "headerName": "Currency"},
    ]

    pruned = prune_empty_columns(rows, cols)
    fields = [c["field"] for c in pruned]
    assert "symbol" in fields
    assert "shortName" in fields
    assert "currency" in fields
    assert "marketCap" not in fields


def test_screener_builder_run_returns_pruned_column_defs(monkeypatch):
    import asyncio
    import json as _json

    from openbb_yfinance import yfinance_router

    async def _fake_get_custom_screener(_body, _limit, keep_illiquid):
        assert keep_illiquid is True
        return [
            {
                "symbol": "SPY",
                "shortName": "SPDR S&P 500 ETF Trust",
                "quoteType": "ETF",
                "regularMarketPrice": 521.01,
                "regularMarketVolume": None,
                "currency": "USD",
                "exchange": "PCX",
            }
        ]

    monkeypatch.setattr(
        "openbb_yfinance.utils.helpers.get_custom_screener", _fake_get_custom_screener
    )

    resp = asyncio.run(
        yfinance_router.screener_builder_run(config='{"type":"etf","filters":[]}')
    )
    payload = _json.loads(bytes(resp.body))
    fields = {c["field"] for c in payload.get("columnDefs", [])}

    assert "symbol" in fields
    assert "shortName" in fields
    assert "currency" in fields
    assert "regularMarketVolume" not in fields


def test_list_presets_includes_yahoo_predefined(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENBB_YFINANCE_PRESETS_DIRECTORY", str(tmp_path))
    names = {item["name"] for item in list_presets()}
    assert "most_active" in names
    assert "gainers" in names


def test_load_preset_config_for_predefined():
    cfg = load_preset_config("most_active")
    assert cfg["type"] == "equity"
    assert cfg["filters"]
    assert any(f["field"] == "exchange" for f in cfg["filters"])


def test_screener_builder_run_uses_predefined(monkeypatch):
    import asyncio
    import json as _json

    from openbb_yfinance import yfinance_router

    async def _fake_get_defined_screener(name, body=None, limit=None, all_fields=False):
        assert name == "most_actives"
        assert limit == 3
        assert all_fields is False
        return [{"symbol": "AAPL", "shortName": "Apple Inc.", "currency": "USD"}]

    monkeypatch.setattr(
        "openbb_yfinance.utils.helpers.get_defined_screener", _fake_get_defined_screener
    )

    resp = asyncio.run(
        yfinance_router.screener_builder_run(
            config='{"type":"equity","predefined":"most_actives"}', limit=3
        )
    )
    payload = _json.loads(bytes(resp.body))
    assert payload["rows"][0]["symbol"] == "AAPL"


def test_screener_content_bridge_transport():
    """The native/notebook surface shares the components but uses the bridge transport."""
    content, toolbars, modals, grid_theme = build_screener_content(
        "dark", transport="bridge"
    )
    assert content.json_data["transport"] == "bridge"
    assert grid_theme == "dark"
    # A templates toolbar and an actions toolbar, both pinned to the top.
    assert len(toolbars) == 2
    templates_bar, actions = toolbars
    assert templates_bar.position == "top"
    assert actions.position == "top"
    # template picker, new, save, save-as, delete.
    assert len(templates_bar.items) == 5
    # asset, +add filter, sort, order, limit, reset, apply.
    assert len(actions.items) == 7
    # add-filter, save-template, delete-template.
    assert {m.component_id for m in modals} == {
        "ob-add-filter",
        "ob-save-template",
        "ob-delete-template",
    }
    assert content.json_data["addFilterModalId"] == "ob-add-filter"
    assert content.json_data["saveModalId"] == "ob-save-template"
    assert content.json_data["deleteModalId"] == "ob-delete-template"


def test_screener_native_callbacks_registered():
    """The native launcher wires a screener-run and theme callback over the bridge."""
    from openbb_yfinance.utils.screener_native import make_screener_callbacks

    class _App:
        theme = None

        def emit(self, *_args):
            return None

    callbacks = make_screener_callbacks(_App())
    assert set(callbacks) == {
        "screener:run",
        "pywry:update-theme",
        "screener:templates-list",
        "screener:template-load",
        "screener:template-save",
        "screener:template-delete",
    }


def test_screener_body_from_config_defaults_to_us_market():
    """With no filters the config falls back to a US-market default per asset."""
    eq = screener_body_from_config({"type": "equity", "filters": []})
    assert eq["query"]["operands"] == [{"operator": "EQ", "operands": ["region", "us"]}]
    assert eq["sortField"] == "intradaymarketcap"

    etf = screener_body_from_config({"type": "etf", "filters": []})
    assert etf["query"]["operands"] == [
        {"operator": "EQ", "operands": ["region", "us"]}
    ]
    assert etf["sortField"] == "fundnetassets"

    fund = screener_body_from_config({"type": "fund", "filters": []})
    assert fund["query"]["operands"][0]["operands"][0] == "performanceratingoverall"


def test_sanitize_preset_name_valid():
    """Well-formed names pass and a trailing .ini is stripped."""
    assert sanitize_preset_name("My Screen") == "My Screen"
    assert sanitize_preset_name("large_cap-value") == "large_cap-value"
    assert sanitize_preset_name("foo.ini") == "foo"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "../escape",
        "a/b",
        "a\\b",
        "_hidden",
        "-leading",
        "weird!",
        "name.with.dots",
    ],
)
def test_sanitize_preset_name_rejects(bad):
    """Traversal, separators, leading '_'/'-' and odd characters are rejected."""
    with pytest.raises(ValueError):
        sanitize_preset_name(bad)


def test_config_ini_round_trip(tmp_path):
    """A builder config survives a write/read cycle in the preset INI format."""
    config = {
        "type": "equity",
        "limit": 25,
        "sort_field": "intradaymarketcap",
        "sort_type": "ASC",
        "filters": [
            {"field": "region", "operator": "eq", "value": "us", "join": "and"},
            {
                "field": "exchange",
                "operator": "is-in",
                "value": ["NMS", "NYQ"],
                "join": "or",
            },
            {
                "field": "intradaymarketcap",
                "operator": "gt",
                "value": 50000000000,
                "join": "and",
            },
            {
                "field": "percentchange",
                "operator": "btwn",
                "value": [1, 5],
                "join": "and",
            },
        ],
    }
    ini = config_to_ini(config)
    assert "intradaymarketcap_gt = 50000000000" in ini
    # 'between' is stored as paired bounds, readable by the legacy body builder.
    assert "percentchange_gte = 1" in ini
    assert "percentchange_lte = 5" in ini

    path = tmp_path / "rt.ini"
    path.write_text(ini, encoding="utf-8")
    back = config_from_ini(path)
    assert back["type"] == "equity"
    assert back["limit"] == 25
    assert back["sort_field"] == "intradaymarketcap"
    assert back["sort_type"] == "ASC"
    by_key = {(f["field"], f["operator"]): f for f in back["filters"]}
    assert by_key[("region", "eq")]["value"] == "us"
    assert by_key[("exchange", "is-in")]["value"] == ["NMS", "NYQ"]
    assert by_key[("intradaymarketcap", "gt")]["value"] == 50000000000
    assert by_key[("percentchange", "gte")]["value"] == 1
    assert by_key[("percentchange", "lte")]["value"] == 5
    # The chosen .ini format is AND-only: the OR join flattens on round-trip.
    assert all(f["join"] == "and" for f in back["filters"])
    # The same file remains valid for screener(preset=...).
    assert build_screener_body(path)["quoteType"] == "EQUITY"


def test_validate_config_coerces():
    """Invalid asset/limit/operator/value entries are coerced or dropped."""
    out = validate_config(
        {
            "type": "mutualfund",
            "limit": 9999,
            "sort_type": "weird",
            "filters": [
                {"field": "x", "operator": "gt", "value": 1},
                {"field": "", "operator": "gt", "value": 1},
                {"field": "y", "operator": "bogus", "value": 1},
                {"field": "z", "operator": "eq", "value": ""},
            ],
        }
    )
    assert out["type"] == "fund"
    assert out["limit"] == 250
    assert out["sort_type"] == "DESC"
    assert [f["field"] for f in out["filters"]] == ["x"]


def test_save_load_delete_round_trip(tmp_path, monkeypatch):
    """Saving, listing, loading and deleting a template hits only the temp dir."""
    monkeypatch.setenv("OPENBB_YFINANCE_PRESETS_DIRECTORY", str(tmp_path))
    config = {
        "type": "etf",
        "limit": 10,
        "sort_field": "fundnetassets",
        "sort_type": "DESC",
        "filters": [
            {
                "field": "fundnetassets",
                "operator": "gt",
                "value": 1000000000,
                "join": "and",
            }
        ],
    }
    saved = save_preset("My ETFs", config)
    assert saved["name"] == "My ETFs"
    assert (tmp_path / "My ETFs.ini").exists()
    assert "My ETFs" in {t["name"] for t in list_presets()}

    loaded = load_preset_config("My ETFs")
    assert loaded["type"] == "etf"
    assert loaded["filters"][0]["field"] == "fundnetassets"

    assert delete_preset("My ETFs") is True
    assert not (tmp_path / "My ETFs.ini").exists()


def test_delete_missing_raises(tmp_path, monkeypatch):
    """Deleting an absent template raises FileNotFoundError."""
    monkeypatch.setenv("OPENBB_YFINANCE_PRESETS_DIRECTORY", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        delete_preset("does_not_exist")


def test_save_preset_rejects_traversal(tmp_path, monkeypatch):
    """A traversal name is rejected and nothing is written outside the dir."""
    monkeypatch.setenv("OPENBB_YFINANCE_PRESETS_DIRECTORY", str(tmp_path))
    with pytest.raises(ValueError):
        save_preset("../evil", {"type": "equity", "filters": []})
    assert not (tmp_path.parent / "evil.ini").exists()


def test_screener_template_routes_offline(tmp_path, monkeypatch):
    """The builder template routes save/load/delete without a network call."""
    import asyncio
    import json as _json

    monkeypatch.setenv("OPENBB_YFINANCE_PRESETS_DIRECTORY", str(tmp_path))
    from openbb_yfinance.yfinance_router import (
        screener_builder_template_delete,
        screener_builder_template_load,
        screener_builder_template_save,
    )

    config = {
        "type": "equity",
        "limit": 5,
        "sort_field": "intradaymarketcap",
        "sort_type": "DESC",
        "filters": [
            {"field": "region", "operator": "eq", "value": "us", "join": "and"}
        ],
    }
    saved = asyncio.run(
        screener_builder_template_save(name="Router Test", config=_json.dumps(config))
    )
    sbody = _json.loads(bytes(saved.body))
    assert sbody["ok"] is True
    assert sbody["name"] == "Router Test"
    assert any(t["name"] == "Router Test" for t in sbody["templates"])

    loaded = asyncio.run(screener_builder_template_load(name="Router Test"))
    lbody = _json.loads(bytes(loaded.body))
    assert lbody["config"]["filters"][0]["field"] == "region"

    deleted = asyncio.run(screener_builder_template_delete(name="Router Test"))
    assert _json.loads(bytes(deleted.body))["ok"] is True

    bad = asyncio.run(
        screener_builder_template_save(name="../x", config=_json.dumps(config))
    )
    assert bad.status_code == 400


def test_resolve_user_presets_directory(monkeypatch, tmp_path):
    """The user presets directory resolves from env var, then the default."""
    monkeypatch.setenv("OPENBB_YFINANCE_PRESETS_DIRECTORY", str(tmp_path / "custom"))
    assert resolve_user_presets_directory("/data") == tmp_path / "custom"
    monkeypatch.delenv("OPENBB_YFINANCE_PRESETS_DIRECTORY", raising=False)
    monkeypatch.setattr(
        "openbb_yfinance.utils.screener_presets._presets_dir_from_config",
        lambda: None,
    )
    resolved = resolve_user_presets_directory(str(tmp_path / "OpenBBUserData"))
    assert resolved == tmp_path / "OpenBBUserData" / "presets" / "yfinance"


def test_build_screener_body_equity():
    """An equity preset INI parses into a valid screener body with operands."""
    choices = get_bundled_presets()
    body = build_screener_body(choices["large_cap_value"])
    assert body["quoteType"] == "EQUITY"
    assert body["sortField"] == "intradaymarketcap"
    operands = body["query"]["operands"]
    by_field = {op["operands"][0]: op for op in operands}
    assert by_field["region"]["operator"] == "EQ"
    assert by_field["intradaymarketcap"]["operator"] == "GT"
    assert by_field["intradaymarketcap"]["operands"][1] == 10000000000.0
    assert by_field["peratio.lasttwelvemonths"]["operator"] == "LT"


def test_build_screener_body_etf():
    """An ETF preset INI maps the type to the ETF quote type."""
    choices = get_bundled_presets()
    body = build_screener_body(choices["top_etfs"])
    assert body["quoteType"] == "ETF"


def test_apps_tabs_curated():
    """The bundled app ships the curated research tabs in order."""
    from openbb_yfinance.utils.apps import build_yfinance_apps

    apps = build_yfinance_apps()
    assert len(apps) == 1
    app = apps[0]
    assert app["name"] == "Yahoo Finance"
    assert app["allowCustomization"] is True
    assert list(app["tabs"]) == ["asset-overview", "screener", "options"]
    for tab in app["tabs"].values():
        assert tab["id"] and tab["name"] and tab["layout"]


def test_apps_layout_no_overlap():
    """No two widgets overlap and every widget stays within the 40-wide grid."""
    from openbb_yfinance.utils.apps import build_yfinance_apps

    app = build_yfinance_apps()[0]

    def _overlap(r1, r2):
        return (
            r1["x"] < r2["x"] + r2["w"]
            and r2["x"] < r1["x"] + r1["w"]
            and r1["y"] < r2["y"] + r2["h"]
            and r2["y"] < r1["y"] + r1["h"]
        )

    for tab in app["tabs"].values():
        layout = tab["layout"]
        for node in layout:
            assert node["x"] + node["w"] <= 40
            assert node["h"] > 0
        for i in range(len(layout)):
            for j in range(i + 1, len(layout)):
                assert not _overlap(layout[i], layout[j]), tab["id"]


def test_asset_info_overview_render():
    """The Asset Info renderer adapts its key stats to the quote type."""
    from openbb_yfinance.utils.asset_info import (
        _holdings_html,
        _overview_stats,
        _sectors_html,
    )

    etf = _overview_stats(
        {
            "quoteType": "ETF",
            "category": "Large Growth",
            "fundFamily": "Invesco",
            "netAssets": 493_987_528_704,
            "ytdReturn": 20.357,
            "yield": 0.0038,
        }
    )
    assert "Category" in etf and "Large Growth" in etf
    assert "493.99B" in etf
    assert "0.38%" in etf  # yield scaled to percent

    equity = _overview_stats(
        {"quoteType": "EQUITY", "sector": "Technology", "marketCap": 4_342_757_195_776}
    )
    assert "Sector" in equity and "Technology" in equity
    assert "4.34T" in equity
    assert "Category" not in equity  # equity overview has no fund fields

    holdings = _holdings_html(
        [{"symbol": "NVDA", "name": "NVIDIA Corporation", "weight": 0.0815}]
    )
    assert "NVDA" in holdings and "8.15%" in holdings
    assert _holdings_html([]) == ""

    sectors = _sectors_html([{"sector": "technology", "weight": 0.5865}])
    assert "Technology" in sectors and "58.65%" in sectors
    assert _sectors_html([]) == ""


class _CaptureApp:
    """Records the tvchart responses and marquee emits the callbacks produce."""

    def __init__(self) -> None:
        self.theme = "dark"
        self.config: dict = {}
        self.history: dict = {}
        self.resolved: dict = {}
        self.emits: list[tuple[str, dict]] = []

    def respond_tvchart_datafeed_config(self, **kwargs) -> None:  # noqa: D102
        self.config = kwargs

    def respond_tvchart_symbol_search(self, **kwargs) -> None:  # noqa: D102
        pass

    def respond_tvchart_symbol_resolve(self, **kwargs) -> None:  # noqa: D102
        self.resolved = kwargs

    def respond_tvchart_history(self, **kwargs) -> None:  # noqa: D102
        self.history = kwargs

    def respond_tvchart_server_time(self, **kwargs) -> None:  # noqa: D102
        pass

    def respond_tvchart_bar_update(self, **kwargs) -> None:  # noqa: D102
        pass

    def emit(self, event: str, data: dict) -> None:  # noqa: D102
        self.emits.append((event, data))


def test_yfinance_datafeed_callbacks():
    """The datafeed callbacks return real config and OHLCV bars."""
    from openbb_yfinance.utils.tvchart_datafeed import (
        BarCache,
        RealtimeStreamer,
        make_callbacks,
    )

    app = _CaptureApp()
    cache = BarCache()
    streamer = RealtimeStreamer(app, cache)
    callbacks = make_callbacks(app, streamer, cache)

    callbacks["tvchart:datafeed-config-request"]({"requestId": "c1", "chartId": "main"})
    config = app.config["config"]
    assert "1d" in config["supported_resolutions"]
    assert {"future", "index"} <= {t["value"] for t in config["symbols_types"]}

    callbacks["tvchart:datafeed-history-request"](
        {"requestId": "h1", "symbol": "AAPL", "resolution": "1d", "chartId": "main"}
    )
    assert app.history["status"] == "ok"
    assert app.history["bars"]
    assert {"time", "open", "high", "low", "close"} <= set(app.history["bars"][0])


def test_yfinance_datafeed_resolve_seeds_marquee():
    """Resolving a symbol seeds the marquee and arms the active streamer symbol."""
    from openbb_yfinance.utils.tvchart_datafeed import (
        BarCache,
        RealtimeStreamer,
        make_callbacks,
    )

    app = _CaptureApp()
    cache = BarCache()
    streamer = RealtimeStreamer(app, cache)
    callbacks = make_callbacks(app, streamer, cache)

    callbacks["tvchart:datafeed-resolve-request"](
        {"requestId": "r1", "symbol": "AAPL", "chartId": "main"}
    )
    assert app.resolved["symbol_info"]["name"]
    assert streamer._active_marquee_symbol == "AAPL"
    marquee_emits = [e for e in app.emits if e[0] == "toolbar:marquee-set-item"]
    assert any(e[1].get("ticker") == "ws-symbol" for e in marquee_emits)


def test_yfinance_build_marquee():
    """The marquee toolbar carries the live-data ticker slots and CSS."""
    from openbb_yfinance.utils.tvchart_datafeed import build_marquee

    toolbar, css = build_marquee("AAPL")
    assert ".yf-marquee-strip" in css
    assert toolbar.items
    html = toolbar.items[0].text
    assert "ws-price" in html and "Mkt Cap" in html
