"""
Strategy Scanner — finds which stocks perform best under a given strategy.
Vectorized: all tickers downloaded in one batch, signals computed in parallel.
"""

import json
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from lib.style import inject_css, signal_badge, section_header, info_banner
from lib.universe import UNIVERSE_OPTIONS
from lib.indicators import sma, ema, rsi, macd, bollinger_bands
from lib.backtest import STRATEGIES

st.set_page_config(page_title="Scanner", layout="wide")
inject_css()

st.title("Strategy Scanner")
st.markdown(
    "<p style='color:#4a5a72;margin-top:-8px'>Find stocks that perform best under any strategy — vectorized across entire universes.</p>",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar config
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Scanner Config")
    universe_choice = st.selectbox("Universe", list(UNIVERSE_OPTIONS.keys()), index=0)
    custom_input = st.text_input("Custom tickers (comma-sep, overrides universe)",
                                  placeholder="AAPL, MSFT, TSLA")

    st.divider()
    strategy_name = st.selectbox("Strategy", list(STRATEGIES.keys()))
    strat_meta = STRATEGIES[strategy_name]
    st.caption(strat_meta["description"])

    params = {}
    for key, cfg in strat_meta["params"].items():
        if cfg["type"] == "int":
            params[key] = st.slider(cfg["label"], cfg["min"], cfg["max"], cfg["default"])
        else:
            params[key] = st.slider(cfg["label"], float(cfg["min"]), float(cfg["max"]),
                                     float(cfg["default"]), step=0.1)

    st.divider()
    lookback = st.selectbox("Lookback", ["3 Months","6 Months","1 Year","2 Years"], index=1)
    period_map = {"3 Months": "3mo", "6 Months": "6mo", "1 Year": "1y", "2 Years": "2y"}
    period = period_map[lookback]

    min_signal_only = st.checkbox("Show active signals only", value=False)
    run_btn = st.button("▶  Run Scanner", type="primary", use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Signal computers (vectorized over DataFrame of closes)
# ─────────────────────────────────────────────────────────────────────────────
def _signals_sma(closes, p):
    fast = closes.rolling(p["fast_period"]).mean()
    slow = closes.rolling(p["slow_period"]).mean()
    return (fast > slow).astype(float)

def _signals_rsi(closes, p):
    delta = closes.diff()
    gain  = delta.clip(lower=0).ewm(com=p["period"]-1, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=p["period"]-1, adjust=False).mean()
    r     = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    sig   = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    sig[r < p["oversold"]]  = 1.0
    sig[r > p["overbought"]] = 0.0
    return sig.ffill()

def _signals_bollinger(closes, p):
    mid = closes.rolling(p["period"]).mean()
    std = closes.rolling(p["period"]).std()
    lower = mid - p["std_dev"] * std
    sig = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    sig[closes < lower] = 1.0
    sig[closes > mid]   = 0.0
    return sig.ffill()

def _signals_macd(closes, p):
    fast_ema = closes.ewm(span=p["fast"],   adjust=False).mean()
    slow_ema = closes.ewm(span=p["slow"],   adjust=False).mean()
    macd_line   = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=p["signal"], adjust=False).mean()
    return (macd_line > signal_line).astype(float)

def _signals_momentum(closes, p):
    ret = closes.pct_change(p["lookback"])
    return (ret > p["threshold"]).astype(float)

SIGNAL_VEC = {
    "SMA Crossover":      _signals_sma,
    "RSI Reversion":      _signals_rsi,
    "Bollinger Reversion":_signals_bollinger,
    "MACD Crossover":     _signals_macd,
    "Momentum":           _signals_momentum,
}

# ─────────────────────────────────────────────────────────────────────────────
# Core scan function
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def run_scan(tickers_key: str, strategy: str, params_key: str, period: str) -> pd.DataFrame:
    tickers = tickers_key.split(",")
    params  = json.loads(params_key)

    raw = yf.download(tickers, period=period, auto_adjust=True, progress=False)
    if raw.empty:
        return pd.DataFrame()

    closes = raw["Close"]  if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    volumes= raw["Volume"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Volume"]]

    # Drop tickers with too little data
    closes = closes.dropna(axis=1, thresh=60)
    if closes.empty:
        return pd.DataFrame()

    # ── Vectorized signals ──
    signal_fn = SIGNAL_VEC[strategy]
    signals   = signal_fn(closes, params)

    cur_sig  = signals.iloc[-1]
    prev_sig = signals.iloc[-2] if len(signals) > 1 else pd.Series(0, index=signals.columns)

    # ── Vectorized returns ──
    daily_ret  = closes.pct_change()
    positions  = signals.shift(1)
    strat_ret  = positions * daily_ret
    cum_strat  = (1 + strat_ret.fillna(0)).prod() - 1
    cum_bh     = (1 + daily_ret.fillna(0)).prod() - 1
    excess     = cum_strat - cum_bh

    # ── Vectorized RSI ──
    delta = closes.diff()
    gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rsi_all = (100 - 100 / (1 + gain / loss.replace(0, np.nan))).iloc[-1]

    # ── SMA distances ──
    sma20_dist = ((closes.iloc[-1] / closes.rolling(20).mean().iloc[-1]) - 1) * 100
    sma50_dist = ((closes.iloc[-1] / closes.rolling(50).mean().iloc[-1]) - 1) * 100

    # ── Volume ratio (today vs 20d avg) ──
    vol_ratio  = (volumes.iloc[-1] / volumes.rolling(20).mean().iloc[-1]) if not volumes.empty else pd.Series(1.0, index=closes.columns)

    # ── 1M / 3M momentum ──
    ret_1m = ((closes.iloc[-1] / closes.iloc[-20]) - 1) * 100 if len(closes) >= 20 else pd.Series(0.0, index=closes.columns)
    ret_3m = ((closes.iloc[-1] / closes.iloc[-60]) - 1) * 100 if len(closes) >= 60 else pd.Series(0.0, index=closes.columns)

    # ── 52W high/low ──
    high52 = closes.rolling(252).max().iloc[-1]
    low52  = closes.rolling(252).min().iloc[-1]
    vs_high = ((closes.iloc[-1] / high52) - 1) * 100

    rows = []
    for sym in closes.columns:
        cs = int(cur_sig.get(sym, 0))
        ps = int(prev_sig.get(sym, 0))
        if   cs == 1 and ps == 0: sig_label = "NEW BUY"
        elif cs == 1:             sig_label = "BUY"
        elif cs == 0 and ps == 1: sig_label = "NEW SELL"
        else:                     sig_label = "NEUTRAL"

        rows.append({
            "Symbol":        sym,
            "Signal":        sig_label,
            "_sig_order":    {"NEW BUY": 0, "BUY": 1, "NEW SELL": 2, "NEUTRAL": 3}[sig_label],
            "Last":          round(float(closes[sym].iloc[-1]), 2),
            "RSI":           round(float(rsi_all.get(sym, 50)), 1),
            "vs SMA20 %":    round(float(sma20_dist.get(sym, 0)), 1),
            "vs SMA50 %":    round(float(sma50_dist.get(sym, 0)), 1),
            "1M Ret %":      round(float(ret_1m.get(sym, 0)), 1),
            "3M Ret %":      round(float(ret_3m.get(sym, 0)), 1),
            "Strat Ret %":   round(float(cum_strat.get(sym, 0)) * 100, 1),
            "B&H Ret %":     round(float(cum_bh.get(sym, 0))   * 100, 1),
            "Excess Ret %":  round(float(excess.get(sym, 0))   * 100, 1),
            "Vol Ratio":     round(float(vol_ratio.get(sym, 1)), 2),
            "vs 52W High %": round(float(vs_high.get(sym, 0)), 1),
        })

    df = pd.DataFrame(rows).sort_values(["_sig_order", "Excess Ret %"], ascending=[True, False])
    return df.drop(columns=["_sig_order"])


# ─────────────────────────────────────────────────────────────────────────────
# Run & display
# ─────────────────────────────────────────────────────────────────────────────
if not run_btn:
    st.markdown(info_banner(
        "⟵  Configure your universe and strategy in the sidebar, then click <b>Run Scanner</b>.",
        "#4e9af1",
    ), unsafe_allow_html=True)

    # Preview universe
    tickers_preview = UNIVERSE_OPTIONS.get(universe_choice, [])
    st.markdown(section_header(f"Universe preview — {universe_choice}", f"{len(tickers_preview)} stocks"), unsafe_allow_html=True)
    chips = " ".join(f"`{t}`" for t in tickers_preview[:40])
    st.markdown(chips + (" …" if len(tickers_preview) > 40 else ""))
    st.stop()

# ── Resolve tickers ───────────────────────────────────────────────────────────
if custom_input.strip():
    tickers = [t.strip().upper() for t in custom_input.split(",") if t.strip()]
else:
    tickers = UNIVERSE_OPTIONS.get(universe_choice, [])

if not tickers:
    st.error("No tickers selected.")
    st.stop()

with st.spinner(f"Scanning {len(tickers)} stocks with **{strategy_name}** over {lookback}…"):
    df = run_scan(
        tickers_key=",".join(sorted(tickers)),
        strategy=strategy_name,
        params_key=json.dumps(params, sort_keys=True),
        period=period,
    )

if df.empty:
    st.error("No data returned. Check ticker symbols and try again.")
    st.stop()

if min_signal_only:
    df = df[df["Signal"].isin(["NEW BUY", "BUY"])]

# ─────────────────────────────────────────────────────────────────────────────
# Summary KPIs
# ─────────────────────────────────────────────────────────────────────────────
new_buys  = (df["Signal"] == "NEW BUY").sum()
buys      = (df["Signal"] == "BUY").sum()
new_sells = (df["Signal"] == "NEW SELL").sum()
avg_excess = df["Excess Ret %"].mean()
top_sym   = df.iloc[0]["Symbol"] if not df.empty else "—"

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Stocks Scanned",   len(df))
k2.metric("🟢 New Buy Signals", new_buys)
k3.metric("▲ Active Buys",    buys)
k4.metric("Avg Excess Return", f"{avg_excess:+.1f}%",
          help="Strategy return minus buy-and-hold, averaged across all stocks")
k5.metric("Best Candidate",   top_sym,
          help="Highest excess return with active signal")

st.divider()

tab_signals, tab_table, tab_rank, tab_dist = st.tabs([
    "🚦  Active Signals", "📋  Full Results", "🏆  Strategy Rankings", "📊  Distributions"
])

# ─────────────────────────────────────────────────────────────────────────────
# Tab 1 – Active signals
# ─────────────────────────────────────────────────────────────────────────────
with tab_signals:
    active = df[df["Signal"].isin(["NEW BUY", "BUY"])].copy()
    if active.empty:
        st.info("No active buy signals in this universe right now.")
    else:
        st.markdown(
            section_header(f"{len(active)} Active Buy Signals",
                           "Sorted by historical strategy excess return → highest conviction first"),
            unsafe_allow_html=True,
        )
        for _, row in active.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1, 2])
                c1.markdown(f"### {row['Symbol']}")
                c1.markdown(signal_badge(row["Signal"]), unsafe_allow_html=True)
                c2.metric("Last Price",   f"${row['Last']:,.2f}")
                c2.metric("RSI",          f"{row['RSI']:.1f}",
                          delta="Oversold" if row['RSI'] < 30 else ("Overbought" if row['RSI'] > 70 else None))
                c3.metric("1M Return",    f"{row['1M Ret %']:+.1f}%",  delta_color="normal")
                c3.metric("3M Return",    f"{row['3M Ret %']:+.1f}%",  delta_color="normal")
                c4.metric("Strat Return", f"{row['Strat Ret %']:+.1f}%")
                c4.metric("Excess vs B&H",f"{row['Excess Ret %']:+.1f}%",
                          delta_color="normal")
                c5.markdown(f"""
<div style='font-size:.8rem;color:#4a5a72;line-height:1.8'>
  <div>vs SMA20: <span style='color:{"#00d4aa" if row["vs SMA20 %"]>0 else "#ff4b4b"}'>{row["vs SMA20 %"]:+.1f}%</span></div>
  <div>vs SMA50: <span style='color:{"#00d4aa" if row["vs SMA50 %"]>0 else "#ff4b4b"}'>{row["vs SMA50 %"]:+.1f}%</span></div>
  <div>vs 52W High: <span style='color:#f1c14e'>{row["vs 52W High %"]:.1f}%</span></div>
  <div>Vol Ratio: <span style='color:{"#f1c14e" if row["Vol Ratio"]>1.5 else "#8892a4"}'>{row["Vol Ratio"]:.2f}x</span></div>
</div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Tab 2 – Full table
# ─────────────────────────────────────────────────────────────────────────────
with tab_table:
    def _color(v):
        if isinstance(v, (int, float)) and not np.isnan(v):
            return "color: #00d4aa" if v > 0 else "color: #ff4b4b"
        return ""

    st.dataframe(
        df.style
            .format({
                "Last":          "${:.2f}",
                "RSI":           "{:.1f}",
                "vs SMA20 %":    "{:+.1f}%",
                "vs SMA50 %":    "{:+.1f}%",
                "1M Ret %":      "{:+.1f}%",
                "3M Ret %":      "{:+.1f}%",
                "Strat Ret %":   "{:+.1f}%",
                "B&H Ret %":     "{:+.1f}%",
                "Excess Ret %":  "{:+.1f}%",
                "Vol Ratio":     "{:.2f}x",
                "vs 52W High %": "{:.1f}%",
            })
            .map(_color, subset=["vs SMA20 %","vs SMA50 %","1M Ret %","3M Ret %",
                                  "Strat Ret %","B&H Ret %","Excess Ret %"]),
        use_container_width=True, hide_index=True, height=500,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Tab 3 – Strategy rankings
# ─────────────────────────────────────────────────────────────────────────────
with tab_rank:
    st.markdown(
        section_header("Best Stocks for This Strategy",
                       f"Ranked by excess return over buy-and-hold ({lookback})"),
        unsafe_allow_html=True,
    )
    top20 = df.nlargest(20, "Excess Ret %")
    bot20 = df.nsmallest(20, "Excess Ret %")

    rc1, rc2 = st.columns(2)
    with rc1:
        st.markdown("**Top 20 — Strategy Works Best Here**")
        fig_top = go.Figure(go.Bar(
            x=top20["Excess Ret %"], y=top20["Symbol"], orientation="h",
            marker=dict(
                color=top20["Excess Ret %"],
                colorscale=[[0,"#131c2e"],[1,"#00d4aa"]],
            ),
            text=[f"{v:+.1f}%" for v in top20["Excess Ret %"]],
            textposition="outside", textfont=dict(size=10),
        ))
        fig_top.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#8892a4", height=480,
            xaxis=dict(gridcolor="#1a2332", ticksuffix="%"),
            yaxis=dict(gridcolor="#1a2332", autorange="reversed"),
            margin=dict(l=0,r=60,t=10,b=0),
        )
        st.plotly_chart(fig_top, use_container_width=True)

    with rc2:
        st.markdown("**Bottom 20 — Strategy Works Worst Here**")
        fig_bot = go.Figure(go.Bar(
            x=bot20["Excess Ret %"], y=bot20["Symbol"], orientation="h",
            marker=dict(
                color=bot20["Excess Ret %"],
                colorscale=[[0,"#ff4b4b"],[1,"#131c2e"]],
                cmin=bot20["Excess Ret %"].min(), cmax=0,
            ),
            text=[f"{v:+.1f}%" for v in bot20["Excess Ret %"]],
            textposition="outside", textfont=dict(size=10),
        ))
        fig_bot.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#8892a4", height=480,
            xaxis=dict(gridcolor="#1a2332", ticksuffix="%"),
            yaxis=dict(gridcolor="#1a2332", autorange="reversed"),
            margin=dict(l=0,r=60,t=10,b=0),
        )
        st.plotly_chart(fig_bot, use_container_width=True)

    # Scatter: B&H return vs strategy return
    st.markdown(section_header("Alpha Map", "Each dot = one stock. Above the diagonal = strategy beats buy & hold"), unsafe_allow_html=True)
    fig_sc = px.scatter(
        df, x="B&H Ret %", y="Strat Ret %", text="Symbol",
        color="Excess Ret %",
        color_continuous_scale=[[0,"#ff4b4b"],[0.5,"#131c2e"],[1,"#00d4aa"]],
        color_continuous_midpoint=0,
        hover_data={"Signal": True, "RSI": True, "Excess Ret %": ":.1f"},
    )
    max_val = max(df[["B&H Ret %","Strat Ret %"]].abs().max())
    fig_sc.add_shape(type="line", x0=-max_val, y0=-max_val, x1=max_val, y1=max_val,
                     line=dict(dash="dash", color="#2a3a52"))
    fig_sc.update_traces(textposition="top center", textfont=dict(size=8, color="#4a5a72"))
    fig_sc.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#8892a4", height=420,
        xaxis=dict(gridcolor="#1a2332", ticksuffix="%", title="Buy & Hold Return"),
        yaxis=dict(gridcolor="#1a2332", ticksuffix="%", title="Strategy Return"),
        coloraxis_showscale=True, margin=dict(l=0,r=0,t=10,b=0),
    )
    st.plotly_chart(fig_sc, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# Tab 4 – Distributions
# ─────────────────────────────────────────────────────────────────────────────
with tab_dist:
    d1, d2 = st.columns(2)
    with d1:
        st.markdown(section_header("RSI Distribution"), unsafe_allow_html=True)
        fig_rsi = go.Figure(go.Histogram(x=df["RSI"], nbinsx=25,
                                          marker_color="#4e9af1", opacity=.8))
        fig_rsi.add_vline(x=30, line_dash="dash", line_color="#00d4aa", annotation_text="30")
        fig_rsi.add_vline(x=70, line_dash="dash", line_color="#ff4b4b", annotation_text="70")
        fig_rsi.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color="#8892a4", height=260,
                               xaxis=dict(gridcolor="#1a2332"), yaxis=dict(gridcolor="#1a2332"),
                               margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig_rsi, use_container_width=True)

    with d2:
        st.markdown(section_header("Excess Return Distribution"), unsafe_allow_html=True)
        fig_ex = go.Figure(go.Histogram(x=df["Excess Ret %"], nbinsx=25,
                                         marker_color="#b44ef1", opacity=.8))
        fig_ex.add_vline(x=0, line_dash="dash", line_color="#fafafa")
        fig_ex.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="#8892a4", height=260,
                              xaxis=dict(gridcolor="#1a2332", ticksuffix="%"),
                              yaxis=dict(gridcolor="#1a2332"),
                              margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig_ex, use_container_width=True)

    # Signal breakdown pie
    sig_counts = df["Signal"].value_counts().reset_index()
    sig_counts.columns = ["Signal","Count"]
    fig_pie = go.Figure(go.Pie(
        labels=sig_counts["Signal"], values=sig_counts["Count"], hole=.5,
        marker_colors=["#00ff99","#00d4aa","#ff4b4b","#3a4a62"],
    ))
    fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#8892a4",
                           title="Signal Breakdown", height=280,
                           margin=dict(l=0,r=0,t=40,b=0))
    st.plotly_chart(fig_pie, use_container_width=True)
