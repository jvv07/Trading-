import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from scipy import stats

from lib.style import inject_css
from lib.nav import render_nav

st.set_page_config(page_title="Seasonality", layout="wide", initial_sidebar_state="collapsed")
inject_css()
render_nav("Seasonality")
st.title("Seasonality Analysis")
st.caption("Discover recurring seasonal patterns in stocks and indices across time dimensions.")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("⚙ Settings")
    symbol = st.text_input("Primary Symbol", value="SPY").upper().strip()
    period = st.selectbox("History Period", ["5y", "10y", "15y", "20y"], index=1)
    return_type = st.radio("Return Type", ["Daily", "Weekly", "Monthly"], index=2)
    show_ci = st.checkbox("Show 95% Confidence Intervals", value=True)
    st.divider()
    compare_syms_raw = st.text_input("Compare Symbols (comma-sep)", placeholder="QQQ,IWM,GLD",
                                      help="Add symbols to compare seasonality patterns side-by-side")
    st.divider()
    st.caption("Patterns are computed from historical data and do not guarantee future results.")

compare_syms = [s.strip().upper() for s in compare_syms_raw.split(",") if s.strip()] if compare_syms_raw else []
all_syms = [symbol] + compare_syms

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=86400)
def load_seasonal_data(sym: str, period: str) -> pd.DataFrame:
    raw = yf.download(sym, period=period, auto_adjust=True, progress=False)
    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel(1)
    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df["daily_return"]  = df["Close"].pct_change()
    df["weekly_return"] = df["Close"].pct_change(5)
    df["monthly_return"] = df["Close"].pct_change(21)
    df["day_of_week"]   = df.index.dayofweek          # 0=Mon … 4=Fri
    df["month"]         = df.index.month
    df["quarter"]       = df.index.quarter
    df["year"]          = df.index.year
    df["week_of_year"]  = df.index.isocalendar().week.astype(int)
    df["day_of_year"]   = df.index.dayofyear
    df["decade"]        = (df["year"] // 10) * 10
    return df.dropna(subset=["daily_return"])

DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
QUARTER_LABELS = ["Q1", "Q2", "Q3", "Q4"]

ret_col_map = {"Daily": "daily_return", "Weekly": "weekly_return", "Monthly": "monthly_return"}
ret_col = ret_col_map[return_type]

# Load primary
df = load_seasonal_data(symbol, period)
if df.empty:
    st.error(f"No data for {symbol}.")
    st.stop()

st.caption(f"**{symbol}** — {len(df)} trading days | {df.index[0].date()} → {df.index[-1].date()}")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_dow, tab_monthly, tab_annual, tab_quarter, tab_multi, tab_heatmap = st.tabs([
    "📅 Day of Week", "📆 Monthly", "📈 Annual", "🗓 Quarterly", "🔀 Multi-Symbol", "🗺 Return Heatmap"
])


def ci_bar(group_series: pd.Series, labels: list, title: str,
           color_positive: str = "#00d4aa", color_negative: str = "#ff4b4b") -> go.Figure:
    """Bar chart with 95% CI error bars."""
    means, errors, counts, win_rates = [], [], [], []
    for lbl in labels:
        vals = group_series.get_group(lbl).dropna() if lbl in group_series.groups else pd.Series(dtype=float)
        means.append(vals.mean() * 100 if len(vals) else 0)
        se = vals.sem() * 100 * 1.96 if len(vals) > 1 else 0
        errors.append(se)
        counts.append(len(vals))
        win_rates.append((vals > 0).mean() * 100 if len(vals) else 0)

    colors = [color_positive if v >= 0 else color_negative for v in means]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=means,
        error_y=dict(type="data", array=errors, visible=show_ci, color="#888"),
        marker_color=colors, opacity=0.85,
        customdata=list(zip(counts, win_rates)),
        hovertemplate="<b>%{x}</b><br>Avg Return: %{y:.2f}%<br>Samples: %{customdata[0]}<br>Win Rate: %{customdata[1]:.1f}%<extra></extra>"
    ))
    fig.add_hline(y=0, line_color="#555", line_width=1)
    fig.update_layout(
        title=title, yaxis_ticksuffix="%",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
        xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
    )
    return fig, means, counts, win_rates


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Day of Week
# ══════════════════════════════════════════════════════════════════════════════
with tab_dow:
    st.subheader("Day of Week Effect")
    st.caption("Average daily returns split by day of week.")

    dow_group = df.dropna(subset=["daily_return"]).groupby("day_of_week")["daily_return"]

    fig_dow, dow_means, dow_counts, dow_wr = ci_bar(
        dow_group, list(range(5)),
        f"{symbol} — Average Return by Day of Week ({return_type})"
    )
    # Rename x-axis ticks
    fig_dow.update_xaxes(tickvals=list(range(5)), ticktext=DOW_LABELS)
    st.plotly_chart(fig_dow, use_container_width=True)

    # Summary table
    dow_df = pd.DataFrame({
        "Day": DOW_LABELS,
        "Avg Return": [f"{v:.3f}%" for v in dow_means],
        "Win Rate": [f"{w:.1f}%" for w in dow_wr],
        "Samples": dow_counts,
    })
    st.dataframe(dow_df, hide_index=True, use_container_width=True)

    # Box/violin plot for distribution
    st.subheader("Return Distribution by Day")
    daily_clean = df.dropna(subset=["daily_return"]).copy()
    daily_clean["Day"] = daily_clean["day_of_week"].map(dict(zip(range(5), DOW_LABELS)))
    fig_viol = go.Figure()
    for i, (day, clr) in enumerate(zip(DOW_LABELS, ["#4e9af1","#00d4aa","#f1c14e","#f17c4e","#b44ef1"])):
        d = daily_clean[daily_clean["Day"] == day]["daily_return"] * 100
        fig_viol.add_trace(go.Violin(
            x=[day] * len(d), y=d, name=day,
            box_visible=True, meanline_visible=True,
            fillcolor=clr, opacity=0.6, line_color=clr
        ))
    fig_viol.update_layout(
        title=f"{symbol} — Daily Return Distribution by Day",
        yaxis_title="Return (%)", yaxis_ticksuffix="%",
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
        xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
    )
    st.plotly_chart(fig_viol, use_container_width=True)

    # Statistical significance (t-test vs zero)
    st.subheader("Statistical Significance (t-test vs 0%)")
    sig_rows = []
    for i, day in enumerate(DOW_LABELS):
        vals = daily_clean[daily_clean["Day"] == day]["daily_return"].dropna()
        if len(vals) > 10:
            t_stat, p_val = stats.ttest_1samp(vals, 0)
            sig_rows.append({
                "Day": day, "t-statistic": f"{t_stat:.3f}",
                "p-value": f"{p_val:.4f}",
                "Significant (p<0.05)": "✓" if p_val < 0.05 else "✗",
                "Avg Return": f"{vals.mean()*100:.3f}%"
            })
    if sig_rows:
        st.dataframe(pd.DataFrame(sig_rows), hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Monthly
# ══════════════════════════════════════════════════════════════════════════════
with tab_monthly:
    st.subheader("Monthly Seasonality")

    # Use monthly returns (first trading day of each month)
    monthly_df = df.groupby(["year", "month"])["Close"].last().reset_index()
    monthly_df["return"] = monthly_df["Close"].pct_change()
    monthly_df = monthly_df.dropna(subset=["return"])

    month_group = monthly_df.groupby("month")["return"]
    fig_mon, mon_means, mon_counts, mon_wr = ci_bar(
        month_group, list(range(1, 13)),
        f"{symbol} — Average Monthly Return by Month"
    )
    fig_mon.update_xaxes(tickvals=list(range(1, 13)), ticktext=MONTH_LABELS)
    st.plotly_chart(fig_mon, use_container_width=True)

    # Monthly table
    mon_table = pd.DataFrame({
        "Month": MONTH_LABELS,
        "Avg Return": [f"{v:.2f}%" for v in mon_means],
        "Win Rate": [f"{w:.1f}%" for w in mon_wr],
        "Samples (years)": mon_counts,
    })
    st.dataframe(mon_table, hide_index=True, use_container_width=True)

    # Boxplot by month
    monthly_df["Month"] = monthly_df["month"].map(dict(zip(range(1, 13), MONTH_LABELS)))
    fig_mbox = go.Figure()
    colors_m = px.colors.qualitative.Plotly
    for i, mon in enumerate(MONTH_LABELS):
        d = monthly_df[monthly_df["Month"] == mon]["return"] * 100
        fig_mbox.add_trace(go.Box(
            y=d, name=mon,
            marker_color=colors_m[i % len(colors_m)],
            boxmean=True, jitter=0.3, pointpos=0
        ))
    fig_mbox.update_layout(
        title=f"{symbol} — Monthly Return Distribution",
        yaxis_title="Monthly Return (%)", yaxis_ticksuffix="%",
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
        xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
    )
    st.plotly_chart(fig_mbox, use_container_width=True)

    # "January Effect" and "Santa Claus Rally" specific callouts
    jan_avg = monthly_df[monthly_df["month"] == 1]["return"].mean() * 100
    dec_avg = monthly_df[monthly_df["month"] == 12]["return"].mean() * 100
    jan_wr  = (monthly_df[monthly_df["month"] == 1]["return"] > 0).mean() * 100
    dec_wr  = (monthly_df[monthly_df["month"] == 12]["return"] > 0).mean() * 100
    sep_avg = monthly_df[monthly_df["month"] == 9]["return"].mean() * 100
    oct_avg = monthly_df[monthly_df["month"] == 10]["return"].mean() * 100

    st.subheader("Classic Seasonal Patterns")
    fx1, fx2, fx3, fx4 = st.columns(4)
    fx1.metric("January Effect", f"{jan_avg:.2f}%", f"Win rate {jan_wr:.0f}%")
    fx2.metric("Santa Claus Rally (Dec)", f"{dec_avg:.2f}%", f"Win rate {dec_wr:.0f}%")
    fx3.metric("September Slump", f"{sep_avg:.2f}%")
    fx4.metric("October Recovery", f"{oct_avg:.2f}%")

    # Best 6 months vs worst 6 months (May-Oct vs Nov-Apr)
    may_oct = monthly_df[monthly_df["month"].isin([5,6,7,8,9,10])]["return"].mean() * 100
    nov_apr = monthly_df[monthly_df["month"].isin([11,12,1,2,3,4])]["return"].mean() * 100
    st.caption(f"**\"Sell in May\" Effect** — May-Oct avg: `{may_oct:.2f}%`  |  Nov-Apr avg: `{nov_apr:.2f}%`  |  "
               f"Difference: `{nov_apr - may_oct:.2f}%`")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Annual
# ══════════════════════════════════════════════════════════════════════════════
with tab_annual:
    st.subheader("Annual Returns")

    annual_df = df.groupby("year")["Close"].last()
    annual_ret = annual_df.pct_change().dropna() * 100

    colors_ann = ["#00d4aa" if v >= 0 else "#ff4b4b" for v in annual_ret.values]
    fig_ann = go.Figure()
    fig_ann.add_trace(go.Bar(
        x=annual_ret.index.astype(str), y=annual_ret.values,
        marker_color=colors_ann, opacity=0.85, name="Annual Return",
        hovertemplate="<b>%{x}</b>: %{y:.2f}%<extra></extra>"
    ))
    fig_ann.add_hline(y=annual_ret.mean(), line_dash="dash", line_color="#f1c14e",
                      annotation_text=f"Mean {annual_ret.mean():.1f}%")
    fig_ann.add_hline(y=0, line_color="#555", line_width=1)
    fig_ann.update_layout(
        title=f"{symbol} — Annual Returns",
        yaxis_ticksuffix="%",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
        xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
    )
    st.plotly_chart(fig_ann, use_container_width=True)

    # Cumulative return chart
    cum_ret = (1 + annual_ret / 100).cumprod()
    fig_cum = go.Figure()
    fig_cum.add_trace(go.Scatter(
        x=cum_ret.index.astype(str), y=cum_ret.values,
        mode="lines+markers", name="Cumulative Growth",
        line=dict(color="#4e9af1", width=2.5),
        fill="tozeroy", fillcolor="rgba(78,154,241,0.1)"
    ))
    fig_cum.update_layout(
        title=f"{symbol} — Cumulative Growth (Annual)",
        yaxis_title="Growth of $1",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
        xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
    )
    st.plotly_chart(fig_cum, use_container_width=True)

    # Rolling statistics
    if len(annual_ret) >= 5:
        roll5 = annual_ret.rolling(5)
        fig_roll = go.Figure()
        fig_roll.add_trace(go.Scatter(
            x=annual_ret.index.astype(str), y=roll5.mean(),
            name="5Y Rolling Mean", line=dict(color="#00d4aa", width=2)
        ))
        fig_roll.add_trace(go.Scatter(
            x=annual_ret.index.astype(str), y=roll5.std(),
            name="5Y Rolling Std Dev", line=dict(color="#ff4b4b", width=2, dash="dash")
        ))
        fig_roll.update_layout(
            title="5-Year Rolling Mean Return & Volatility",
            yaxis_ticksuffix="%",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#fafafa",
            xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig_roll, use_container_width=True)

    # Annual stats summary
    af1, af2, af3, af4, af5 = st.columns(5)
    af1.metric("Best Year", f"{annual_ret.index[annual_ret.argmax()]} ({annual_ret.max():.1f}%)")
    af2.metric("Worst Year", f"{annual_ret.index[annual_ret.argmin()]} ({annual_ret.min():.1f}%)")
    af3.metric("Average Annual Return", f"{annual_ret.mean():.2f}%")
    af4.metric("Annual Std Dev", f"{annual_ret.std():.2f}%")
    af5.metric("% Positive Years", f"{(annual_ret > 0).mean()*100:.0f}%")

    # Year-by-year table
    ann_table = pd.DataFrame({
        "Year": annual_ret.index,
        "Return": [f"{v:+.2f}%" for v in annual_ret.values],
        "Result": ["✓ Up" if v >= 0 else "✗ Down" for v in annual_ret.values],
    })
    st.dataframe(ann_table, hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Quarterly
# ══════════════════════════════════════════════════════════════════════════════
with tab_quarter:
    st.subheader("Quarterly Patterns")

    # Quarterly return = last close / first close within each (year, quarter)
    qtr_clean = df.groupby(["year", "quarter"])["Close"].agg(["first", "last"]).reset_index()
    qtr_clean["return"] = (qtr_clean["last"] / qtr_clean["first"] - 1) * 100

    q_grp = qtr_clean.groupby("quarter")["return"]
    q_means2 = [q_grp.get_group(q).mean() if q in q_grp.groups else 0 for q in range(1, 5)]
    q_wr2    = [(q_grp.get_group(q) > 0).mean() * 100 if q in q_grp.groups else 0 for q in range(1, 5)]
    q_cnt    = [len(q_grp.get_group(q)) if q in q_grp.groups else 0 for q in range(1, 5)]

    fig_q = go.Figure()
    fig_q.add_trace(go.Bar(
        x=QUARTER_LABELS, y=q_means2,
        marker_color=["#00d4aa" if v >= 0 else "#ff4b4b" for v in q_means2],
        opacity=0.85, name="Avg Quarterly Return",
        hovertemplate="<b>%{x}</b><br>Avg: %{y:.2f}%<extra></extra>"
    ))
    fig_q.add_hline(y=0, line_color="#555")
    fig_q.update_layout(
        title=f"{symbol} — Average Quarterly Return",
        yaxis_ticksuffix="%",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
        xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
    )
    st.plotly_chart(fig_q, use_container_width=True)

    # Q table
    st.dataframe(pd.DataFrame({
        "Quarter": QUARTER_LABELS,
        "Avg Return": [f"{v:.2f}%" for v in q_means2],
        "Win Rate": [f"{w:.1f}%" for w in q_wr2],
        "Samples": q_cnt,
    }), hide_index=True, use_container_width=True)

    # Quarterly heatmap: year × quarter
    qtr_pivot = qtr_clean.pivot(index="year", columns="quarter", values="return")
    qtr_pivot.columns = QUARTER_LABELS
    fig_qheat = go.Figure(go.Heatmap(
        z=qtr_pivot.values,
        x=QUARTER_LABELS,
        y=qtr_pivot.index.tolist(),
        colorscale=[[0, "#ff4b4b"], [0.5, "#1a1e2e"], [1, "#00d4aa"]],
        zmid=0,
        text=[[f"{v:.1f}%" if not np.isnan(v) else "" for v in row] for row in qtr_pivot.values],
        texttemplate="%{text}",
        colorbar=dict(title="Return %"),
    ))
    fig_qheat.update_layout(
        title=f"{symbol} — Quarterly Returns by Year",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
        xaxis=dict(side="top"),
        height=max(300, len(qtr_pivot) * 22 + 100),
    )
    st.plotly_chart(fig_qheat, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Multi-Symbol Comparison
# ══════════════════════════════════════════════════════════════════════════════
with tab_multi:
    st.subheader("Multi-Symbol Seasonality Comparison")

    if not compare_syms:
        st.info("Add comparison symbols in the sidebar (e.g. QQQ,IWM,GLD) to compare seasonal patterns.")
    else:
        @st.cache_data(ttl=86400)
        def load_monthly_returns(sym: str, period: str) -> pd.Series:
            raw = yf.download(sym, period=period, auto_adjust=True, progress=False)
            if raw.empty:
                return pd.Series(dtype=float)
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.droplevel(1)
            monthly = raw["Close"].resample("ME").last()
            return monthly.pct_change().dropna()

        # Load for all symbols
        monthly_data = {}
        for sym in all_syms:
            s = load_monthly_returns(sym, period)
            if not s.empty:
                monthly_data[sym] = s

        if len(monthly_data) < 2:
            st.warning("Could not load data for comparison symbols.")
        else:
            # Monthly averages comparison
            compare_dim = st.radio("Compare by", ["Month", "Quarter", "Day of Week"], horizontal=True)

            fig_comp = go.Figure()
            colors_comp = ["#4e9af1", "#00d4aa", "#f1c14e", "#ff4b4b", "#b44ef1", "#f17c4e"]

            for i, (sym, s) in enumerate(monthly_data.items()):
                s_df = s.reset_index()
                s_df.columns = ["date", "return"]
                s_df["month"]   = s_df["date"].dt.month
                s_df["quarter"] = s_df["date"].dt.quarter
                s_df["dow"]     = s_df["date"].dt.dayofweek

                if compare_dim == "Month":
                    grp = s_df.groupby("month")["return"].mean() * 100
                    x_labels = MONTH_LABELS
                    x_vals = list(range(1, 13))
                elif compare_dim == "Quarter":
                    grp = s_df.groupby("quarter")["return"].mean() * 100
                    x_labels = QUARTER_LABELS
                    x_vals = list(range(1, 5))
                else:
                    grp = s_df.groupby("dow")["return"].mean() * 100
                    x_labels = DOW_LABELS
                    x_vals = list(range(5))

                y_vals = [float(grp.get(v, np.nan)) for v in x_vals]
                fig_comp.add_trace(go.Scatter(
                    x=x_labels, y=y_vals, mode="lines+markers",
                    name=sym, line=dict(color=colors_comp[i % len(colors_comp)], width=2.5),
                    marker=dict(size=8)
                ))

            fig_comp.add_hline(y=0, line_color="#555")
            fig_comp.update_layout(
                title=f"Average Return by {compare_dim} — Multi-Symbol Comparison",
                yaxis_title="Avg Return (%)", yaxis_ticksuffix="%",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#fafafa",
                xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
                legend=dict(bgcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(fig_comp, use_container_width=True)

            # Correlation matrix of monthly returns
            st.subheader("Monthly Return Correlations")
            all_monthly = pd.DataFrame({sym: monthly_data[sym] for sym in monthly_data}).dropna()
            if len(all_monthly.columns) >= 2:
                corr = all_monthly.corr()
                fig_corr = go.Figure(go.Heatmap(
                    z=corr.values, x=corr.columns, y=corr.index,
                    colorscale=[[0, "#ff4b4b"], [0.5, "#1a1e2e"], [1, "#00d4aa"]],
                    zmid=0, zmin=-1, zmax=1,
                    text=[[f"{v:.2f}" for v in row] for row in corr.values],
                    texttemplate="%{text}",
                    colorbar=dict(title="Correlation"),
                ))
                fig_corr.update_layout(
                    title="Monthly Return Correlation Matrix",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#fafafa",
                )
                st.plotly_chart(fig_corr, use_container_width=True)

            # Relative strength over time
            st.subheader("Relative Performance Over Time")
            all_monthly_cum = (1 + all_monthly).cumprod()
            fig_rel = go.Figure()
            for i, sym in enumerate(all_monthly_cum.columns):
                fig_rel.add_trace(go.Scatter(
                    x=all_monthly_cum.index, y=all_monthly_cum[sym],
                    mode="lines", name=sym,
                    line=dict(color=colors_comp[i % len(colors_comp)], width=2)
                ))
            fig_rel.update_layout(
                title="Cumulative Growth Comparison (Monthly Rebalanced)",
                yaxis_title="Growth of $1",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#fafafa",
                xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
                legend=dict(bgcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(fig_rel, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Return Heatmap (Week × Year / Month × Year)
# ══════════════════════════════════════════════════════════════════════════════
with tab_heatmap:
    st.subheader("Historical Return Heatmap")
    heat_mode = st.radio("Heatmap Mode", ["Month × Year", "Day of Year (52-week calendar)"], horizontal=True)

    if heat_mode == "Month × Year":
        monthly_rets = df.groupby(["year", "month"])["Close"].apply(
            lambda g: (g.iloc[-1] / g.iloc[0] - 1) * 100
        ).reset_index(name="return")
        pivot = monthly_rets.pivot(index="month", columns="year", values="return")
        pivot.index = [MONTH_LABELS[i-1] for i in pivot.index]

        fig_heat = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.astype(str).tolist(),
            y=pivot.index.tolist(),
            colorscale=[[0.0, "#7f0000"], [0.35, "#ff4b4b"], [0.5, "#1a1e2e"],
                         [0.65, "#00d4aa"], [1.0, "#005f4e"]],
            zmid=0,
            text=[[f"{v:.1f}%" if not np.isnan(v) else "" for v in row] for row in pivot.values],
            texttemplate="%{text}",
            textfont=dict(size=9),
            colorbar=dict(title="Return %"),
        ))
        fig_heat.update_layout(
            title=f"{symbol} — Monthly Return Heatmap (Month × Year)",
            xaxis_title="Year",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#fafafa",
            height=420,
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    else:
        # 52-week calendar heatmap (week × day-of-week)
        daily_copy = df[["daily_return", "week_of_year", "day_of_week", "year"]].dropna(subset=["daily_return"]).copy()
        avg_by_week_day = daily_copy.groupby(["week_of_year", "day_of_week"])["daily_return"].mean() * 100
        pivot_wd = avg_by_week_day.unstack(level="day_of_week")
        pivot_wd = pivot_wd[[c for c in pivot_wd.columns if int(c) < 5]]
        pivot_wd.columns = [DOW_LABELS[int(c)] for c in pivot_wd.columns]

        fig_cal = go.Figure(go.Heatmap(
            z=pivot_wd.values.T,
            x=[f"Wk {w}" for w in pivot_wd.index],
            y=pivot_wd.columns.tolist(),
            colorscale=[[0, "#ff4b4b"], [0.5, "#1a1e2e"], [1, "#00d4aa"]],
            zmid=0,
            colorbar=dict(title="Avg Return %"),
        ))
        fig_cal.update_layout(
            title=f"{symbol} — Average Daily Return by Week & Day (Calendar Heatmap)",
            xaxis_title="Week of Year",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#fafafa",
            height=250,
        )
        st.plotly_chart(fig_cal, use_container_width=True)
        st.caption("Greener cells = historically strong days. Computed as average across all years in the history period.")

    # Best & worst seasonal windows
    st.subheader("Strongest Seasonal Windows")
    monthly_window = df.groupby(["year", "month"])["Close"].apply(
        lambda g: (g.iloc[-1] / g.iloc[0] - 1) * 100
    ).reset_index(name="return")
    best_months = monthly_window.groupby("month")["return"].mean().sort_values(ascending=False)
    worst_months = best_months.tail(3)
    best_months_top = best_months.head(3)

    bw1, bw2 = st.columns(2)
    with bw1:
        st.markdown("**Top 3 Strongest Months**")
        for m_num, avg in best_months_top.items():
            st.markdown(f"- **{MONTH_LABELS[int(m_num)-1]}**: avg `{avg:.2f}%`")
    with bw2:
        st.markdown("**Top 3 Weakest Months**")
        for m_num, avg in worst_months.items():
            st.markdown(f"- **{MONTH_LABELS[int(m_num)-1]}**: avg `{avg:.2f}%`")
