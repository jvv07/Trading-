import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

st.set_page_config(
    page_title="QUANTEDGE",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from lib.style import inject_css, kpi_card, section_header
from lib.nav import render_nav
from lib.portfolio import get_trades_df, compute_positions, fetch_current_prices
from lib.supabase_client import get_client, SOLO_USER_ID

inject_css()
render_nav("Home")

# ── Data ──────────────────────────────────────────────────────────────────────
trades_df = get_trades_df()
positions = compute_positions(trades_df)

total_market_value = 0.0
total_unrealized = 0.0
prices = {}

if not positions.empty:
    prices = fetch_current_prices(positions["symbol"].tolist())
    for _, row in positions.iterrows():
        price = prices.get(row["symbol"])
        if price:
            mv = row["quantity"] * price
            total_market_value += mv
            total_unrealized += mv - row["cost_basis"]

total_realized = 0.0
if not trades_df.empty:
    sells = trades_df[trades_df["side"] == "sell"]
    buys = trades_df[trades_df["side"] == "buy"]
    total_realized = float(sells["notional"].sum() - buys["notional"].sum()) if not sells.empty else 0.0

open_count = len(positions)
trade_count = len(trades_df)

# ── Hero KPI row ──────────────────────────────────────────────────────────────
upnl_pct = (total_unrealized / (total_market_value - total_unrealized) * 100
            if (total_market_value - total_unrealized) > 0 else 0.0)

st.html(f"""
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:28px">
  {kpi_card("Portfolio Value", f"${total_market_value:,.2f}")}
  {kpi_card("Unrealized P&L", f"${total_unrealized:,.2f}",
            delta=f"{upnl_pct:+.2f}%",
            positive=(total_unrealized >= 0))}
  {kpi_card("Realized P&L", f"${total_realized:,.2f}",
            positive=(total_realized >= 0))}
  {kpi_card("Open Positions", str(open_count))}
  {kpi_card("Total Trades", str(trade_count))}
</div>
""")

# ── Main layout: left (portfolio) | right (market + news) ─────────────────────
col_left, col_right = st.columns([3, 2], gap="large")

# ── LEFT: Positions ────────────────────────────────────────────────────────────
with col_left:
    st.html(section_header("Open Positions", "Live P&L at market price"))

    if positions.empty:
        st.info("No open positions. Log your first trade on the **Trades** page.")
    else:
        pos_disp = positions.copy()
        pos_disp["Last"] = pos_disp["symbol"].map(lambda s: prices.get(s))
        pos_disp["Mkt Value"] = pos_disp.apply(
            lambda r: r["quantity"] * r["Last"] if r["Last"] else None, axis=1)
        pos_disp["Unreal. P&L"] = pos_disp.apply(
            lambda r: r["Mkt Value"] - r["cost_basis"] if r["Mkt Value"] is not None else None, axis=1)
        pos_disp["P&L %"] = pos_disp.apply(
            lambda r: r["Unreal. P&L"] / r["cost_basis"] * 100 if r["cost_basis"] and r["Unreal. P&L"] is not None else None,
            axis=1)
        display_cols = pos_disp[["symbol", "quantity", "avg_cost", "Last", "Mkt Value", "Unreal. P&L", "P&L %"]].copy()
        display_cols.columns = ["Symbol", "Qty", "Avg Cost", "Last", "Mkt Value", "Unreal. P&L", "P&L %"]
        st.dataframe(
            display_cols.style.format({
                "Avg Cost": "${:.2f}",
                "Last": lambda v: f"${v:.2f}" if v else "N/A",
                "Mkt Value": lambda v: f"${v:,.2f}" if v else "N/A",
                "Unreal. P&L": lambda v: f"${v:,.2f}" if v else "N/A",
                "P&L %": lambda v: f"{v:+.2f}%" if v is not None else "N/A",
            }).map(
                lambda v: "color:#00d4aa" if isinstance(v, str) and v.startswith("+") else
                          "color:#ff4b4b" if isinstance(v, str) and v.startswith("-") else "",
                subset=["P&L %", "Unreal. P&L"],
            ),
            use_container_width=True, hide_index=True,
        )

    # Recent trades ──────────────────────────────────────────────────────────────
    st.html(section_header("Recent Trades", "Last 8 executions"))
    if not trades_df.empty:
        recent = trades_df.sort_values("executed_at", ascending=False).head(8).copy()
        recent["Date"] = pd.to_datetime(recent["executed_at"]).dt.strftime("%m/%d %H:%M")
        recent["Notional"] = recent["notional"].map("${:,.0f}".format)
        side_color = recent["side"].map(lambda s: "color:#00d4aa" if s == "buy" else "color:#ff4b4b")
        tbl = recent[["Date", "symbol", "side", "quantity", "price", "Notional"]].rename(
            columns={"symbol": "Symbol", "side": "Side", "quantity": "Qty", "price": "Price"})
        st.dataframe(
            tbl.style.format({"Price": "${:.2f}"}).map(
                lambda v: "color:#00d4aa" if v == "buy" else "color:#ff4b4b" if v == "sell" else "",
                subset=["Side"]),
            use_container_width=True, hide_index=True)
    else:
        st.info("No trades yet.")

# ── RIGHT: Market snapshot + News ─────────────────────────────────────────────
with col_right:
    # Market snapshot
    st.html(section_header("Market Snapshot", "Major indices & volatility"))

    @st.cache_data(ttl=300)
    def _market_snap():
        tickers = {"S&P 500": "^GSPC", "NASDAQ": "^IXIC", "Russell 2000": "^RUT",
                   "VIX": "^VIX", "Gold": "GC=F", "Oil (WTI)": "CL=F"}
        rows = []
        for name, sym in tickers.items():
            try:
                fi = yf.Ticker(sym).fast_info
                last = fi.last_price
                prev = fi.previous_close
                if last and prev:
                    chg = last - prev
                    pct = chg / prev * 100
                    rows.append({"Index": name, "Last": f"{last:,.2f}",
                                 "Chg": f"{chg:+.2f}", "% Chg": pct})
            except Exception:
                pass
        return rows

    snap = _market_snap()
    if snap:
        snap_df = pd.DataFrame(snap)
        st.dataframe(
            snap_df.style.format({"% Chg": "{:+.2f}%"}).map(
                lambda v: f"color:{'#00d4aa' if v >= 0 else '#ff4b4b'}" if isinstance(v, float) else "",
                subset=["% Chg"]),
            use_container_width=True, hide_index=True)

    # Market news
    st.html(section_header("Market News", "Latest headlines"))

    @st.cache_data(ttl=600)
    def _news():
        try:
            raw = yf.Ticker("SPY").news or []
            return raw[:8]
        except Exception:
            return []

    news_items = _news()
    if news_items:
        for item in news_items:
            title = item.get("title", "")
            publisher = item.get("publisher", "")
            link = item.get("link", "#")
            ts = item.get("providerPublishTime", 0)
            age = ""
            if ts:
                diff = int(datetime.now().timestamp()) - ts
                if diff < 3600:
                    age = f"{diff // 60}m ago"
                elif diff < 86400:
                    age = f"{diff // 3600}h ago"
                else:
                    age = f"{diff // 86400}d ago"
            st.html(f"""
<div style="border-left:2px solid #1a2332;padding:8px 12px;margin-bottom:8px;
            background:#0d1422;border-radius:0 8px 8px 0">
  <a href="{link}" target="_blank" style="color:#c8d0e0;font-size:.82rem;font-weight:500;
            text-decoration:none;line-height:1.4;display:block">{title}</a>
  <div style="color:#2a3a52;font-size:.7rem;margin-top:4px">{publisher} · {age}</div>
</div>""")
    else:
        st.caption("News unavailable.")

# ── Bottom: Watchlist snapshot ─────────────────────────────────────────────────
st.divider()
st.html(section_header("Watchlist", "Tracked tickers — click to research"))

@st.cache_data(ttl=300)
def _watchlist_snap(tickers_key: str):
    tickers = tickers_key.split(",") if tickers_key else []
    rows = []
    for sym in tickers:
        try:
            fi = yf.Ticker(sym).fast_info
            last = fi.last_price
            prev = fi.previous_close
            if last and prev:
                chg = last - prev
                pct = chg / prev * 100
                rows.append({"sym": sym, "last": last, "pct": pct})
        except Exception:
            rows.append({"sym": sym, "last": None, "pct": None})
    return rows

try:
    db = get_client()
    wl_rows = db.table("watchlist").select("symbol").eq("user_id", SOLO_USER_ID).execute().data or []
    wl_syms = [r["symbol"] for r in wl_rows]
except Exception:
    wl_syms = []

if wl_syms:
    snap_data = _watchlist_snap(",".join(sorted(wl_syms)))
    cols = st.columns(min(len(snap_data), 6))
    for i, item in enumerate(snap_data):
        sym = item["sym"]
        last = item["last"]
        pct = item["pct"]
        color = "#00d4aa" if (pct or 0) >= 0 else "#ff4b4b"
        arrow = "▲" if (pct or 0) >= 0 else "▼"
        last_str = f"${last:,.2f}" if last else "N/A"
        pct_str = f"{arrow} {abs(pct):.2f}%" if pct is not None else "—"
        with cols[i % 6]:
            st.html(f"""
<a href="/Watchlist?ticker={sym}" target="_self" style="text-decoration:none">
<div style="background:#0d1422;border:1px solid #1a2332;border-radius:12px;
            padding:14px 16px;text-align:center;cursor:pointer;
            transition:border-color .2s" onmouseover="this.style.borderColor='#00d4aa40'"
            onmouseout="this.style.borderColor='#1a2332'">
  <div style="font-size:1rem;font-weight:800;color:#e2e8f0;letter-spacing:-.02em">{sym}</div>
  <div style="font-size:.95rem;font-weight:600;color:#c8d0e0;margin:4px 0">{last_str}</div>
  <div style="font-size:.78rem;font-weight:600;color:{color}">{pct_str}</div>
</div>
</a>""")
else:
    st.caption("No watchlist tickers yet. Add stocks on the **Watchlist** page.")
