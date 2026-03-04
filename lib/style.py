"""
Premium dark-terminal CSS + reusable HTML component helpers.
Call inject_css() at the top of every page.
"""

import os
import streamlit as st

# ── CSS loader ─────────────────────────────────────────────────────────────

def inject_css():
    css_path = os.path.join(os.path.dirname(__file__), "..", "style.css")
    with open(css_path) as f:
        css = f.read()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ── Design tokens (mirror CSS :root vars for Python components) ────────────

_BG_CARD   = "#131928"
_BG_EL     = "#0f1520"
_BORDER    = "rgba(255,255,255,0.07)"
_ACCENT    = "#00e5a3"
_TEXT1     = "#eef2f7"
_TEXT2     = "#7a8fa8"
_TEXT3     = "#3a4d66"
_GREEN     = "#16c784"
_RED       = "#ea3943"


# ── HTML component helpers ─────────────────────────────────────────────────

def kpi_card(label: str, value: str, delta: str = None,
             positive: bool = None, icon: str = "", accent: str = _ACCENT) -> str:
    delta_html = ""
    if delta is not None:
        color = (_GREEN if positive else _RED) if positive is not None else _TEXT2
        arrow = "+" if positive else "-" if positive is not None else ""
        delta_html = (f'<div style="color:{color};font-size:.78rem;font-weight:600;'
                      f'margin-top:4px">{delta}</div>')

    return (
        f'<div style="background:{_BG_CARD};border:1px solid {_BORDER};border-radius:16px;'
        f'padding:20px 24px;position:relative;overflow:hidden;transition:border-color .2s,transform .2s">'
        f'<div style="position:absolute;top:0;left:0;right:0;height:2px;'
        f'background:linear-gradient(90deg,{accent},transparent)"></div>'
        f'<div style="color:{_TEXT3};font-size:.68rem;font-weight:700;'
        f'letter-spacing:.12em;text-transform:uppercase;margin-bottom:6px">{label}</div>'
        f'<div style="color:{_TEXT1};font-size:1.75rem;font-weight:800;'
        f'letter-spacing:-.03em;line-height:1">{value}</div>'
        f'{delta_html}'
        f'</div>'
    )


def signal_badge(signal: str) -> str:
    cfg = {
        "NEW BUY":  (_GREEN,  "rgba(22,199,132,.12)", "NEW BUY"),
        "BUY":      (_ACCENT, "rgba(0,229,163,.10)",  "BUY"),
        "NEW SELL": (_RED,    "rgba(234,57,67,.12)",  "NEW SELL"),
        "SELL":     (_RED,    "rgba(234,57,67,.08)",  "SELL"),
        "NEUTRAL":  (_TEXT2,  "rgba(122,143,168,.08)", "NEUTRAL"),
    }
    color, bg, label = cfg.get(signal, (_TEXT2, "rgba(122,143,168,.08)", signal))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}40;'
        f'border-radius:6px;padding:3px 10px;font-size:.72rem;'
        f'font-weight:700;letter-spacing:.06em;white-space:nowrap">{label}</span>'
    )


def section_header(title: str, subtitle: str = "") -> str:
    sub = (f'<div style="color:{_TEXT3};font-size:.82rem;margin-top:2px">{subtitle}</div>'
           if subtitle else "")
    return (
        f'<div style="margin:0.5rem 0 1.2rem 0;padding-bottom:12px;border-bottom:1px solid {_BORDER}">'
        f'<div style="font-size:1.05rem;font-weight:700;color:{_TEXT2};letter-spacing:-.01em">{title}</div>'
        f'{sub}</div>'
    )


def info_banner(text: str, color: str = _ACCENT) -> str:
    return (
        f'<div style="background:{color}10;border:1px solid {color}28;border-left:3px solid {color};'
        f'border-radius:8px;padding:10px 16px;font-size:.85rem;color:{color};margin:.5rem 0">'
        f'{text}</div>'
    )


