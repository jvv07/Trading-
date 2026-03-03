"""
Portfolio Optimization — Markowitz Mean-Variance Framework
- Efficient frontier
- Max Sharpe portfolio
- Minimum Variance portfolio
- Risk Parity portfolio
- Equal Weight benchmark
"""

import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from scipy.optimize import minimize
from lib.style import inject_css, section_header, kpi_card, info_banner
from lib.portfolio import get_trades_df, compute_positions
from lib import metrics as m

st.set_page_config(page_title="Optimize", layout="wide")
inject_css()

st.title("Portfolio Optimizer")
st.markdown(
    "<p style='color:#4a5a72;margin-top:-8px'>Markowitz mean-variance optimization · efficient frontier · risk parity</p>",
    unsafe_allow_html=True,
)

RISK_FREE = 0.05
TRADING_DAYS = 252

# ── Helpers ───────────────────────────────────────────────────────────────────

def portfolio_stats(weights, mu, cov):
    w = np.array(weights)
    ret = float(w @ mu * TRADING_DAYS)
    vol = float(np.sqrt(w @ cov @ w * TRADING_DAYS))
    sharpe = (ret - RISK_FREE) / vol if vol else 0
    return ret, vol, sharpe

def neg_sharpe(weights, mu, cov):
    return -portfolio_stats(weights, mu, cov)[2]

def port_vol(weights, mu, cov):
    return portfolio_stats(weights, mu, cov)[1]

def _optimize(obj, mu, cov, extra_constraints=None):
    n = len(mu)
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    if extra_constraints:
        cons += extra_constraints
    bounds = tuple((0.0, 1.0) for _ in range(n))
    res = minimize(obj, x0=np.ones(n) / n, args=(mu, cov),
                   method="SLSQP", bounds=bounds, constraints=cons,
                   options={"maxiter": 1000, "ftol": 1e-9})
    return res.x if res.success else np.ones(n) / n

def max_sharpe(mu, cov):
    return _optimize(neg_sharpe, mu, cov)

def min_variance(mu, cov):
    return _optimize(port_vol, mu, cov)

def risk_parity(cov):
    n = cov.shape[0]
    def obj(w):
        w = np.array(w)
        port_v = np.sqrt(w @ cov @ w)
        mrc = cov @ w / port_v          # marginal risk contribution
        rc  = w * mrc                   # risk contribution
        return np.sum((rc - rc.mean()) ** 2)
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = tuple((0.001, 1.0) for _ in range(n))
    res = minimize(obj, x0=np.ones(n)/n, method="SLSQP",
                   bounds=bounds, constraints=cons, options={"maxiter": 2000})
    return res.x / res.x.sum()

def efficient_frontier_points(mu, cov, n=80):
    lo = float(mu.min() * TRADING_DAYS)
    hi = float(mu.max() * TRADING_DAYS)
    targets = np.linspace(lo, hi, n)
    vols, rets = [], []
    for t in targets:
        cons_t = [{"type": "eq", "fun": lambda w, t=t: portfolio_stats(w, mu, cov)[0] - t}]
        w = _optimize(port_vol, mu, cov, extra_constraints=cons_t)
        r, v, _ = portfolio_stats(w, mu, cov)
        vols.append(v); rets.append(r)
    return np.array(vols), np.array(rets)

# ── Input: use portfolio positions OR manual tickers ──────────────────────────
trades_df  = get_trades_df()
positions  = compute_positions(trades_df)
port_syms  = positions["symbol"].tolist() if not positions.empty else []

