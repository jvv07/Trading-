"""
lib/nav.py — Fixed top navigation bar for QUANTEDGE Trading Dashboard.
Call render_nav(current_page) on every page AFTER inject_css().
"""

import streamlit as st

# ── Nav structure ─────────────────────────────────────────────────────────────
_NAV_ITEMS = [
    ("Home",      "/",          None),
    ("Market",    "/Market",    None),
    ("Watchlist", "/Watchlist", None),
    ("Screener",  None, [
        ("Scanner",  "/Scanner"),
        ("Screener", "/Screener"),
    ]),
    ("Trading", None, [
        ("Portfolio",  "/Portfolio"),
        ("Trades",     "/Trades"),
        ("Strategies", "/Strategies"),
        ("Analytics",  "/Analytics"),
        ("Backtester", "/Backtester"),
        ("Risk",       "/Risk"),
        ("Journal",    "/Journal"),
    ]),
    ("Quant", None, [
        ("Optimize",    "/Optimize"),
        ("Options",     "/Options"),
        ("Monte Carlo", "/MonteCarlo"),
        ("Seasonality", "/Seasonality"),
    ]),
]

# ── CSS ───────────────────────────────────────────────────────────────────────
_NAV_CSS = """<style>
.qe-topnav{position:fixed;top:0;left:0;right:0;height:52px;background:#080c14;border-bottom:1px solid #131c2e;display:flex;align-items:center;padding:0 20px;gap:0;z-index:99999;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;box-sizing:border-box;}
.qe-logo{font-size:.9rem;font-weight:900;letter-spacing:-.03em;background:linear-gradient(135deg,#ffffff 30%,#00d4aa 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;white-space:nowrap;text-decoration:none;margin-right:20px;flex-shrink:0;}
.qe-nav-links{display:flex;align-items:center;gap:2px;flex:1;}
.qe-nav-a{color:#4a5a72;font-size:.8rem;font-weight:500;padding:6px 11px;border-radius:6px;text-decoration:none;transition:all .15s;white-space:nowrap;cursor:pointer;}
.qe-nav-a:hover,.qe-nav-a.qe-active{color:#c8d0e0;background:rgba(255,255,255,.05);}
.qe-nav-a.qe-active{color:#00d4aa !important;}
.qe-dd{position:relative;}
.qe-dd-btn{color:#4a5a72;font-size:.8rem;font-weight:500;padding:6px 11px;border-radius:6px;cursor:pointer;transition:all .15s;white-space:nowrap;user-select:none;}
.qe-dd:hover .qe-dd-btn{color:#c8d0e0;background:rgba(255,255,255,.05);}
.qe-dd-menu{display:none;position:absolute;top:calc(100% + 6px);left:0;background:#0d1422;border:1px solid #1a2332;border-radius:10px;padding:6px;min-width:160px;box-shadow:0 12px 40px rgba(0,0,0,.7);z-index:100000;}
.qe-dd:hover .qe-dd-menu{display:block;}
.qe-dd-menu a{display:block;color:#8892a4;font-size:.8rem;font-weight:500;padding:7px 12px;border-radius:7px;text-decoration:none;transition:all .15s;white-space:nowrap;}
.qe-dd-menu a:hover{color:#00d4aa;background:rgba(0,212,170,.08);}
.qe-search{display:flex;align-items:center;background:#0d1422;border:1px solid #1a2332;border-radius:8px;overflow:hidden;height:32px;margin-left:auto;flex-shrink:0;}
.qe-search input{background:transparent;border:none;color:#e2e8f0;font-size:.8rem;padding:0 12px;width:150px;outline:none;font-family:'Inter',sans-serif;}
.qe-search input::placeholder{color:#2a3a52;}
.qe-search button{background:#00d4aa;border:none;color:#060a10;font-weight:700;padding:0 14px;height:100%;cursor:pointer;font-size:.8rem;transition:background .15s;font-family:'Inter',sans-serif;}
.qe-search button:hover{background:#00b894;}
</style>"""


def render_nav(current_page: str = "") -> None:
    """Inject the fixed top nav bar. Call after inject_css()."""

    def _link(label: str, url: str) -> str:
        cls = "qe-active" if current_page == label else ""
        return f'<a href="{url}" class="qe-nav-a {cls}">{label}</a>'

    def _dropdown(label: str, children: list) -> str:
        items = "".join(f'<a href="{u}">{l}</a>' for l, u in children)
        return (f'<div class="qe-dd"><span class="qe-dd-btn">{label} ▾</span>'
                f'<div class="qe-dd-menu">{items}</div></div>')

    links = ""
    for item in _NAV_ITEMS:
        name, url, children = item
        if children is None:
            links += _link(name, url)
        else:
            links += _dropdown(name, children)

    html = (
        f'{_NAV_CSS}'
        f'<nav class="qe-topnav">'
        f'<a href="/" class="qe-logo">⟨ QUANTEDGE ⟩</a>'
        f'<div class="qe-nav-links">{links}</div>'
        f'<form class="qe-search" action="/Watchlist" method="get">'
        f'<input type="text" name="ticker" placeholder="Search ticker…" autocomplete="off" spellcheck="false">'
        f'<button type="submit">→</button>'
        f'</form>'
        f'</nav>'
    )
    st.markdown(html, unsafe_allow_html=True)
