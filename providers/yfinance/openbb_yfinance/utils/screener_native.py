"""Native / Jupyter screener builder powered by PyWry and the yfinance screener."""

from typing import Any


def _run_screen(config: dict, limit: int | None) -> list[dict]:
    """Run the screener for a builder config on a private event loop."""
    import asyncio

    from openbb_core.provider.utils.errors import EmptyDataError

    from openbb_yfinance.utils.helpers import get_custom_screener
    from openbb_yfinance.utils.screener_catalog import screener_body_from_config

    body = screener_body_from_config(config)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            get_custom_screener(body, limit, keep_illiquid=True)
        )
    except EmptyDataError:
        return []
    finally:
        loop.close()


def make_screener_callbacks(app: Any) -> dict:
    """Build the callback dict that serves screener results over the PyWry bridge."""
    import json

    def on_run(data: dict[str, Any], *_: Any) -> None:
        is_default = bool(data.get("isDefault"))
        try:
            config = json.loads(data.get("config") or "{}")
        except (ValueError, TypeError):
            config = {}
        # limit <= 0 is the universe puller: None paginates to the region total.
        requested = int(data.get("limit") or 0)
        limit = None if requested <= 0 else requested
        try:
            rows = _run_screen(config, limit)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI status line
            app.emit(
                "screener:results",
                {"error": str(exc), "rows": [], "isDefault": is_default},
            )
            return
        app.emit("screener:results", {"rows": rows, "isDefault": is_default})

    def on_theme(data: dict[str, Any], *_: Any) -> None:
        from pywry import ThemeMode

        theme = (data.get("theme") or "dark").lower()
        app.theme = ThemeMode.LIGHT if theme == "light" else ThemeMode.DARK

    def on_templates_list(_data: dict[str, Any], *_: Any) -> None:
        from openbb_yfinance.utils.screener_presets import list_presets

        try:
            app.emit("screener:templates", {"templates": list_presets()})
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI status line
            app.emit("screener:templates", {"templates": [], "error": str(exc)})

    def on_template_load(data: dict[str, Any], *_: Any) -> None:
        from openbb_yfinance.utils.screener_presets import load_preset_config

        name = str(data.get("name") or "")
        try:
            app.emit(
                "screener:template-loaded",
                {"config": load_preset_config(name), "name": name},
            )
        except (FileNotFoundError, ValueError) as exc:
            app.emit("screener:template-loaded", {"error": str(exc)})

    def on_template_save(data: dict[str, Any], *_: Any) -> None:
        from openbb_yfinance.utils.screener_presets import list_presets, save_preset

        try:
            config = json.loads(data.get("config") or "{}")
        except (ValueError, TypeError):
            config = {}
        try:
            saved = save_preset(str(data.get("name") or ""), config)
        except (ValueError, OSError) as exc:
            app.emit("screener:template-saved", {"error": str(exc)})
            return
        app.emit(
            "screener:template-saved",
            {"ok": True, "name": saved["name"], "templates": list_presets()},
        )

    def on_template_delete(data: dict[str, Any], *_: Any) -> None:
        from openbb_yfinance.utils.screener_presets import delete_preset, list_presets

        try:
            delete_preset(str(data.get("name") or ""))
        except (FileNotFoundError, ValueError, OSError) as exc:
            app.emit("screener:template-deleted", {"error": str(exc)})
            return
        app.emit("screener:template-deleted", {"ok": True, "templates": list_presets()})

    return {
        "screener:run": on_run,
        "pywry:update-theme": on_theme,
        "screener:templates-list": on_templates_list,
        "screener:template-load": on_template_load,
        "screener:template-save": on_template_save,
        "screener:template-delete": on_template_delete,
    }


_APP: Any = None


def _get_app(theme_mode: Any) -> Any:
    """Return the process-wide PyWry application, creating it once."""
    global _APP  # noqa: PLW0603 - process-wide PyWry singleton
    from pywry import PyWry

    if _APP is None:
        _APP = PyWry(theme=theme_mode)
    else:
        _APP.theme = theme_mode
    return _APP


def launch_screener_builder(
    theme: str = "dark",
    width: int = 1320,
    height: int = 880,
) -> Any:
    """Open the interactive screener builder and return the PyWry window handle.

    The window opens without blocking; the live results path runs over the PyWry
    bridge via the ``screener:run`` callback. Call this off the event loop (the
    router command runs it in an executor) so PyWry can start its window.

    Parameters
    ----------
    theme : str
        ``dark`` or ``light``.
    width, height : int
        Native window dimensions.

    Returns
    -------
    Any
        The PyWry window handle (native) or inline widget (Jupyter).
    """
    from pywry import ThemeMode

    from openbb_yfinance.utils.screener_iframe import build_screener_content

    theme_mode = ThemeMode.LIGHT if str(theme).lower() == "light" else ThemeMode.DARK
    app = _get_app(theme_mode)

    content, toolbars, modals, _ = build_screener_content(theme, transport="bridge")

    return app.show(
        content,
        title="OpenBB - Yahoo Finance Screener Builder",
        width=width,
        height=height,
        include_aggrid=True,
        aggrid_theme="quartz",
        toolbars=toolbars,
        modals=modals,
        callbacks=make_screener_callbacks(app),
    )
