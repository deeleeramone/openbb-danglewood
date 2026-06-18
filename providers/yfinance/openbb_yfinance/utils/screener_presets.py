"""Yahoo Finance screener preset loading from INI files."""

import re
from pathlib import Path
from typing import Any

_PRESETS_ENV_VAR = "OPENBB_YFINANCE_PRESETS_DIRECTORY"
_DEFAULT_PRESETS_DIR = Path(__file__).parent.resolve() / "presets"
_QUOTE_TYPES = {
    "equity": "EQUITY",
    "fund": "MUTUALFUND",
    "mutualfund": "MUTUALFUND",
    "etf": "ETF",
    "index": "INDEX",
    "future": "FUTURE",
}
_RANGE_OPERATORS = ("_gte", "_lte", "_gt", "_lt")


def get_bundled_presets() -> dict[str, Path]:
    """Return the selectable preset INI files that ship with the provider.

    Files whose name starts with ``_`` (e.g. the ``_template.ini`` reference)
    are shipped but excluded from the selectable choices.
    """
    if not _DEFAULT_PRESETS_DIR.exists():
        return {}
    return {
        filepath.stem: filepath
        for filepath in _DEFAULT_PRESETS_DIR.iterdir()
        if filepath.suffix == ".ini" and not filepath.stem.startswith("_")
    }


def _presets_dir_from_config() -> str | None:
    """Read the presets directory from the layered ``openbb.toml`` config."""
    try:
        from openbb_core.app.config.loader import load_config

        config = load_config()
        section = config.get("yfinance")
        if isinstance(section, dict) and section.get("presets_directory"):
            return section["presets_directory"]
        return config.get("yfinance_presets_directory")
    except Exception:
        return None


def resolve_user_presets_directory(data_directory: str | None = None) -> Path:
    """Resolve the user presets directory from env var, openbb.toml, or default."""
    import os

    env_dir = os.environ.get(_PRESETS_ENV_VAR)
    if env_dir:
        return Path(env_dir).expanduser()

    config_dir = _presets_dir_from_config()
    if config_dir:
        return Path(config_dir).expanduser()

    base = data_directory or str(Path.home() / "OpenBBUserData")
    return Path(base) / "presets" / "yfinance"


def get_preset_choices(data_directory: str | None = None) -> dict[str, Path]:
    """Return a combined map of bundled and user screener presets."""
    import shutil
    from warnings import warn

    choices: dict[str, Path] = dict(get_bundled_presets())
    presets_user = resolve_user_presets_directory(data_directory)

    try:
        presets_user.mkdir(parents=True, exist_ok=True)
        for filepath in _DEFAULT_PRESETS_DIR.iterdir():
            if filepath.suffix == ".ini":
                target = presets_user / filepath.name
                if not target.exists():
                    shutil.copy(filepath, target)
        for filepath in presets_user.iterdir():
            if filepath.suffix == ".ini" and not filepath.stem.startswith("_"):
                choices[filepath.stem] = filepath
    except Exception as exc:
        warn(f"Error loading user yfinance screener presets: {exc}")

    return dict(sorted(choices.items()))


def _split_operator(key: str) -> tuple[str, str]:
    """Split a filter key into its (operator, field) parts."""
    for suffix in _RANGE_OPERATORS:
        if key.endswith(suffix):
            return suffix[1:], key[: -len(suffix)]
    return "eq", key


