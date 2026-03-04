"""E_Screener.py — Comprehensive Stock Screener"""
import streamlit as st
import pandas as pd
import requests

from lib.style import inject_css, section_header
from lib.nav import render_nav
from lib.fundamental import (get_fmp_key, safe_get, format_large,
    SECTOR_PE_MEDIANS, SECTOR_EV_EBITDA_MEDIANS, SECTOR_NAME_MAP)

st.set_page_config(page_title="Screener", layout="wide", initial_sidebar_state="collapsed")
inject_css()
render_nav("Screener")
st.title("Stock Screener")
st.caption("Find stocks with 15+ financial filters. FMP API key unlocks global markets.")

fmp_key = get_fmp_key()

with st.expander("Screen Filters", expanded=True):
    _r1c1, _r1c2, _r1c3, _r1c4 = st.columns(4)
    with _r1c1:
        _uni = ["FMP Global Screener (API)"] if fmp_key else []
        _uni.append("S&P 100 Scan (yfinance)")
        universe = st.selectbox("Universe", _uni)
        exchange = st.selectbox("Exchange", ["Any","NYSE","NASDAQ","AMEX"]) if "FMP" in universe else "Any"
        _secs = ["Any"] + sorted(set(SECTOR_PE_MEDIANS.keys()))
        sector_f = st.selectbox("Sector", _secs)
        _mc = {"Any":(None,None),"Mega Cap (>$200B)":(200e9,None),"Large Cap ($10B-$200B)":(10e9,200e9),
               "Mid Cap ($2B-$10B)":(2e9,10e9),"Small Cap (<$2B)":(None,2e9)}
        mc_sel = st.selectbox("Market Cap", list(_mc.keys()))
        mc_min, mc_max = _mc[mc_sel]
    with _r1c2:
        st.markdown("**Valuation**")
        max_pe  = st.slider("Max P/E",         0,150,80)
        max_fpe = st.slider("Max Forward P/E", 0,100,60)
        max_pb  = st.slider("Max P/B",         0.0,30.0,15.0,0.5)
        max_ev  = st.slider("Max EV/EBITDA",   0,100,60)
    with _r1c3:
        st.markdown("**Growth & Profitability**")
        min_rg  = st.slider("Min Revenue Growth %",  -50,100,0)
        min_eg  = st.slider("Min Earnings Growth %", -50,100,0)
        min_roe = st.slider("Min ROE %",             -50,100,0)
        min_mgn = st.slider("Min Net Margin %",      -50, 50,0)
    with _r1c4:
        st.markdown("**Health & Risk**")
        max_de  = st.slider("Max Debt/Equity",      0.0,15.0,10.0,0.5)
        min_cr  = st.slider("Min Current Ratio",    0.0, 5.0, 0.0,0.1)
        min_dy  = st.slider("Min Dividend Yield %", 0.0,15.0,0.0,0.1)
        min_up  = st.slider("Min Analyst Upside %",-50,100,0)
        max_bt  = st.slider("Max Beta",             0.0, 5.0,5.0,0.1)
        rat_f   = st.multiselect("Analyst Rating",
            ["Strong Buy","Buy","Hold","Sell","Strong Sell"], default=[])
        val_st  = st.selectbox("Valuation vs Sector P/E",
            ["Any","Potentially Undervalued","Potentially Overvalued"])
    run_btn = st.button("Run Screen", type="primary")

if not run_btn:
    st.info("Configure filters above then click Run Screen.")
    st.markdown("""
**FMP API key** → global screener (thousands of stocks, real-time)
**No key** → S&P 100 via yfinance (~60 seconds)

Set `FMP_API_KEY` in Streamlit Cloud secrets.
    """)
    st.stop()

