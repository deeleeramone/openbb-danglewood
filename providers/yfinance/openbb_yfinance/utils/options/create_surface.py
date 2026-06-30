"""Implied-volatility 3-D surface chart.

Built on openbb-charting's generic ``surface3d`` (DTE / Strike / IV axes). Only
implied volatility is plotted because yfinance carries no greeks.
"""

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from openbb_core.app.model.obbject import OBBject
    from openbb_core.provider.standard_models.options_chains import OptionsChainsData


def create_surface(  # noqa: PLR0912
    data: "OptionsChainsData",
    option_type: Literal["otm", "itm", "puts", "calls"] = "otm",
    dte_range: list[int] | None = None,
    moneyness: float | None = None,
    oi: bool = False,
    volume: bool = False,
    **kwargs,
) -> "OBBject":
    """Chart implied volatility as a 3-D surface over DTE and strike."""
    from openbb_charting.charts.generic_charts import surface3d
    from openbb_core.app.model.abstract.error import OpenBBError
    from openbb_core.app.model.charts.chart import Chart
    from openbb_core.app.model.obbject import OBBject
    from openbb_core.app.utils import df_to_basemodel
    from pandas import concat

    target = "implied_volatility"
    options = data.dataframe
    last_price = float(data.underlying_price[0] or 0.0)
    symbol = data.underlying_symbol[0]

    if target not in options.columns:
        raise OpenBBError("No implied volatility data available.")

    calls = options.query(f"`option_type` == 'call' & `dte` >= 0 & `{target}` > 0")
    puts = options.query(f"`option_type` == 'put' & `dte` >= 0 & `{target}` > 0")

    if oi:
        calls = calls[calls["open_interest"] > 0]
        puts = puts[puts["open_interest"] > 0]
    if volume:
        calls = calls[calls["volume"] > 0]
        puts = puts[puts["volume"] > 0]

    def _between(frame, col, low, high):
        return frame[(frame[col] >= low) & (frame[col] <= high)]

    if dte_range is not None and len(dte_range) > 1:
        calls = _between(calls, "dte", min(dte_range), max(dte_range))
        puts = _between(puts, "dte", min(dte_range), max(dte_range))

    if moneyness is not None and moneyness > 0:
        low = (1 - (moneyness / 100)) * last_price
        high = (1 + (moneyness / 100)) * last_price
        calls = _between(calls, "strike", low, high)
        puts = _between(puts, "strike", low, high)

    keys = ["expiration", "strike", "option_type"]
    if option_type == "otm":
        df = (
            concat(
                [
                    calls.query("`strike` > @last_price").set_index(keys),
                    puts.query("`strike` < @last_price").set_index(keys),
                ]
            )
            .sort_index()
            .reset_index()
        )
    elif option_type == "itm":
        df = (
            concat(
                [
                    calls.query("`strike` < @last_price").set_index(keys),
                    puts.query("`strike` > @last_price").set_index(keys),
                ]
            )
            .sort_index()
            .reset_index()
        )
    elif option_type == "calls":
        df = calls
    else:
        df = puts

    df = df[
        [
            "expiration",
            "strike",
            "option_type",
            "dte",
            target,
            "open_interest",
            "volume",
        ]
    ]

    label_dict = {"calls": "Call", "puts": "Put", "otm": "OTM", "itm": "ITM"}
    label = f"{symbol} {label_dict[option_type]} IV Surface"
    if oi:
        label += " With Open Interest"
    if volume:
        label += " Excluding Untraded Contracts"

    theme = kwargs.get("theme", "light")
    fig = surface3d(
        X=df["dte"],
        Y=df["strike"],
        Z=df[target],
        xtitle="DTE",
        ytitle="Strike",
        ztitle="IV",
        title=label,
        theme=theme,
    )

    df.expiration = df.expiration.astype(str)
    output: Any = OBBject(results=df_to_basemodel(df))
    output.charting._charting_settings.chart_style = theme
    fig = output.charting._set_chart_style(fig)
    text_color = "white" if theme == "dark" else "black"
    fig.update_layout(
        hoverlabel=dict(
            bgcolor="#0E0E0E" if text_color == "white" else "#FFFFFF",
            bordercolor=text_color,
            font=dict(color=text_color, size=12),
        )
    )
    content = fig.show(
        config={"scrollZoom": True, "displayModeBar": True}, external=True
    ).to_plotly_json()
    output.chart = Chart(fig=fig, content=content, format="plotly")

    return output
