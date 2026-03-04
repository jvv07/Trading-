"""
lib/nav.py — Fixed top navigation bar for Vulpen Capital.
Call render_nav(current_page) after inject_css() on every page.
"""

import streamlit as st

_NAV_ITEMS = [
    ("Home",      "/",          None),
    ("Market",    "/Market",    None),
    ("Watchlist", "/Watchlist", None),
    ("Screener", None, [
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

_NAV_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');
.vc-nav{position:fixed;top:0;left:0;right:0;height:52px;background:#131825;border-bottom:1px solid #1d2437;display:flex;align-items:center;padding:0 24px;z-index:99999;font-family:'Space Grotesk',-apple-system,sans-serif;box-sizing:border-box;gap:0;}
.vc-logo{font-size:15px;font-weight:700;color:#e2e8f0;letter-spacing:-0.01em;white-space:nowrap;text-decoration:none !important;margin-right:32px;flex-shrink:0;}
.vc-links{display:flex;align-items:center;gap:0;flex:1;height:100%;}
.vc-a{color:#8892a4;font-size:14px;font-weight:500;padding:0 14px;height:52px;display:flex;align-items:center;text-decoration:none !important;border-bottom:2px solid transparent;transition:color 0.15s,border-color 0.15s;white-space:nowrap;box-sizing:border-box;}
.vc-a:hover{color:#e2e8f0;text-decoration:none !important;}
.vc-a.vc-on{color:#e2e8f0;border-bottom-color:#00d4aa;}
.vc-dd{position:relative;height:100%;display:flex;align-items:center;}
.vc-dd-btn{color:#8892a4;font-size:14px;font-weight:500;padding:0 14px;height:52px;display:flex;align-items:center;cursor:pointer;border-bottom:2px solid transparent;transition:color 0.15s;white-space:nowrap;user-select:none;box-sizing:border-box;}
.vc-dd:hover .vc-dd-btn{color:#e2e8f0;}
.vc-dd-menu{display:none;position:absolute;top:52px;left:0;background:#161b2e;border:1px solid #1e2640;border-radius:8px;padding:6px;min-width:160px;box-shadow:0 8px 24px rgba(0,0,0,0.5);z-index:100000;}
.vc-dd:hover .vc-dd-menu{display:block;}
.vc-dd-menu a{display:block;color:#8892a4;font-size:14px;font-weight:400;padding:8px 12px;border-radius:6px;text-decoration:none !important;transition:all 0.12s;white-space:nowrap;}
.vc-dd-menu a:hover{color:#e2e8f0;background:rgba(0,212,170,0.08);}
.vc-search{display:flex;align-items:center;background:#0f1117;border:1px solid #1e2640;border-radius:8px;overflow:hidden;height:34px;margin-left:auto;flex-shrink:0;}
.vc-search input{background:transparent;border:none;color:#e2e8f0;font-size:14px;padding:0 12px;width:160px;outline:none;font-family:'Inter',sans-serif;}
.vc-search input::placeholder{color:#8892a4;}
.vc-search input:focus{outline:none;}
.vc-search button{background:#00d4aa;border:none;color:#0a0d14;font-size:13px;font-weight:600;padding:0 14px;height:100%;cursor:pointer;transition:opacity 0.15s;font-family:'Inter',sans-serif;}
.vc-search button:hover{opacity:0.85;}
</style>"""


def render_nav(current_page: str = "") -> None:
    """Inject fixed top navigation bar. Call after inject_css()."""

    def _link(label: str, url: str) -> str:
        cls = "vc-on" if current_page == label else ""
        return f'<a href="{url}" target="_self" class="vc-a {cls}">{label}</a>'

    def _dropdown(label: str, children: list) -> str:
        items = "".join(f'<a href="{u}" target="_self">{l}</a>' for l, u in children)
        return (
            f'<div class="vc-dd">'
            f'<span class="vc-dd-btn">{label} &#9662;</span>'
            f'<div class="vc-dd-menu">{items}</div>'
            f'</div>'
        )

    links = ""
    for name, url, children in _NAV_ITEMS:
        links += _link(name, url) if children is None else _dropdown(name, children)

    html = (
        f'{_NAV_CSS}'
        f'<nav class="vc-nav">'
        f'<a href="/" target="_self" class="vc-logo">VULPEN CAPITAL</a>'
        f'<div class="vc-links">{links}</div>'
        f'<form class="vc-search" action="/Watchlist" method="get">'
        f'<input type="text" name="ticker" placeholder="Search ticker..." autocomplete="off" spellcheck="false">'
        f'<button type="submit">Go</button>'
        f'</form>'
        f'</nav>'
    )
    st.markdown(html, unsafe_allow_html=True)