results = []
with st.spinner("Screening..."):
    if "FMP" in universe and fmp_key:
        _fmp_sec = {"Technology":"Technology","Healthcare":"Healthcare",
                    "Financials":"Financial Services","Energy":"Energy",
                    "Consumer Disc.":"Consumer Cyclical","Consumer Discretionary":"Consumer Cyclical",
                    "Consumer Staples":"Consumer Defensive","Industrials":"Industrials",
                    "Communication":"Communication Services",
                    "Communication Services":"Communication Services",
                    "Utilities":"Utilities","Real Estate":"Real Estate",
                    "Materials":"Basic Materials","Basic Materials":"Basic Materials"}
        _p = {"apikey":fmp_key,"isEtf":"false","isActivelyTrading":"true","limit":250}
        if sector_f != "Any": _p["sector"] = _fmp_sec.get(sector_f, sector_f)
        if exchange != "Any": _p["exchange"] = exchange
        if mc_min: _p["marketCapMoreThan"] = int(mc_min)
        if mc_max: _p["marketCapLessThan"] = int(mc_max)
        if max_bt < 5.0: _p["betaLowerThan"] = max_bt
        if min_dy > 0:   _p["dividendMoreThan"] = min_dy/100
        try:
            _r = requests.get("https://financialmodelingprep.com/api/v3/stock-screener",
                              params=_p, timeout=20)
            if _r.ok:
                for _it in _r.json():
                    _pe2 = _it.get("pe"); _mc2 = _it.get("marketCap")
                    results.append({"Ticker":_it.get("symbol",""),"Company":_it.get("companyName",""),
                        "Exchange":_it.get("exchangeShortName",""),"Sector":_it.get("sector",""),
                        "Mkt Cap($B)":round(_mc2/1e9,2) if _mc2 else None,
                        "Price":_it.get("price"),"P/E":round(float(_pe2),1) if _pe2 else None,
                        "Beta":_it.get("beta"),"Volume(M)":round(_it.get("volume",0)/1e6,2),
                        "Country":_it.get("country","")})
            else:
                st.warning(f"FMP error {_r.status_code} — falling back to S&P 100.")
                universe = "S&P 100"
        except Exception as _fe:
            st.warning(f"FMP failed ({_fe}) — using S&P 100 fallback."); universe="S&P 100"

    if "S&P" in universe or not results:
        import yfinance as _yf
        from lib.universe import SP100
        _prog = st.progress(0, text="Scanning S&P 100...")
        for _i, _tk in enumerate(SP100):
            _prog.progress((_i+1)/len(SP100), text=f"Scanning {_tk}...")
            try:
                _inf = _yf.Ticker(_tk).info or {}
                if not _inf.get("symbol"): continue
                _sec2 = _inf.get("sector","")
                if sector_f != "Any":
                    _mp = SECTOR_NAME_MAP.get(_sec2,_sec2)
                    if _mp != sector_f and _sec2 != sector_f: continue
                def _n(k):
                    v = safe_get(_inf,k)
                    try: return float(v) if v is not None else None
                    except: return None
                _mkt=_n("marketCap"); _pe=_n("trailingPE"); _fpe=_n("forwardPE")
                _pb=_n("priceToBook"); _ev=_n("enterpriseToEbitda"); _rg=_n("revenueGrowth")
                _eg=_n("earningsGrowth"); _roe=_n("returnOnEquity"); _mg=_n("profitMargins")
                _de=_n("debtToEquity"); _cr=_n("currentRatio"); _dy=_n("dividendYield")
                _bt=_n("beta"); _tg=_n("targetMeanPrice"); _pr=_n("currentPrice") or _n("regularMarketPrice")
                _rc=safe_get(_inf,"recommendationKey","")
                if mc_min and _mkt and _mkt<mc_min: continue
                if mc_max and _mkt and _mkt>mc_max: continue
                if _pe  and _pe >max_pe:  continue
                if _fpe and _fpe>max_fpe: continue
                if _pb  and _pb >max_pb:  continue
                if _ev  and _ev >max_ev:  continue
                if _rg  is not None and _rg*100 <min_rg:  continue
                if _eg  is not None and _eg*100 <min_eg:  continue
                if _roe is not None and _roe*100<min_roe:  continue
                if _mg  is not None and _mg*100 <min_mgn:  continue
                if _de  is not None and _de/100 >max_de:  continue
                if _cr  is not None and _cr     <min_cr:  continue
                if (_dy or 0)*100<min_dy: continue
                if _bt and _bt>max_bt: continue
                _upd = ((_tg-_pr)/_pr*100) if (_tg and _pr) else None
                if _upd is not None and _upd<min_up: continue
                if rat_f:
                    _rm={"strong_buy":"Strong Buy","buy":"Buy","hold":"Hold","sell":"Sell","strong_sell":"Strong Sell"}
                    if _rm.get(_rc,"") not in rat_f: continue
                if val_st != "Any" and _pe:
                    _mps = SECTOR_NAME_MAP.get(_sec2,_sec2)
                    _isu = _pe < SECTOR_PE_MEDIANS.get(_mps,20)
                    if val_st=="Potentially Undervalued" and not _isu: continue
                    if val_st=="Potentially Overvalued"  and _isu:     continue
                results.append({"Ticker":_tk,"Company":_inf.get("longName",""),"Sector":_sec2,
                    "Mkt Cap($B)":round(_mkt/1e9,2) if _mkt else None,
                    "Price":round(_pr,2) if _pr else None,
                    "P/E":round(_pe,1) if _pe else None,"Fwd P/E":round(_fpe,1) if _fpe else None,
                    "EV/EBITDA":round(_ev,1) if _ev else None,"P/B":round(_pb,2) if _pb else None,
                    "Rev Gr%":round(_rg*100,1) if _rg is not None else None,
                    "EPS Gr%":round(_eg*100,1) if _eg is not None else None,
                    "ROE%":round(_roe*100,1) if _roe is not None else None,
                    "Net Mgn%":round(_mg*100,1) if _mg is not None else None,
                    "D/E":round(_de/100,2) if _de is not None else None,
                    "Curr Ratio":round(_cr,2) if _cr else None,
                    "Div Yield%":round((_dy or 0)*100,2),
                    "Beta":round(_bt,2) if _bt else None,
                    "Target($)":round(_tg,2) if _tg else None,
                    "Upside%":round(_upd,1) if _upd is not None else None,
                    "Rating":_rc.replace("_"," ").title() if _rc else None,
                    "Val Status":("Undervalued" if (_pe and _pe<SECTOR_PE_MEDIANS.get(
                        SECTOR_NAME_MAP.get(_sec2,_sec2),20)) else "Overvalued") if _pe else "N/A"})
            except Exception: continue
        _prog.empty()