col_cfg, col_res = st.columns([1, 3])
with col_cfg:
    st.markdown("### Symbols")
    mode = st.radio("Source", ["My Portfolio", "Custom"], horizontal=True)
    if mode == "My Portfolio" and port_syms:
        symbols = st.multiselect("Symbols", port_syms, default=port_syms)
    else:
        raw = st.text_input("Tickers (comma-sep)", value="AAPL,MSFT,NVDA,GOOGL,AMZN,JPM,XOM")
        symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]

    period  = st.selectbox("Lookback", ["1y","2y","3y","5y"], index=1)
    max_w   = st.slider("Max weight per asset (%)", 10, 100, 40) / 100
    rf      = st.slider("Risk-free rate (%)", 0.0, 8.0, 5.0, 0.25) / 100
    RISK_FREE = rf
    run     = st.button("Optimize", type="primary", use_container_width=True)

with col_res:
    if not run:
        st.markdown(info_banner(
            "⟵ Set your symbols and click <b>Optimize</b> to compute the efficient frontier.",
            "#4e9af1"), unsafe_allow_html=True)
        st.stop()

    if len(symbols) < 2:
        st.error("Need at least 2 symbols.")
        st.stop()

    with st.spinner("Downloading data and computing frontier…"):
        raw = yf.download(symbols, period=period, auto_adjust=True, progress=False)
        closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        closes = closes.dropna(axis=1, thresh=50)
        avail = [s for s in symbols if s in closes.columns]
        closes = closes[avail] if avail else closes
        symbols = list(closes.columns)
        rets = closes.pct_change().dropna()
        mu   = rets.mean().values
        cov  = rets.cov().values

        # Cap weights
        bounds_capped = tuple((0.0, max_w) for _ in range(len(symbols)))
        def _opt_capped(obj):
            cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
            res = minimize(obj, x0=np.ones(len(symbols))/len(symbols),
                           args=(mu, cov), method="SLSQP",
                           bounds=bounds_capped, constraints=cons,
                           options={"maxiter": 1000})
            return res.x if res.success else np.ones(len(symbols))/len(symbols)

        w_sharpe  = _opt_capped(neg_sharpe)
        w_minvar  = _opt_capped(port_vol)
        w_rp      = risk_parity(cov)
        w_eq      = np.ones(len(symbols)) / len(symbols)
        ef_vols, ef_rets = efficient_frontier_points(mu, cov)

    # ── Stats for each portfolio ──────────────────────────────────────────────
    portfolios = {
        "Max Sharpe":    w_sharpe,
        "Min Variance":  w_minvar,
        "Risk Parity":   w_rp,
        "Equal Weight":  w_eq,
    }
    port_stats = {name: portfolio_stats(w, mu, cov) for name, w in portfolios.items()}

    # ── KPI row ───────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    for col, (name, (r, v, s)) in zip([k1, k2, k3, k4], port_stats.items()):
        col.metric(name, f"Sharpe {s:.2f}", f"Ret {r*100:.1f}%  Vol {v*100:.1f}%")

    st.divider()
    tab_frontier, tab_weights, tab_corr, tab_sim = st.tabs(
        ["📈 Efficient Frontier", "⚖️ Weights", "🔗 Correlation", "📊 Return Simulation"]
    )

    with tab_frontier:
        fig = go.Figure()

        # Frontier curve
        fig.add_trace(go.Scatter(
            x=ef_vols*100, y=ef_rets*100, mode="lines",
            name="Efficient Frontier",
            line=dict(color="#4e9af1", width=2),
        ))

        # Random portfolios (Monte Carlo scatter)
        n_rand = 3000
        rand_w  = np.random.dirichlet(np.ones(len(symbols)), n_rand)
        rand_rv = [portfolio_stats(w, mu, cov)[:2] for w in rand_w]
        rand_r  = [x[0]*100 for x in rand_rv]
        rand_v  = [x[1]*100 for x in rand_rv]
        rand_sh = [(x[0]-rf)/x[1] for x in rand_rv]
        fig.add_trace(go.Scatter(
            x=rand_v, y=rand_r, mode="markers", name="Random Portfolios",
            marker=dict(size=3, color=rand_sh,
                        colorscale=[[0,"#ff4b4b"],[0.5,"#1a2332"],[1,"#00d4aa"]],
                        opacity=0.5, showscale=True,
                        colorbar=dict(title="Sharpe", thickness=10,
                                      tickfont=dict(color="#4a5a72"))),
        ))

        # Key portfolios
        colors = {"Max Sharpe":"#00d4aa","Min Variance":"#4e9af1","Risk Parity":"#f1c14e","Equal Weight":"#b44ef1"}
        for name, (r, v, s) in port_stats.items():
            fig.add_trace(go.Scatter(
                x=[v*100], y=[r*100], mode="markers+text",
                name=name, text=[name], textposition="top center",
                textfont=dict(size=10, color=colors[name]),
                marker=dict(size=14, color=colors[name], symbol="star",
                            line=dict(color="#080c14", width=1)),
            ))

        # Capital Market Line
        ms_r, ms_v, ms_s = port_stats["Max Sharpe"]
        cml_x = np.linspace(0, ms_v*100*1.5, 50)
        cml_y = rf*100 + (ms_s) * cml_x
        fig.add_trace(go.Scatter(
            x=cml_x, y=cml_y, mode="lines", name="Capital Market Line",
            line=dict(color="#00d4aa", dash="dash", width=1),
        ))
        fig.add_hline(y=rf*100, line_dash="dot", line_color="#2a3a52",
                      annotation_text=f"Risk-free {rf*100:.1f}%")

        fig.update_layout(
            title="Mean-Variance Efficient Frontier",
            xaxis=dict(title="Annualised Volatility (%)", gridcolor="#1a2332", ticksuffix="%"),
            yaxis=dict(title="Annualised Return (%)",    gridcolor="#1a2332", ticksuffix="%"),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#8892a4", height=520, legend=dict(bgcolor="rgba(0,0,0,0.4)"),
            margin=dict(l=0,r=0,t=40,b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab_weights:
        wdf = pd.DataFrame({
            name: {sym: float(w[i])*100 for i, sym in enumerate(symbols)}
            for name, w in portfolios.items()
        }).round(1)
        wdf.index.name = "Symbol"

        # Grouped bar
        fig2 = go.Figure()
        colors_list = ["#00d4aa","#4e9af1","#f1c14e","#b44ef1"]
        for i, name in enumerate(portfolios):
            fig2.add_trace(go.Bar(
                name=name, x=symbols, y=wdf[name],
                marker_color=colors_list[i],
            ))
        fig2.update_layout(
            barmode="group", title="Optimal Weights (%)",
            yaxis=dict(gridcolor="#1a2332", ticksuffix="%"),
            xaxis=dict(gridcolor="#1a2332"),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#8892a4", height=380,
            legend=dict(bgcolor="rgba(0,0,0,0.4)"),
            margin=dict(l=0,r=0,t=40,b=0),
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(
            wdf.style.format("{:.1f}%")
                .background_gradient(cmap="RdYlGn", vmin=0, vmax=50, axis=0),
            use_container_width=True,
        )

        # Stats table
        st.markdown(section_header("Portfolio Metrics Comparison"), unsafe_allow_html=True)
        stats_df = pd.DataFrame({
            name: {
                "Ann. Return": f"{r*100:.2f}%",
                "Ann. Volatility": f"{v*100:.2f}%",
                "Sharpe Ratio": f"{s:.3f}",
                "Max Weight": f"{max(portfolios[name])*100:.1f}%",
                "# Assets (>1%)": int(sum(portfolios[name] > 0.01)),
            }
            for name, (r, v, s) in port_stats.items()
        }).T
        st.dataframe(stats_df, use_container_width=True)

    with tab_corr:
        corr = rets.corr()

        # Heatmap
        fig3 = go.Figure(go.Heatmap(
            z=corr.values, x=corr.columns, y=corr.index,
            text=[[f"{v:.2f}" for v in row] for row in corr.values],
            texttemplate="%{text}",
            colorscale=[[0,"#7f1d1d"],[0.5,"#131c2e"],[1,"#064e3b"]],
            zmid=0, zmin=-1, zmax=1,
            colorbar=dict(thickness=12, tickfont=dict(color="#4a5a72")),
        ))
        fig3.update_layout(
            title="Return Correlation Matrix",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#8892a4", height=420, margin=dict(l=0,r=0,t=40,b=0),
        )
        st.plotly_chart(fig3, use_container_width=True)

        # Rolling pairwise correlations
        st.markdown(section_header("Rolling 60-Day Correlations"), unsafe_allow_html=True)
        pairs = [(a, b) for i, a in enumerate(symbols) for b in symbols[i+1:]]
        fig4 = go.Figure()
        palette = ["#00d4aa","#4e9af1","#f1c14e","#b44ef1","#f17c4e","#4ef1c1"]
        for i, (a, b) in enumerate(pairs[:6]):
            if a in rets.columns and b in rets.columns:
                rc = rets[a].rolling(60).corr(rets[b]).dropna()
                fig4.add_trace(go.Scatter(x=rc.index, y=rc.values,
                                           name=f"{a}/{b}", mode="lines",
                                           line=dict(color=palette[i%6], width=1.5)))
        fig4.add_hline(y=0, line_dash="dot", line_color="#2a3a52")
        fig4.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#8892a4", height=320,
            xaxis=dict(gridcolor="#1a2332"), yaxis=dict(gridcolor="#1a2332"),
            legend=dict(bgcolor="rgba(0,0,0,0.4)"), margin=dict(l=0,r=0,t=10,b=0),
        )
        st.plotly_chart(fig4, use_container_width=True)

    with tab_sim:
        st.markdown(section_header("Historical Return Distributions"), unsafe_allow_html=True)

        # Individual stock return distributions
        fig5 = go.Figure()
        palette2 = ["#00d4aa","#4e9af1","#f1c14e","#b44ef1","#f17c4e","#4ef1c1","#ff4b4b"]
        for i, sym in enumerate(symbols[:7]):
            if sym in rets.columns:
                r = rets[sym] * 100
                fig5.add_trace(go.Violin(
                    x=[sym]*len(r), y=r.values,
                    name=sym, box_visible=True, meanline_visible=True,
                    fillcolor=palette2[i%7]+"40", line_color=palette2[i%7],
                ))
        fig5.update_layout(
            title="Daily Return Distribution by Stock",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#8892a4", height=380, violinmode="group",
            yaxis=dict(gridcolor="#1a2332", ticksuffix="%"),
            margin=dict(l=0,r=0,t=40,b=0),
        )
        st.plotly_chart(fig5, use_container_width=True)

        # Cumulative returns comparison
        cum_rets = (1 + rets).cumprod()
        fig6 = go.Figure()
        for i, sym in enumerate(symbols):
            fig6.add_trace(go.Scatter(
                x=cum_rets.index, y=(cum_rets[sym]-1)*100,
                name=sym, mode="lines", line=dict(color=palette2[i%7], width=1.5),
            ))
        # Add optimal portfolio line
        port_daily = rets @ w_sharpe
        port_cum   = (1 + port_daily).cumprod()
        fig6.add_trace(go.Scatter(
            x=port_cum.index, y=(port_cum-1)*100,
            name="Max Sharpe Portfolio", mode="lines",
            line=dict(color="#ffffff", width=2.5, dash="dash"),
        ))
        fig6.update_layout(
            title="Cumulative Returns (Equal Start)",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#8892a4", height=380,
            xaxis=dict(gridcolor="#1a2332"),
            yaxis=dict(gridcolor="#1a2332", ticksuffix="%"),
            legend=dict(bgcolor="rgba(0,0,0,0.4)"),
            margin=dict(l=0,r=0,t=40,b=0),
        )
        st.plotly_chart(fig6, use_container_width=True)
