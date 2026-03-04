import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from lib.style import inject_css, kpi_card, section_header
from lib.nav import render_nav
from lib.universe import SECTOR_ETFS, SECTOR_WEIGHTS, SP100

st.set_page_config(page_title="Market Overview", layout="wide", initial_sidebar_state="collapsed")
inject_css()
render_nav("Market")

st.title("Market Overview")

INDICES = {
    "S&P 500":    "^GSPC",
    "NASDAQ":     "^IXIC",
    "Dow Jones":  "^DJI",
    "Russell 2K": "^RUT",
    "VIX":        "^VIX",
    "10Y Yield":  "^TNX",
}

# ── Index KPIs ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=180)
def _index_snap():
    rows = {}
    for name, ticker in INDICES.items():
        try:
            fi = yf.Ticker(ticker).fast_info
            last = fi.last_price
            prev = fi.previous_close
            chg = last - prev
            pct = chg / prev * 100 if prev else 0
            rows[name] = {"last": last, "chg": chg, "pct": pct}
        except Exception:
            rows[name] = {"last": 0, "chg": 0, "pct": 0}
    return rows

snap = _index_snap()
cols = st.columns(len(INDICES))
for i, (name, data) in enumerate(snap.items()):
    pos = data["pct"] >= 0
    suffix = "%" if name not in ("10Y Yield",) else "%"
    with cols[i]:
        st.markdown(kpi_card(
            label=name,
            value=f"{data['last']:,.2f}",
            delta=f"{data['pct']:+.2f}%",
            positive=pos,
            accent="#00d4aa" if pos else "#ff4b4b",
        ), unsafe_allow_html=True)

st.divider()

tab_sectors, tab_movers, tab_internals = st.tabs(
    ["📊  Sector Rotation", "🚀  Top Movers", "🌡  Market Internals"]
)

# ── Sector Rotation ───────────────────────────────────────────────────────────
with tab_sectors:
    @st.cache_data(ttl=600)
    def _sector_data():
        etfs = list(SECTOR_ETFS.values())
        raw = yf.download(etfs, period="1y", auto_adjust=True, progress=False)
        closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]

        results = {}
        for sector, etf in SECTOR_ETFS.items():
            if etf not in closes.columns:
                continue
            c = closes[etf].dropna()
            if len(c) < 2:
                continue
            last = float(c.iloc[-1])
            prev = float(c.iloc[-2])

            def ret(n):
                return (last / float(c.iloc[-n]) - 1) * 100 if len(c) >= n else None

            results[sector] = {
                "ETF": etf, "Last": last,
                "1D":  round((last/prev - 1)*100, 2),
                "1W":  round(ret(6),  2) if ret(6)  is not None else None,
                "1M":  round(ret(22), 2) if ret(22) is not None else None,
                "3M":  round(ret(66), 2) if ret(66) is not None else None,
                "6M":  round(ret(130),2) if ret(130)is not None else None,
                "1Y":  round((last/float(c.iloc[0]) - 1)*100, 2),
            }
        return results

    sector_data = _sector_data()

    if sector_data:
        c1, c2 = st.columns([3, 2])

        with c1:
            st.markdown(section_header("Performance Heatmap", "Returns across timeframes"), unsafe_allow_html=True)
            periods = ["1D", "1W", "1M", "3M", "6M", "1Y"]
            sectors_list = list(sector_data.keys())
            z = [[sector_data[s].get(p) for p in periods] for s in sectors_list]
            text = [[f"{v:+.1f}%" if v is not None else "" for v in row] for row in z]

            fig = go.Figure(go.Heatmap(
                z=z, x=periods, y=sectors_list,
                text=text, texttemplate="%{text}",
                textfont=dict(size=11, family="JetBrains Mono"),
                colorscale=[[0,"#7f1d1d"],[0.35,"#ff4b4b"],[0.5,"#131c2e"],[0.65,"#00d4aa"],[1,"#064e3b"]],
                zmid=0, showscale=True,
                colorbar=dict(ticksuffix="%", thickness=12, len=0.8,
                              tickfont=dict(color="#4a5a72"), bgcolor="#0a0e1a",
                              bordercolor="#1a2332"),
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#8892a4", margin=dict(l=0, r=0, t=10, b=0),
                xaxis=dict(side="top", gridcolor="#1a2332"),
                yaxis=dict(gridcolor="#1a2332"),
                height=340,
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown(section_header("Today's Allocation", "S&P 500 sector weights × 1D return"), unsafe_allow_html=True)
            treemap_rows = []
            for sector, d in sector_data.items():
                treemap_rows.append({
                    "Sector": sector,
                    "Weight": SECTOR_WEIGHTS.get(sector, 5),
                    "1D Return": d["1D"],
                    "Label": f"{sector}<br>{d['1D']:+.2f}%",
                })
            tm_df = pd.DataFrame(treemap_rows)

            fig2 = px.treemap(
                tm_df, path=["Sector"], values="Weight", color="1D Return",
                color_continuous_scale=[[0,"#7f1d1d"],[0.35,"#ff4b4b"],[0.5,"#131c2e"],[0.65,"#00d4aa"],[1,"#064e3b"]],
                color_continuous_midpoint=0,
                custom_data=["1D Return"],
            )
            fig2.update_traces(
                texttemplate="<b>%{label}</b><br>%{customdata[0]:+.1f}%",
                textfont_size=11,
            )
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=0,b=0),
                coloraxis_showscale=False, height=340,
            )
            st.plotly_chart(fig2, use_container_width=True)

        # Sector table
        st.markdown(section_header("Sector Detail"), unsafe_allow_html=True)
        df_sec = pd.DataFrame([
            {"Sector": s, **{k: v for k, v in d.items() if k != "ETF"}}
            for s, d in sector_data.items()
        ]).sort_values("1D", ascending=False)

        def _color_pct(v):
            if not isinstance(v, (int, float)) or np.isnan(v):
                return ""
            return "color: #00d4aa" if v > 0 else "color: #ff4b4b"

        st.dataframe(
            df_sec.style
                .format({"Last": "${:.2f}", "1D": "{:+.2f}%", "1W": "{:+.2f}%",
                         "1M": "{:+.2f}%", "3M": "{:+.2f}%", "6M": "{:+.2f}%", "1Y": "{:+.2f}%"})
                .map(_color_pct, subset=["1D","1W","1M","3M","6M","1Y"]),
            use_container_width=True, hide_index=True,
        )

