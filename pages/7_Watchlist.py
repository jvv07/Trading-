import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf

from lib.supabase_client import get_client, SOLO_USER_ID
from lib.indicators import sma, ema, rsi, macd, bollinger_bands
from lib.charts import candlestick_with_indicators
from lib.style import (
    inject_css, kpi_card, section_header, info_banner, stat_row,
    company_card_header, score_bar, check_item, analyst_badge, valuation_model_card,
)
from lib.fundamental import (
    fetch_info, fetch_financials, fetch_holders, fetch_market_data,
    fetch_peer_info, fetch_fmp, get_fmp_key, safe_get, format_large,
    bs_row, _first_val,
    calc_dcf, calc_graham_number, calc_ddm, calc_altman_z, calc_relative_valuation,
    score_value, score_future, score_past, score_health, score_dividend,
    get_sector_peers, SECTOR_NAME_MAP,
)

st.set_page_config(page_title="Watchlist / Research", layout="wide")
inject_css()
st.title("Watchlist & Research")

client = get_client()

# ── Watchlist CRUD ────────────────────────────────────────────────────────────

def load_watchlist():
    res = (client.table("watchlist").select("*")
           .eq("user_id", SOLO_USER_ID).order("added_at").execute())
    return res.data or []


with st.sidebar:
    st.subheader("Add Symbol")
    with st.form("add_watch"):
        new_sym   = st.text_input("Ticker").upper().strip()
        new_notes = st.text_input("Notes (optional)")
        add_btn   = st.form_submit_button("Add", use_container_width=True)
    if add_btn and new_sym:
        try:
            client.table("watchlist").insert({
                "user_id": SOLO_USER_ID,
                "symbol":  new_sym,
                "notes":   new_notes or None,
            }).execute()
            st.rerun()
        except Exception:
            st.warning(f"{new_sym} already in watchlist.")

    st.divider()
    st.caption("Chart overlay (used in candlestick view)")
    chart_period = st.selectbox("Period", ["1mo","3mo","6mo","1y","2y","5y"], index=3)
    show_sma20   = st.checkbox("SMA 20",  value=True)
    show_sma50   = st.checkbox("SMA 50",  value=True)
    show_sma200  = st.checkbox("SMA 200", value=False)
    show_ema     = st.checkbox("EMA 20",  value=False)
    show_bb      = st.checkbox("Bollinger Bands", value=False)
    show_rsi     = st.checkbox("RSI (14)", value=True)
    show_macd    = st.checkbox("MACD",    value=False)

watchlist = load_watchlist()

if not watchlist:
    st.info("Add symbols using the sidebar.")
    st.stop()

# ── Snapshot expander ─────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _snapshot(symbols_key: str):
    symbols = symbols_key.split(",")
    rows = []
    for sym in symbols:
        try:
            fi   = yf.Ticker(sym).fast_info
            last = fi.last_price
            prev = fi.previous_close
            chg  = last - prev
            pct  = chg / prev * 100 if prev else 0
            rows.append({"Symbol": sym, "Last": last, "Chg": chg, "Chg%": pct,
                         "52W Hi": fi.year_high, "52W Lo": fi.year_low,
                         "vs Hi%": (last / fi.year_high - 1)*100 if fi.year_high else None})
        except Exception:
            rows.append({"Symbol": sym, "Last": None, "Chg": None, "Chg%": None,
                         "52W Hi": None, "52W Lo": None, "vs Hi%": None})
    return rows


