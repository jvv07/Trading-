"""
lib/nav.py — Fixed top navigation bar for Vulpen Capital Trading Dashboard.
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
.qe-topnav{position:fixed;top:0;left:0;right:0;height:58px;background:#0b0d12;border-bottom:1px solid rgba(255,255,255,0.07);display:flex;align-items:center;padding:0 28px;gap:0;z-index:99999;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;box-sizing:border-box;}
.qe-logo{font-size:1.1rem;font-weight:900;letter-spacing:-.02em;background:linear-gradient(135deg,#ffffff 30%,#00e5a3 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;white-space:nowrap;text-decoration:none !important;margin-right:28px;flex-shrink:0;}
.qe-nav-links{display:flex;align-items:center;gap:2px;flex:1;}
.qe-nav-a{color:#3a4d66;font-size:.95rem;font-weight:500;padding:7px 13px;border-radius:8px;text-decoration:none !important;transition:all .15s;white-space:nowrap;cursor:pointer;}
.qe-nav-a:hover,.qe-nav-a.qe-active{color:#eef2f7;background:rgba(255,255,255,.05);text-decoration:none !important;}
.qe-nav-a.qe-active{color:#00e5a3 !important;}
.qe-dd{position:relative;}
.qe-dd-btn{color:#3a4d66;font-size:.95rem;font-weight:500;padding:7px 13px;border-radius:8px;cursor:pointer;transition:all .15s;white-space:nowrap;user-select:none;text-decoration:none !important;}
.qe-dd:hover .qe-dd-btn{color:#eef2f7;background:rgba(255,255,255,.05);}
.qe-dd-menu{display:none;position:absolute;top:calc(100% + 8px);left:0;background:#131928;border:1px solid rgba(255,255,255,0.09);border-radius:12px;padding:6px;min-width:168px;box-shadow:0 16px 48px rgba(0,0,0,.8);z-index:100000;}
.qe-dd:hover .qe-dd-menu{display:block;}
.qe-dd-menu a{display:block;color:#7a8fa8;font-size:.9rem;font-weight:500;padding:8px 13px;border-radius:8px;text-decoration:none !important;transition:all .15s;white-space:nowrap;}
.qe-dd-menu a:hover{color:#00e5a3;background:rgba(0,229,163,.08);}
.qe-search{display:flex;align-items:center;background:#131928;border:1px solid rgba(255,255,255,0.07);border-radius:8px;overflow:hidden;height:34px;margin-left:auto;flex-shrink:0;}
.qe-search input{background:transparent;border:none;color:#eef2f7;font-size:.88rem;padding:0 13px;width:160px;outline:none;font-family:'Inter',sans-serif;}
.qe-search input::placeholder{color:#3a4d66;}
.qe-search button{background:#00e5a3;border:none;color:#060a10;font-weight:700;padding:0 15px;height:100%;cursor:pointer;font-size:.85rem;transition:background .15s;font-family:'Inter',sans-serif;}
.qe-search button:hover{background:#00c48a;}
</style>"""


def render_nav(current_page: str = "") -> None:
    """Inject the fixed top nav bar. Call after inject_css()."""

    def _link(label: str, url: str) -> str:
        cls = "qe-active" if current_page == label else ""
        return f'<a href="{url}" class="qe-nav-a {cls}">{label}</a>'

    def _dropdown(label: str, children: list) -> str:
        items = "".join(f'<a href="{u}">{l}</a>' for l, u in children)
        return (f'<div class="qe-dd"><span class="qe-dd-btn">{label} &#9662;</span>'
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
        f'<a href="/" class="qe-logo">VULPEN CAPITAL</a>'
        f'<div class="qe-nav-links">{links}</div>'
        f'<form class="qe-search" action="/Watchlist" method="get">'
        f'<input type="text" name="ticker" placeholder="Search ticker..." '
        f'autocomplete="off" spellcheck="false">'
        f'<button type="submit">Go</button>'
        f'</form>'
        f'</nav>'
    )
    st.markdown(html, unsafe_allow_html=True)