# ── Top Movers ────────────────────────────────────────────────────────────────
with tab_movers:
    st.markdown(section_header("Top Movers — S&P 100", "Today's biggest % moves"), unsafe_allow_html=True)

    @st.cache_data(ttl=300)
    def _movers():
        raw = yf.download(SP100[:80], period="2d", auto_adjust=True, progress=False)
        closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        if len(closes) < 2:
            return [], []
        ret = ((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100).dropna()
        rows = [{"Symbol": s, "Last": float(closes[s].iloc[-1]),
                 "Chg %": float(ret[s])} for s in ret.index if s in closes.columns]
        df = pd.DataFrame(rows).sort_values("Chg %", ascending=False)
        return df.head(10).to_dict("records"), df.tail(10).to_dict("records")

    gainers, losers = _movers()

    g_col, l_col = st.columns(2)

    def _movers_chart(data, title, color):
        if not data:
            return go.Figure()
        syms = [d["Symbol"] for d in data]
        vals = [d["Chg %"] for d in data]
        fig = go.Figure(go.Bar(
            x=vals, y=syms, orientation="h",
            marker_color=color, text=[f"{v:+.2f}%" for v in vals],
            textposition="outside", textfont=dict(size=11),
        ))
        fig.update_layout(
            title=title, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#8892a4", xaxis=dict(gridcolor="#1a2332", ticksuffix="%"),
            yaxis=dict(gridcolor="#1a2332"), margin=dict(l=0,r=60,t=40,b=0), height=320,
        )
        return fig

    with g_col:
        st.plotly_chart(_movers_chart(gainers, "Top Gainers", "#00d4aa"), use_container_width=True)
    with l_col:
        st.plotly_chart(_movers_chart(list(reversed(losers)), "Top Losers", "#ff4b4b"), use_container_width=True)

    # Bubble chart: return vs volume
    @st.cache_data(ttl=600)
    def _bubble():
        raw = yf.download(SP100[:60], period="5d", auto_adjust=True, progress=False)
        closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        vols   = raw["Volume"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Volume"]]
        if len(closes) < 2:
            return pd.DataFrame()
        ret_1d = ((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100).dropna()
        ret_5d = ((closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0] * 100).dropna()
        avg_vol = vols.mean()
        rows = []
        for s in ret_1d.index:
            if s in ret_5d.index and s in avg_vol.index:
                rows.append({"Symbol": s, "1D %": float(ret_1d[s]),
                             "5D %": float(ret_5d[s]), "Avg Vol M": float(avg_vol[s])/1e6})
        return pd.DataFrame(rows)

    bdf = _bubble()
    if not bdf.empty:
        st.markdown(section_header("Momentum Map", "1-day vs 5-day return (bubble = avg volume)"), unsafe_allow_html=True)
        fig3 = px.scatter(
            bdf, x="5D %", y="1D %", size="Avg Vol M", text="Symbol",
            color="1D %",
            color_continuous_scale=[[0,"#ff4b4b"],[0.5,"#131c2e"],[1,"#00d4aa"]],
            color_continuous_midpoint=0, size_max=40,
        )
        fig3.update_traces(textposition="top center", textfont=dict(size=9, color="#8892a4"))
        fig3.add_hline(y=0, line_dash="dash", line_color="#1a2332")
        fig3.add_vline(x=0, line_dash="dash", line_color="#1a2332")
        fig3.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#8892a4", xaxis=dict(gridcolor="#1a2332", ticksuffix="%", title="5-Day Return"),
            yaxis=dict(gridcolor="#1a2332", ticksuffix="%", title="1-Day Return"),
            coloraxis_showscale=False, height=420, margin=dict(l=0,r=0,t=10,b=0),
        )
        st.plotly_chart(fig3, use_container_width=True)

# ── Market Internals ──────────────────────────────────────────────────────────
with tab_internals:
    @st.cache_data(ttl=600)
    def _internals():
        from lib.indicators import sma, rsi as rsi_fn
        raw = yf.download(SP100[:80], period="1y", auto_adjust=True, progress=False)
        closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]

        above_50  = sum(1 for s in closes.columns
                        if len(closes[s].dropna()) > 50
                        and float(closes[s].dropna().iloc[-1]) > float(sma(closes[s].dropna(), 50).iloc[-1]))
        above_200 = sum(1 for s in closes.columns
                        if len(closes[s].dropna()) > 200
                        and float(closes[s].dropna().iloc[-1]) > float(sma(closes[s].dropna(), 200).iloc[-1]))
        n = len(closes.columns)

        rsi_vals = []
        for s in closes.columns:
            c = closes[s].dropna()
            if len(c) > 14:
                v = rsi_fn(c).iloc[-1]
                if not pd.isna(v):
                    rsi_vals.append(float(v))

        return {
            "above_50": above_50, "above_200": above_200, "n": n,
            "rsi_vals": rsi_vals,
            "pct_50": above_50/n*100, "pct_200": above_200/n*100,
            "avg_rsi": float(np.mean(rsi_vals)) if rsi_vals else 50,
        }

    with st.spinner("Computing market breadth..."):
        internals = _internals()

    i1, i2, i3, i4 = st.columns(4)
    i1.metric("% Above 50-Day MA",  f"{internals['pct_50']:.1f}%",
              help="Breadth indicator. >70% = broad rally; <30% = broad weakness")
    i2.metric("% Above 200-Day MA", f"{internals['pct_200']:.1f}%",
              help="Long-term trend breadth. >60% = bull market")
    i3.metric("Avg RSI (S&P 100)",  f"{internals['avg_rsi']:.1f}",
              help="Overbought > 70, oversold < 30")
    i4.metric("Stocks Analysed",    internals["n"])

    # RSI distribution
    if internals["rsi_vals"]:
        st.markdown(section_header("RSI Distribution — S&P 100"), unsafe_allow_html=True)
        fig4 = go.Figure(go.Histogram(
            x=internals["rsi_vals"], nbinsx=30,
            marker_color="#4e9af1", opacity=0.8,
        ))
        fig4.add_vline(x=30, line_dash="dash", line_color="#00d4aa", annotation_text="Oversold 30")
        fig4.add_vline(x=70, line_dash="dash", line_color="#ff4b4b", annotation_text="Overbought 70")
        fig4.add_vline(x=internals["avg_rsi"], line_color="#f1c14e",
                       annotation_text=f"Avg {internals['avg_rsi']:.0f}")
        fig4.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#8892a4", xaxis=dict(gridcolor="#1a2332", title="RSI"),
            yaxis=dict(gridcolor="#1a2332", title="# Stocks"),
            height=280, margin=dict(l=0,r=0,t=10,b=0),
        )
        st.plotly_chart(fig4, use_container_width=True)
        oversold  = sum(1 for v in internals["rsi_vals"] if v < 30)
        overbought = sum(1 for v in internals["rsi_vals"] if v > 70)
        neutral   = len(internals["rsi_vals"]) - oversold - overbought
        bc1, bc2, bc3 = st.columns(3)
        bc1.metric("Oversold  (RSI < 30)", oversold,  help="Potential mean-reversion candidates")
        bc2.metric("Neutral   (30–70)",    neutral)
        bc3.metric("Overbought (RSI > 70)", overbought, help="Stretched — watch for pullbacks")
