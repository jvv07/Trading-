"""
Premium dark-terminal CSS + reusable HTML component helpers.
Call inject_css() at the top of every page.
"""

import streamlit as st


def inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)
    # Custom sidebar logo injected once per session
    if "sidebar_logo_injected" not in st.session_state:
        st.session_state.sidebar_logo_injected = True
        st.sidebar.markdown(_SIDEBAR_LOGO, unsafe_allow_html=True)


# ── HTML component helpers ─────────────────────────────────────────────────

def kpi_card(label: str, value: str, delta: str = None,
             positive: bool = None, icon: str = "", accent: str = "#00d4aa") -> str:
    delta_html = ""
    if delta is not None:
        color = ("#00d4aa" if positive else "#ff4b4b") if positive is not None else "#8892a4"
        arrow = "▲" if positive else "▼" if positive is not None else "◆"
        delta_html = f'<div style="color:{color};font-size:.78rem;font-weight:600;margin-top:4px">{arrow} {delta}</div>'

    return f"""
<div style="
    background:linear-gradient(135deg,#0d1422 0%,#0a1020 100%);
    border:1px solid #1a2332;border-radius:14px;padding:20px 24px;
    position:relative;overflow:hidden;transition:border-color .2s;
">
  <div style="position:absolute;top:0;left:0;right:0;height:2px;
              background:linear-gradient(90deg,{accent},transparent)"></div>
  <div style="color:#4a5a72;font-size:.68rem;font-weight:700;
              letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px">{icon} {label}</div>
  <div style="color:#e2e8f0;font-size:1.7rem;font-weight:700;
              letter-spacing:-.02em;line-height:1">{value}</div>
  {delta_html}
</div>"""


def signal_badge(signal: str) -> str:
    cfg = {
        "NEW BUY":  ("#00ff99", "#003322", "▲ NEW BUY"),
        "BUY":      ("#00d4aa", "#002a22", "▲ BUY"),
        "NEW SELL": ("#ff6b6b", "#330011", "▼ NEW SELL"),
        "SELL":     ("#ff4b4b", "#2a0010", "▼ SELL"),
        "NEUTRAL":  ("#6b7a99", "#1a1f2e", "● NEUTRAL"),
    }
    color, bg, label = cfg.get(signal, ("#6b7a99", "#1a1f2e", signal))
    return f"""<span style="
        background:{bg};color:{color};border:1px solid {color}40;
        border-radius:6px;padding:3px 10px;font-size:.72rem;
        font-weight:700;letter-spacing:.06em;white-space:nowrap">{label}</span>"""


def section_header(title: str, subtitle: str = "") -> str:
    sub = f'<div style="color:#4a5a72;font-size:.82rem;margin-top:2px">{subtitle}</div>' if subtitle else ""
    return f"""
<div style="margin:0.5rem 0 1.2rem 0;padding-bottom:12px;border-bottom:1px solid #1a2332">
  <div style="font-size:1.05rem;font-weight:700;color:#c8d0e0;
              letter-spacing:-.01em">{title}</div>
  {sub}
</div>"""


def info_banner(text: str, color: str = "#00d4aa") -> str:
    return f"""
<div style="background:{color}12;border:1px solid {color}30;border-left:3px solid {color};
            border-radius:8px;padding:10px 16px;font-size:.85rem;color:{color};margin:.5rem 0">
  {text}
</div>"""


def stat_row(items: list) -> str:
    """items = list of (label, value, color_optional)"""
    cells = ""
    for item in items:
        label, value = item[0], item[1]
        color = item[2] if len(item) > 2 else "#e2e8f0"
        cells += f"""
        <div style="text-align:center;padding:0 16px;border-right:1px solid #1a2332">
          <div style="color:#4a5a72;font-size:.68rem;font-weight:700;
                      text-transform:uppercase;letter-spacing:.08em">{label}</div>
          <div style="color:{color};font-size:1.1rem;font-weight:700;margin-top:2px">{value}</div>
        </div>"""
    return f"""
<div style="display:flex;background:#0d1422;border:1px solid #1a2332;
            border-radius:10px;padding:14px 0;margin:.5rem 0">
  {cells}
</div>"""


# ── Sidebar logo ───────────────────────────────────────────────────────────

_SIDEBAR_LOGO = """
<div style="
    padding: 0 8px 20px 8px;
    border-bottom: 1px solid #1a2332;
    margin-bottom: 12px;
">
  <div style="
    font-size: 1.25rem;
    font-weight: 900;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, #ffffff 30%, #00d4aa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.2;
  ">⟨ QUANTEDGE ⟩</div>
  <div style="color:#2a3a52;font-size:.68rem;font-weight:600;
              letter-spacing:.15em;text-transform:uppercase;margin-top:2px">
    TRADING DASHBOARD
  </div>
</div>
"""

