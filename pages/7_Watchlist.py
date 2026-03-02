import streamlit as st
import pandas as pd
import yfinance as yf
from lib.supabase_client import get_client, SOLO_USER_ID
from lib.indicators import sma, ema, rsi, macd, bollinger_bands
from lib.charts import candlestick_with_indicators

st.set_page_config(page_title="Watchlist", layout="wide")
st.title("Watchlist")

client = get_client()


def load_watchlist():
    res = client.table("watchlist").select("*").eq("user_id", SOLO_USER_ID).order("added_at").execute()
    return res.data or []


# ── Add symbol ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Add Symbol")
    with st.form("add_watch"):
        new_sym = st.text_input("Ticker").upper().strip()
        new_notes = st.text_input("Notes (optional)")
        add_btn = st.form_submit_button("Add", use_container_width=True)
    if add_btn and new_sym:
        try:
            client.table("watchlist").insert({
                "user_id": SOLO_USER_ID,
                "symbol": new_sym,
                "notes": new_notes or None,
            }).execute()
            st.rerun()
        except Exception:
            st.warning(f"{new_sym} already in watchlist.")

    st.divider()
    st.subheader("Chart Settings")
    chart_period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)
    show_sma20 = st.checkbox("SMA 20", value=True)
    show_sma50 = st.checkbox("SMA 50", value=True)
    show_sma200 = st.checkbox("SMA 200", value=False)
    show_ema = st.checkbox("EMA 20", value=False)
    show_bb = st.checkbox("Bollinger Bands", value=False)
    show_rsi = st.checkbox("RSI (14)", value=True)
    show_macd = st.checkbox("MACD", value=False)


watchlist = load_watchlist()

if not watchlist:
    st.info("Add symbols using the sidebar.")
    st.stop()

# ── Snapshot table ────────────────────────────────────────────────────────────
st.subheader("Snapshot")

@st.cache_data(ttl=300)
def _snapshot(symbols_key):
    symbols = symbols_key.split(",")
    rows = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            fi = t.fast_info
            last = fi.last_price
            prev = fi.previous_close
            high52 = fi.year_high
            low52 = fi.year_low
            chg = last - prev
            pct = chg / prev * 100 if prev else 0
            rows.append({
                "Symbol": sym,
                "Last": last,
                "Chg": chg,
                "Chg %": pct,
                "52W High": high52,
                "52W Low": low52,
                "vs 52W High": (last / high52 - 1) * 100 if high52 else None,
            })
        except Exception:
            rows.append({"Symbol": sym, "Last": None, "Chg": None, "Chg %": None,
                         "52W High": None, "52W Low": None, "vs 52W High": None})
    return rows

syms_key = ",".join(sorted(w["symbol"] for w in watchlist))
snap = _snapshot(syms_key)
snap_df = pd.DataFrame(snap)

# Add RSI to snapshot
@st.cache_data(ttl=3600)
def _rsi_snapshot(syms_key):
    syms = syms_key.split(",")
    result = {}
    for sym in syms:
        try:
            df = yf.download(sym, period="3mo", auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            r = rsi(df["Close"])
            result[sym] = round(float(r.iloc[-1]), 1) if not r.empty else None
        except Exception:
            result[sym] = None
    return result

rsi_values = _rsi_snapshot(syms_key)
snap_df["RSI(14)"] = snap_df["Symbol"].map(rsi_values)

def _rsi_color(v):
    if v is None or pd.isna(v):
        return ""
    if v >= 70:
        return "color: #ff4b4b"
    if v <= 30:
        return "color: #00d4aa"
    return ""

st.dataframe(
    snap_df.style
        .format({
            "Last": lambda v: f"${v:.2f}" if v else "N/A",
            "Chg": lambda v: f"{v:+.2f}" if v else "N/A",
            "Chg %": lambda v: f"{v:+.2f}%" if v else "N/A",
            "52W High": lambda v: f"${v:.2f}" if v else "N/A",
            "52W Low": lambda v: f"${v:.2f}" if v else "N/A",
            "vs 52W High": lambda v: f"{v:.1f}%" if v else "N/A",
            "RSI(14)": lambda v: f"{v:.1f}" if v else "N/A",
        })
        .applymap(lambda v: f"color: {'#00d4aa' if isinstance(v, str) and v.startswith('+') else '#ff4b4b' if isinstance(v, str) and (v.startswith('-') and v != '-') else ''}",
                  subset=["Chg", "Chg %"])
        .applymap(_rsi_color, subset=["RSI(14)"]),
    use_container_width=True, hide_index=True,
)

st.divider()

# ── Per-symbol charts ─────────────────────────────────────────────────────────
st.subheader("Charts")
selected_sym = st.selectbox("Select symbol to chart", [w["symbol"] for w in watchlist])

col_remove, _ = st.columns([1, 5])
if col_remove.button(f"Remove {selected_sym} from watchlist"):
    client.table("watchlist").delete().eq("user_id", SOLO_USER_ID).eq("symbol", selected_sym).execute()
    st.rerun()

@st.cache_data(ttl=3600)
def _chart_data(sym, period):
    df = yf.download(sym, period=period, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    return df

df = _chart_data(selected_sym, chart_period)

if df.empty:
    st.error(f"No data for {selected_sym}")
    st.stop()

# Build indicator overlays
price_indicators = {}
if show_sma20:
    price_indicators["SMA 20"] = sma(df["Close"], 20)
if show_sma50:
    price_indicators["SMA 50"] = sma(df["Close"], 50)
if show_sma200:
    price_indicators["SMA 200"] = sma(df["Close"], 200)
if show_ema:
    price_indicators["EMA 20"] = ema(df["Close"], 20)
if show_bb:
    upper, middle, lower = bollinger_bands(df["Close"])
    price_indicators["BB Upper"] = upper
    price_indicators["BB Middle"] = middle
    price_indicators["BB Lower"] = lower

rsi_indicators = {}
if show_rsi:
    rsi_indicators["RSI 14"] = rsi(df["Close"])

# Combine all indicators (RSI tagged so candlestick fn routes it to RSI panel)
all_indicators = {**price_indicators, **rsi_indicators}

fig = candlestick_with_indicators(df, all_indicators, title=f"{selected_sym} — {chart_period}")
st.plotly_chart(fig, use_container_width=True)

# MACD subplot (separate chart for clarity)
if show_macd:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    macd_line, signal_line, histogram = macd(df["Close"])
    fig_macd = make_subplots(rows=1, cols=1)
    colors = ["#00d4aa" if v >= 0 else "#ff4b4b" for v in histogram]
    fig_macd.add_trace(go.Bar(x=df.index, y=histogram, name="Histogram", marker_color=colors))
    fig_macd.add_trace(go.Scatter(x=df.index, y=macd_line, name="MACD", line=dict(color="#4e9af1")))
    fig_macd.add_trace(go.Scatter(x=df.index, y=signal_line, name="Signal", line=dict(color="#f1c14e")))
    fig_macd.update_layout(title=f"{selected_sym} MACD",
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#fafafa",
                            xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
                            margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_macd, use_container_width=True)

# Notes for this symbol
wl_entry = next((w for w in watchlist if w["symbol"] == selected_sym), None)
if wl_entry and wl_entry.get("notes"):
    st.info(f"Notes: {wl_entry['notes']}")
