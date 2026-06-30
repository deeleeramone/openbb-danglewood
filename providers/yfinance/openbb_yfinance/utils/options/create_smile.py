"""Implied-volatility smile and skew chart."""

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from openbb_core.app.model.obbject import OBBject
    from openbb_core.provider.standard_models.options_chains import OptionsChainsData


def create_smile(
    data: "OptionsChainsData",
    expirations: str | None = None,
    otm: bool = False,
    skew: bool = False,
    **kwargs,
) -> "OBBject":
    """Build the IV smile/skew across strikes for up to five expirations."""
    from openbb_charting.core.chart_style import ChartStyle
    from openbb_charting.core.openbb_figure import OpenBBFigure
    from openbb_core.app.model.abstract.error import OpenBBError
    from openbb_core.app.model.charts.chart import Chart
    from openbb_core.app.model.obbject import OBBject
    from openbb_core.app.utils import df_to_basemodel
    from pandas import DataFrame, concat, to_datetime

    if data.has_iv is False:
        raise OpenBBError(
            "Implied Volatility was not found in the data and is required here."
        )

    exp_list = (
        expirations.split(",")
        if isinstance(expirations, str)
        else expirations
        if isinstance(expirations, list)
        else [data.expirations[0]]
    )
    exp_list = [data._get_nearest_expiration(e) for e in exp_list]

    if len(exp_list) > 5:
        raise OpenBBError("Too many dates! Up to five can be selected.")

    df = concat(
        [data.skew(date=cast(str, to_datetime(exp).date())) for exp in exp_list]
    )

    output_df = DataFrame()
    symbol = data.underlying_symbol[0]
    colors = [
        "royalblue",
        "red",
        "orange",
        "green",
        "grey",
        "burlywood",
        "magenta",
        "cyan",
        "indigo",
        "yellowgreen",
    ]
    index_name = exp_list[0] if len(exp_list) <= 1 else None
    target_col = "Skew" if skew is True else "IV"
    title = (
        f"{symbol} {'OTM ' if otm is True else ''}"
        f"{'IV Skew' if skew is True else 'Implied Volatility'}"
    )

    fig = OpenBBFigure(create_backend=True)
    fig.update_layout(ChartStyle().plotly_template.get("layout", {}))
    text_color = "white" if "dark" in fig.layout.template else "black"
    color = -1
    theme = kwargs.get("theme", "light")
    if theme:
        text_color = "black" if theme == "light" else "white"

    for expiration in exp_list:
        calls = (
            df.query("`Expiration` == @expiration & `Option Type` == 'call'")
            .copy()
            .reset_index(drop=True)
        )
        puts = (
            df.query("`Expiration` == @expiration & `Option Type` == 'put'")
            .copy()
            .reset_index(drop=True)
        )
        if otm is True:
            put_idx = puts[puts["Skew"] == 0].index.values[0]
            put_iv = puts.iloc[0 : put_idx + 1]
            call_idx = calls[calls["Skew"] == 0].index.values[0]
            call_iv = calls.iloc[call_idx:-1]
            calls = call_iv.reset_index(drop=True)
            puts = put_iv.reset_index(drop=True)

        output_df = (
            concat([output_df, calls, puts], axis=0)
            if not output_df.empty
            else concat([calls, puts], axis=0)
        )
        color = color + 1
        fig.add_scatter(
            x=calls["Strike"].unique().tolist(),
            y=calls[target_col],
            mode="lines+markers",
            name="Calls" if len(exp_list) <= 1 else f"Calls at {expiration}",
            marker_color=colors[color],
            hoverinfo="x+y+name",
        )
        color = color + 1
        fig.add_scatter(
            x=puts["Strike"].unique().tolist(),
            y=puts[target_col],
            mode="lines+markers",
            name="Puts" if len(exp_list) <= 1 else f"Puts at {expiration}",
            marker_color=colors[color],
            hoverinfo="x+y+name",
        )

    bg = "rgba(0,0,0,0)" if text_color == "white" else "rgba(255,255,255,0)"
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=18)),
        yaxis=dict(
            ticklen=0,
            showline=False,
            linecolor=text_color,
            tickfont=dict(size=14),
            nticks=7,
        ),
        xaxis=dict(
            showgrid=False,
            autorange=True,
            ticklen=5,
            showline=False,
            linecolor=text_color,
            title=dict(text=index_name if index_name else "", font=dict(size=16)),
            tickfont=dict(size=16),
            nticks=7,
            showspikes=False,
            tickprefix="$",
        ),
        legend=dict(
            font=dict(size=14),
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="center",
            x=0.5,
            itemdoubleclick="toggleothers",
        ),
        font=dict(color=text_color),
        paper_bgcolor=bg,
        plot_bgcolor=bg,
        hoverdistance=1,
        hovermode="x unified",
        dragmode="pan",
    )
    output_df = (
        output_df.set_index(["Expiration", "Strike", "Option Type"])
        .sort_index()
        .reset_index()
    )
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