def stat_row(items: list) -> str:
    """items = list of (label, value) or (label, value, color)"""
    cells = "".join(
        f'<div style="text-align:center;padding:0 16px;border-right:1px solid {_BORDER}">'
        f'<div style="color:{_TEXT3};font-size:.68rem;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:.1em">{item[0]}</div>'
        f'<div style="color:{item[2] if len(item) > 2 else _TEXT1};font-size:1.05rem;'
        f'font-weight:700;margin-top:3px">{item[1]}</div></div>'
        for item in items
    )
    return (
        f'<div style="display:flex;background:{_BG_CARD};border:1px solid {_BORDER};'
        f'border-radius:10px;padding:14px 0;margin:.5rem 0">{cells}</div>'
    )


# ── Research report HTML components ──────────────────────────────────────────

def company_card_header(
    ticker: str, name: str, sector: str, industry: str,
    employees, market_cap_str: str,
    price, change_pct, accent: str = _ACCENT,
) -> str:
    chg_color = _GREEN if (change_pct or 0) >= 0 else _RED
    arrow     = "+" if (change_pct or 0) >= 0 else "-"
    emp_str   = f"{int(employees):,}" if employees else "N/A"
    chg_str   = f"{abs(change_pct):.2f}%" if change_pct is not None else "N/A"
    price_str = f"${float(price):.2f}" if price else "N/A"
    return (
        f'<div style="background:{_BG_CARD};border:1px solid {_BORDER};border-radius:16px;'
        f'padding:20px 22px;position:relative;overflow:hidden;margin-bottom:16px">'
        f'<div style="position:absolute;top:0;left:0;right:0;height:3px;'
        f'background:linear-gradient(90deg,{accent},transparent)"></div>'
        f'<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px">'
        f'<div>'
        f'<div style="font-size:1.6rem;font-weight:900;color:{_TEXT1};'
        f'letter-spacing:-.03em;line-height:1">{ticker}</div>'
        f'<div style="font-size:.82rem;color:{_TEXT2};margin-top:4px;'
        f'max-width:220px;line-height:1.3">{name}</div>'
        f'</div>'
        f'<div style="text-align:right;flex-shrink:0">'
        f'<div style="font-size:1.5rem;font-weight:700;color:{_TEXT1}">{price_str}</div>'
        f'<div style="font-size:.82rem;font-weight:600;color:{chg_color}">{arrow} {chg_str}</div>'
        f'</div></div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:12px">'
        f'<span style="background:{accent}16;color:{accent};border:1px solid {accent}28;'
        f'border-radius:12px;padding:3px 10px;font-size:.7rem;font-weight:600">{sector}</span>'
        f'<span style="background:{_BG_EL};color:{_TEXT2};border:1px solid {_BORDER};'
        f'border-radius:12px;padding:3px 10px;font-size:.7rem">{industry}</span>'
        f'</div>'
        f'<div style="display:flex;gap:16px;margin-top:12px;color:{_TEXT3};font-size:.72rem">'
        f'<span>Mkt Cap <strong style="color:{_TEXT2}">{market_cap_str}</strong></span>'
        f'<span>Employees <strong style="color:{_TEXT2}">{emp_str}</strong></span>'
        f'</div></div>'
    )


def score_bar(label: str, score: float, max_score: float = 6.0, color: str = None) -> str:
    pct = min(100.0, max(0.0, (score / max_score) * 100))
    if color is None:
        color = _RED if score < 2 else "#f0b429" if score < 3.5 else _GREEN
    return (
        f'<div style="margin:6px 0">'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:4px">'
        f'<span style="font-size:.75rem;font-weight:600;color:{_TEXT2};'
        f'text-transform:uppercase;letter-spacing:.06em">{label}</span>'
        f'<span style="font-size:.75rem;font-weight:700;color:{color}">{score:.1f}/{max_score:.0f}</span>'
        f'</div>'
        f'<div style="background:{_BG_EL};border-radius:6px;height:6px;overflow:hidden">'
        f'<div style="width:{pct:.1f}%;height:100%;background:{color};'
        f'border-radius:6px;transition:width .4s ease"></div>'
        f'</div></div>'
    )


