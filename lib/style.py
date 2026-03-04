"""
Vulpen Capital — CSS + reusable HTML component helpers.
Call inject_css() at the top of every page.
"""

import streamlit as st

# ── Design tokens (Python mirrors of CSS vars) ─────────────────────────────
_BG      = "#12151e"
_SURFACE = "#1a1d27"
_BORDER  = "#252a38"
_TEXT1   = "#f0f4f8"
_TEXT2   = "#8892a4"
_ACCENT  = "#4ade80"
_POS     = "#4ade80"
_NEG     = "#f87171"
_SHADOW  = "0 1px 6px rgba(0,0,0,0.5)"
_RADIUS  = "4px"

# ── Master CSS (inline — avoids Streamlit file-path and tag-escaping issues)
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');

:root{--bg:#12151e;--surface:#1a1d27;--border:#252a38;--text-1:#f0f4f8;--text-2:#8892a4;--accent:#4ade80;--pos:#4ade80;--neg:#f87171;--radius:4px;--shadow:0 1px 6px rgba(0,0,0,0.5);}

html,body,[class*="css"],.stApp,button,input,select,textarea{font-family:'Space Grotesk',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif !important;font-size:14px;font-weight:400;color:var(--text-1);}
code,pre,kbd{font-family:'JetBrains Mono','Fira Code',monospace !important;}

#MainMenu{visibility:hidden !important;}
footer{visibility:hidden !important;}
[data-testid="stHeader"]{display:none !important;}
[data-testid="stToolbar"]{display:none !important;}
[data-testid="stDecoration"]{display:none !important;}
[data-testid="stStatusWidget"]{display:none !important;}
[data-testid="stSidebarNavItems"]{display:none !important;}
[data-testid="stSidebarNavSeparator"]{display:none !important;}
[data-testid="stSidebar"]{display:none !important;}
[data-testid="collapsedControl"]{display:none !important;}

.stApp{background:var(--bg) !important;}
.main .block-container{padding:64px 2rem 2rem 2rem !important;max-width:100% !important;}

h1{font-size:22px !important;font-weight:600 !important;color:var(--text-1) !important;letter-spacing:-0.02em !important;line-height:1.3 !important;margin-bottom:0.2rem !important;background:none !important;-webkit-background-clip:unset !important;-webkit-text-fill-color:unset !important;background-clip:unset !important;}
h2{font-size:15px !important;font-weight:600 !important;color:var(--text-1) !important;}
h3{font-size:11px !important;font-weight:500 !important;color:var(--text-2) !important;text-transform:uppercase !important;letter-spacing:0.08em !important;}
p,li{color:var(--text-2) !important;font-size:14px !important;}
strong{color:var(--text-1) !important;font-weight:600 !important;}
a{color:var(--accent) !important;text-decoration:none !important;}
code{color:var(--accent) !important;background:var(--surface) !important;border:1px solid var(--border) !important;border-radius:3px !important;padding:1px 5px !important;font-size:12px !important;}

[data-testid="stMetric"]{background:var(--surface) !important;border:1px solid var(--border) !important;border-radius:var(--radius) !important;padding:20px !important;box-shadow:var(--shadow) !important;transition:border-color 0.15s !important;}
[data-testid="stMetric"]:hover{border-color:var(--accent) !important;}
[data-testid="stMetricLabel"]>div{font-size:11px !important;font-weight:500 !important;text-transform:uppercase !important;letter-spacing:0.08em !important;color:var(--text-2) !important;}
[data-testid="stMetricValue"]>div{font-size:24px !important;font-weight:700 !important;color:var(--text-1) !important;letter-spacing:-0.02em !important;line-height:1.2 !important;}
[data-testid="stMetricDelta"]>div{font-size:12px !important;font-weight:500 !important;}

[data-testid="stVerticalBlockBorderWrapper"]{background:var(--surface) !important;border:1px solid var(--border) !important;border-radius:var(--radius) !important;box-shadow:var(--shadow) !important;}

[data-testid="stTabs"] [role="tablist"]{background:var(--surface) !important;border-radius:var(--radius) !important;padding:3px !important;border:1px solid var(--border) !important;gap:2px !important;}
[data-testid="stTabs"] [role="tab"]{font-size:13px !important;font-weight:500 !important;color:var(--text-2) !important;border-radius:3px !important;padding:5px 14px !important;border:none !important;transition:all 0.12s !important;text-decoration:none !important;}
[data-testid="stTabs"] [role="tab"]:hover{color:var(--text-1) !important;}
[data-testid="stTabs"] [role="tab"][aria-selected="true"]{background:rgba(74,222,128,0.1) !important;color:var(--accent) !important;border:1px solid rgba(74,222,128,0.2) !important;}

button[kind="primary"],[data-testid="stFormSubmitButton"]>button{background:var(--accent) !important;color:#061409 !important;border:none !important;border-radius:var(--radius) !important;font-size:13px !important;font-weight:600 !important;letter-spacing:0.02em !important;transition:opacity 0.12s !important;}
button[kind="primary"]:hover,[data-testid="stFormSubmitButton"]>button:hover{opacity:0.85 !important;}
button[kind="secondary"]{background:transparent !important;color:var(--accent) !important;border:1px solid rgba(74,222,128,0.3) !important;border-radius:var(--radius) !important;font-size:13px !important;font-weight:500 !important;transition:all 0.12s !important;}
button[kind="secondary"]:hover{background:rgba(74,222,128,0.07) !important;border-color:var(--accent) !important;}

[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,[data-testid="stTextArea"] textarea{background:var(--bg) !important;border:1px solid var(--border) !important;border-radius:var(--radius) !important;color:var(--text-1) !important;font-size:14px !important;}
[data-testid="stTextInput"] input:focus,[data-testid="stNumberInput"] input:focus,[data-testid="stTextArea"] textarea:focus{border-color:var(--accent) !important;box-shadow:0 0 0 2px rgba(74,222,128,0.1) !important;outline:none !important;}
[data-testid="stSelectbox"]>div>div,[data-testid="stMultiSelect"]>div>div{background:var(--bg) !important;border-color:var(--border) !important;border-radius:var(--radius) !important;color:var(--text-1) !important;font-size:14px !important;}

[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"]{background:var(--accent) !important;border-color:var(--accent) !important;}
[data-testid="stSlider"] div[data-baseweb="slider"]>div:first-child>div:last-child{background:var(--accent) !important;}

[data-testid="stExpander"]{background:var(--surface) !important;border:1px solid var(--border) !important;border-radius:var(--radius) !important;box-shadow:var(--shadow) !important;}
[data-testid="stExpander"] summary{font-size:14px !important;font-weight:500 !important;color:var(--text-2) !important;}

[data-testid="stProgressBar"]>div>div{background:var(--accent) !important;}

hr{border:none !important;border-top:1px solid var(--border) !important;margin:1.25rem 0 !important;}

[data-testid="stAlert"]{border-radius:var(--radius) !important;}
.stAlert [data-testid="stMarkdownContainer"] p{color:inherit !important;}

[data-testid="stDataFrame"]{background:var(--surface) !important;border:1px solid var(--border) !important;border-radius:var(--radius) !important;overflow:hidden !important;box-shadow:var(--shadow) !important;}
[data-testid="stDataFrame"] th,[data-testid="stDataFrame"] [role="columnheader"]{background:var(--surface) !important;color:var(--text-2) !important;font-size:11px !important;font-weight:500 !important;text-transform:uppercase !important;letter-spacing:0.08em !important;border-bottom:1px solid var(--border) !important;}
[data-testid="stDataFrame"] tr:nth-child(odd) td{background:var(--surface) !important;}
[data-testid="stDataFrame"] tr:nth-child(even) td{background:#1f2233 !important;}
[data-testid="stDataFrame"] tr:hover td{background:rgba(74,222,128,0.04) !important;}
[data-testid="stDataFrame"] td,[data-testid="stDataFrame"] [role="gridcell"]{color:var(--text-1) !important;font-size:13px !important;border-bottom:1px solid var(--border) !important;}

[data-testid="stSpinner"]>div>div{border-top-color:var(--accent) !important;}

::-webkit-scrollbar{width:4px;height:4px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px;}
::-webkit-scrollbar-thumb:hover{background:rgba(74,222,128,0.35);}

[data-testid="stCaptionContainer"]{color:var(--text-2) !important;font-size:12px !important;}

[data-testid="stRadio"] label,[data-testid="stCheckbox"] label{font-size:14px !important;color:var(--text-2) !important;}
[data-testid="stRadio"] label:hover,[data-testid="stCheckbox"] label:hover{color:var(--text-1) !important;}

.js-plotly-plot .plotly{background:transparent !important;}
.svg-container{background:transparent !important;}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ── HTML component helpers ─────────────────────────────────────────────────

def kpi_card(label: str, value: str, delta: str = None,
             positive: bool = None, icon: str = "", accent: str = _ACCENT) -> str:
    delta_html = ""
    if delta is not None:
        color = (_POS if positive else _NEG) if positive is not None else _TEXT2
        delta_html = (
            f'<div style="color:{color};font-size:12px;font-weight:500;margin-top:6px">'
            f'{delta}</div>'
        )
    return (
        f'<div style="background:{_SURFACE};border:1px solid {_BORDER};border-radius:{_RADIUS};'
        f'padding:20px;box-shadow:{_SHADOW};position:relative;overflow:hidden">'
        f'<div style="position:absolute;top:0;left:0;right:0;height:2px;'
        f'background:linear-gradient(90deg,{accent}80,transparent)"></div>'
        f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:{_TEXT2};margin-bottom:8px">{label}</div>'
        f'<div style="font-size:24px;font-weight:700;color:{_TEXT1};'
        f'letter-spacing:-0.02em;line-height:1.2">{value}</div>'
        f'{delta_html}</div>'
    )


def signal_badge(signal: str) -> str:
    cfg = {
        "NEW BUY":  (_POS,   "rgba(74,222,128,0.12)",  "NEW BUY"),
        "BUY":      (_POS,   "rgba(74,222,128,0.08)",  "BUY"),
        "NEW SELL": (_NEG,   "rgba(248,113,113,0.12)", "NEW SELL"),
        "SELL":     (_NEG,   "rgba(248,113,113,0.08)", "SELL"),
        "NEUTRAL":  (_TEXT2, "rgba(136,146,164,0.08)", "NEUTRAL"),
    }
    color, bg, lbl = cfg.get(signal, (_TEXT2, "rgba(136,146,164,0.08)", signal))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}40;'
        f'border-radius:6px;padding:3px 10px;font-size:11px;'
        f'font-weight:600;letter-spacing:0.06em;white-space:nowrap">{lbl}</span>'
    )


def section_header(title: str, subtitle: str = "") -> str:
    sub = (f'<div style="color:{_TEXT2};font-size:13px;margin-top:2px">{subtitle}</div>'
           if subtitle else "")
    return (
        f'<div style="margin:0.5rem 0 1rem 0;padding-bottom:12px;border-bottom:1px solid {_BORDER}">'
        f'<div style="font-size:15px;font-weight:600;color:{_TEXT1}">{title}</div>'
        f'{sub}</div>'
    )


def info_banner(text: str, color: str = _ACCENT) -> str:
    return (
        f'<div style="background:{color}14;border:1px solid {color}30;border-left:3px solid {color};'
        f'border-radius:{_RADIUS};padding:10px 16px;font-size:13px;color:{color};margin:0.5rem 0">'
        f'{text}</div>'
    )


def stat_row(items: list) -> str:
    cells = "".join(
        f'<div style="text-align:center;padding:0 20px;border-right:1px solid {_BORDER}">'
        f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:{_TEXT2};margin-bottom:4px">{item[0]}</div>'
        f'<div style="font-size:16px;font-weight:700;color:{item[2] if len(item)>2 else _TEXT1}">'
        f'{item[1]}</div></div>'
        for item in items
    )
    return (
        f'<div style="display:flex;background:{_SURFACE};border:1px solid {_BORDER};'
        f'border-radius:{_RADIUS};padding:16px 0;box-shadow:{_SHADOW};margin:0.5rem 0">'
        f'{cells}</div>'
    )


def company_card_header(
    ticker: str, name: str, sector: str, industry: str,
    employees, market_cap_str: str,
    price, change_pct, accent: str = _ACCENT,
) -> str:
    chg_color = _POS if (change_pct or 0) >= 0 else _NEG
    sign      = "+" if (change_pct or 0) >= 0 else ""
    emp_str   = f"{int(employees):,}" if employees else "N/A"
    chg_str   = f"{sign}{change_pct:.2f}%" if change_pct is not None else "N/A"
    price_str = f"${float(price):.2f}" if price else "N/A"
    return (
        f'<div style="background:{_SURFACE};border:1px solid {_BORDER};border-radius:{_RADIUS};'
        f'padding:20px;box-shadow:{_SHADOW};position:relative;overflow:hidden;margin-bottom:16px">'
        f'<div style="position:absolute;top:0;left:0;right:0;height:2px;'
        f'background:linear-gradient(90deg,{accent},transparent)"></div>'
        f'<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px">'
        f'<div>'
        f'<div style="font-size:22px;font-weight:700;color:{_TEXT1};letter-spacing:-0.02em">{ticker}</div>'
        f'<div style="font-size:13px;color:{_TEXT2};margin-top:4px;line-height:1.4">{name}</div>'
        f'</div>'
        f'<div style="text-align:right;flex-shrink:0">'
        f'<div style="font-size:22px;font-weight:700;color:{_TEXT1}">{price_str}</div>'
        f'<div style="font-size:13px;font-weight:500;color:{chg_color}">{chg_str}</div>'
        f'</div></div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:12px">'
        f'<span style="background:{accent}18;color:{accent};border:1px solid {accent}30;'
        f'border-radius:20px;padding:3px 10px;font-size:11px;font-weight:500">{sector}</span>'
        f'<span style="background:{_BORDER}40;color:{_TEXT2};border:1px solid {_BORDER};'
        f'border-radius:20px;padding:3px 10px;font-size:11px">{industry}</span>'
        f'</div>'
        f'<div style="display:flex;gap:20px;margin-top:12px;font-size:12px;color:{_TEXT2}">'
        f'<span>Market Cap <strong style="color:{_TEXT1}">{market_cap_str}</strong></span>'
        f'<span>Employees <strong style="color:{_TEXT1}">{emp_str}</strong></span>'
        f'</div></div>'
    )


def score_bar(label: str, score: float, max_score: float = 6.0, color: str = None) -> str:
    pct = min(100.0, max(0.0, score / max_score * 100))
    if color is None:
        color = _NEG if score < 2 else "#f0b429" if score < 3.5 else _POS
    return (
        f'<div style="margin:8px 0">'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:5px">'
        f'<span style="font-size:11px;font-weight:500;color:{_TEXT2};'
        f'text-transform:uppercase;letter-spacing:0.08em">{label}</span>'
        f'<span style="font-size:12px;font-weight:600;color:{color}">{score:.1f}/{max_score:.0f}</span>'
        f'</div>'
        f'<div style="background:{_BORDER};border-radius:4px;height:5px;overflow:hidden">'
        f'<div style="width:{pct:.1f}%;height:100%;background:{color};border-radius:4px"></div>'
        f'</div></div>'
    )


def check_item(text: str, passed, detail: str = "") -> str:
    if passed is True:
        icon, color = "&#10003;", _POS
    elif passed is False:
        icon, color = "&#10007;", _NEG
    else:
        icon, color = "&mdash;", _TEXT2
    det = (f'<span style="color:{_TEXT2};font-size:11px;margin-left:6px">{detail}</span>'
           if detail else "")
    return (
        f'<div style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;'
        f'border-bottom:1px solid {_BORDER}">'
        f'<span style="color:{color};font-weight:600;font-size:13px;flex-shrink:0;'
        f'width:16px;text-align:center">{icon}</span>'
        f'<span style="color:{_TEXT2};font-size:13px;line-height:1.5">{text}{det}</span>'
        f'</div>'
    )


def analyst_badge(recommendation_key: str) -> str:
    cfg = {
        "strong_buy":  (_POS,   "rgba(74,222,128,0.12)",  "Strong Buy"),
        "buy":         (_POS,   "rgba(74,222,128,0.08)",  "Buy"),
        "hold":        ("#f0b429", "rgba(240,180,41,0.10)", "Hold"),
        "sell":        (_NEG,   "rgba(248,113,113,0.10)", "Sell"),
        "strong_sell": (_NEG,   "rgba(248,113,113,0.14)", "Strong Sell"),
    }
    color, bg, lbl = cfg.get(recommendation_key, (_TEXT2, "rgba(136,146,164,0.1)", "N/A"))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}40;'
        f'border-radius:{_RADIUS};padding:4px 14px;font-size:13px;font-weight:600;'
        f'letter-spacing:0.02em;white-space:nowrap">{lbl}</span>'
    )


def valuation_model_card(
    model_name: str, fair_value, current_price,
    upside_pct, methodology_note: str, accent: str = _ACCENT,
) -> str:
    if fair_value is None or current_price is None:
        return (
            f'<div style="background:{_SURFACE};border:1px solid {_BORDER};'
            f'border-radius:{_RADIUS};padding:20px;box-shadow:{_SHADOW};text-align:center;height:100%">'
            f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
            f'letter-spacing:0.08em;color:{_TEXT2};margin-bottom:8px">{model_name}</div>'
            f'<div style="font-size:22px;font-weight:700;color:{_TEXT2}">N/A</div>'
            f'<div style="font-size:11px;color:{_TEXT2};margin-top:6px;line-height:1.4">'
            f'{methodology_note}</div></div>'
        )
    up_color = _POS if (upside_pct or 0) >= 0 else _NEG
    sign     = "+" if (upside_pct or 0) >= 0 else ""
    up_str   = f"{sign}{upside_pct:.1f}%" if upside_pct is not None else "N/A"
    fv_str   = f"${float(fair_value):.2f}"
    return (
        f'<div style="background:{_SURFACE};border:1px solid {_BORDER};'
        f'border-radius:{_RADIUS};padding:20px;box-shadow:{_SHADOW};'
        f'position:relative;overflow:hidden;height:100%">'
        f'<div style="position:absolute;top:0;left:0;right:0;height:2px;'
        f'background:linear-gradient(90deg,{accent}60,transparent)"></div>'
        f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:{_TEXT2};margin-bottom:6px">{model_name}</div>'
        f'<div style="font-size:24px;font-weight:700;color:{_TEXT1};'
        f'letter-spacing:-0.02em">{fv_str}</div>'
        f'<div style="font-size:14px;font-weight:600;color:{up_color};margin-top:2px">{up_str}</div>'
        f'<div style="font-size:11px;color:{_TEXT2};margin-top:8px;line-height:1.4">'
        f'{methodology_note}</div></div>'
    )
