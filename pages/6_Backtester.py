import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from lib.backtest import run_backtest, STRATEGIES
from lib.charts import equity_curve, drawdown_chart, monthly_returns_heatmap
from lib.supabase_client import get_client, SOLO_USER_ID

from lib.style import inject_css
st.set_page_config(page_title="Backtester", layout="wide")
inject_css()
st.title("Strategy Backtester")
st.caption("Test how a strategy would have performed on historical data.")

client = get_client()

# ── Configuration ─────────────────────────────────────────────────────────────
cfg_col, res_col = st.columns([1, 3])

with cfg_col:
    st.subheader("Configuration")
    symbol = st.text_input("Symbol", value="AAPL").upper().strip()

    strategy_name = st.selectbox("Strategy", list(STRATEGIES.keys()))
    strat_meta = STRATEGIES[strategy_name]
    st.caption(strat_meta["description"])

    st.subheader("Parameters")
    params = {}
    for key, cfg in strat_meta["params"].items():
        if cfg["type"] == "int":
            params[key] = st.slider(cfg["label"], cfg["min"], cfg["max"], cfg["default"])
        else:
            params[key] = st.slider(cfg["label"], float(cfg["min"]), float(cfg["max"]),
                                     float(cfg["default"]), step=0.1)

    st.subheader("Backtest Settings")
    end_date = st.date_input("End Date", value=date.today())
    lookback = st.selectbox("Lookback Period", ["1 Year", "2 Years", "3 Years", "5 Years", "10 Years"])
    lookback_map = {"1 Year": 365, "2 Years": 730, "3 Years": 1095, "5 Years": 1825, "10 Years": 3650}
    start_date = end_date - timedelta(days=lookback_map[lookback])
    initial_capital = st.number_input("Initial Capital ($)", value=10000, min_value=100, step=1000)

    run_btn = st.button("Run Backtest", type="primary", use_container_width=True)

# ── Results ───────────────────────────────────────────────────────────────────
with res_col:
    if not run_btn:
        st.info("Configure parameters on the left and click **Run Backtest**.")
        st.stop()

    with st.spinner(f"Backtesting {strategy_name} on {symbol}..."):
        try:
            result = run_backtest(
                symbol=symbol,
                strategy_name=strategy_name,
                params=params,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                initial_capital=float(initial_capital),
            )
        except Exception as e:
            st.error(f"Backtest failed: {e}")
            st.stop()

    # Save to DB
    client.table("backtest_runs").insert({
        "user_id": SOLO_USER_ID,
        "strategy_name": strategy_name,
        "symbol": symbol,
        "params": params,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "metrics": result["metrics"],
    }).execute()

    # KPI row
    st.subheader(f"Results — {strategy_name} on {symbol}")
    metrics = result["metrics"]
    kpi_cols = st.columns(min(len(metrics), 5))
    for i, (k, v) in enumerate(metrics.items()):
        kpi_cols[i % len(kpi_cols)].metric(k, v)

    st.divider()

    tab_eq, tab_dd, tab_trades, tab_monthly = st.tabs(
        ["Equity Curve", "Drawdown", "Trade List", "Monthly Returns"]
    )

    with tab_eq:
        fig = equity_curve({
            f"{strategy_name}": result["equity"],
            "Buy & Hold": result["bh_equity"],
        }, title=f"{symbol} — {strategy_name} vs Buy & Hold")
        st.plotly_chart(fig, use_container_width=True)

        # Signal overlay on price
        df = result["df"]
        entries = df[df["signal"].diff() > 0]
        exits = df[df["signal"].diff() < 0]

        price_fig = go.Figure()
        price_fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Price",
                                        line=dict(color="#4e9af1", width=1.5)))
        price_fig.add_trace(go.Scatter(x=entries.index, y=entries["Close"],
                                        mode="markers", name="Entry",
                                        marker=dict(color="#00d4aa", size=10, symbol="triangle-up")))
        price_fig.add_trace(go.Scatter(x=exits.index, y=exits["Close"],
                                        mode="markers", name="Exit",
                                        marker=dict(color="#ff4b4b", size=10, symbol="triangle-down")))
        price_fig.update_layout(title=f"{symbol} Price with Entry/Exit Signals",
                                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  font_color="#fafafa",
                                  xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"))
        st.plotly_chart(price_fig, use_container_width=True)

    with tab_dd:
        st.plotly_chart(drawdown_chart(result["equity"], "Strategy Drawdown"), use_container_width=True)

        # Strategy vs B&H drawdown comparison
        fig2 = go.Figure()
        from lib import metrics as m
        dd_strat = m.drawdown_series(result["equity"]) * 100
        dd_bh = m.drawdown_series(result["bh_equity"]) * 100
        fig2.add_trace(go.Scatter(x=dd_strat.index, y=dd_strat.values, name=strategy_name,
                                   fill="tozeroy", line=dict(color="#ff4b4b", width=1)))
        fig2.add_trace(go.Scatter(x=dd_bh.index, y=dd_bh.values, name="Buy & Hold",
                                   fill="tozeroy", fillcolor="rgba(78,154,241,0.15)",
                                   line=dict(color="#4e9af1", width=1)))
        fig2.update_layout(title="Drawdown Comparison",
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#fafafa", yaxis_ticksuffix="%",
                            xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"))
        st.plotly_chart(fig2, use_container_width=True)

    with tab_trades:
        trades = result["trades"]
        if trades:
            trade_df = pd.DataFrame(trades)
            trade_df.columns = [c.replace("_", " ").title() for c in trade_df.columns]
            if "Return Pct" in trade_df.columns:
                trade_df.rename(columns={"Return Pct": "Return %"}, inplace=True)
            st.dataframe(
                trade_df.style.format({
                    "Entry Price": "${:.4g}", "Exit Price": "${:.4g}",
                    "Return %": "{:+.2f}%", "Pnl": "${:.4g}",
                }).map(
                    lambda v: "color: #00d4aa" if isinstance(v, str) and "+" in v else
                               "color: #ff4b4b" if isinstance(v, str) and v.startswith("-") else "",
                    subset=["Return %"] if "Return %" in trade_df.columns else [],
                ),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No trades were triggered in this period.")

    with tab_monthly:
        strat_ret = result["returns"].dropna()
        if len(strat_ret) > 20:
            st.plotly_chart(monthly_returns_heatmap(strat_ret, f"{strategy_name} Monthly Returns"),
                            use_container_width=True)
        else:
            st.info("Need more data for monthly heatmap.")
