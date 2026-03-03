import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from scipy import stats
import json
from datetime import date

from lib.style import inject_css
from lib.portfolio import get_trades_df, compute_positions, fetch_current_prices
from lib import metrics as m

st.set_page_config(page_title="Monte Carlo", layout="wide")
inject_css()
st.title("Monte Carlo Simulation")
st.caption("Probabilistic forecasting of portfolio and strategy performance using thousands of simulated paths.")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("⚙ Simulation Settings")
    n_sims   = st.select_slider("Simulations", [500, 1000, 2000, 5000, 10000], value=2000)
    horizon  = st.selectbox("Horizon", ["1 Year", "2 Years", "5 Years", "10 Years", "20 Years", "30 Years"], index=2)
    method   = st.radio("Method", ["Bootstrap (Historical)", "Parametric (Cholesky)", "GARCH-like (Volatility Clustering)"])
    conf_levels = st.multiselect("Confidence Bands", [5, 10, 25, 75, 90, 95], default=[5, 25, 75, 95])
    st.divider()
    target_return = st.number_input("Target Portfolio Value ($)", value=0, min_value=0, step=1000,
                                     help="Set to 0 to skip probability calculation")
    withdrawal = st.number_input("Annual Withdrawal ($)", value=0, min_value=0, step=1000,
                                  help="Simulates annual withdrawals (retirement mode)")
    st.divider()
    st.caption("Bootstrap: resamples historical returns.\nParametric: multivariate-normal with full covariance.\nGARCH-like: adds volatility clustering.")

horizon_days_map = {
    "1 Year": 252, "2 Years": 504, "5 Years": 1260,
    "10 Years": 2520, "20 Years": 5040, "30 Years": 7560
}
n_days = horizon_days_map[horizon]

