"""
Reusable Plotly chart builders for the trading dashboard.
All charts use the dark theme palette.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from lib import metrics as m

TEAL = "#00d4aa"
BLUE = "#4e9af1"
RED = "#ff4b4b"
YELLOW = "#f1c14e"
PURPLE = "#b44ef1"
GRID = "#2a2f3e"
BG = "rgba(0,0,0,0)"
FONT = "#fafafa"

PALETTE = [TEAL, BLUE, YELLOW, PURPLE, "#f17c4e", "#4ef1c1", "#f14e9a"]

_layout = dict(
    paper_bgcolor=BG,
    plot_bgcolor=BG,
    font_color=FONT,
    xaxis=dict(gridcolor=GRID, showgrid=True),
    yaxis=dict(gridcolor=GRID, showgrid=True),
    legend=dict(bgcolor="rgba(0,0,0,0.3)", bordercolor=GRID),
    margin=dict(l=10, r=10, t=40, b=10),
)


def equity_curve(series_dict: dict, title: str = "Equity Curve") -> go.Figure:
    """series_dict: {label: pd.Series}"""
    fig = go.Figure()
    for i, (label, s) in enumerate(series_dict.items()):
        color = PALETTE[i % len(PALETTE)]
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values,
            name=label,
            mode="lines",
            line=dict(color=color, width=2),
        ))
    fig.update_layout(title=title, yaxis_tickprefix="$", **_layout)
    return fig


def drawdown_chart(equity: pd.Series, title: str = "Drawdown") -> go.Figure:
    dd = m.drawdown_series(equity) * 100
    fig = go.Figure(go.Scatter(
        x=dd.index, y=dd.values,
        mode="lines",
        fill="tozeroy",
        line=dict(color=RED, width=1),
        fillcolor=f"rgba(255,75,75,0.2)",
        name="Drawdown",
    ))
    fig.update_layout(title=title, yaxis_ticksuffix="%", **_layout)
    return fig


def monthly_returns_heatmap(returns: pd.Series, title: str = "Monthly Returns") -> go.Figure:
    r = returns.copy()
    r.index = pd.to_datetime(r.index)
    monthly = r.resample("ME").apply(lambda x: (1 + x).prod() - 1) * 100
    df = monthly.to_frame("ret")
    df["year"] = df.index.year
    df["month"] = df.index.month

    pivot = df.pivot(index="year", columns="month", values="ret")
    pivot.columns = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    z = pivot.values
    text = [[f"{v:.1f}%" if not np.isnan(v) else "" for v in row] for row in z]

    fig = go.Figure(go.Heatmap(
        z=z,
        x=list(pivot.columns),
        y=[str(y) for y in pivot.index],
        text=text,
        texttemplate="%{text}",
        colorscale=[[0, RED], [0.5, "#1a1f2e"], [1, TEAL]],
        zmid=0,
        showscale=True,
        colorbar=dict(ticksuffix="%"),
    ))
    fig.update_layout(title=title, **_layout)
    return fig


def rolling_sharpe_chart(returns: pd.Series, window: int = 63, title: str = "Rolling Sharpe (63-day)") -> go.Figure:
    rs = m.rolling_sharpe(returns, window).dropna()
    fig = go.Figure(go.Scatter(
        x=rs.index, y=rs.values,
        mode="lines",
        line=dict(color=BLUE, width=1.5),
        name="Rolling Sharpe",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color=GRID)
    fig.add_hline(y=1, line_dash="dot", line_color=TEAL, annotation_text="Sharpe=1")
    fig.update_layout(title=title, **_layout)
    return fig


def return_distribution(returns: pd.Series, title: str = "Daily Return Distribution") -> go.Figure:
    r = returns.dropna() * 100
    fig = go.Figure(go.Histogram(
        x=r,
        nbinsx=50,
        marker_color=BLUE,
        opacity=0.8,
        name="Returns",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color=FONT)
    fig.add_vline(x=r.mean(), line_color=TEAL, annotation_text=f"Mean {r.mean():.2f}%")
    fig.update_layout(title=title, xaxis_ticksuffix="%", **_layout)
    return fig


def candlestick_with_indicators(df: pd.DataFrame, indicators: dict = None, title: str = "") -> go.Figure:
    """
    df: must have Open/High/Low/Close/Volume columns.
    indicators: {label: pd.Series} overlaid on price panel.
    """
    rows = 3 if "Volume" in df.columns else 2
    specs = [[{"type": "candlestick"}], [{"type": "scatter"}]]
    if rows == 3:
        specs.append([{"type": "bar"}])
    row_heights = [0.6, 0.2, 0.2] if rows == 3 else [0.7, 0.3]

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=[title, "RSI", "Volume"] if rows == 3 else [title, "RSI"],
    )

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="Price",
        increasing_line_color=TEAL,
        decreasing_line_color=RED,
    ), row=1, col=1)

    if indicators:
        for i, (label, series) in enumerate(indicators.items()):
            if label.startswith("RSI"):
                fig.add_trace(go.Scatter(x=series.index, y=series.values, name=label,
                                         line=dict(color=PURPLE, width=1.5)), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color=RED, row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color=TEAL, row=2, col=1)
            else:
                color = PALETTE[i % len(PALETTE)]
                fig.add_trace(go.Scatter(x=series.index, y=series.values, name=label,
                                         line=dict(color=color, width=1.5)), row=1, col=1)

    if rows == 3 and "Volume" in df.columns:
        colors = [TEAL if c >= o else RED for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume",
                              marker_color=colors, opacity=0.6), row=3, col=1)

    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG, font_color=FONT,
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(bgcolor="rgba(0,0,0,0.3)"),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    for i in range(1, rows + 1):
        fig.update_xaxes(gridcolor=GRID, row=i, col=1)
        fig.update_yaxes(gridcolor=GRID, row=i, col=1)
    return fig


def correlation_heatmap(corr_matrix: pd.DataFrame, title: str = "Correlation Matrix") -> go.Figure:
    z = corr_matrix.values
    labels = list(corr_matrix.columns)
    text = [[f"{v:.2f}" for v in row] for row in z]
    fig = go.Figure(go.Heatmap(
        z=z, x=labels, y=labels,
        text=text, texttemplate="%{text}",
        colorscale=[[0, RED], [0.5, "#1a1f2e"], [1, TEAL]],
        zmin=-1, zmax=1, zmid=0,
        showscale=True,
    ))
    fig.update_layout(title=title, **_layout)
    return fig


def bar_by_category(data: pd.Series, title: str, xlabel: str = "", ylabel: str = "$") -> go.Figure:
    colors = [TEAL if v >= 0 else RED for v in data.values]
    fig = go.Figure(go.Bar(x=data.index, y=data.values, marker_color=colors))
    fig.update_layout(
        title=title,
        xaxis_title=xlabel,
        yaxis_tickprefix=ylabel if ylabel == "$" else "",
        yaxis_ticksuffix=ylabel if ylabel != "$" else "",
        **_layout,
    )
    return fig