def build_screener_body(preset_path: Path) -> dict[str, Any]:
    """Parse a preset INI file into a Yahoo Finance screener request body."""
    from configparser import ConfigParser

    parser = ConfigParser()
    parser.optionxform = str  # ty: ignore[invalid-assignment]
    parser.read(preset_path, encoding="utf-8")

    screener = parser["screener"] if parser.has_section("screener") else {}
    asset_type = (screener.get("type", "equity") or "equity").lower()
    quote_type = _QUOTE_TYPES.get(asset_type, "EQUITY")

    operands: list[dict] = []
    if parser.has_section("filters"):
        for key, raw in parser["filters"].items():
            operator, field = _split_operator(key)
            if operator in ("gt", "lt", "gte", "lte"):
                operands.append(
                    {"operator": operator.upper(), "operands": [field, float(raw)]}
                )
                continue
            values = [v.strip() for v in raw.split(",") if v.strip()]
            if len(values) > 1:
                operands.append({"operator": "is-in", "operands": [field, *values]})
            elif values:
                operands.append({"operator": "EQ", "operands": [field, values[0]]})

    return {
        "offset": 0,
        "size": int(screener.get("limit", 100) or 100),
        "sortField": screener.get("sort_field", "percentchange"),
        "sortType": (screener.get("sort_type", "DESC") or "DESC").upper(),
        "quoteType": quote_type,
        "query": {"operator": "AND", "operands": operands},
        "userId": "",
        "userIdType": "guid",
    }


_TEMPLATE_STRING_FIELDS = {"region", "ticker", "primary_sector"}


def build_preset_template() -> str:
    """Generate a fully-documented preset template.

    Every screenable field (equity, ETF, mutual fund) and every enumerated value
    from yfinance is emitted as a commented-out entry for users to copy and
    uncomment.
    """
    from yfinance.const import (
        EQUITY_SCREENER_EQ_MAP,
        EQUITY_SCREENER_FIELDS,
        ETF_SCREENER_EQ_MAP,
        ETF_SCREENER_FIELDS,
        FUND_SCREENER_EQ_MAP,
        FUND_SCREENER_FIELDS,
    )

    def _wrap(values: list[str]) -> list[str]:
        out: list[str] = []
        for i in range(0, len(values), 4):
            out.append(";     " + " | ".join(values[i : i + 4]))
        return out

    lines = [
        "; " + "=" * 75,
        ";  Yahoo Finance Screener Preset Template",
        ";",
        ";  Copy this file to your presets directory, rename it (no leading '_'),",
        ";  and uncomment the lines you want. Every screenable field and every",
        ";  enumerated value is listed below.",
        ";",
        ";  [screener]  meta: asset type, result limit, sort order",
        ";  [filters]   one line per criterion",
        ";",
        ";  Operators (append to the field name):",
        ";    field      = value     equals (EQ); comma-separated values -> is-in",
        ";    field_gt   = number    greater than",
        ";    field_gte  = number    greater than or equal",
        ";    field_lt   = number    less than",
        ";    field_lte  = number    less than or equal",
        ";",
        ";  Fields are grouped by asset type; set [screener] type to match.",
        "; " + "=" * 75,
        "",
        "[screener]",
        "; type = equity         ; equity | etf | fund | mutualfund",
        "; limit = 100",
        "; sort_field = intradaymarketcap",
        "; sort_type = DESC      ; ASC | DESC",
        "",
        "[filters]",
    ]

    groups = [
        ("EQUITY", "equity", EQUITY_SCREENER_FIELDS, EQUITY_SCREENER_EQ_MAP),
        ("ETF", "etf", ETF_SCREENER_FIELDS, ETF_SCREENER_EQ_MAP),
        ("MUTUAL FUND", "fund", FUND_SCREENER_FIELDS, FUND_SCREENER_EQ_MAP),
    ]

    for label, type_value, fields, eq_map in groups:
        lines += [
            "",
            "; " + "=" * 75,
            f";  {label} fields   (set: type = {type_value})",
            "; " + "=" * 75,
        ]
        for category in sorted(fields):
            lines.append(f"; --- {category} ---")
            for field in sorted(fields[category]):
                if field in eq_map:
                    values = sorted(str(v) for v in eq_map[field])
                    example = values[0] if values else "value"
                    lines.append(
                        f"; {field} = {example}    ; equals; comma-separate for is-in"
                    )
                    lines.append(f";   {len(values)} values:")
                    lines += _wrap(values)
                elif field in _TEMPLATE_STRING_FIELDS:
                    lines.append(
                        f"; {field} = value    ; equals; comma-separate for is-in"
                    )
                else:
                    lines.append(f"; {field}_gt =     ; numeric; or _gte / _lt / _lte")

    return "\n".join(lines) + "\n"