tab_port, tab_asset, tab_boot, tab_retirement = st.tabs([
    "📈 Portfolio Simulation", "🔬 Single Asset", "♻ Strategy Bootstrap", "🏖 Retirement Planner"
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Portfolio Monte Carlo
# ══════════════════════════════════════════════════════════════════════════════
with tab_port:
    st.subheader("Portfolio Monte Carlo")

    # Load portfolio or custom input
    input_mode = st.radio("Portfolio Source", ["My Portfolio (from trades)", "Custom Allocation"], horizontal=True)

    if input_mode == "My Portfolio (from trades)":
        trades_df = get_trades_df()
        positions = compute_positions(trades_df)
        if positions.empty:
            st.info("No open positions. Log trades first or use Custom Allocation.")
            st.stop()
        prices = fetch_current_prices(positions["symbol"].tolist())
        positions["market_value"] = positions.apply(
            lambda r: r["quantity"] * prices.get(r["symbol"], r["avg_cost"]), axis=1
        )
        total_mv = positions["market_value"].sum()
        positions["weight"] = positions["market_value"] / total_mv
        symbols  = positions["symbol"].tolist()
        weights  = positions["weight"].values
        initial_capital = st.number_input("Initial Portfolio Value ($)", value=int(total_mv), min_value=100, step=1000)
    else:
        tickers_raw = st.text_input("Tickers (comma-separated)", value="AAPL,MSFT,GOOGL,AMZN,SPY")
        symbols = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]
        if not symbols:
            st.info("Enter at least one ticker.")
            st.stop()
        alloc_cols = st.columns(min(len(symbols), 5))
        raw_weights = []
        for i, sym in enumerate(symbols):
            w = alloc_cols[i % 5].number_input(f"{sym} %", 0.0, 100.0, 100.0 / len(symbols), 1.0, key=f"w_{sym}")
            raw_weights.append(w)
        total_w = sum(raw_weights)
        weights = np.array(raw_weights) / total_w if total_w > 0 else np.ones(len(symbols)) / len(symbols)
        initial_capital = st.number_input("Initial Capital ($)", value=10000, min_value=100, step=1000)

    hist_period = st.selectbox("Historical Period for Parameters", ["1y", "2y", "3y", "5y"], index=2, key="port_hist")

    @st.cache_data(ttl=3600)
    def load_port_returns(syms_key: str, period: str):
        syms = syms_key.split(",")
        raw = yf.download(syms, period=period, auto_adjust=True, progress=False)
        if isinstance(raw.columns, pd.MultiIndex):
            closes = raw["Close"]
        else:
            closes = raw[["Close"]]
            closes.columns = syms
        return closes.pct_change().dropna()

    if st.button("Run Portfolio Simulation", type="primary", key="run_port"):
        with st.spinner(f"Running {n_sims:,} simulations × {n_days} trading days..."):
            ret_df = load_port_returns(",".join(symbols), hist_period)

            # Align weights to available columns
            avail = [s for s in symbols if s in ret_df.columns]
            if not avail:
                st.error("No return data available.")
                st.stop()
            avail_weights = np.array([weights[symbols.index(s)] for s in avail])
            avail_weights /= avail_weights.sum()
            ret_df = ret_df[avail]

            port_hist_returns = (ret_df * avail_weights).sum(axis=1).values
            mu_daily  = ret_df.mean().values
            cov_daily = ret_df.cov().values
            annual_withdrawal_daily = withdrawal / 252

            def simulate(method_name: str) -> np.ndarray:
                paths = np.zeros((n_sims, n_days + 1))
                paths[:, 0] = initial_capital
                rng = np.random.default_rng(42)

                if method_name.startswith("Bootstrap"):
                    for i in range(n_sims):
                        idx = rng.integers(0, len(port_hist_returns), n_days)
                        daily_r = port_hist_returns[idx]
                        cum = initial_capital
                        for d, r in enumerate(daily_r):
                            cum = cum * (1 + r) - annual_withdrawal_daily
                            paths[i, d + 1] = max(cum, 0)
                elif method_name.startswith("Parametric"):
                    try:
                        L = np.linalg.cholesky(cov_daily + 1e-9 * np.eye(len(avail)))
                    except np.linalg.LinAlgError:
                        L = np.linalg.cholesky(
                            cov_daily + 1e-7 * np.eye(len(avail))
                        )
                    for i in range(n_sims):
                        z = rng.standard_normal((n_days, len(avail)))
                        sim_ret = z @ L.T + mu_daily
                        pr = (sim_ret * avail_weights).sum(axis=1)
                        cum = initial_capital
                        for d, r in enumerate(pr):
                            cum = cum * (1 + r) - annual_withdrawal_daily
                            paths[i, d + 1] = max(cum, 0)
                else:  # GARCH-like
                    hist_vol = np.std(port_hist_returns)
                    hist_mean = np.mean(port_hist_returns)
                    alpha, beta_g = 0.10, 0.85
                    omega = hist_vol ** 2 * (1 - alpha - beta_g)
                    for i in range(n_sims):
                        vol = hist_vol
                        cum = initial_capital
                        for d in range(n_days):
                            r = hist_mean + vol * rng.standard_normal()
                            vol = np.sqrt(omega + alpha * r ** 2 + beta_g * vol ** 2)
                            cum = cum * (1 + r) - annual_withdrawal_daily
                            paths[i, d + 1] = max(cum, 0)
                return paths

            paths = simulate(method)

        # ── Plot fan chart ─────────────────────────────────────────────────────
        days_axis = np.arange(n_days + 1)
        years_axis = days_axis / 252

        fig = go.Figure()
        pct_pairs = sorted([(min(a, 100-a), max(a, 100-a)) for a in conf_levels if a < 50])
        fill_colors = ["rgba(78,154,241,0.08)", "rgba(78,154,241,0.14)",
                        "rgba(78,154,241,0.20)", "rgba(78,154,241,0.26)"]

        for i, (lo, hi) in enumerate(pct_pairs):
            lo_vals = np.percentile(paths, lo, axis=0)
            hi_vals = np.percentile(paths, hi, axis=0)
            fill_c = fill_colors[min(i, len(fill_colors)-1)]
            fig.add_trace(go.Scatter(
                x=np.concatenate([years_axis, years_axis[::-1]]),
                y=np.concatenate([hi_vals, lo_vals[::-1]]),
                fill="toself", fillcolor=fill_c,
                line=dict(width=0), name=f"P{lo}–P{hi}",
                hoverinfo="skip",
            ))

        median = np.percentile(paths, 50, axis=0)
        p5 = np.percentile(paths, 5, axis=0)
        p95 = np.percentile(paths, 95, axis=0)

        fig.add_trace(go.Scatter(x=years_axis, y=median, name="Median",
                                  line=dict(color="#4e9af1", width=2.5)))
        fig.add_trace(go.Scatter(x=years_axis, y=p95, name="P95",
                                  line=dict(color="#00d4aa", width=1.5, dash="dash")))
        fig.add_trace(go.Scatter(x=years_axis, y=p5, name="P5",
                                  line=dict(color="#ff4b4b", width=1.5, dash="dash")))

        # Plot 50 sample paths (thin)
        rng_sample = np.random.default_rng(0)
        sample_idx = rng_sample.choice(n_sims, size=min(50, n_sims), replace=False)
        for idx in sample_idx:
            fig.add_trace(go.Scatter(
                x=years_axis, y=paths[idx],
                line=dict(color="rgba(150,150,150,0.12)", width=0.8),
                showlegend=False, hoverinfo="skip"
            ))

        if target_return > 0:
            fig.add_hline(y=target_return, line_color="#f1c14e", line_dash="dash",
                           annotation_text=f"Target ${target_return:,.0f}")

        fig.add_hline(y=initial_capital, line_color="#666", line_width=1, line_dash="dot")

        fig.update_layout(
            title=f"Portfolio Monte Carlo — {n_sims:,} Simulations over {horizon}",
            xaxis_title="Years", yaxis_title="Portfolio Value ($)",
            yaxis_tickprefix="$", yaxis_tickformat=",.0f",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#fafafa", height=550,
            xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── Statistics ────────────────────────────────────────────────────────
        final = paths[:, -1]
        st.subheader("Simulation Statistics")
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("Median Final Value", f"${np.median(final):,.0f}")
        mc2.metric("P5 (Worst 5%)", f"${np.percentile(final, 5):,.0f}")
        mc3.metric("P95 (Best 5%)", f"${np.percentile(final, 95):,.0f}")
        pct_positive = (final > initial_capital).mean() * 100
        mc4.metric("Prob. of Profit", f"{pct_positive:.1f}%")
        if target_return > 0:
            prob_target = (final >= target_return).mean() * 100
            mc5.metric(f"Prob. ≥ ${target_return:,.0f}", f"{prob_target:.1f}%")
        else:
            median_cagr = ((np.median(final) / initial_capital) ** (1/(n_days/252)) - 1) * 100
            mc5.metric("Median CAGR", f"{median_cagr:.2f}%")

        # Terminal value distribution
        fig_dist = go.Figure()
        fig_dist.add_trace(go.Histogram(
            x=final, nbinsx=80,
            marker_color="#4e9af1", opacity=0.75, name="Terminal Values"
        ))
        fig_dist.add_vline(x=np.median(final), line_color="#f1c14e", line_dash="dash",
                            annotation_text="Median")
        fig_dist.add_vline(x=np.percentile(final, 5), line_color="#ff4b4b", line_dash="dot",
                            annotation_text="P5")
        fig_dist.add_vline(x=initial_capital, line_color="#888", line_dash="dot",
                            annotation_text="Initial")
        if target_return > 0:
            fig_dist.add_vline(x=target_return, line_color="#00d4aa", line_dash="dash",
                                annotation_text="Target")
        fig_dist.update_layout(
            title=f"Distribution of Terminal Values after {horizon}",
            xaxis_title="Portfolio Value ($)", yaxis_title="Frequency",
            xaxis_tickprefix="$", xaxis_tickformat=",.0f",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#fafafa",
            xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
        )
        st.plotly_chart(fig_dist, use_container_width=True)

        # Percentile table
        pcts = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        perc_df = pd.DataFrame({
            "Percentile": [f"P{p}" for p in pcts],
            "Terminal Value": [f"${np.percentile(final, p):,.0f}" for p in pcts],
            "CAGR": [f"{((np.percentile(final, p)/initial_capital)**(1/(n_days/252))-1)*100:.2f}%" for p in pcts],
            "Total Return": [f"{(np.percentile(final, p)/initial_capital-1)*100:.1f}%" for p in pcts],
        })
        st.dataframe(perc_df, hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Single Asset Monte Carlo
# ══════════════════════════════════════════════════════════════════════════════
with tab_asset:
    st.subheader("Single Asset Simulation")

    a_sym = st.text_input("Symbol", value="SPY", key="asset_sym").upper().strip()
    a_cap = st.number_input("Initial Capital ($)", value=10000, min_value=100, step=1000, key="asset_cap")
    a_period = st.selectbox("Historical Period", ["1y", "2y", "3y", "5y"], index=2, key="asset_period")

    @st.cache_data(ttl=3600)
    def load_asset_returns(sym: str, period: str):
        raw = yf.download(sym, period=period, auto_adjust=True, progress=False)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.droplevel(1)
        return raw["Close"].pct_change().dropna()

    if st.button("Run Asset Simulation", type="primary", key="run_asset"):
        with st.spinner("Simulating..."):
            a_ret = load_asset_returns(a_sym, a_period)
            hist_r = a_ret.values
            mu_a = hist_r.mean()
            sig_a = hist_r.std()
            annual_wd = withdrawal / 252

            rng2 = np.random.default_rng(42)
            paths_a = np.zeros((n_sims, n_days + 1))
            paths_a[:, 0] = a_cap

            if method.startswith("Bootstrap"):
                for i in range(n_sims):
                    idx = rng2.integers(0, len(hist_r), n_days)
                    cum = a_cap
                    for d, r in enumerate(hist_r[idx]):
                        cum = cum * (1 + r) - annual_wd
                        paths_a[i, d + 1] = max(cum, 0)
            else:
                for i in range(n_sims):
                    r_seq = rng2.normal(mu_a, sig_a, n_days)
                    cum = a_cap
                    for d, r in enumerate(r_seq):
                        cum = cum * (1 + r) - annual_wd
                        paths_a[i, d + 1] = max(cum, 0)

        yrs = np.arange(n_days + 1) / 252
        fig_a = go.Figure()

        for lo, hi in [(5, 95), (10, 90), (25, 75)]:
            fig_a.add_trace(go.Scatter(
                x=np.concatenate([yrs, yrs[::-1]]),
                y=np.concatenate([np.percentile(paths_a, hi, axis=0),
                                   np.percentile(paths_a, lo, axis=0)[::-1]]),
                fill="toself", fillcolor="rgba(0,212,170,0.08)",
                line=dict(width=0), name=f"P{lo}-P{hi}", hoverinfo="skip"
            ))

        fig_a.add_trace(go.Scatter(x=yrs, y=np.percentile(paths_a, 50, axis=0),
                                    name="Median", line=dict(color="#00d4aa", width=2.5)))
        fig_a.add_trace(go.Scatter(x=yrs, y=np.percentile(paths_a, 95, axis=0),
                                    name="P95", line=dict(color="#4e9af1", width=1.5, dash="dash")))
        fig_a.add_trace(go.Scatter(x=yrs, y=np.percentile(paths_a, 5, axis=0),
                                    name="P5", line=dict(color="#ff4b4b", width=1.5, dash="dash")))
        fig_a.add_hline(y=a_cap, line_color="#666", line_dash="dot")

        fig_a.update_layout(
            title=f"{a_sym} Monte Carlo — {n_sims:,} Paths | {horizon}",
            xaxis_title="Years", yaxis_title="Value ($)",
            yaxis_tickprefix="$", yaxis_tickformat=",.0f",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#fafafa", height=500,
            xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig_a, use_container_width=True)

        final_a = paths_a[:, -1]
        ma1, ma2, ma3, ma4 = st.columns(4)
        ma1.metric("Median", f"${np.median(final_a):,.0f}")
        ma2.metric("P5", f"${np.percentile(final_a, 5):,.0f}")
        ma3.metric("P95", f"${np.percentile(final_a, 95):,.0f}")
        ma4.metric("Prob. of Profit", f"{(final_a > a_cap).mean()*100:.1f}%")

        # Annualized stats from history
        ann_ret  = (1 + mu_a) ** 252 - 1
        ann_vol  = sig_a * np.sqrt(252)
        sharpe_a = (ann_ret - 0.045) / ann_vol if ann_vol > 0 else 0
        mdd_a = m.max_drawdown(a_ret)

        st.caption(f"**{a_sym} Historical Stats ({a_period})** — "
                   f"Ann. Return: `{ann_ret*100:.2f}%`  |  "
                   f"Ann. Vol: `{ann_vol*100:.2f}%`  |  "
                   f"Sharpe: `{sharpe_a:.2f}`  |  "
                   f"Max DD: `{mdd_a*100:.2f}%`")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Strategy Bootstrap
# ══════════════════════════════════════════════════════════════════════════════
with tab_boot:
    st.subheader("Strategy Bootstrap Simulation")
    st.caption("Upload backtest trade returns or enter them manually. "
               "Bootstrap resamples trades to estimate strategy robustness.")

    input_method = st.radio("Input Method", ["Load from Backtester (last run)", "Enter trade returns manually"], horizontal=True)

    sample_returns = None
    if input_method == "Enter trade returns manually":
        returns_raw = st.text_area(
            "Trade returns (comma-separated, e.g. 0.05,-0.03,0.12)",
            value="0.05,-0.03,0.12,0.08,-0.15,0.04,0.10,-0.02,0.07,-0.06,0.09,0.03,-0.08,0.14,0.02"
        )
        try:
            sample_returns = np.array([float(x.strip()) for x in returns_raw.split(",") if x.strip()])
        except ValueError:
            st.error("Invalid input. Use comma-separated numbers.")
    else:
        from lib.supabase_client import get_client, SOLO_USER_ID
        client = get_client()
        res = client.table("backtest_runs").select("*").eq("user_id", SOLO_USER_ID)\
            .order("created_at", desc=True).limit(10).execute()
        runs = res.data or []
        if not runs:
            st.info("No backtest runs saved yet. Run a backtest on the Backtester page first.")
        else:
            run_labels = [f"{r['strategy_name']} on {r['symbol']} ({r['start_date']} → {r['end_date']})" for r in runs]
            sel_run = st.selectbox("Select Backtest Run", run_labels)
            st.info("Bootstrap will use the strategy's metric returns. For full trade-level bootstrap, run the backtest and note the trade P&L.")
            # Use synthetic returns based on metrics if available
            sel_metrics = runs[run_labels.index(sel_run)].get("metrics", {})
            if sel_metrics:
                st.json(sel_metrics)

    boot_capital = st.number_input("Initial Capital ($)", value=10000, min_value=100, step=1000, key="boot_cap")

    if sample_returns is not None and len(sample_returns) >= 5:
        if st.button("Run Bootstrap", type="primary", key="run_boot"):
            with st.spinner("Bootstrapping..."):
                rng3 = np.random.default_rng(42)
                paths_b = np.zeros((n_sims, n_days + 1))
                paths_b[:, 0] = boot_capital
                for i in range(n_sims):
                    idx = rng3.integers(0, len(sample_returns), n_days)
                    r_seq = sample_returns[idx]
                    cum = np.cumprod(1 + r_seq) * boot_capital
                    paths_b[i, 1:] = cum

            yrs_b = np.arange(n_days + 1) / 252
            fig_b = go.Figure()

            for lo, hi in [(5, 95), (25, 75)]:
                fig_b.add_trace(go.Scatter(
                    x=np.concatenate([yrs_b, yrs_b[::-1]]),
                    y=np.concatenate([np.percentile(paths_b, hi, axis=0),
                                       np.percentile(paths_b, lo, axis=0)[::-1]]),
                    fill="toself", fillcolor="rgba(180,78,241,0.10)",
                    line=dict(width=0), name=f"P{lo}-P{hi}", hoverinfo="skip"
                ))
            fig_b.add_trace(go.Scatter(x=yrs_b, y=np.percentile(paths_b, 50, axis=0),
                                        name="Median", line=dict(color="#b44ef1", width=2.5)))
            fig_b.add_trace(go.Scatter(x=yrs_b, y=np.percentile(paths_b, 95, axis=0),
                                        name="P95", line=dict(color="#00d4aa", width=1.5, dash="dash")))
            fig_b.add_trace(go.Scatter(x=yrs_b, y=np.percentile(paths_b, 5, axis=0),
                                        name="P5", line=dict(color="#ff4b4b", width=1.5, dash="dash")))
            fig_b.add_hline(y=boot_capital, line_color="#666", line_dash="dot")
            fig_b.update_layout(
                title=f"Strategy Bootstrap — {n_sims:,} Resampled Paths | {horizon}",
                xaxis_title="Years", yaxis_title="Value ($)",
                yaxis_tickprefix="$", yaxis_tickformat=",.0f",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#fafafa", height=500,
                xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
                legend=dict(bgcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(fig_b, use_container_width=True)

            final_b = paths_b[:, -1]
            mb1, mb2, mb3, mb4 = st.columns(4)
            mb1.metric("Median Final", f"${np.median(final_b):,.0f}")
            mb2.metric("P5 (Worst)", f"${np.percentile(final_b, 5):,.0f}")
            mb3.metric("P95 (Best)", f"${np.percentile(final_b, 95):,.0f}")
            mb4.metric("Prob. of Profit", f"{(final_b > boot_capital).mean()*100:.1f}%")

            # Win rate, avg trade from sample
            win_r = (sample_returns > 0).mean()
            avg_win = sample_returns[sample_returns > 0].mean() if (sample_returns > 0).any() else 0
            avg_loss = sample_returns[sample_returns < 0].mean() if (sample_returns < 0).any() else 0
            st.caption(
                f"**Trade Sample Stats** — Win Rate: `{win_r*100:.1f}%`  |  "
                f"Avg Win: `{avg_win*100:.2f}%`  |  Avg Loss: `{avg_loss*100:.2f}%`  |  "
                f"Profit Factor: `{abs(avg_win/avg_loss):.2f}`" if avg_loss != 0 else ""
            )

            # Expected shortfall analysis
            sorted_final = np.sort(final_b)
            fig_dens = go.Figure()
            fig_dens.add_trace(go.Histogram(
                x=final_b, nbinsx=80, marker_color="#b44ef1", opacity=0.75, name="Final Values"
            ))
            fig_dens.add_vline(x=np.percentile(final_b, 5), line_color="#ff4b4b",
                                annotation_text="VaR 95%")
            fig_dens.add_vline(x=np.median(final_b), line_color="#f1c14e",
                                annotation_text="Median")
            fig_dens.update_layout(
                title="Bootstrap Terminal Value Distribution",
                xaxis_tickprefix="$", xaxis_tickformat=",.0f",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#fafafa",
                xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
            )
            st.plotly_chart(fig_dens, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Retirement Planner
# ══════════════════════════════════════════════════════════════════════════════
with tab_retirement:
    st.subheader("Retirement / FIRE Planner")
    st.caption("Simulates a portfolio with annual withdrawals to estimate sustainability.")

    rt1, rt2, rt3 = st.columns(3)
    retire_capital = rt1.number_input("Starting Portfolio ($)", value=1_000_000, min_value=1000, step=10000)
    retire_wd      = rt2.number_input("Annual Withdrawal ($)", value=40_000, min_value=0, step=1000)
    retire_years   = rt3.selectbox("Retirement Horizon", [10, 15, 20, 25, 30, 35, 40, 50], index=4)
    retire_ticker  = st.text_input("Benchmark Asset (historical returns)", value="SPY", key="retire_sym").upper().strip()
    retire_period  = st.selectbox("Historical Period for Returns", ["5y", "10y", "20y", "30y"], index=2, key="retire_period")
    inflation_rate = st.slider("Annual Inflation (for withdrawal)", 0.0, 8.0, 2.5, 0.1) / 100

    if st.button("Run Retirement Simulation", type="primary", key="run_retire"):
        @st.cache_data(ttl=86400)
        def load_retire_returns(sym: str, period: str):
            raw = yf.download(sym, period=period, auto_adjust=True, progress=False)
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.droplevel(1)
            return raw["Close"].pct_change().dropna().values

        with st.spinner("Running retirement simulations..."):
            ret_r = load_retire_returns(retire_ticker, retire_period)
            retire_n_days = retire_years * 252
            rng4 = np.random.default_rng(42)
            retire_paths = np.zeros((n_sims, retire_n_days + 1))
            retire_paths[:, 0] = retire_capital
            daily_wd_base = retire_wd / 252
            daily_inf = (1 + inflation_rate) ** (1/252) - 1

            for i in range(n_sims):
                cum = retire_capital
                wd_daily = daily_wd_base
                for d in range(retire_n_days):
                    r = ret_r[rng4.integers(0, len(ret_r))]
                    cum = cum * (1 + r) - wd_daily
                    wd_daily *= (1 + daily_inf)
                    retire_paths[i, d + 1] = max(cum, 0)
                    if cum <= 0:
                        retire_paths[i, d + 1:] = 0
                        break

        yrs_r = np.arange(retire_n_days + 1) / 252
        prob_survive = (retire_paths[:, -1] > 0).mean() * 100

        fig_r = go.Figure()
        for lo, hi in [(5, 95), (25, 75)]:
            fig_r.add_trace(go.Scatter(
                x=np.concatenate([yrs_r, yrs_r[::-1]]),
                y=np.concatenate([np.percentile(retire_paths, hi, axis=0),
                                   np.percentile(retire_paths, lo, axis=0)[::-1]]),
                fill="toself", fillcolor="rgba(241,193,78,0.08)",
                line=dict(width=0), name=f"P{lo}-P{hi}", hoverinfo="skip"
            ))
        fig_r.add_trace(go.Scatter(x=yrs_r, y=np.percentile(retire_paths, 50, axis=0),
                                    name="Median", line=dict(color="#f1c14e", width=2.5)))
        fig_r.add_trace(go.Scatter(x=yrs_r, y=np.percentile(retire_paths, 10, axis=0),
                                    name="P10 (Pessimistic)", line=dict(color="#ff4b4b", width=1.5, dash="dash")))
        fig_r.add_trace(go.Scatter(x=yrs_r, y=np.percentile(retire_paths, 90, axis=0),
                                    name="P90 (Optimistic)", line=dict(color="#00d4aa", width=1.5, dash="dash")))
        fig_r.add_hline(y=0, line_color="#666", line_width=1)
        fig_r.update_layout(
            title=f"Retirement Simulation — ${retire_wd:,.0f}/yr withdrawal, {inflation_rate*100:.1f}% inflation | {retire_years} years",
            xaxis_title="Years into Retirement", yaxis_title="Portfolio Value ($)",
            yaxis_tickprefix="$", yaxis_tickformat=",.0f",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#fafafa", height=500,
            xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig_r, use_container_width=True)

        cr1, cr2, cr3, cr4 = st.columns(4)
        cr1.metric("Portfolio Survival Rate", f"{prob_survive:.1f}%",
                   help="% of simulations where portfolio > $0 at the end")
        cr2.metric("Median Final Value", f"${np.median(retire_paths[:,-1]):,.0f}")
        cr3.metric("Withdrawal Rate", f"{retire_wd/retire_capital*100:.2f}%")
        safe_wd = retire_capital * 0.04
        cr4.metric("4% Rule Safe Withdrawal", f"${safe_wd:,.0f}/yr")

        # Ruin probability over time
        ruin_by_year = np.mean(retire_paths == 0, axis=0)
        fig_ruin = go.Figure()
        fig_ruin.add_trace(go.Scatter(
            x=yrs_r, y=ruin_by_year * 100,
            mode="lines", name="Cumulative Ruin Probability",
            line=dict(color="#ff4b4b", width=2), fill="tozeroy",
            fillcolor="rgba(255,75,75,0.15)"
        ))
        fig_ruin.update_layout(
            title="Cumulative Probability of Portfolio Ruin Over Time",
            xaxis_title="Years", yaxis_title="% Ruined",
            yaxis_ticksuffix="%",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#fafafa",
            xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
        )
        st.plotly_chart(fig_ruin, use_container_width=True)
