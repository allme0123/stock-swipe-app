
# stock_swipe_app.py
# Mobile-friendly ASX stock chart swiper with crisp CommSec-style candles.
# Version: v3 CommSec-style 85% Streamlit layout
#
# Run:
#   pip install streamlit pandas openpyxl yfinance
#   streamlit run stock_swipe_app.py

import io
import json
import math

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    import yfinance as yf
except Exception:
    yf = None


st.set_page_config(
    page_title="Stock Swipe Charts",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { height: 0rem; }
    .block-container {
        padding-top: 0.15rem;
        padding-left: 0.15rem;
        padding-right: 0.15rem;
        padding-bottom: 0.15rem;
        max-width: 100%;
    }
    div[data-testid="stHorizontalBlock"] { gap: 0.25rem; }
    button[kind="primary"], button[kind="secondary"] {
        width: 100%;
        height: 2.15rem;
        border-radius: 8px;
        padding: 0.1rem;
        font-size: 1rem;
    }
    div[data-baseweb="select"] > div {
        min-height: 2.15rem;
    }
    iframe { width: 100%; border: none; display: block; }
    </style>
    """,
    unsafe_allow_html=True,
)

REQUIRED = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "date": "Date",
        "datetime": "Date",
        "time": "Date",
        "ticker": "Ticker",
        "symbol": "Ticker",
        "code": "Ticker",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "adj close": "Close",
        "volume": "Volume",
        "vol": "Volume",
    }
    rename = {}
    for c in df.columns:
        key = str(c).strip().lower()
        if key in aliases:
            rename[c] = aliases[key]
    return df.rename(columns=rename)


def load_uploaded(file) -> pd.DataFrame:
    data = file.read()
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(io.BytesIO(data))
    else:
        df = pd.read_excel(io.BytesIO(data))

    df = normalise_columns(df)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}. Need {REQUIRED}")

    df = df[REQUIRED].copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()

    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna(subset=["Date", "Ticker", "Open", "High", "Low", "Close"]).sort_values(["Ticker", "Date"])


@st.cache_data(show_spinner=False, ttl=900)
def fetch_yahoo(tickers_text: str, period: str, interval: str) -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("yfinance is not installed. Add yfinance to requirements.txt")

    tickers = [t.strip().upper() for t in tickers_text.replace("\n", ",").split(",") if t.strip()]
    frames = []

    for t in tickers:
        d = yf.download(t, period=period, interval=interval, auto_adjust=False, progress=False)
        if d.empty:
            continue

        if isinstance(d.columns, pd.MultiIndex):
            d.columns = [x[0] for x in d.columns]

        d = d.reset_index()
        date_col = "Date" if "Date" in d.columns else "Datetime"
        d["Ticker"] = t

        keep = d[[date_col, "Ticker", "Open", "High", "Low", "Close", "Volume"]].copy()
        keep = keep.rename(columns={date_col: "Date"})
        frames.append(keep)

    if not frames:
        return pd.DataFrame(columns=REQUIRED)

    df = pd.concat(frames, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df.dropna(subset=["Date", "Open", "High", "Low", "Close"]).sort_values(["Ticker", "Date"])


def add_indicators(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["SMA20"] = d["Close"].rolling(20).mean()
    d["SMA50"] = d["Close"].rolling(50).mean()
    d["SMA200"] = d["Close"].rolling(200).mean()
    d["High52w"] = d["High"].rolling(252, min_periods=20).max()
    d["Dist52wPct"] = ((d["Close"] / d["High52w"]) - 1) * 100

    prev_close = d["Close"].shift(1)
    tr = pd.concat(
        [
            d["High"] - d["Low"],
            (d["High"] - prev_close).abs(),
            (d["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    d["ATR14"] = tr.rolling(14).mean()
    d["ATRPct"] = d["ATR14"] / d["Close"] * 100
    return d


def clean_number(x, default=None):
    try:
        if x is None or pd.isna(x) or math.isinf(float(x)):
            return default
        return float(x)
    except Exception:
        return default


def chart_html(d: pd.DataFrame, ticker: str, show_sma: bool = False) -> str:
    d = add_indicators(d).copy()
    rows = []
    for _, r in d.iterrows():
        o = clean_number(r["Open"]); h = clean_number(r["High"]); l = clean_number(r["Low"]); c = clean_number(r["Close"]); v = clean_number(r["Volume"], 0)
        if None in [o, h, l, c]:
            continue
        rows.append({
            "date": pd.Timestamp(r["Date"]).strftime("%d/%m/%y"),
            "open": o, "high": h, "low": l, "close": c, "volume": v,
            "sma20": clean_number(r.get("SMA20")),
            "sma50": clean_number(r.get("SMA50")),
            "sma200": clean_number(r.get("SMA200")),
        })
    if not rows:
        return "<div>No chart data available.</div>"

    last = d.iloc[-1]
    prev = d.iloc[-2] if len(d) > 1 else last
    close = float(last["Close"])
    change = close - float(prev["Close"])
    change_pct = change / float(prev["Close"]) * 100 if float(prev["Close"]) else 0
    high = float(last["High"]); low = float(last["Low"])
    date_str = pd.Timestamp(last["Date"]).strftime("%d/%m/%Y").lstrip("0").replace("/0", "/")
    change_colour = "#178b2c" if change >= 0 else "#d40000"
    arrow = "▲" if change >= 0 else "▼"
    safe_ticker = ticker.replace(".AX", ":ASX")

    return f'''
<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
<style>
html, body {{ margin:0; padding:0; width:100%; background:#fff; font-family:Arial, Helvetica, sans-serif; overscroll-behavior:contain; -webkit-tap-highlight-color:transparent; }}
.wrap {{ width:100%; background:#fff; box-sizing:border-box; padding:0 2px 8px 2px; }}
.topbar {{ display:flex; align-items:baseline; gap:7px; height:25px; padding:0 5px; border-bottom:1px solid #ededed; white-space:nowrap; overflow:hidden; box-sizing:border-box; }}
.ticker {{ font-weight:700; font-size:18px; color:#000; }} .price {{ font-weight:700; font-size:16px; color:#000; }} .change {{ font-weight:700; font-size:15px; color:{change_colour}; }}
.toolbar {{ display:flex; justify-content:space-between; align-items:center; height:22px; color:#666; background:#f3f2ef; font-size:12px; padding:0 7px; border-bottom:1px solid #dededa; box-sizing:border-box; }}
.ohlc {{ display:flex; justify-content:space-around; align-items:center; height:23px; font-size:12px; color:#555; box-sizing:border-box; }}
.panel {{ margin:0 1px 7px 1px; border:1px solid #bdbdbd; background:#fff; box-sizing:border-box; }}
.panel-title {{ height:20px; display:flex; align-items:center; gap:6px; padding-left:6px; color:#666; font-size:12px; border-bottom:1px solid #e1e1e1; background:#f8f8f6; box-sizing:border-box; }}
.legend-price, .legend-volume {{ width:15px; height:12px; border-left:7px solid #00a33a; border-right:7px solid #df0000; box-sizing:border-box; }}
#priceCanvas {{ width:100%; height:470px; display:block; touch-action:none; }}
#volumeCanvas {{ width:100%; height:155px; display:block; touch-action:none; }}
.hint {{ font-size:11px; color:#8a8a8a; text-align:center; margin-top:-3px; padding-bottom:2px; }}
@media (max-height:760px) {{ #priceCanvas {{ height:430px; }} #volumeCanvas {{ height:142px; }} }}
@media (max-height:690px) {{ #priceCanvas {{ height:390px; }} #volumeCanvas {{ height:128px; }} }}
</style></head><body>
<div class="wrap">
<div class="topbar"><span class="ticker">{safe_ticker}</span><span class="price">${close:.3f}</span><span class="change">{arrow} ${abs(change):.3f} ({change_pct:.2f}%)</span></div>
<div class="toolbar"><span>Daily</span><span>Candle</span><span>Drag / pinch zoom</span></div>
<div class="ohlc"><span>H ${high:.2f}</span><span>L ${low:.2f}</span><span>C ${close:.2f}</span><span>{date_str}</span></div>
<div class="panel"><div class="panel-title"><span class="legend-price"></span><span>Price</span></div><canvas id="priceCanvas"></canvas></div>
<div class="panel"><div class="panel-title"><span class="legend-volume"></span><span>Volume</span></div><canvas id="volumeCanvas"></canvas></div>
<div class="hint">Double tap resets view</div>
</div>
<script>
const rows = {json.dumps(rows)};
const showSma = {str(bool(show_sma)).lower()};
const priceCanvas = document.getElementById('priceCanvas');
const volumeCanvas = document.getElementById('volumeCanvas');
const pctx = priceCanvas.getContext('2d');
const vctx = volumeCanvas.getContext('2d');
let view = {{ count: Math.min(58, rows.length), end: rows.length - 1, minCount: 18, maxCount: Math.min(180, rows.length) }};
let lastTap = 0, drag = null, pinch = null;
function clamp(v, lo, hi) {{ return Math.max(lo, Math.min(hi, v)); }}
function setupCanvas(canvas, ctx) {{ const dpr = window.devicePixelRatio || 1; const w = canvas.clientWidth, h = canvas.clientHeight; canvas.width = Math.max(1, Math.floor(w*dpr)); canvas.height = Math.max(1, Math.floor(h*dpr)); ctx.setTransform(dpr,0,0,dpr,0,0); }}
function visibleRange() {{ view.count = clamp(view.count, view.minCount, view.maxCount); view.end = clamp(view.end, view.count-1, rows.length-1); const start = Math.max(0, Math.round(view.end-view.count+1)); const end = Math.min(rows.length-1, Math.round(view.end)); return {{start,end,data:rows.slice(start,end+1)}}; }}
function fmtPrice(x) {{ if (x >= 10) return x.toFixed(2); if (x >= 1) return x.toFixed(3); return x.toFixed(4); }}
function niceVolume(x) {{ if (x>=1000000000) return (x/1000000000).toFixed(1)+'B'; if (x>=1000000) return (x/1000000).toFixed(1)+'M'; if (x>=1000) return (x/1000).toFixed(0)+'K'; return String(Math.round(x)); }}
function drawGrid(ctx, left, right, top, bottom, yTicks) {{ ctx.strokeStyle='#e6e6e6'; ctx.lineWidth=1; for(let i=0;i<=yTicks;i++){{ const y=top+(bottom-top)*i/yTicks; ctx.beginPath(); ctx.moveTo(left,y); ctx.lineTo(right,y); ctx.stroke(); }} for(let i=0;i<=4;i++){{ const x=left+(right-left)*i/4; ctx.beginPath(); ctx.moveTo(x,top); ctx.lineTo(x,bottom); ctx.stroke(); }} }}
function drawPrice() {{
 setupCanvas(priceCanvas,pctx); const w=priceCanvas.clientWidth,h=priceCanvas.clientHeight; const r=visibleRange(); const data=r.data; pctx.clearRect(0,0,w,h); pctx.fillStyle='#fff'; pctx.fillRect(0,0,w,h);
 const left=7,right=w-54,top=12,bottom=h-23; drawGrid(pctx,left,right,top,bottom,5);
 let minP=Math.min(...data.map(x=>x.low)), maxP=Math.max(...data.map(x=>x.high));
 if(showSma){{ for(const k of ['sma20','sma50','sma200']){{ const vals=data.map(x=>x[k]).filter(x=>x!==null&&Number.isFinite(x)); if(vals.length){{ minP=Math.min(minP,...vals); maxP=Math.max(maxP,...vals); }} }} }}
 const pad=(maxP-minP)*0.14 || maxP*0.02 || 1; minP-=pad; maxP+=pad; const y=val=>bottom-(val-minP)/(maxP-minP)*(bottom-top); const step=(right-left)/data.length; const bodyW=clamp(step*0.72,5.5,17);
 pctx.fillStyle='#666'; pctx.font='11px Arial'; pctx.textAlign='left'; pctx.textBaseline='middle'; for(let i=0;i<=5;i++){{ const val=maxP-(maxP-minP)*i/5; pctx.fillText(fmtPrice(val),right+5,top+(bottom-top)*i/5); }}
 function drawLine(key,color){{ pctx.strokeStyle=color; pctx.lineWidth=1; let started=false; data.forEach((bar,i)=>{{ const val=bar[key]; if(val===null||!Number.isFinite(val)){{started=false; return;}} const x=left+step*i+step/2, yy=y(val); if(!started){{pctx.beginPath(); pctx.moveTo(x,yy); started=true;}} else pctx.lineTo(x,yy); }}); if(started)pctx.stroke(); }}
 if(showSma){{ drawLine('sma20','#777'); drawLine('sma50','#aaa'); drawLine('sma200','#ccc'); }}
 data.forEach((bar,i)=>{{ const x=left+step*i+step/2; const up=bar.close>=bar.open; const col=up?'#009b35':'#df0000'; const yo=y(bar.open),yc=y(bar.close),yh=y(bar.high),yl=y(bar.low); const bodyTop=Math.min(yo,yc), bodyBot=Math.max(yo,yc), bw=Math.max(1.5,bodyBot-bodyTop); pctx.strokeStyle=col; pctx.lineWidth=1.35; pctx.beginPath(); pctx.moveTo(x,yh); pctx.lineTo(x,yl); pctx.stroke(); if(up){{ pctx.fillStyle='#fff'; pctx.strokeStyle=col; pctx.lineWidth=1.55; pctx.fillRect(x-bodyW/2,bodyTop,bodyW,bw); pctx.strokeRect(x-bodyW/2,bodyTop,bodyW,bw); }} else {{ pctx.fillStyle=col; pctx.fillRect(x-bodyW/2,bodyTop,bodyW,bw); }} }});
 const last=rows[rows.length-1], ly=y(last.close); if(ly>=top&&ly<=bottom){{ pctx.strokeStyle='#147aa5'; pctx.lineWidth=1; pctx.setLineDash([4,3]); pctx.beginPath(); pctx.moveTo(left,ly); pctx.lineTo(right,ly); pctx.stroke(); pctx.setLineDash([]); pctx.fillStyle='#147aa5'; const label=fmtPrice(last.close); pctx.fillRect(right+2,ly-10,49,20); pctx.fillStyle='#fff'; pctx.font='bold 11px Arial'; pctx.textAlign='center'; pctx.textBaseline='middle'; pctx.fillText(label,right+26.5,ly); }}
}}
function drawVolume() {{
 setupCanvas(volumeCanvas,vctx); const w=volumeCanvas.clientWidth,h=volumeCanvas.clientHeight; const r=visibleRange(); const data=r.data; vctx.clearRect(0,0,w,h); vctx.fillStyle='#fff'; vctx.fillRect(0,0,w,h);
 const left=7,right=w-54,top=8,bottom=h-25; drawGrid(vctx,left,right,top,bottom,3); const maxV=Math.max(...data.map(x=>x.volume),1); const step=(right-left)/data.length; const barW=clamp(step*0.72,5.5,17);
 data.forEach((bar,i)=>{{ const x=left+step*i+step/2; const bh=Math.max(1,(bar.volume/maxV)*(bottom-top)*0.92); vctx.fillStyle=bar.close>=bar.open?'#009b35':'#df0000'; vctx.fillRect(x-barW/2,bottom-bh,barW,bh); }});
 vctx.fillStyle='#666'; vctx.font='11px Arial'; vctx.textAlign='left'; vctx.textBaseline='middle'; vctx.fillText(niceVolume(maxV),right+5,top+2); vctx.textAlign='center'; vctx.textBaseline='top'; const ticks=Math.min(4,data.length-1); for(let i=0;i<=ticks;i++){{ const idx=Math.round(i*(data.length-1)/ticks); const x=left+step*idx+step/2; vctx.fillText(data[idx].date,x,bottom+7); }}
}}
function drawAll(){{ drawPrice(); drawVolume(); }}
function pointerToIndex(clientX){{ const rect=priceCanvas.getBoundingClientRect(); const left=7,right=rect.width-54; const frac=clamp((clientX-rect.left-left)/Math.max(1,right-left),0,1); return view.end-view.count+1+frac*view.count; }}
function start(e){{ if(e.touches&&e.touches.length===2){{ const a=e.touches[0],b=e.touches[1]; const dist=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY); const midX=(a.clientX+b.clientX)/2; pinch={{dist,count:view.count,end:view.end,center:pointerToIndex(midX)}}; drag=null; e.preventDefault(); return; }} const t=e.touches?e.touches[0]:e; drag={{x:t.clientX,end:view.end}}; }}
function move(e){{ if(pinch&&e.touches&&e.touches.length===2){{ const a=e.touches[0],b=e.touches[1]; const dist=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY); const rect=priceCanvas.getBoundingClientRect(); const midX=(a.clientX+b.clientX)/2; const frac=clamp((midX-rect.left-7)/Math.max(1,rect.width-61),0,1); view.count=clamp(pinch.count*pinch.dist/Math.max(10,dist),view.minCount,view.maxCount); view.end=pinch.center+view.count*(1-frac)-1; view.end=clamp(view.end,view.count-1,rows.length-1); drawAll(); e.preventDefault(); return; }} if(drag){{ const t=e.touches?e.touches[0]:e; const dx=t.clientX-drag.x; const rect=priceCanvas.getBoundingClientRect(); const pxPerBar=Math.max(1,(rect.width-61)/view.count); view.end=clamp(drag.end-dx/pxPerBar,view.count-1,rows.length-1); drawAll(); e.preventDefault(); }} }}
function end(e){{ if(e.touches&&e.touches.length>0){{ if(e.touches.length<2)pinch=null; return; }} pinch=null; drag=null; const now=Date.now(); if(now-lastTap<300){{ view.count=Math.min(58,rows.length); view.end=rows.length-1; drawAll(); }} lastTap=now; }}
function wheel(e){{ const center=pointerToIndex(e.clientX); const rect=priceCanvas.getBoundingClientRect(); const frac=clamp((e.clientX-rect.left-7)/Math.max(1,rect.width-61),0,1); view.count=clamp(view.count*(e.deltaY>0?1.12:0.88),view.minCount,view.maxCount); view.end=center+view.count*(1-frac)-1; view.end=clamp(view.end,view.count-1,rows.length-1); drawAll(); e.preventDefault(); }}
[priceCanvas,volumeCanvas].forEach(el=>{{ el.addEventListener('touchstart',start,{{passive:false}}); el.addEventListener('touchmove',move,{{passive:false}}); el.addEventListener('touchend',end,{{passive:false}}); el.addEventListener('mousedown',start); el.addEventListener('mousemove',e=>{{if(drag)move(e);}}); el.addEventListener('mouseup',end); el.addEventListener('mouseleave',end); el.addEventListener('wheel',wheel,{{passive:false}}); }});
window.addEventListener('resize',drawAll); setTimeout(drawAll,50); setTimeout(drawAll,250);
</script></body></html>
'''


if "idx" not in st.session_state:
    st.session_state.idx = 0

if "watchlist_text" not in st.session_state:
    st.session_state.watchlist_text = "SRL.AX, VNT.AX, SRG.AX, WGX.AX, NXT.AX, MAQ.AX, QBE.AX, SSM.AX"


with st.sidebar:
    st.header("Data")
    source = st.radio("Source", ["Yahoo tickers", "Upload spreadsheet"])

    if source == "Yahoo tickers":
        tickers_text = st.text_area("Tickers", key="watchlist_text", height=100)
        period = st.selectbox("History", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
        interval = st.selectbox("Interval", ["1d", "1wk"], index=0)
        uploaded = None
    else:
        uploaded = st.file_uploader("Upload CSV/XLSX", type=["csv", "xlsx", "xls"])
        tickers_text = ""
        period = "1y"
        interval = "1d"

    st.header("Display")
    candles_to_load = st.slider("Data loaded into chart", 60, 520, 220, step=20)
    show_sma = st.toggle("Show 20/50/200 averages", value=False)

    st.header("Filters")
    only_near_highs = st.toggle("Only within 10% of 52-week high", value=False)
    only_uptrend = st.toggle("Only 20 > 50 > 200 trend", value=False)


try:
    if source == "Upload spreadsheet":
        if uploaded is None:
            st.info("Upload a spreadsheet with Date, Ticker, Open, High, Low, Close, Volume.")
            st.stop()
        df = load_uploaded(uploaded)
    else:
        df = fetch_yahoo(tickers_text, period, interval)
        if df.empty:
            st.warning("No data returned. For ASX stocks, use .AX, e.g. SRL.AX or VNT.AX.")
            st.stop()

    tickers = sorted(df["Ticker"].dropna().unique().tolist())

    filtered = []
    for t in tickers:
        d = df[df["Ticker"] == t].copy()
        if len(d) < 20:
            continue

        dd = add_indicators(d)
        last = dd.iloc[-1]

        if only_near_highs and not (pd.notna(last["Dist52wPct"]) and last["Dist52wPct"] >= -10):
            continue

        if only_uptrend and not (
            pd.notna(last["SMA20"])
            and pd.notna(last["SMA50"])
            and pd.notna(last["SMA200"])
            and last["SMA20"] > last["SMA50"] > last["SMA200"]
        ):
            continue

        filtered.append(t)

    if not filtered:
        st.warning("No tickers passed the filters.")
        st.stop()

    st.session_state.idx %= len(filtered)

    col_prev, col_select, col_next = st.columns([1, 2.1, 1])

    with col_prev:
        if st.button("◀", use_container_width=True):
            st.session_state.idx = (st.session_state.idx - 1) % len(filtered)

    with col_select:
        selected = st.selectbox("Ticker", filtered, index=st.session_state.idx, label_visibility="collapsed")
        st.session_state.idx = filtered.index(selected)

    with col_next:
        if st.button("▶", type="primary", use_container_width=True):
            st.session_state.idx = (st.session_state.idx + 1) % len(filtered)

    ticker = filtered[st.session_state.idx]
    full_d = df[df["Ticker"] == ticker].copy().sort_values("Date")
    d = full_d.tail(candles_to_load)

    html = chart_html(d, ticker, show_sma=show_sma)
    components.html(html, height=760, scrolling=True)

except Exception as e:
    st.error(str(e))