_VALID_ASSETS = {"equity", "etf", "fund", "mutualfund"}
_VALID_OPERATORS = {"gt", "gte", "lt", "lte", "btwn", "eq", "is-in"}
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]*$")


def sanitize_preset_name(name: str) -> str:
    """Return a filesystem-safe preset stem, rejecting traversal or odd names.

    Only letters, numbers, spaces, ``-`` and ``_`` are allowed, the name may not
    start with ``_`` (reserved for shipped templates) or a space/hyphen, and a
    trailing ``.ini`` is stripped. Raises ``ValueError`` for anything else.
    """
    raw = str(name or "").strip()
    if raw.lower().endswith(".ini"):
        raw = raw[:-4].strip()
    if raw.startswith("_"):
        raise ValueError("Template names cannot start with '_'.")
    if not _NAME_RE.match(raw):
        raise ValueError(
            "Invalid template name. Use letters, numbers, spaces, '-' or '_'."
        )
    return raw


def _safe_preset_path(name: str, directory: Path) -> Path:
    """Resolve ``name`` to an ``.ini`` path proven to live inside ``directory``."""
    directory = Path(directory)
    target = (directory / f"{sanitize_preset_name(name)}.ini").resolve()
    try:
        target.relative_to(directory.resolve())
    except ValueError as exc:
        raise ValueError(
            "Resolved template path escapes the presets directory."
        ) from exc
    return target


def validate_config(config: dict) -> dict:
    """Coerce a builder config into a clean, whitelisted shape before saving."""
    if not isinstance(config, dict):
        raise ValueError("Template config must be an object.")

    asset = str(config.get("type", "equity")).lower()
    asset = "fund" if asset == "mutualfund" else asset
    if asset not in {"equity", "etf", "fund", "index", "future"}:
        asset = "equity"

    try:
        limit = int(config.get("limit") or 100)
    except (TypeError, ValueError):
        limit = 100
    limit = min(max(1, limit), 250)

    filters: list[dict] = []
    for item in config.get("filters") or []:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        operator = str(item.get("operator") or "").lower()
        value = item.get("value")
        if not field or operator not in _VALID_OPERATORS or value in (None, "", []):
            continue
        join = "or" if str(item.get("join", "and")).lower() == "or" else "and"
        filters.append(
            {"field": field, "operator": operator, "value": value, "join": join}
        )

    sort_type = (
        "ASC" if str(config.get("sort_type", "DESC")).upper() == "ASC" else "DESC"
    )
    return {
        "type": asset,
        "limit": limit,
        "sort_field": str(config.get("sort_field") or ""),
        "sort_type": sort_type,
        "filters": filters,
    }