# ── Master CSS ─────────────────────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Global ── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}
code, pre, kbd { font-family: 'JetBrains Mono', monospace !important; }

/* ── Chrome removal ── */
#MainMenu { visibility: hidden !important; }
footer    { visibility: hidden !important; }
/* Keep header present so sidebar toggle stays accessible when sidebar is closed */
[data-testid="stHeader"] {
    background: #080c14 !important;
    border-bottom: 1px solid #131c2e !important;
}
/* Hide decorative/status chrome inside the header */
[data-testid="stToolbar"]      { display: none !important; }
[data-testid="stDecoration"]   { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }

/* ── App background ── */
.stApp { background: #080c14 !important; }
.main .block-container {
    padding: 1.5rem 2rem 2rem 2rem !important;
    max-width: 100% !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0e1a 0%, #080c14 100%) !important;
    border-right: 1px solid #131c2e !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 1rem !important; }

/* Nav links */
[data-testid="stSidebarNavLink"] {
    border-radius: 8px !important;
    margin: 1px 8px !important;
    padding: 8px 14px !important;
    font-size: .865rem !important;
    font-weight: 500 !important;
    color: #4a5a72 !important;
    border-left: 3px solid transparent !important;
    transition: all .15s ease !important;
    background: transparent !important;
}
[data-testid="stSidebarNavLink"]:hover {
    color: #c8d0e0 !important;
    background: rgba(255,255,255,.04) !important;
    border-left-color: #2a3a52 !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    color: #00d4aa !important;
    background: linear-gradient(90deg,rgba(0,212,170,.12) 0%,rgba(0,212,170,.02) 100%) !important;
    border-left-color: #00d4aa !important;
    font-weight: 600 !important;
}

/* ── Typography ── */
h1 {
    background: linear-gradient(135deg, #ffffff 20%, #00d4aa 100%);
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    font-weight: 800 !important;
    letter-spacing: -.03em !important;
    font-size: 1.9rem !important;
    line-height: 1.15 !important;
    margin-bottom: .15rem !important;
}
h2 {
    color: #c8d0e0 !important;
    font-weight: 700 !important;
    letter-spacing: -.02em !important;
    font-size: 1.2rem !important;
}
h3 {
    color: #4a5a72 !important;
    font-weight: 700 !important;
    font-size: .72rem !important;
    text-transform: uppercase !important;
    letter-spacing: .1em !important;
}
p, li { color: #8892a4 !important; }
strong { color: #c8d0e0 !important; }
code { color: #00d4aa !important; background: #0d1422 !important; border-radius: 4px !important; padding: 1px 5px !important; }

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #0d1422 0%, #0a1020 100%) !important;
    border: 1px solid #1a2332 !important;
    border-radius: 14px !important;
    padding: 1.2rem 1.4rem !important;
    transition: border-color .2s !important;
    position: relative !important;
    overflow: hidden !important;
}
[data-testid="stMetric"]::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #00d4aa40, transparent);
}
[data-testid="stMetric"]:hover { border-color: #00d4aa40 !important; }
[data-testid="stMetricLabel"] > div {
    font-size: .68rem !important; font-weight: 700 !important;
    letter-spacing: .1em !important; text-transform: uppercase !important;
    color: #3a4a62 !important;
}
[data-testid="stMetricValue"] > div {
    font-size: 1.65rem !important; font-weight: 700 !important;
    color: #e2e8f0 !important; letter-spacing: -.02em !important;
}
[data-testid="stMetricDelta"] > div { font-size: .78rem !important; font-weight: 600 !important; }

/* ── Containers ── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: linear-gradient(135deg, #0d1422 0%, #0a1020 100%) !important;
    border: 1px solid #1a2332 !important;
    border-radius: 14px !important;
    transition: border-color .2s !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover { border-color: #1e2d42 !important; }

/* ── Tabs ── */
[data-testid="stTabs"] [role="tablist"] {
    background: #0a0f1e !important;
    border-radius: 10px !important;
    padding: 4px !important;
    border: 1px solid #1a2332 !important;
    gap: 2px !important;
}
[data-testid="stTabs"] [role="tab"] {
    border-radius: 7px !important; font-weight: 500 !important;
    font-size: .83rem !important; color: #3a4a62 !important;
    padding: 6px 18px !important; transition: all .15s !important; border: none !important;
}
[data-testid="stTabs"] [role="tab"]:hover { color: #c8d0e0 !important; background: rgba(255,255,255,.04) !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, rgba(0,212,170,.15), rgba(0,212,170,.05)) !important;
    color: #00d4aa !important; border: 1px solid rgba(0,212,170,.2) !important;
}

/* ── Buttons ── */
button[kind="primary"], [data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #00d4aa 0%, #00a882 100%) !important;
    color: #060a10 !important; border: none !important; border-radius: 8px !important;
    font-weight: 700 !important; font-size: .875rem !important;
    letter-spacing: .02em !important; transition: all .2s !important;
    box-shadow: 0 2px 12px rgba(0,212,170,.2) !important;
}
button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 24px rgba(0,212,170,.4) !important;
}
button[kind="secondary"] {
    background: transparent !important; color: #00d4aa !important;
    border: 1px solid rgba(0,212,170,.3) !important; border-radius: 8px !important;
    font-weight: 600 !important; transition: all .2s !important;
}
button[kind="secondary"]:hover {
    background: rgba(0,212,170,.08) !important; border-color: #00d4aa !important;
}

/* ── Inputs ── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
    background: #0d1422 !important; border: 1px solid #1a2332 !important;
    border-radius: 8px !important; color: #e2e8f0 !important;
    font-size: .9rem !important; transition: border-color .15s !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: rgba(0,212,170,.5) !important;
    box-shadow: 0 0 0 2px rgba(0,212,170,.1) !important; outline: none !important;
}
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
    background: #0d1422 !important; border-color: #1a2332 !important;
    border-radius: 8px !important; color: #e2e8f0 !important;
}

/* ── Slider ── */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background: #00d4aa !important; border-color: #00d4aa !important;
}
[data-testid="stSlider"] div[data-baseweb="slider"] > div:first-child > div:last-child {
    background: #00d4aa !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    background: #0d1422 !important; border: 1px solid #1a2332 !important; border-radius: 10px !important;
}
[data-testid="stExpander"] summary { font-weight: 600 !important; color: #8892a4 !important; }

/* ── Progress ── */
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #00d4aa, #00a882) !important;
}

/* ── Divider ── */
hr { border: none !important; border-top: 1px solid #131c2e !important; margin: 1.2rem 0 !important; }

/* ── Alerts ── */
[data-testid="stAlert"] { border-radius: 10px !important; }

/* ── Dataframe ── */
[data-testid="stDataFrame"] { border: 1px solid #1a2332 !important; border-radius: 10px !important; overflow: hidden !important; }

/* ── Spinner ── */
[data-testid="stSpinner"] > div > div { border-top-color: #00d4aa !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #080c14; }
::-webkit-scrollbar-thumb { background: #1a2332; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #00d4aa40; }

/* ── Caption / small text ── */
[data-testid="stCaptionContainer"] { color: #2a3a52 !important; font-size: .75rem !important; }

/* ── Info / success / warning boxes ── */
.stAlert [data-testid="stMarkdownContainer"] p { color: inherit !important; }
</style>
"""


# ── Research report HTML components ──────────────────────────────────────────

def company_card_header(
    ticker: str, name: str, sector: str, industry: str,
    employees, market_cap_str: str,
    price, change_pct, accent: str = "#00d4aa",
) -> str:
    chg_color = "#00d4aa" if (change_pct or 0) >= 0 else "#ff4b4b"
    arrow     = "▲" if (change_pct or 0) >= 0 else "▼"
    emp_str   = f"{int(employees):,}" if employees else "N/A"
    chg_str   = f"{abs(change_pct):.2f}%" if change_pct is not None else "N/A"
    price_str = f"${float(price):.2f}" if price else "N/A"
    return f"""
<div style="
    background:linear-gradient(135deg,#0d1422 0%,#0a1020 100%);
    border:1px solid #1a2332;border-radius:16px;padding:20px 22px;
    position:relative;overflow:hidden;margin-bottom:16px;
">
  <div style="position:absolute;top:0;left:0;right:0;height:3px;
              background:linear-gradient(90deg,{accent},transparent)"></div>
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px">
    <div>
      <div style="font-size:1.6rem;font-weight:900;color:#e2e8f0;
                  letter-spacing:-.03em;line-height:1">{ticker}</div>
      <div style="font-size:.82rem;color:#8892a4;margin-top:4px;
                  max-width:220px;line-height:1.3">{name}</div>
    </div>
    <div style="text-align:right;flex-shrink:0">
      <div style="font-size:1.5rem;font-weight:700;color:#e2e8f0">{price_str}</div>
      <div style="font-size:.82rem;font-weight:600;color:{chg_color}">{arrow} {chg_str}</div>
    </div>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:12px">
    <span style="background:{accent}18;color:{accent};border:1px solid {accent}30;
                 border-radius:12px;padding:3px 10px;font-size:.7rem;font-weight:600">{sector}</span>
    <span style="background:#1a2332;color:#8892a4;border:1px solid #2a3a52;
                 border-radius:12px;padding:3px 10px;font-size:.7rem">{industry}</span>
  </div>
  <div style="display:flex;gap:16px;margin-top:12px;color:#4a5a72;font-size:.72rem">
    <span>Mkt Cap <strong style="color:#c8d0e0">{market_cap_str}</strong></span>
    <span>Employees <strong style="color:#c8d0e0">{emp_str}</strong></span>
  </div>
</div>"""


def score_bar(label: str, score: float, max_score: float = 6.0, color: str = None) -> str:
    pct = min(100.0, max(0.0, (score / max_score) * 100))
    if color is None:
        color = "#ff4b4b" if score < 2 else "#f1c14e" if score < 3.5 else "#00d4aa"
    return f"""
<div style="margin:6px 0">
  <div style="display:flex;justify-content:space-between;margin-bottom:4px">
    <span style="font-size:.75rem;font-weight:600;color:#8892a4;
                 text-transform:uppercase;letter-spacing:.06em">{label}</span>
    <span style="font-size:.75rem;font-weight:700;color:{color}">{score:.1f}/{max_score:.0f}</span>
  </div>
  <div style="background:#1a2332;border-radius:6px;height:7px;overflow:hidden">
    <div style="width:{pct:.1f}%;height:100%;
                background:linear-gradient(90deg,{color},{color}aa);
                border-radius:6px;transition:width .4s ease"></div>
  </div>
</div>"""


def check_item(text: str, passed, detail: str = "") -> str:
    if passed is True:
        icon, color = "✓", "#00d4aa"
    elif passed is False:
        icon, color = "✗", "#ff4b4b"
    else:
        icon, color = "—", "#4a5a72"
    det = (f'<span style="color:#4a5a72;font-size:.7rem;margin-left:6px">{detail}</span>'
           if detail else "")
    return f"""
<div style="display:flex;align-items:flex-start;gap:8px;padding:5px 0;
            border-bottom:1px solid #0d1422">
  <span style="color:{color};font-weight:700;font-size:.85rem;flex-shrink:0;
               width:16px;text-align:center">{icon}</span>
  <span style="color:#8892a4;font-size:.8rem;line-height:1.4">{text}{det}</span>
</div>"""


def analyst_badge(recommendation_key: str) -> str:
    cfg = {
        "strong_buy":  ("#00d4aa", "#003322", "Strong Buy"),
        "buy":         ("#00b894", "#002a1e", "Buy"),
        "hold":        ("#f1c14e", "#2a2000", "Hold"),
        "sell":        ("#e17055", "#2a1000", "Sell"),
        "strong_sell": ("#ff4b4b", "#2a0010", "Strong Sell"),
    }
    color, bg, label = cfg.get(recommendation_key, ("#4a5a72", "#1a2332", "N/A"))
    return f"""<span style="
        background:{bg};color:{color};border:1px solid {color}40;
        border-radius:8px;padding:4px 14px;font-size:.8rem;font-weight:700;
        letter-spacing:.04em;white-space:nowrap">{label}</span>"""


def valuation_model_card(
    model_name: str, fair_value, current_price,
    upside_pct, methodology_note: str, accent: str = "#00d4aa",
) -> str:
    if fair_value is None or current_price is None:
        return f"""
<div style="background:#0d1422;border:1px solid #1a2332;border-radius:12px;
            padding:16px 18px;text-align:center;height:100%">
  <div style="color:#4a5a72;font-size:.7rem;font-weight:700;
              text-transform:uppercase;letter-spacing:.08em">{model_name}</div>
  <div style="color:#2a3a52;font-size:1.4rem;font-weight:700;margin:8px 0">N/A</div>
  <div style="color:#4a5a72;font-size:.7rem">{methodology_note}</div>
</div>"""
    up_color = "#00d4aa" if (upside_pct or 0) >= 0 else "#ff4b4b"
    up_arrow = "▲" if (upside_pct or 0) >= 0 else "▼"
    up_str   = f"{up_arrow} {abs(upside_pct):.1f}%" if upside_pct is not None else "N/A"
    fv_str   = f"${float(fair_value):.2f}"
    return f"""
<div style="background:linear-gradient(135deg,#0d1422,#0a1020);
            border:1px solid #1a2332;border-radius:12px;padding:16px 18px;
            position:relative;overflow:hidden;height:100%">
  <div style="position:absolute;top:0;left:0;right:0;height:2px;
              background:linear-gradient(90deg,{accent}80,transparent)"></div>
  <div style="color:#4a5a72;font-size:.68rem;font-weight:700;
              text-transform:uppercase;letter-spacing:.08em">{model_name}</div>
  <div style="color:#e2e8f0;font-size:1.5rem;font-weight:800;
              letter-spacing:-.02em;margin:6px 0 2px">{fv_str}</div>
  <div style="color:{up_color};font-size:.88rem;font-weight:700">{up_str}</div>
  <div style="color:#4a5a72;font-size:.68rem;margin-top:8px;line-height:1.3">{methodology_note}</div>
</div>"""