def check_item(text: str, passed, detail: str = "") -> str:
    if passed is True:
        icon, color = "✓", _GREEN
    elif passed is False:
        icon, color = "✗", _RED
    else:
        icon, color = "—", _TEXT3
    det = (f'<span style="color:{_TEXT3};font-size:.7rem;margin-left:6px">{detail}</span>'
           if detail else "")
    return (
        f'<div style="display:flex;align-items:flex-start;gap:8px;padding:5px 0;'
        f'border-bottom:1px solid {_BG_EL}">'
        f'<span style="color:{color};font-weight:700;font-size:.85rem;flex-shrink:0;'
        f'width:16px;text-align:center">{icon}</span>'
        f'<span style="color:{_TEXT2};font-size:.8rem;line-height:1.4">{text}{det}</span>'
        f'</div>'
    )


def analyst_badge(recommendation_key: str) -> str:
    cfg = {
        "strong_buy":  (_GREEN, "rgba(22,199,132,.12)", "Strong Buy"),
        "buy":         (_ACCENT, "rgba(0,229,163,.10)", "Buy"),
        "hold":        ("#f0b429", "rgba(240,180,41,.10)", "Hold"),
        "sell":        (_RED,   "rgba(234,57,67,.10)",  "Sell"),
        "strong_sell": (_RED,   "rgba(234,57,67,.14)",  "Strong Sell"),
    }
    color, bg, label = cfg.get(recommendation_key, (_TEXT2, _BG_EL, "N/A"))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}40;'
        f'border-radius:8px;padding:4px 14px;font-size:.8rem;font-weight:700;'
        f'letter-spacing:.04em;white-space:nowrap">{label}</span>'
    )


def valuation_model_card(
    model_name: str, fair_value, current_price,
    upside_pct, methodology_note: str, accent: str = _ACCENT,
) -> str:
    if fair_value is None or current_price is None:
        return (
            f'<div style="background:{_BG_CARD};border:1px solid {_BORDER};border-radius:12px;'
            f'padding:16px 18px;text-align:center;height:100%">'
            f'<div style="color:{_TEXT3};font-size:.7rem;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:.08em">{model_name}</div>'
            f'<div style="color:{_TEXT3};font-size:1.4rem;font-weight:700;margin:8px 0">N/A</div>'
            f'<div style="color:{_TEXT3};font-size:.7rem">{methodology_note}</div>'
            f'</div>'
        )
    up_color = _GREEN if (upside_pct or 0) >= 0 else _RED
    up_arrow = "+" if (upside_pct or 0) >= 0 else "-"
    up_str   = f"{up_arrow} {abs(upside_pct):.1f}%" if upside_pct is not None else "N/A"
    fv_str   = f"${float(fair_value):.2f}"
    return (
        f'<div style="background:{_BG_CARD};border:1px solid {_BORDER};border-radius:12px;'
        f'padding:16px 18px;position:relative;overflow:hidden;height:100%">'
        f'<div style="position:absolute;top:0;left:0;right:0;height:2px;'
        f'background:linear-gradient(90deg,{accent}80,transparent)"></div>'
        f'<div style="color:{_TEXT3};font-size:.68rem;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:.08em">{model_name}</div>'
        f'<div style="color:{_TEXT1};font-size:1.5rem;font-weight:800;'
        f'letter-spacing:-.02em;margin:6px 0 2px">{fv_str}</div>'
        f'<div style="color:{up_color};font-size:.88rem;font-weight:700">{up_str}</div>'
        f'<div style="color:{_TEXT3};font-size:.68rem;margin-top:8px;line-height:1.3">{methodology_note}</div>'
        f'</div>'
    )