if not results:
    st.warning("No results. Try relaxing your filters."); st.stop()

df = pd.DataFrame(results)
st.success(f"{len(df)} stocks matched")

_sortable = [c for c in df.columns if c not in ["Ticker","Company","Sector","Rating","Val Status","Country"]]
_s1,_s2 = st.columns([3,1])
_sc = _s1.selectbox("Sort by", _sortable)
_sa = _s2.checkbox("Ascending", False)
if _sc in df.columns:
    df = df.sort_values(_sc, ascending=_sa, na_position="last")

def _style(row):
    s = [""]*len(row); idx = list(row.index)
    for _ci,_cn in enumerate(idx):
        if _cn=="Val Status":
            if row.get(_cn)=="Undervalued": s[_ci]="color:#00d4aa;font-weight:bold"
            elif row.get(_cn)=="Overvalued": s[_ci]="color:#ff4b4b"
        elif _cn=="Rating":
            v=str(row.get(_cn,"")).lower()
            if "buy" in v: s[_ci]="color:#00d4aa"
            elif "sell" in v: s[_ci]="color:#ff4b4b"
        elif _cn=="Upside%":
            v=row.get(_cn)
            if v is not None:
                if v>15: s[_ci]="color:#00d4aa"
                elif v<-10: s[_ci]="color:#ff4b4b"
    return s

try:
    st.dataframe(df.style.apply(_style,axis=1), use_container_width=True, height=600)
except Exception:
    st.dataframe(df, use_container_width=True, height=600)

st.divider()
if st.button("Download Results (Excel)"):
    import io
    _b = io.BytesIO(); df.to_excel(_b, index=False, engine="openpyxl"); _b.seek(0)
    st.download_button("Save",_b.getvalue(),"screener_results.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",key="dl_sc_save")