@st.cache_data(ttl=3600)
def _rsi_snapshot(syms_key: str) -> dict:
    result = {}
    for sym in syms_key.split(","):
        try:
            df = yf.download(sym, period="3mo", auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            r = rsi(df["Close"])
            result[sym] = round(float(r.iloc[-1]), 1) if not r.empty else None
        except Exception:
            result[sym] = None
    return result


syms_key = ",".join(sorted(w["symbol"] for w in watchlist))

with st.expander("Watchlist Snapshot", expanded=False):
    snap     = _snapshot(syms_key)
    snap_df  = pd.DataFrame(snap)
    rsi_vals = _rsi_snapshot(syms_key)
    snap_df["RSI"] = snap_df["Symbol"].map(rsi_vals)

    def _rsi_color(v):
        if v is None or pd.isna(v): return ""
        if v >= 70: return "color:#ff4b4b"
        if v <= 30: return "color:#00d4aa"
        return ""

    st.dataframe(
        snap_df.style
            .format({
                "Last":   lambda v: f"${v:.2f}" if v else "N/A",
                "Chg":    lambda v: f"{v:+.2f}" if v else "N/A",
                "Chg%":   lambda v: f"{v:+.2f}%" if v else "N/A",
                "52W Hi": lambda v: f"${v:.2f}" if v else "N/A",
                "52W Lo": lambda v: f"${v:.2f}" if v else "N/A",
                "vs Hi%": lambda v: f"{v:.1f}%" if v else "N/A",
                "RSI":    lambda v: f"{v:.1f}" if v else "N/A",
            })
            .map(lambda v: f"color:{'#00d4aa' if isinstance(v,str) and v.startswith('+') else '#ff4b4b' if isinstance(v,str) and v.startswith('-') and v != '-' else ''}",
                 subset=["Chg","Chg%"])
            .map(_rsi_color, subset=["RSI"]),
        use_container_width=True, hide_index=True,
    )

st.divider()

# ── Symbol selector ───────────────────────────────────────────────────────────

sym_list     = [w["symbol"] for w in watchlist]
selected_sym = st.radio(
    "Select symbol for research report:",
    sym_list,
    horizontal=True,
    label_visibility="visible",
)

wl_entry = next((w for w in watchlist if w["symbol"] == selected_sym), None)

col_remove, _ = st.columns([1, 6])
if col_remove.button(f"Remove {selected_sym}", type="secondary"):
    client.table("watchlist").delete().eq("user_id", SOLO_USER_ID).eq("symbol", selected_sym).execute()
    st.rerun()

st.divider()

# ── Load all data ─────────────────────────────────────────────────────────────

# Safe defaults — used if data loading partially fails
_empty_fin = {k: pd.DataFrame() for k in
              ["annual_income","quarterly_income","annual_bs",
               "quarterly_bs","annual_cf","quarterly_cf"]}
info        = {}
financials  = _empty_fin.copy()
holders     = {"institutional": pd.DataFrame(), "major": pd.DataFrame(),
               "insider_tx": pd.DataFrame()}
market_d    = {"recommendations": pd.DataFrame(), "upgrades": pd.DataFrame(),
               "news": [], "dividends": pd.Series(dtype=float)}
fmp_data    = {}
_load_error = None

with st.spinner(f"Loading {selected_sym} report…"):
    try:
        info       = fetch_info(selected_sym)
        financials = fetch_financials(selected_sym)
        holders    = fetch_holders(selected_sym)
        market_d   = fetch_market_data(selected_sym)
        fmp_data   = fetch_fmp(selected_sym)
    except Exception as _e:
        _load_error = str(_e)

# Run scoring (safe — each returns a default tuple on error)
def _safe_score(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return 0.0, []

val_score,  val_sigs  = _safe_score(score_value,    info, financials)
fut_score,  fut_sigs  = _safe_score(score_future,   info, financials, fmp_data)
past_score, past_sigs = _safe_score(score_past,     info, financials)
hlt_score,  hlt_sigs  = _safe_score(score_health,   info, financials)
div_score,  div_sigs  = _safe_score(score_dividend, info, financials)

try:
    dcf_result = calc_dcf(info, financials)
except Exception:
    dcf_result = None
try:
    graham = calc_graham_number(info)
except Exception:
    graham = None
try:
    ddm_result = calc_ddm(info)
except Exception:
    ddm_result = None
try:
    altman = calc_altman_z(info, financials)
except Exception:
    altman = None
try:
    rel_val = calc_relative_valuation(info)
except Exception:
    rel_val = {"pe_fair_value": None, "evebitda_fair_value": None,
               "pe_median": 20, "ev_median": 14, "sector": ""}
peers = get_sector_peers(safe_get(info, "sector", ""), selected_sym)

if _load_error:
    st.warning(f"Some data failed to load: {_load_error}")

# ── Company Research Report ────────────────────────────────────────────────────

st.markdown(
    "<div style='color:#00d4aa;font-size:.7rem;font-weight:700;"
    "text-transform:uppercase;letter-spacing:.15em;margin-bottom:.5rem'>"
    f"◆ COMPANY RESEARCH REPORT — {selected_sym}</div>",
    unsafe_allow_html=True,
)

left_col, right_col = st.columns([1, 2.5], gap="large")

# ════════════════════════════════════════════════════════════════════════════════
#  LEFT COLUMN
# ════════════════════════════════════════════════════════════════════════════════
with left_col:
    # Company card
    price      = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice")
    prev_close = safe_get(info, "previousClose") or safe_get(info, "regularMarketPreviousClose")
    chg_pct    = ((float(price) - float(prev_close)) / float(prev_close) * 100
                  if price and prev_close else None)
    mkt_cap    = safe_get(info, "marketCap")

    st.markdown(company_card_header(
        ticker       = selected_sym,
        name         = safe_get(info, "longName", safe_get(info, "shortName", selected_sym)),
        sector       = safe_get(info, "sector", "N/A"),
        industry     = safe_get(info, "industry", "N/A"),
        employees    = safe_get(info, "fullTimeEmployees"),
        market_cap_str = format_large(mkt_cap),
        price        = price,
        change_pct   = chg_pct,
    ), unsafe_allow_html=True)

    # Pentagon radar
    dims       = ["Value", "Future", "Past", "Health", "Dividend"]
    dim_scores = [val_score, fut_score, past_score, hlt_score, div_score]
    r_scores   = dim_scores + [dim_scores[0]]  # close polygon
    theta      = dims + [dims[0]]

    fig_radar = go.Figure()
    # Background
    fig_radar.add_trace(go.Scatterpolar(
        r=[6, 6, 6, 6, 6, 6], theta=theta,
        fill="toself", fillcolor="rgba(26,35,50,0.5)",
        line=dict(color="#1a2332", width=1),
        showlegend=False, hoverinfo="skip",
    ))
    # Score polygon
    fig_radar.add_trace(go.Scatterpolar(
        r=r_scores, theta=theta,
        fill="toself", fillcolor="rgba(0,212,170,0.15)",
        line=dict(color="#00d4aa", width=2),
        showlegend=False,
        hovertemplate="%{theta}: %{r:.1f}/6<extra></extra>",
    ))
    fig_radar.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                range=[0, 6], dtick=2, showticklabels=True,
                tickfont=dict(size=9, color="#4a5a72"),
                gridcolor="#1a2332", linecolor="#1a2332",
            ),
            angularaxis=dict(
                tickfont=dict(size=11, color="#8892a4"),
                gridcolor="#1a2332", linecolor="#1a2332",
            ),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e2e8f0",
        margin=dict(l=30, r=30, t=20, b=20),
        height=280,
        showlegend=False,
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # Score bars
    st.markdown("---")
    for label, sc in zip(dims, dim_scores):
        st.markdown(score_bar(label, sc), unsafe_allow_html=True)

    # Overall score
    total = sum(dim_scores)
    overall = (total / 30) * 10
    ov_color = "#ff4b4b" if overall < 3.5 else "#f1c14e" if overall < 6 else "#00d4aa"
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#0d1422,#0a1020);
            border:1px solid #1a2332;border-radius:12px;padding:14px;
            text-align:center;margin-top:12px">
  <div style="color:#4a5a72;font-size:.68rem;font-weight:700;
              text-transform:uppercase;letter-spacing:.1em">Overall Score</div>
  <div style="color:{ov_color};font-size:2.2rem;font-weight:900;
              letter-spacing:-.04em">{overall:.1f}<span style="font-size:1rem;
              color:#4a5a72">/10</span></div>
</div>""", unsafe_allow_html=True)

    # Price target bar
    t_lo  = safe_get(info, "targetLowPrice")
    t_hi  = safe_get(info, "targetHighPrice")
    t_med = safe_get(info, "targetMeanPrice")
    if t_lo and t_hi and price:
        st.markdown("---")
        st.markdown("<div style='color:#4a5a72;font-size:.68rem;font-weight:700;"
                    "text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px'>"
                    "Analyst Price Targets</div>", unsafe_allow_html=True)
        fig_pt = go.Figure()
        fig_pt.add_trace(go.Bar(
            x=["Low","Mean","High","Current"],
            y=[t_lo, t_med or 0, t_hi, float(price)],
            marker_color=["#4a5a72","#f1c14e","#00d4aa","#4e9af1"],
            text=[f"${v:.0f}" for v in [t_lo, t_med or 0, t_hi, float(price)]],
            textposition="outside", textfont=dict(size=10),
        ))
        fig_pt.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e2e8f0", showlegend=False,
            margin=dict(l=0, r=0, t=10, b=20),
            height=180,
            yaxis=dict(gridcolor="#1a2332", showticklabels=False),
            xaxis=dict(gridcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig_pt, use_container_width=True)

    if wl_entry and wl_entry.get("notes"):
        st.markdown(info_banner(f"📌 {wl_entry['notes']}", "#4e9af1"), unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
#  RIGHT COLUMN — 8 TABS
# ════════════════════════════════════════════════════════════════════════════════
with right_col:
    tabs = st.tabs([
        "Overview", "Valuation", "Future Growth", "Past Performance",
        "Financial Health", "Dividend", "Management", "Ownership",
    ])

    # ── TAB 0: OVERVIEW ───────────────────────────────────────────────────────
    with tabs[0]:
        try:
            desc = safe_get(info, "longBusinessSummary", "No description available.")
            with st.expander("Business Description", expanded=True):
                st.write(desc)

            # KPI row
            pe_str    = f"{safe_get(info,'trailingPE'):.1f}x" if safe_get(info,"trailingPE") else "N/A"
            eps_str   = f"${safe_get(info,'trailingEps'):.2f}" if safe_get(info,"trailingEps") else "N/A"
            beta_str  = f"{safe_get(info,'beta'):.2f}" if safe_get(info,"beta") else "N/A"
            hi52      = safe_get(info, "fiftyTwoWeekHigh")
            lo52      = safe_get(info, "fiftyTwoWeekLow")
            rng52     = (f"${lo52:.2f} – ${hi52:.2f}" if hi52 and lo52 else "N/A")
            vol_str   = format_large(safe_get(info,"volume"), prefix="")
            rec_key   = safe_get(info, "recommendationKey", "")
            n_analysts = safe_get(info, "numberOfAnalystOpinions", 0) or 0

            st.markdown(stat_row([
                ("P/E (TTM)", pe_str),
                ("EPS (TTM)", eps_str),
                ("Beta",      beta_str),
                ("52W Range", rng52),
                ("Volume",    vol_str),
            ]), unsafe_allow_html=True)

            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown(
                    analyst_badge(rec_key) +
                    f'<span style="color:#4a5a72;font-size:.75rem;margin-left:8px">'
                    f'{n_analysts} analysts</span>',
                    unsafe_allow_html=True,
                )
            st.markdown("")

            # Peer comparison table
            if peers:
                st.markdown(section_header("Peer Comparison"), unsafe_allow_html=True)
                with st.spinner("Loading peers…"):
                    p_info = fetch_peer_info(",".join(sorted(peers)))
                peer_rows = []
                all_tickers = [selected_sym] + list(p_info.keys())
                all_infos   = {selected_sym: info, **p_info}
                for sym2 in all_tickers:
                    inf2  = all_infos[sym2]
                    peer_rows.append({
                        "Symbol":   sym2,
                        "Price":    safe_get(inf2,"currentPrice") or safe_get(inf2,"regularMarketPrice"),
                        "Mkt Cap":  format_large(safe_get(inf2,"marketCap")),
                        "P/E":      f"{safe_get(inf2,'trailingPE'):.1f}" if safe_get(inf2,"trailingPE") else "N/A",
                        "Fwd P/E":  f"{safe_get(inf2,'forwardPE'):.1f}"  if safe_get(inf2,"forwardPE")  else "N/A",
                        "Rev Gr%":  f"{safe_get(inf2,'revenueGrowth',0)*100:.1f}%" if safe_get(inf2,"revenueGrowth") else "N/A",
                        "Net Mgn%": f"{safe_get(inf2,'profitMargins',0)*100:.1f}%" if safe_get(inf2,"profitMargins") else "N/A",
                    })
                peer_df = pd.DataFrame(peer_rows)
                st.dataframe(peer_df, use_container_width=True, hide_index=True)

            # News feed
            news = market_d.get("news", [])
            if news:
                st.markdown(section_header("Latest News"), unsafe_allow_html=True)
                for item in news[:6]:
                    try:
                        title = item.get("title","")
                        link  = item.get("link","")
                        pub   = item.get("publisher","")
                        st.markdown(
                            f'<div style="padding:6px 0;border-bottom:1px solid #1a2332">'
                            f'<a href="{link}" target="_blank" style="color:#e2e8f0;'
                            f'text-decoration:none;font-size:.85rem;font-weight:500">{title}</a>'
                            f'<div style="color:#4a5a72;font-size:.7rem;margin-top:2px">{pub}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    except Exception:
                        pass

        except Exception as e:
            st.warning(f"Overview error: {e}")

    # ── TAB 1: VALUATION ──────────────────────────────────────────────────────
    with tabs[1]:
        try:
            price = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice")

            def _upside(fv):
                if fv is None or price is None: return None
                return (float(fv) - float(price)) / float(price) * 100

            # 4 model cards
            c1, c2 = st.columns(2, gap="medium")
            with c1:
                st.markdown(valuation_model_card(
                    "DCF (2-Stage)",
                    dcf_result["fair_value"] if dcf_result else None,
                    price,
                    _upside(dcf_result["fair_value"] if dcf_result else None),
                    dcf_result["methodology"] if dcf_result else "Requires positive FCF",
                ), unsafe_allow_html=True)
            with c2:
                st.markdown(valuation_model_card(
                    "Graham Number",
                    graham["graham_number"] if graham else None,
                    price,
                    _upside(graham["graham_number"] if graham else None),
                    "√(22.5 × EPS × Book Value)",
                ), unsafe_allow_html=True)

            st.markdown("")
            c3, c4 = st.columns(2, gap="medium")
            rel = calc_relative_valuation(info)
            with c3:
                st.markdown(valuation_model_card(
                    f"Relative P/E (vs sector {rel['pe_median']}×)",
                    rel["pe_fair_value"],
                    price,
                    _upside(rel["pe_fair_value"]),
                    f"Sector median P/E: {rel['pe_median']}×",
                ), unsafe_allow_html=True)
            with c4:
                st.markdown(valuation_model_card(
                    f"EV/EBITDA (vs {rel['ev_median']}×)",
                    rel["evebitda_fair_value"],
                    price,
                    _upside(rel["evebitda_fair_value"]),
                    f"Sector median EV/EBITDA: {rel['ev_median']}×",
                ), unsafe_allow_html=True)

            if ddm_result:
                st.markdown("")
                st.markdown(valuation_model_card(
                    "DDM (Dividend Discount)",
                    ddm_result["fair_value"],
                    price,
                    _upside(ddm_result["fair_value"]),
                    ddm_result["methodology"],
                    accent="#f1c14e",
                ), unsafe_allow_html=True)

            # Price vs fair values bar chart
            st.markdown("---")
            fv_vals, fv_labels, fv_colors = [], [], []
            if price:
                fv_vals.append(float(price)); fv_labels.append("Current"); fv_colors.append("#4e9af1")
            if dcf_result:
                fv_vals.append(dcf_result["fair_value"]); fv_labels.append("DCF"); fv_colors.append("#00d4aa")
            if graham:
                fv_vals.append(graham["graham_number"]); fv_labels.append("Graham"); fv_colors.append("#00b894")
            if rel["pe_fair_value"]:
                fv_vals.append(rel["pe_fair_value"]); fv_labels.append("Rel P/E"); fv_colors.append("#f1c14e")
            if rel["evebitda_fair_value"]:
                fv_vals.append(rel["evebitda_fair_value"]); fv_labels.append("EV/EBITDA"); fv_colors.append("#a29bfe")
            if ddm_result:
                fv_vals.append(ddm_result["fair_value"]); fv_labels.append("DDM"); fv_colors.append("#fd79a8")

            if len(fv_vals) > 1:
                fig_fv = go.Figure(go.Bar(
                    x=fv_labels, y=fv_vals,
                    marker_color=fv_colors,
                    text=[f"${v:.2f}" for v in fv_vals],
                    textposition="outside",
                ))
                fig_fv.update_layout(
                    title="Price vs Valuation Models",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#e2e8f0", showlegend=False,
                    yaxis=dict(gridcolor="#1a2332", tickprefix="$"),
                    xaxis=dict(gridcolor="rgba(0,0,0,0)"),
                    margin=dict(l=0, r=0, t=40, b=20), height=300,
                )
                st.plotly_chart(fig_fv, use_container_width=True)

            # Valuation signals
            st.markdown(section_header("Valuation Signals"), unsafe_allow_html=True)
            for sig in val_sigs:
                st.markdown(check_item(sig["text"], sig["passed"]), unsafe_allow_html=True)

            # Peer scatter: P/E vs Revenue Growth
            if peers:
                st.markdown(section_header("Peer: P/E vs Revenue Growth"), unsafe_allow_html=True)
                p_info = fetch_peer_info(",".join(sorted(peers)))
                all_info2 = {selected_sym: info, **p_info}
                sx, sy, slabels = [], [], []
                for sym2, inf2 in all_info2.items():
                    pe2 = safe_get(inf2, "trailingPE")
                    gr2 = safe_get(inf2, "revenueGrowth")
                    if pe2 and gr2:
                        sx.append(pe2); sy.append(gr2*100); slabels.append(sym2)
                if sx:
                    fig_sc = go.Figure(go.Scatter(
                        x=sx, y=sy, mode="markers+text",
                        text=slabels, textposition="top center",
                        marker=dict(
                            color=["#00d4aa" if s == selected_sym else "#4e9af1" for s in slabels],
                            size=10,
                        ),
                        textfont=dict(size=10, color="#8892a4"),
                    ))
                    fig_sc.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#e2e8f0",
                        xaxis=dict(title="P/E Ratio", gridcolor="#1a2332"),
                        yaxis=dict(title="Revenue Growth %", gridcolor="#1a2332"),
                        margin=dict(l=0, r=0, t=20, b=20), height=300,
                    )
                    st.plotly_chart(fig_sc, use_container_width=True)

        except Exception as e:
            st.warning(f"Valuation error: {e}")

    # ── TAB 2: FUTURE GROWTH ──────────────────────────────────────────────────
    with tabs[2]:
        try:
            rev_g    = safe_get(info, "revenueGrowth")
            earn_g   = safe_get(info, "earningsGrowth")
            fwd_eps  = safe_get(info, "forwardEps")
            trail_eps = safe_get(info, "trailingEps")

            st.markdown(stat_row([
                ("Revenue Growth", f"{rev_g*100:.1f}%"   if rev_g    else "N/A",
                 "#00d4aa" if rev_g and rev_g > 0 else "#ff4b4b"),
                ("Earnings Growth", f"{earn_g*100:.1f}%" if earn_g   else "N/A",
                 "#00d4aa" if earn_g and earn_g > 0 else "#ff4b4b"),
                ("Fwd EPS",  f"${fwd_eps:.2f}"  if fwd_eps  else "N/A"),
                ("Trail EPS", f"${trail_eps:.2f}" if trail_eps else "N/A"),
                ("Target",   f"${safe_get(info,'targetMeanPrice'):.2f}"
                              if safe_get(info,"targetMeanPrice") else "N/A", "#f1c14e"),
            ]), unsafe_allow_html=True)

            # Revenue + Earnings bar chart (4Y)
            inc = financials.get("annual_income", pd.DataFrame())
            rev_row = bs_row(inc, "Total Revenue", "Revenue")
            ni_row  = bs_row(inc, "Net Income")

            if rev_row is not None and not rev_row.dropna().empty:
                rev_data = rev_row.dropna().iloc[:4]
                ni_data  = ni_row.dropna().iloc[:4]  if ni_row is not None else pd.Series(dtype=float)

                years = [str(d)[:4] for d in rev_data.index][::-1]
                revs  = [float(v)/1e9 for v in rev_data.values][::-1]
                nis   = [float(v)/1e9 for v in ni_data.reindex(rev_data.index).values][::-1] if not ni_data.empty else []

                fig_gr = make_subplots(specs=[[{"secondary_y": True}]])
                fig_gr.add_trace(go.Bar(name="Revenue ($B)", x=years, y=revs,
                                        marker_color="#4e9af1"), secondary_y=False)
                if nis:
                    ni_colors = ["#00d4aa" if v >= 0 else "#ff4b4b" for v in nis]
                    fig_gr.add_trace(go.Bar(name="Net Income ($B)", x=years, y=nis,
                                            marker_color=ni_colors), secondary_y=True)

                # FMP forecast bars
                fmp_ests = fmp_data.get("analyst_estimates", [])
                if fmp_ests and get_fmp_key():
                    try:
                        fwd_revs = [float(e.get("estimatedRevenueAvg", 0))/1e9 for e in fmp_ests[:2]]
                        fwd_yrs  = [e.get("date","")[:4] for e in fmp_ests[:2]]
                        fig_gr.add_trace(go.Bar(name="Est Revenue ($B)", x=fwd_yrs, y=fwd_revs,
                                                marker_color="#00d4aa", opacity=0.5),
                                         secondary_y=False)
                    except Exception:
                        pass

                fig_gr.update_layout(
                    title="Annual Revenue & Net Income", barmode="group",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#e2e8f0", legend=dict(bgcolor="rgba(0,0,0,0)"),
                    yaxis=dict(title="Revenue $B", gridcolor="#1a2332"),
                    yaxis2=dict(title="Net Income $B", gridcolor="rgba(0,0,0,0)"),
                    margin=dict(l=0, r=0, t=40, b=20), height=320,
                )
                st.plotly_chart(fig_gr, use_container_width=True)
            else:
                st.info("Annual income statement not available.")

            # Upgrades/downgrades
            upgrades = market_d.get("upgrades", pd.DataFrame())
            if not upgrades.empty:
                st.markdown(section_header("Recent Upgrades / Downgrades"), unsafe_allow_html=True)
                try:
                    disp = upgrades.reset_index()
                    st.dataframe(disp.head(10), use_container_width=True, hide_index=True)
                except Exception:
                    st.dataframe(upgrades.head(10), use_container_width=True)

            # Future signals
            st.markdown(section_header("Future Growth Signals"), unsafe_allow_html=True)
            for sig in fut_sigs:
                st.markdown(check_item(sig["text"], sig["passed"]), unsafe_allow_html=True)

        except Exception as e:
            st.warning(f"Future Growth error: {e}")

    # ── TAB 3: PAST PERFORMANCE ───────────────────────────────────────────────
    with tabs[3]:
        try:
            inc = financials.get("annual_income", pd.DataFrame())
            cf  = financials.get("annual_cf", pd.DataFrame())

            roe = safe_get(info, "returnOnEquity")
            roa = safe_get(info, "returnOnAssets")
            st.markdown(stat_row([
                ("ROE",        f"{roe*100:.1f}%" if roe else "N/A",
                 "#00d4aa" if roe and roe > 0.15 else "#f1c14e" if roe and roe > 0 else "#ff4b4b"),
                ("ROA",        f"{roa*100:.1f}%" if roa else "N/A",
                 "#00d4aa" if roa and roa > 0.05 else "#f1c14e" if roa and roa > 0 else "#ff4b4b"),
                ("Net Margin", f"{safe_get(info,'profitMargins',0)*100:.1f}%" if safe_get(info,'profitMargins') else "N/A"),
                ("Gross Mgn",  f"{safe_get(info,'grossMargins',0)*100:.1f}%"  if safe_get(info,'grossMargins')  else "N/A"),
                ("Op Margin",  f"{safe_get(info,'operatingMargins',0)*100:.1f}%" if safe_get(info,'operatingMargins') else "N/A"),
            ]), unsafe_allow_html=True)

            # Revenue + NI grouped bars
            rev_row = bs_row(inc, "Total Revenue", "Revenue")
            ni_row  = bs_row(inc, "Net Income")
            if rev_row is not None and not rev_row.dropna().empty:
                rev_data = rev_row.dropna().iloc[:5]
                years = [str(d)[:4] for d in rev_data.index][::-1]
                revs  = [float(v)/1e9 for v in rev_data.values][::-1]

                fig_hist = go.Figure()
                fig_hist.add_trace(go.Bar(name="Revenue ($B)", x=years, y=revs,
                                           marker_color="#4e9af1"))
                if ni_row is not None and not ni_row.dropna().empty:
                    ni_data = ni_row.dropna().reindex(rev_data.index)
                    nis = [float(v)/1e9 if not pd.isna(v) else 0 for v in ni_data.values][::-1]
                    ni_colors = ["#00d4aa" if v >= 0 else "#ff4b4b" for v in nis]
                    fig_hist.add_trace(go.Bar(name="Net Income ($B)", x=years, y=nis,
                                              marker_color=ni_colors))
                fig_hist.update_layout(
                    title="Revenue & Net Income History", barmode="group",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#e2e8f0", legend=dict(bgcolor="rgba(0,0,0,0)"),
                    yaxis=dict(gridcolor="#1a2332"),
                    margin=dict(l=0, r=0, t=40, b=20), height=300,
                )
                st.plotly_chart(fig_hist, use_container_width=True)

            # Margin trend
            gross_row = bs_row(inc, "Gross Profit")
            op_row    = bs_row(inc, "Operating Income", "Operating Income Loss")
            ni_row2   = bs_row(inc, "Net Income")
            if rev_row is not None and gross_row is not None:
                rev_d = rev_row.dropna().iloc[:5]
                years = [str(d)[:4] for d in rev_d.index][::-1]
                fig_mg = go.Figure()
                for row_data, name, color in [
                    (gross_row, "Gross Margin", "#00d4aa"),
                    (op_row,    "Op Margin",    "#f1c14e"),
                    (ni_row2,   "Net Margin",   "#4e9af1"),
                ]:
                    if row_data is not None:
                        mgns = [(float(r)/float(v)*100) if float(v) != 0 else 0
                                for r, v in zip(
                                    row_data.reindex(rev_d.index).fillna(0).values,
                                    rev_d.values,
                                )][::-1]
                        fig_mg.add_trace(go.Scatter(
                            x=years, y=mgns, name=name, mode="lines+markers",
                            line=dict(color=color, width=2),
                        ))
                fig_mg.update_layout(
                    title="Margin Trends (%)",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#e2e8f0", legend=dict(bgcolor="rgba(0,0,0,0)"),
                    yaxis=dict(gridcolor="#1a2332", ticksuffix="%"),
                    xaxis=dict(gridcolor="#1a2332"),
                    margin=dict(l=0, r=0, t=40, b=20), height=280,
                )
                st.plotly_chart(fig_mg, use_container_width=True)

            # Altman Z components
            if altman:
                st.markdown(section_header(
                    f"Altman Z-Score: {altman['z_score']:.2f} — {altman['zone']}"), unsafe_allow_html=True)
                comps = altman["components"]
                fig_z = go.Figure(go.Bar(
                    x=list(comps.keys()),
                    y=list(comps.values()),
                    marker_color=["#00d4aa" if v > 0 else "#ff4b4b" for v in comps.values()],
                ))
                fig_z.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#e2e8f0",
                    yaxis=dict(gridcolor="#1a2332"),
                    margin=dict(l=0, r=0, t=10, b=20), height=200,
                )
                st.plotly_chart(fig_z, use_container_width=True)

            # Past signals
            st.markdown(section_header("Past Performance Signals"), unsafe_allow_html=True)
            for sig in past_sigs:
                st.markdown(check_item(sig["text"], sig["passed"]), unsafe_allow_html=True)

        except Exception as e:
            st.warning(f"Past Performance error: {e}")

    # ── TAB 4: FINANCIAL HEALTH ───────────────────────────────────────────────
    with tabs[4]:
        try:
            total_cash = float(safe_get(info, "totalCash", 0) or 0)
            total_debt = float(safe_get(info, "totalDebt", 0) or 0)
            curr_ratio = safe_get(info, "currentRatio")
            de         = safe_get(info, "debtToEquity")
            de_actual  = (de / 100) if de else None

            st.markdown(stat_row([
                ("Cash",          format_large(total_cash)),
                ("Total Debt",    format_large(total_debt)),
                ("Net Cash",      format_large(total_cash - total_debt),
                 "#00d4aa" if total_cash > total_debt else "#ff4b4b"),
                ("Current Ratio", f"{curr_ratio:.2f}" if curr_ratio else "N/A",
                 "#00d4aa" if curr_ratio and curr_ratio > 1.5 else
                 "#f1c14e" if curr_ratio and curr_ratio > 1 else "#ff4b4b"),
                ("D/E",           f"{de_actual:.2f}x" if de_actual else "N/A",
                 "#00d4aa" if de_actual and de_actual < 1 else
                 "#f1c14e" if de_actual and de_actual < 2 else "#ff4b4b"),
            ]), unsafe_allow_html=True)

            # Cash vs Debt bar
            fig_cd = go.Figure(go.Bar(
                x=["Cash", "Total Debt"],
                y=[total_cash/1e9, total_debt/1e9],
                marker_color=["#00d4aa", "#ff4b4b"],
                text=[f"${v/1e9:.2f}B" for v in [total_cash, total_debt]],
                textposition="outside",
            ))
            fig_cd.update_layout(
                title="Cash vs Total Debt ($B)",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e2e8f0", showlegend=False,
                yaxis=dict(gridcolor="#1a2332", ticksuffix="B"),
                margin=dict(l=0, r=0, t=40, b=20), height=250,
            )
            st.plotly_chart(fig_cd, use_container_width=True)

            # Balance sheet composition
            bs = financials.get("annual_bs", pd.DataFrame())
            if not bs.empty:
                curr_assets = _first_val(bs_row(bs, "Current Assets", "Total Current Assets"))
                non_curr_a  = _first_val(bs_row(bs, "Net PPE", "Non Current Assets",
                                                 "Total Non Current Assets"))
                curr_liab   = _first_val(bs_row(bs, "Current Liabilities", "Total Current Liabilities"))
                non_curr_l  = _first_val(bs_row(bs, "Non Current Liabilities",
                                                  "Total Non Current Liabilities"))
                if curr_assets and curr_liab:
                    fig_bs = go.Figure()
                    fig_bs.add_trace(go.Bar(name="Current Assets",   x=["Assets"],
                                            y=[curr_assets/1e9],    marker_color="#00d4aa"))
                    fig_bs.add_trace(go.Bar(name="Non-Current Assets", x=["Assets"],
                                            y=[(non_curr_a or 0)/1e9], marker_color="#00a882"))
                    fig_bs.add_trace(go.Bar(name="Current Liab.",    x=["Liabilities"],
                                            y=[curr_liab/1e9],      marker_color="#ff4b4b"))
                    fig_bs.add_trace(go.Bar(name="Non-Current Liab.", x=["Liabilities"],
                                            y=[(non_curr_l or 0)/1e9], marker_color="#cc3333"))
                    fig_bs.update_layout(
                        title="Balance Sheet Composition ($B)", barmode="stack",
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#e2e8f0", legend=dict(bgcolor="rgba(0,0,0,0)"),
                        yaxis=dict(gridcolor="#1a2332", ticksuffix="B"),
                        margin=dict(l=0, r=0, t=40, b=20), height=280,
                    )
                    st.plotly_chart(fig_bs, use_container_width=True)

            # Altman Z gauge
            if altman:
                z = altman["z_score"]
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=min(z, 5),
                    title={"text": "Altman Z-Score", "font": {"color": "#8892a4", "size": 14}},
                    number={"font": {"color": altman["color"], "size": 28},
                            "suffix": f" ({altman['zone']})"},
                    gauge={
                        "axis": {"range": [0, 5], "tickcolor": "#4a5a72"},
                        "bar": {"color": altman["color"]},
                        "bgcolor": "#0d1422",
                        "steps": [
                            {"range": [0, 1.81], "color": "#2a0010"},
                            {"range": [1.81, 2.99], "color": "#2a2000"},
                            {"range": [2.99, 5], "color": "#003322"},
                        ],
                        "threshold": {"line": {"color": "#e2e8f0", "width": 2},
                                      "thickness": 0.75, "value": z},
                    },
                ))
                fig_gauge.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", font_color="#e2e8f0",
                    margin=dict(l=20, r=20, t=30, b=20), height=220,
                )
                st.plotly_chart(fig_gauge, use_container_width=True)

            # Health signals
            st.markdown(section_header("Financial Health Signals"), unsafe_allow_html=True)
            for sig in hlt_sigs:
                st.markdown(check_item(sig["text"], sig["passed"]), unsafe_allow_html=True)

        except Exception as e:
            st.warning(f"Financial Health error: {e}")

    # ── TAB 5: DIVIDEND ───────────────────────────────────────────────────────
    with tabs[5]:
        try:
            div_yield = safe_get(info, "dividendYield")
            div_rate  = safe_get(info, "dividendRate")

            if not div_yield or div_yield <= 0:
                st.markdown(info_banner(
                    "This company does not currently pay a dividend. "
                    "The dividend score is 0/6.", "#4a5a72"
                ), unsafe_allow_html=True)
            else:
                payout    = safe_get(info, "payoutRatio")
                ex_date   = safe_get(info, "exDividendDate")
                last_div  = safe_get(info, "lastDividendValue")
                five_yr   = safe_get(info, "fiveYearAvgDividendYield")

                st.markdown(stat_row([
                    ("Yield",        f"{div_yield*100:.2f}%", "#00d4aa"),
                    ("Annual Rate",  f"${div_rate:.2f}"       if div_rate  else "N/A"),
                    ("Payout Ratio", f"{payout*100:.0f}%"     if payout   else "N/A",
                     "#00d4aa" if payout and payout < 0.6 else
                     "#f1c14e" if payout and payout < 0.8 else "#ff4b4b"),
                    ("5Y Avg Yield", f"{five_yr:.2f}%"        if five_yr  else "N/A"),
                    ("Last Div",     f"${last_div:.4f}"       if last_div else "N/A"),
                ]), unsafe_allow_html=True)

                # Dividend history bar
                divs = market_d.get("dividends", pd.Series(dtype=float))
                if not divs.empty:
                    try:
                        annual = divs.resample("YE").sum()
                        annual = annual[annual > 0].tail(10)
                        years  = [str(d.year) for d in annual.index]
                        fig_div = go.Figure(go.Bar(
                            x=years, y=annual.values,
                            marker_color="#00d4aa",
                            text=[f"${v:.2f}" for v in annual.values],
                            textposition="outside",
                        ))
                        fig_div.add_trace(go.Scatter(
                            x=years, y=annual.values, mode="lines+markers",
                            line=dict(color="#f1c14e", width=2, dash="dot"),
                            name="Trend",
                        ))
                        fig_div.update_layout(
                            title="Annual Dividend per Share",
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#e2e8f0", showlegend=False,
                            yaxis=dict(gridcolor="#1a2332", tickprefix="$"),
                            margin=dict(l=0, r=0, t=40, b=20), height=280,
                        )
                        st.plotly_chart(fig_div, use_container_width=True)
                    except Exception:
                        pass

                # DDM sensitivity table (±1% growth / WACC grid)
                if ddm_result:
                    import numpy as np
                    st.markdown(section_header("DDM Sensitivity Table"), unsafe_allow_html=True)
                    base_g    = ddm_result["growth_rate"]
                    base_wacc = ddm_result["wacc"]
                    g_range   = [base_g - 0.01, base_g, base_g + 0.01]
                    w_range   = [base_wacc - 0.01, base_wacc, base_wacc + 0.01]
                    rows_ddm  = {}
                    for g in g_range:
                        row_data = {}
                        for w in w_range:
                            if w > g + 0.005 and div_rate:
                                fv = float(div_rate) * (1 + g) / (w - g)
                                row_data[f"WACC={w*100:.1f}%"] = f"${fv:.2f}"
                            else:
                                row_data[f"WACC={w*100:.1f}%"] = "N/A"
                        rows_ddm[f"g={g*100:.1f}%"] = row_data
                    st.dataframe(pd.DataFrame(rows_ddm).T, use_container_width=True)

            # Dividend signals
            st.markdown(section_header("Dividend Signals"), unsafe_allow_html=True)
            for sig in div_sigs:
                st.markdown(check_item(sig["text"], sig["passed"]), unsafe_allow_html=True)

        except Exception as e:
            st.warning(f"Dividend error: {e}")

    # ── TAB 6: MANAGEMENT ─────────────────────────────────────────────────────
    with tabs[6]:
        try:
            # Governance risk scores
            audit_risk = safe_get(info, "auditRisk")
            board_risk = safe_get(info, "boardRisk")
            comp_risk  = safe_get(info, "compensationRisk")
            sh_rights  = safe_get(info, "shareHolderRightsRisk")
            overall_gr = safe_get(info, "overallRisk")

            gov_items = [
                ("Audit Risk",            audit_risk),
                ("Board Risk",            board_risk),
                ("Compensation Risk",     comp_risk),
                ("Shareholder Rights",    sh_rights),
                ("Overall Governance",    overall_gr),
            ]
            has_gov = any(v is not None for _, v in gov_items)
            if has_gov:
                st.markdown(section_header("Governance Risk (1=Low, 10=High)"),
                            unsafe_allow_html=True)
                g_labels = [l for l, v in gov_items if v is not None]
                g_values = [float(v) for _, v in gov_items if v is not None]
                g_colors = ["#ff4b4b" if v >= 7 else "#f1c14e" if v >= 4 else "#00d4aa"
                            for v in g_values]
                fig_gov = go.Figure(go.Bar(
                    x=g_values, y=g_labels, orientation="h",
                    marker_color=g_colors,
                    text=[str(int(v)) for v in g_values], textposition="outside",
                ))
                fig_gov.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#e2e8f0", showlegend=False,
                    xaxis=dict(range=[0, 11], gridcolor="#1a2332"),
                    yaxis=dict(gridcolor="rgba(0,0,0,0)"),
                    margin=dict(l=0, r=0, t=10, b=20), height=200,
                )
                st.plotly_chart(fig_gov, use_container_width=True)
            else:
                st.markdown(info_banner("Governance risk scores not available.", "#4a5a72"),
                            unsafe_allow_html=True)

            # Insider transactions
            ins_tx = holders.get("insider_tx", pd.DataFrame())

            # Merge with FMP insider data if available
            fmp_ins = fmp_data.get("insider_trading", [])
            if fmp_ins:
                try:
                    fmp_df = pd.DataFrame(fmp_ins)[
                        ["reportingName", "transactionType", "securitiesTransacted",
                         "price", "transactionDate"]
                    ].rename(columns={
                        "reportingName":       "Name",
                        "transactionType":     "Transaction",
                        "securitiesTransacted":"Shares",
                        "price":               "Price",
                        "transactionDate":     "Date",
                    })
                    ins_tx = fmp_df
                except Exception:
                    pass

            if not ins_tx.empty:
                st.markdown(section_header("Insider Transactions"), unsafe_allow_html=True)
                st.dataframe(ins_tx.head(15), use_container_width=True, hide_index=True)

                # Buy/sell donut
                try:
                    tx_col = None
                    for col in ["Transaction", "Transaction Type", "Relationship"]:
                        if col in ins_tx.columns:
                            tx_col = col
                            break
                    if tx_col:
                        buys  = ins_tx[ins_tx[tx_col].str.contains("Buy|Purchase|S-1", case=False, na=False)].shape[0]
                        sells = ins_tx[ins_tx[tx_col].str.contains("Sell|Sale|S-1 K", case=False, na=False)].shape[0]
                        if buys + sells > 0:
                            fig_ins = go.Figure(go.Pie(
                                labels=["Buys", "Sells"],
                                values=[buys, sells],
                                marker_colors=["#00d4aa", "#ff4b4b"],
                                hole=0.5,
                            ))
                            fig_ins.update_layout(
                                paper_bgcolor="rgba(0,0,0,0)", font_color="#e2e8f0",
                                showlegend=True, legend=dict(bgcolor="rgba(0,0,0,0)"),
                                margin=dict(l=20, r=20, t=20, b=20), height=220,
                            )
                            st.plotly_chart(fig_ins, use_container_width=True)
                except Exception:
                    pass
            else:
                st.markdown(info_banner("Insider transaction data not available.", "#4a5a72"),
                            unsafe_allow_html=True)

            # Analyst recommendation trend
            recs = market_d.get("recommendations", pd.DataFrame())
            if not recs.empty:
                st.markdown(section_header("Analyst Recommendation Trend"), unsafe_allow_html=True)
                try:
                    recs2 = recs.copy()
                    if "period" in recs2.columns:
                        recs2 = recs2.set_index("period")
                    grade_cols = [c for c in recs2.columns if c in
                                  ["strongBuy","buy","hold","sell","strongSell"]]
                    if grade_cols:
                        fig_rec = go.Figure()
                        colors  = {"strongBuy":"#00d4aa","buy":"#00b894","hold":"#f1c14e",
                                   "sell":"#e17055","strongSell":"#ff4b4b"}
                        for gc in grade_cols:
                            fig_rec.add_trace(go.Bar(
                                name=gc, x=recs2.index,
                                y=recs2[gc].values,
                                marker_color=colors.get(gc, "#4a5a72"),
                            ))
                        fig_rec.update_layout(
                            barmode="stack",
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#e2e8f0", legend=dict(bgcolor="rgba(0,0,0,0)"),
                            yaxis=dict(gridcolor="#1a2332"),
                            margin=dict(l=0, r=0, t=10, b=20), height=250,
                        )
                        st.plotly_chart(fig_rec, use_container_width=True)
                except Exception:
                    pass

        except Exception as e:
            st.warning(f"Management error: {e}")

    # ── TAB 7: OWNERSHIP ──────────────────────────────────────────────────────
    with tabs[7]:
        try:
            inst = holders.get("institutional", pd.DataFrame())
            major = holders.get("major", pd.DataFrame())

            # Short interest
            short_pct = safe_get(info, "shortPercentOfFloat")
            short_str = f"{short_pct*100:.1f}%" if short_pct else "N/A"
            inst_pct  = safe_get(info, "heldPercentInstitutions")
            inside_pct = safe_get(info, "heldPercentInsiders")

            st.markdown(stat_row([
                ("Institutional %", f"{inst_pct*100:.1f}%"  if inst_pct   else "N/A"),
                ("Insider %",       f"{inside_pct*100:.1f}%" if inside_pct else "N/A"),
                ("Short Float %",   short_str,
                 "#ff4b4b" if short_pct and short_pct > 0.15 else
                 "#f1c14e" if short_pct and short_pct > 0.05 else "#00d4aa"),
            ]), unsafe_allow_html=True)

            # Major holders
            if not major.empty:
                st.markdown(section_header("Major Holders"), unsafe_allow_html=True)
                st.dataframe(major, use_container_width=True, hide_index=True)

            # Institutional holders
            if not inst.empty:
                col_a, col_b = st.columns([1.2, 1], gap="medium")
                with col_a:
                    st.markdown(section_header("Top Institutional Holders"), unsafe_allow_html=True)
                    disp_cols = [c for c in ["Holder", "Shares", "% Out", "Value"]
                                 if c in inst.columns]
                    if disp_cols:
                        st.dataframe(inst[disp_cols].head(15), use_container_width=True,
                                     hide_index=True)
                    else:
                        st.dataframe(inst.head(15), use_container_width=True, hide_index=True)

                with col_b:
                    # Top 10 horizontal bar
                    try:
                        bar_df = inst.head(10)
                        h_col  = next((c for c in ["Holder","Name"] if c in bar_df.columns), None)
                        s_col  = next((c for c in ["Shares","% Out"] if c in bar_df.columns), None)
                        if h_col and s_col:
                            fig_inst = go.Figure(go.Bar(
                                y=bar_df[h_col].str[:25],
                                x=bar_df[s_col],
                                orientation="h",
                                marker_color="#4e9af1",
                            ))
                            fig_inst.update_layout(
                                title="Top 10 Institutions",
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                font_color="#e2e8f0", showlegend=False,
                                yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"),
                                xaxis=dict(gridcolor="#1a2332"),
                                margin=dict(l=0, r=0, t=40, b=20), height=350,
                            )
                            st.plotly_chart(fig_inst, use_container_width=True)
                    except Exception:
                        pass

                # Pie: top 5 institutional + "Other"
                try:
                    s_col2 = next((c for c in ["Shares","Value"] if c in inst.columns), None)
                    h_col2 = next((c for c in ["Holder","Name"] if c in inst.columns), None)
                    if s_col2 and h_col2:
                        top5   = inst.head(5)
                        others = inst.iloc[5:][s_col2].sum() if len(inst) > 5 else 0
                        pie_labels = list(top5[h_col2].str[:20]) + (["Others"] if others else [])
                        pie_vals   = list(top5[s_col2]) + ([others] if others else [])
                        fig_pie = go.Figure(go.Pie(
                            labels=pie_labels, values=pie_vals, hole=0.45,
                            textfont=dict(size=10),
                        ))
                        fig_pie.update_layout(
                            title="Institutional Ownership Distribution",
                            paper_bgcolor="rgba(0,0,0,0)", font_color="#e2e8f0",
                            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
                            margin=dict(l=0, r=0, t=40, b=20), height=300,
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)
                except Exception:
                    pass
            else:
                st.markdown(info_banner("Institutional holder data not available.", "#4a5a72"),
                            unsafe_allow_html=True)

        except Exception as e:
            st.warning(f"Ownership error: {e}")

# ── Candlestick (legacy) in expander ─────────────────────────────────────────

with st.expander("Candlestick Chart", expanded=False):
    @st.cache_data(ttl=3600)
    def _chart_data(sym, period):
        df = yf.download(sym, period=period, auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df

    df = _chart_data(selected_sym, chart_period)
    if df.empty:
        st.error(f"No data for {selected_sym}")
    else:
        price_indicators = {}
        if show_sma20:  price_indicators["SMA 20"]  = sma(df["Close"], 20)
        if show_sma50:  price_indicators["SMA 50"]  = sma(df["Close"], 50)
        if show_sma200: price_indicators["SMA 200"] = sma(df["Close"], 200)
        if show_ema:    price_indicators["EMA 20"]  = ema(df["Close"], 20)
        if show_bb:
            upper, middle, lower = bollinger_bands(df["Close"])
            price_indicators.update({"BB Upper": upper, "BB Middle": middle, "BB Lower": lower})
        rsi_indicators = {"RSI 14": rsi(df["Close"])} if show_rsi else {}
        all_indicators = {**price_indicators, **rsi_indicators}
        fig = candlestick_with_indicators(df, all_indicators,
                                          title=f"{selected_sym} — {chart_period}")
        st.plotly_chart(fig, use_container_width=True)

        if show_macd:
            macd_line, signal_line, histogram = macd(df["Close"])
            fig_macd = make_subplots(rows=1, cols=1)
            colors = ["#00d4aa" if v >= 0 else "#ff4b4b" for v in histogram]
            fig_macd.add_trace(go.Bar(x=df.index, y=histogram, name="Histogram",
                                      marker_color=colors))
            fig_macd.add_trace(go.Scatter(x=df.index, y=macd_line, name="MACD",
                                          line=dict(color="#4e9af1")))
            fig_macd.add_trace(go.Scatter(x=df.index, y=signal_line, name="Signal",
                                          line=dict(color="#f1c14e")))
            fig_macd.update_layout(
                title=f"{selected_sym} MACD",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#fafafa",
                xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_macd, use_container_width=True)