def _fmt_number(value: Any) -> str:
    """Format a numeric filter value without a redundant trailing ``.0``."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else repr(number)


def config_to_ini(config: dict) -> str:
    """Serialise a builder config into the preset INI format.

    Filters are AND-joined (the join operand is not representable in the flat INI
    layout) and a ``between`` filter is written as paired ``_gte``/``_lte`` bounds,
    keeping the file readable by :func:`build_screener_body`.
    """
    clean = validate_config(config)
    lines = [
        "; Saved from the OpenBB Yahoo Finance screener builder.",
        "; Filters are AND-joined; 'between' is stored as _gte / _lte bounds.",
        "",
        "[screener]",
        f"type = {clean['type']}",
        f"limit = {clean['limit']}",
    ]
    if clean["sort_field"]:
        lines.append(f"sort_field = {clean['sort_field']}")
    lines += [f"sort_type = {clean['sort_type']}", "", "[filters]"]

    seen: set[str] = set()

    def put(key: str, val: str) -> None:
        if key not in seen:
            seen.add(key)
            lines.append(f"{key} = {val}")

    for item in clean["filters"]:
        field, operator, value = item["field"], item["operator"], item["value"]
        if operator in ("gt", "gte", "lt", "lte"):
            put(f"{field}_{operator}", _fmt_number(value))
        elif (
            operator == "btwn" and isinstance(value, (list, tuple)) and len(value) == 2
        ):
            put(f"{field}_gte", _fmt_number(value[0]))
            put(f"{field}_lte", _fmt_number(value[1]))
        elif operator == "is-in":
            values = value if isinstance(value, list) else [value]
            cleaned = [str(v).strip() for v in values if str(v).strip()]
            if cleaned:
                put(field, ", ".join(cleaned))
        else:
            put(field, str(value))

    return "\n".join(lines) + "\n"


def config_from_ini(preset_path: Path) -> dict:
    """Parse a preset INI file into a builder config.

    The inverse of :func:`config_to_ini`: numeric suffixes map back to gt/gte/lt/lte
    filters, comma lists to ``is-in`` and bare values to ``eq``; every filter is
    AND-joined. Display metadata (label, category, value type) is filled in by the
    builder from its field catalog.
    """
    from configparser import ConfigParser

    parser = ConfigParser()
    parser.optionxform = str  # ty: ignore[invalid-assignment]
    parser.read(preset_path, encoding="utf-8")

    screener = parser["screener"] if parser.has_section("screener") else {}
    asset = (screener.get("type", "equity") or "equity").lower()
    asset = "fund" if asset == "mutualfund" else asset
    if asset not in {"equity", "etf", "fund", "index", "future"}:
        asset = "equity"

    filters: list[dict] = []
    if parser.has_section("filters"):
        for key, raw in parser["filters"].items():
            operator, field = _split_operator(key)
            text = (raw or "").strip()
            if not text:
                continue
            if operator in ("gt", "gte", "lt", "lte"):
                try:
                    number = float(text)
                except ValueError:
                    continue
                value: Any = int(number) if number.is_integer() else number
                filters.append(
                    {
                        "field": field,
                        "operator": operator,
                        "value": value,
                        "join": "and",
                    }
                )
                continue
            values = [v.strip() for v in text.split(",") if v.strip()]
            if len(values) > 1:
                filters.append(
                    {
                        "field": field,
                        "operator": "is-in",
                        "value": values,
                        "join": "and",
                    }
                )
            elif values:
                filters.append(
                    {
                        "field": field,
                        "operator": "eq",
                        "value": values[0],
                        "join": "and",
                    }
                )

    try:
        limit = int(screener.get("limit", 100) or 100)
    except (TypeError, ValueError):
        limit = 100
    return {
        "type": asset,
        "limit": limit,
        "sort_field": screener.get("sort_field", "") or "",
        "sort_type": (screener.get("sort_type", "DESC") or "DESC").upper(),
        "filters": filters,
    }


def list_presets(data_directory: str | None = None) -> list[dict]:
    """Return the selectable screener templates as ``{name, label}`` entries."""
    return [
        {"name": stem, "label": stem.replace("_", " ").title()}
        for stem in get_preset_choices(data_directory)
    ]


def load_preset_config(name: str, data_directory: str | None = None) -> dict:
    """Load a saved template by name and return its builder config."""
    choices = get_preset_choices(data_directory)
    path = choices.get(name)
    if path is None:
        path = _safe_preset_path(name, resolve_user_presets_directory(data_directory))
        if not path.exists():
            raise FileNotFoundError(f"Template '{name}' was not found.")
    return config_from_ini(path)


def save_preset(name: str, config: dict, data_directory: str | None = None) -> dict:
    """Write a builder config to a named user template, returning ``{name}``."""
    directory = resolve_user_presets_directory(data_directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = _safe_preset_path(name, directory)
    target.write_text(config_to_ini(config), encoding="utf-8")
    return {"name": target.stem}


def delete_preset(name: str, data_directory: str | None = None) -> bool:
    """Delete a named user template, raising if it is missing or out of bounds."""
    directory = resolve_user_presets_directory(data_directory)
    target = _safe_preset_path(name, directory)
    if not target.exists():
        raise FileNotFoundError(f"Template '{name}' was not found.")
    target.unlink()
    return True
