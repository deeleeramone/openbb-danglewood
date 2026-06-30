"""Options term-structure chart (price or implied volatility across expirations)."""

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from openbb_core.app.model.obbject import OBBject
    from openbb_core.provider.standard_models.options_chains import OptionsChainsData


def create_term_structure(
    data: "OptionsChainsData",
    strike: float | None = None,
    moneyness: float | None = None,
    metric: Literal["price", "iv"] = "iv",
    option_type: Literal["both", "calls", "puts"] = "both",
    **kwargs,
) -> "OBBject":
    """Chart price or IV at the nearest strike across each expiration."""
    from openbb_charting.core.chart_style import ChartStyle
    from openbb_charting.core.openbb_figure import OpenBBFigure
    from openbb_core.app.model.abstract.error import OpenBBError
    from openbb_core.app.model.charts.chart import Chart
    from openbb_core.app.model.obbject import OBBject
    from openbb_core.app.utils import df_to_basemodel
    from pandas import DataFrame, concat, to_datetime

    if metric == "iv" and not data.has_iv:
        raise OpenBBError("No implied volatility data available.")

    df = data.dataframe.copy()
    expirations = data.expirations
    symbol = data.underlying_symbol[0]
    price_col = (
        "last_trade_price"
        if "last_trade_price" in df.columns
        else data._identify_price_col(df, "call", "ask")
    )
    target_col_map = {"price": price_col, "iv": "implied_volatility"}
    df.expiration = df.expiration.astype(str)

    base = f"{symbol} {'Implied Volatility' if metric == 'iv' else 'Price'}"
    if strike:
        title = f"{base} @ Strike Nearest To ${strike}"
    elif moneyness:
        title = f"{base} @ {moneyness}% Moneyness"
    else:
        title = f"{base} Nearest OTM Strikes"

    calls = DataFrame()
    puts = DataFrame()
    for expiration in expirations:
        if expiration not in df.expiration.unique():
            continue
        nearest_otm = (
            data._get_nearest_otm_strikes(expiration, moneyness=moneyness)
            if moneyness
            else {}
        )
        call_strike = (
            nearest_otm.get("call")
            if nearest_otm
            else data._get_nearest_strike(
                option_type="call", days=expiration, strike=strike
            )
        )
        put_strike = (
            nearest_otm.get("put")
            if nearest_otm
            else data._get_nearest_strike(
                option_type="put", days=expiration, strike=strike
            )
        )

        calls_filtered = df[
            (df.expiration == expiration)
            & (df.option_type == "call")
            & (df[price_col] > 0)
        ]
        if not calls_filtered.empty:
            calls = concat(
                [
                    calls,
                    calls_filtered.iloc[
                        (calls_filtered.strike - call_strike).abs().argsort()[:1]
                    ],
                ]
            )
        puts_filtered = df[
            (df.expiration == expiration)
            & (df.option_type == "put")
            & (df[price_col] > 0)
        ]
        if not puts_filtered.empty:
            puts = concat(
                [
                    puts,
                    puts_filtered.iloc[
                        (puts_filtered.strike - put_strike).abs().argsort()[:1]
                    ],
                ]
            )

    output_df = concat([calls, puts], axis=0).reset_index(drop=True)

    theme = kwargs.get("theme", "light")
    fig = OpenBBFigure(create_backend=True)
    fig.update_layout(ChartStyle().plotly_template.get("layout", {}))
    text_color = "white" if theme == "dark" else "black"
    hovertemplate = (
        "$<b>%{y} @ $</b>%{customdata} Strike<extra></extra>"
        if metric == "price"
        else "<b>%{y} @ $</b>%{customdata} Strike<extra></extra>"
    )

    if option_type in ["calls", "both"] and not calls.empty:
        fig.add_scatter(
            x=expirations,
            y=calls[target_col_map[metric]],
            mode="lines+markers",
            name="Calls",
            marker_color="blue",
            hovertemplate=hovertemplate,
            customdata=calls["strike"],
        )
    if option_type in ["puts", "both"] and not puts.empty:
        fig.add_scatter(
            x=expirations,
            y=puts[target_col_map[metric]],
            mode="lines+markers",
            name="Puts",
            marker_color="red",
            hovertemplate=hovertemplate,
            customdata=puts["strike"],
        )

    bg = "rgba(0,0,0,0)" if text_color == "white" else "rgba(255,255,255,0)"
    fig.set_title(title, x=0.5, font=dict(size=16))
    fig.update_layout(
        paper_bgcolor=bg,
        plot_bgcolor=bg,
        yaxis=dict(
            ticklen=0,
            showgrid=True,
            tickfont=dict(size=12),
            automargin=True,
            linecolor=text_color,
            showline=True,
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(size=11),
            ticklen=0,
            type="category",
            linecolor=text_color,
            showline=True,
            nticks=10,
            showspikes=False,
        ),
        legend=dict(orientation="v", yanchor="top", y=0.90, xanchor="right", x=-0.01),
        hovermode="x unified",
        font=dict(color=text_color),
        margin=dict(l=10, r=10, t=10, b=10),
    )

    df.expiration = to_datetime(df.expiration).dt.date
    output: Any = OBBject(results=df_to_basemodel(output_df))
    output.charting._charting_settings.chart_style = theme
    fig = output.charting._set_chart_style(fig)
    fig.update_layout(
        hoverlabel=dict(
            bgcolor="#0E0E0E" if text_color == "white" else "#FFFFFF",
            bordercolor=text_color,
            font=dict(color=text_color, size=12),
        )
    )
    content = fig.show(config={"scrollZoom": True}, external=True).to_plotly_json()
    output.chart = Chart(fig=fig, content=content, format="plotly")

    return output
