
# stock_swipe_app.py
# Mobile-friendly ASX stock chart swiper with crisp CommSec-style candles.
# Version: v16 chart spacing and layout refinements
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
    d["VolumeSMA14"] = d["Volume"].rolling(14).mean()
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
            "volumeSma14": clean_number(r.get("VolumeSMA14")),
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
html, body {{ margin:0; padding:0; width:100%; background:#fff; font-family:Arial, Helvetica, sans-serif; overscroll-behavior:auto; -webkit-tap-highlight-color:transparent; overflow-y:auto; }}
.wrap {{ width:100%; background:#fff; box-sizing:border-box; padding:0 9px 16px 9px; }}
.topbar {{ display:flex; align-items:baseline; gap:7px; height:25px; padding:0 5px; border-bottom:1px solid #ededed; white-space:nowrap; overflow:hidden; box-sizing:border-box; }}
.ticker {{ font-weight:700; font-size:18px; color:#000; }} .price {{ font-weight:700; font-size:16px; color:#000; }} .change {{ font-weight:700; font-size:15px; color:{change_colour}; }}
.toolbar {{ display:flex; justify-content:space-between; align-items:center; height:22px; color:#666; background:#f3f2ef; font-size:12px; padding:0 7px; border-bottom:1px solid #dededa; box-sizing:border-box; }}
.ohlc {{ display:flex; justify-content:space-around; align-items:center; height:23px; font-size:12px; color:#555; box-sizing:border-box; }}
.panel {{ margin:0 10px 4px 10px; border:1px solid #bdbdbd; background:#fff; box-sizing:border-box; }}
.panel-title {{ height:20px; display:flex; align-items:center; gap:6px; padding-left:6px; color:#666; font-size:12px; border-bottom:1px solid #e1e1e1; background:#f8f8f6; box-sizing:border-box; }}
.legend-price, .legend-volume {{ width:15px; height:12px; border-left:7px solid #00a33a; border-right:7px solid #df0000; box-sizing:border-box; }}
#priceCanvas {{ width:100%; height:423px; display:block; touch-action:pan-y pinch-zoom; }}
#volumeCanvas {{ width:100%; height:155px; display:block; touch-action:pan-y pinch-zoom; }}
.scroll-gap {{ height:10px; margin:0 10px 0 10px; background:#fff; touch-action:pan-y; display:flex; align-items:center; justify-content:center; color:#c0c0c0; font-size:11px; }}
.hint {{ font-size:11px; color:#8a8a8a; text-align:center; margin-top:4px; padding-bottom:2px; }}
.sma-button {{ display:block; width:calc(100% - 20px); margin:8px 10px 4px 10px; height:40px; border:1px solid #777; border-radius:8px; background:#f3f3f3; color:#222; font-size:14px; font-weight:700; }}
.sma-button.on {{ background:#1679a5; color:#fff; border-color:#1679a5; }}
@media (max-height:760px) {{ #priceCanvas {{ height:387px; }} #volumeCanvas {{ height:142px; }} }}
@media (max-height:690px) {{ #priceCanvas {{ height:351px; }} #volumeCanvas {{ height:128px; }} }}
</style></head><body>
<div class="wrap">
<div class="topbar"><span class="ticker">{safe_ticker}</span><span class="price">${close:.3f}</span><span class="change">{arrow} ${abs(change):.3f} ({change_pct:.2f}%)</span></div>
<div class="toolbar"><span>Daily</span><span id="chartModeLabel">Candle</span><span>Drag / pinch zoom</span></div>
<div class="ohlc"><span>H ${high:.2f}</span><span>L ${low:.2f}</span><span>C ${close:.2f}</span><span>{date_str}</span></div>
<div class="panel"><div class="panel-title"><span class="legend-price"></span><span>Price</span></div><canvas id="priceCanvas"></canvas></div>
<div class="scroll-gap"></div>
<div class="panel"><div class="panel-title"><span class="legend-volume"></span><span>Volume · 14-day average</span></div><canvas id="volumeCanvas"></canvas></div>
<button id="sma20Button" class="sma-button" type="button">20-DAY SMA: OFF</button>
<div class="hint">Double tap quickly in the same spot to toggle candle / line</div>
<div style="height:220px"></div>
</div>
<script>
const rows = {json.dumps(rows)};
let showSma = {str(bool(show_sma)).lower()};
try {{ const savedSma=localStorage.getItem('stockSwipeSma20'); if(savedSma!==null) showSma=savedSma==='true'; }} catch(e) {{}}
const priceCanvas = document.getElementById('priceCanvas');
const volumeCanvas = document.getElementById('volumeCanvas');
const pctx = priceCanvas.getContext('2d');
const vctx = volumeCanvas.getContext('2d');
const sma20Button = document.getElementById('sma20Button');

// The view is deliberately not clamped to the first/last candle.
// This copies CommSec-style behaviour where you can pan into blank space
// before the first bar and after the latest bar.
let savedView=null; try{{savedView=JSON.parse(localStorage.getItem('stockSwipeView')||'null');}}catch(e){{}}
let view={{count:savedView&&Number.isFinite(savedView.count)?savedView.count:Math.min(95,rows.length+30),end:savedView&&Number.isFinite(savedView.end)?savedView.end:rows.length-1+10,minCount:8}};
let chartMode=savedView&&savedView.chartMode==='line'?'line':'candle';
let lastTap = 0, lastTapX = null, lastTapY = null, drag = null, pinch = null;
let gestureMode = null; // null, pan-x, pan-y
let ignoreSingleTouchUntilEnd = false;

function clamp(v, lo, hi) {{ return Math.max(lo, Math.min(hi, v)); }}
function setupCanvas(canvas, ctx) {{
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    canvas.width = Math.max(1, Math.floor(w*dpr));
    canvas.height = Math.max(1, Math.floor(h*dpr));
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.imageSmoothingEnabled = false;
}}
function chartBounds(canvas, axisPad=62) {{
    // Keep the price labels fully inside the canvas and balance the date spacing.
    return {{ left: 9, right: canvas.clientWidth - axisPad, top: 10, bottom: canvas.clientHeight - 22 }};
}}
function maxZoomOut(canvas) {{
    const b = chartBounds(canvas);
    // Allow extreme zoom-out so even the longest loaded history can fit on screen.
    // At this level candles stay hairline-thin rather than being clipped by the data length.
    const allDataPlusBlank = rows.length + Math.max(80, Math.round(rows.length * 0.18));
    const pixelExtreme = Math.floor((b.right - b.left) / 0.62);
    return Math.max(120, Math.min(allDataPlusBlank, pixelExtreme));
}}
function clampView(canvas=priceCanvas) {{
    const maxCount = maxZoomOut(canvas);
    view.count = clamp(view.count, view.minCount, maxCount);
    const emptyLeft = Math.max(25, Math.round(view.count * 0.65));
    const emptyRight = Math.max(35, Math.round(view.count * 0.85));
    const minEnd = -emptyLeft + view.count - 1;
    const maxEnd = rows.length - 1 + emptyRight;
    view.end = clamp(view.end, minEnd, maxEnd);
}}
function visibleMeta(canvas=priceCanvas) {{
    clampView(canvas);
    const start = view.end - view.count + 1;
    const end = view.end;
    const lo = Math.max(0, Math.floor(start) - 2);
    const hi = Math.min(rows.length - 1, Math.ceil(end) + 2);
    const data = [];
    for (let i = lo; i <= hi; i++) data.push({{...rows[i], idx:i}});
    return {{start,end,data}};
}}
function niceStep(range, targetTicks=5) {{
    const rough=Math.max(range/targetTicks,1e-9), pow=Math.pow(10,Math.floor(Math.log10(rough))), n=rough/pow;
    return (n<=1?1:n<=2?2:n<=5?5:10)*pow;
}}
function priceDecimals(step) {{ if(step>=1)return 0; if(step>=0.1)return 1; if(step>=0.01)return 2; if(step>=0.001)return 3; return 4; }}
function fmtPrice(x,step=1) {{ return Number(x).toFixed(priceDecimals(step)); }}
function niceVolume(x) {{ if (x>=1000000000) return (x/1000000000).toFixed(1)+'B'; if (x>=1000000) return (x/1000000).toFixed(1)+'M'; if (x>=1000) return (x/1000).toFixed(0)+'K'; return String(Math.round(x)); }}
function drawGrid(ctx, left, right, top, bottom, yTicks) {{
    ctx.strokeStyle='#e7e7e7'; ctx.lineWidth=0.65;
    for(let i=0;i<=yTicks;i++){{ const y=Math.round(top+(bottom-top)*i/yTicks)+0.5; ctx.beginPath(); ctx.moveTo(left,y); ctx.lineTo(right,y); ctx.stroke(); }}
    for(let i=0;i<=4;i++){{ const x=Math.round(left+(right-left)*i/4)+0.5; ctx.beginPath(); ctx.moveTo(x,top); ctx.lineTo(x,bottom); ctx.stroke(); }}
}}
function dateTicks(meta) {{
    const ticks = [];
    const visibleBars = Math.max(1, meta.end - meta.start + 1);
    // Dense labels while zoomed in, progressively wider spacing while zooming out.
    // Around 15-30 visible daily bars this produces a label every second trading day.
    let step;
    if (visibleBars <= 14) step = 2;
    else if (visibleBars <= 32) step = 4;
    else if (visibleBars <= 65) step = 10;
    else if (visibleBars <= 130) step = 20;
    else if (visibleBars <= 260) step = 40;
    else step = 80;
    let first = Math.ceil(meta.start / step) * step;
    for (let idx = first; idx <= meta.end; idx += step) {{
        const r = rows[Math.round(idx)];
        if (r) ticks.push({{idx: Math.round(idx), label: r.date}});
    }}
    return ticks;
}}
function xForIdx(idx, left, right, meta) {{ return left + ((idx - meta.start) / view.count) * (right - left); }}

function drawPrice() {{
    setupCanvas(priceCanvas,pctx);
    const w=priceCanvas.clientWidth,h=priceCanvas.clientHeight;
    const b=chartBounds(priceCanvas,62); const left=b.left,right=b.right,top=b.top,bottom=b.bottom;
    const meta=visibleMeta(priceCanvas); const data=meta.data.filter(bar => bar.idx >= meta.start-1 && bar.idx <= meta.end+1);
    pctx.clearRect(0,0,w,h); pctx.fillStyle='#fff'; pctx.fillRect(0,0,w,h); drawGrid(pctx,left,right,top,bottom,5);

    const priceData = data.length ? data : rows.map((r,i)=>({{...r,idx:i}})).slice(-50);
    let minP=Math.min(...priceData.map(x=>x.low)), maxP=Math.max(...priceData.map(x=>x.high));
    if(showSma){{ for(const k of ['sma20']){{ const vals=priceData.map(x=>x[k]).filter(x=>x!==null&&Number.isFinite(x)); if(vals.length){{ minP=Math.min(minP,...vals); maxP=Math.max(maxP,...vals); }} }} }}
    const rawRange=Math.max(maxP-minP,Math.abs(maxP)*0.01,0.01);
    const pad=rawRange*0.18; minP-=pad; maxP+=pad;
    const tickStep=niceStep(maxP-minP,5); minP=Math.floor(minP/tickStep)*tickStep; maxP=Math.ceil(maxP/tickStep)*tickStep;
    const y=val=>bottom-(val-minP)/(maxP-minP)*(bottom-top);
    const step=(right-left)/view.count;
    // CommSec-style: candle bodies expand as you pinch in, but never fully touch.
    const bodyW=Math.max(0.55, Math.min(step*0.58, 54));

    pctx.fillStyle='#666'; pctx.font='11px Arial'; pctx.textAlign='left'; pctx.textBaseline='middle';
    const yTicks=Math.max(2,Math.round((maxP-minP)/tickStep));
    for(let i=0;i<=yTicks;i++){{ const val=maxP-tickStep*i; if(val<minP-1e-9)continue; pctx.fillText(fmtPrice(val,tickStep),right+5,y(val)); }}

    function drawLine(key,color){{
        pctx.strokeStyle=color; pctx.lineWidth=0.85; let started=false;
        data.forEach(bar=>{{ const val=bar[key]; if(val===null||!Number.isFinite(val)){{started=false; return;}} const x=xForIdx(bar.idx,left,right,meta)+step/2, yy=y(val); if(x<left-5||x>right+5) return; if(!started){{pctx.beginPath(); pctx.moveTo(x,yy); started=true;}} else pctx.lineTo(x,yy); }});
        if(started)pctx.stroke();
    }}
    if(showSma){{ drawLine('sma20','#777'); }}

    pctx.save(); pctx.beginPath(); pctx.rect(left,top,right-left,bottom-top); pctx.clip();
    if(chartMode==='line'){{
        pctx.strokeStyle='#1679a5'; pctx.lineWidth=1.5; let started=false;
        data.forEach(bar=>{{ const x=xForIdx(bar.idx,left,right,meta)+step/2, yy=y(bar.close); if(x<left-step||x>right+step)return; if(!started){{pctx.beginPath();pctx.moveTo(x,yy);started=true;}} else pctx.lineTo(x,yy); }});
        if(started)pctx.stroke();
    }} else {{
        data.forEach(bar=>{{
            const x=xForIdx(bar.idx,left,right,meta)+step/2; if(x<left-bodyW/2||x>right+bodyW/2) return;
            const up=bar.close>=bar.open; const col=up?'#009735':'#d90000';
            const yo=y(bar.open),yc=y(bar.close),yh=y(bar.high),yl=y(bar.low);
            const bodyTop=Math.min(yo,yc), bodyBot=Math.max(yo,yc), bh=Math.max(1.0,bodyBot-bodyTop);
            pctx.strokeStyle=col; pctx.lineWidth=0.72; pctx.beginPath(); pctx.moveTo(Math.round(x)+0.5,yh); pctx.lineTo(Math.round(x)+0.5,yl); pctx.stroke();
            if(up){{ pctx.fillStyle='#fff'; pctx.strokeStyle=col; pctx.lineWidth=0.72; pctx.fillRect(x-bodyW/2,bodyTop,bodyW,bh); pctx.strokeRect(x-bodyW/2,bodyTop,bodyW,bh); }}
            else {{ pctx.fillStyle=col; pctx.fillRect(x-bodyW/2,bodyTop,bodyW,bh); }}
        }});
    }}
    pctx.restore();

    const lastIdx=rows.length-1, last=rows[lastIdx], lx=xForIdx(lastIdx,left,right,meta)+step/2, ly=y(last.close);
    if(ly>=top&&ly<=bottom){{
        pctx.strokeStyle='#1679a5'; pctx.lineWidth=0.8; pctx.setLineDash([4,3]); pctx.beginPath(); pctx.moveTo(left,ly); pctx.lineTo(right,ly); pctx.stroke(); pctx.setLineDash([]);
        pctx.fillStyle='#1679a5'; const label=fmtPrice(last.close,tickStep); pctx.fillRect(right+2,ly-10,49,20); pctx.fillStyle='#fff'; pctx.font='bold 11px Arial'; pctx.textAlign='center'; pctx.textBaseline='middle'; pctx.fillText(label,right+26.5,ly);
    }}

    pctx.fillStyle='#6e6e6e'; pctx.font='10px Arial'; pctx.textAlign='center'; pctx.textBaseline='top';
    for(const t of dateTicks(meta)){{ const x=xForIdx(t.idx,left,right,meta)+step/2; if(x<left+25||x>right-25)continue; const a=t.label.split('/'); if(a.length===3){{ const label=a[0].padStart(2,'0')+'/'+a[1].padStart(2,'0')+'/'+a[2].slice(-2); pctx.fillText(label,x,bottom+6); }} }}
}}

function drawVolume() {{
    setupCanvas(volumeCanvas,vctx);
    const w=volumeCanvas.clientWidth,h=volumeCanvas.clientHeight;
    const b=chartBounds(volumeCanvas,50); const left=b.left,right=b.right,top=8,bottom=h-20;
    const meta=visibleMeta(volumeCanvas); const data=meta.data.filter(bar => bar.idx >= meta.start-1 && bar.idx <= meta.end+1);
    vctx.clearRect(0,0,w,h); vctx.fillStyle='#fff'; vctx.fillRect(0,0,w,h); drawGrid(vctx,left,right,top,bottom,3);
    const volData = data.length ? data : rows.map((r,i)=>({{...r,idx:i}})).slice(-50);
    const avgVals=volData.map(x=>x.volumeSma14).filter(x=>x!==null&&Number.isFinite(x));
    const maxV=Math.max(...volData.map(x=>x.volume),...(avgVals.length?avgVals:[1]),1);
    // Volume bars also widen while zooming in, keeping a CommSec-like gap.
    const step=(right-left)/view.count; const barW=Math.max(0.5, Math.min(step*0.56, 56));
    data.forEach(bar=>{{ const x=xForIdx(bar.idx,left,right,meta)+step/2; if(x<left-3||x>right+3) return; const bh=Math.max(1,(bar.volume/maxV)*(bottom-top)*0.9); vctx.fillStyle=bar.close>=bar.open?'#009735':'#d90000'; vctx.fillRect(x-barW/2,bottom-bh,barW,bh); }});
    // 14-day simple moving average through the volume bars.
    vctx.save(); vctx.beginPath(); vctx.rect(left,top,right-left,bottom-top); vctx.clip();
    vctx.strokeStyle='#1679a5'; vctx.lineWidth=1.6; let avgStarted=false;
    data.forEach(bar=>{{
        const val=bar.volumeSma14;
        if(val===null||!Number.isFinite(val)){{avgStarted=false;return;}}
        const x=xForIdx(bar.idx,left,right,meta)+step/2;
        const yy=bottom-(val/maxV)*(bottom-top)*0.9;
        if(x<left-step||x>right+step)return;
        if(!avgStarted){{vctx.beginPath();vctx.moveTo(x,yy);avgStarted=true;}} else vctx.lineTo(x,yy);
    }});
    if(avgStarted)vctx.stroke(); vctx.restore();
    vctx.fillStyle='#666'; vctx.font='11px Arial'; vctx.textAlign='left'; vctx.textBaseline='middle'; vctx.fillText(niceVolume(maxV),right+5,top+2);
}}
function persistView(){{try{{localStorage.setItem('stockSwipeView',JSON.stringify({{count:view.count,end:view.end,chartMode}}));}}catch(e){{}}}}
function drawAll(){{document.getElementById('chartModeLabel').textContent=chartMode==='line'?'Line':'Candle';sma20Button.textContent=showSma?'20-DAY SMA: ON':'20-DAY SMA: OFF';sma20Button.classList.toggle('on',showSma);drawPrice();drawVolume();persistView();}}
function pointerToIndex(clientX, canvas=priceCanvas){{ const rect=canvas.getBoundingClientRect(); const b=chartBounds(canvas); const frac=(clientX-rect.left-b.left)/Math.max(1,b.right-b.left); return view.end-view.count+1+frac*view.count; }}
function start(e){{
    gestureMode = null;
    if(e.touches&&e.touches.length===2){{
        const a=e.touches[0],b=e.touches[1];
        const dist=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);
        const midX=(a.clientX+b.clientX)/2;
        const rect=priceCanvas.getBoundingClientRect();
        const bnd=chartBounds(priceCanvas);
        const frac=(midX-rect.left-bnd.left)/Math.max(1,bnd.right-bnd.left);
        // Two-finger mode is locked to zoom only. Sideways movement of either finger is ignored.
        // The chart stays anchored to the original midpoint from the moment the pinch starts.
        pinch={{dist,count:view.count,end:view.end,center:pointerToIndex(midX),frac:frac}};
        drag=null;
        ignoreSingleTouchUntilEnd = true;
        e.preventDefault();
        return;
    }}
    if(ignoreSingleTouchUntilEnd) return;
    const t=e.touches?e.touches[0]:e;
    drag={{x:t.clientX,y:t.clientY,lastY:t.clientY,end:view.end}};
}}
function move(e){{
    if(e.touches && e.touches.length===2){{
        if(!pinch){{
            const a=e.touches[0],b=e.touches[1];
            const dist=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);
            const midX=(a.clientX+b.clientX)/2;
            const rect=priceCanvas.getBoundingClientRect();
            const bnd=chartBounds(priceCanvas);
            const frac=(midX-rect.left-bnd.left)/Math.max(1,bnd.right-bnd.left);
            pinch={{dist,count:view.count,end:view.end,center:pointerToIndex(midX),frac:frac}};
            drag=null;
            ignoreSingleTouchUntilEnd = true;
        }}
        const a=e.touches[0],b=e.touches[1];
        const dist=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);
        view.count=pinch.count*pinch.dist/Math.max(10,dist);
        // Keep the original pinch midpoint fixed. Do not use the moving midpoint,
        // because that allows accidental side-to-side panning with two fingers.
        view.end=pinch.center+view.count*(1-pinch.frac)-1;
        clampView(priceCanvas); drawAll(); e.preventDefault(); return;
    }}
    if(e.touches && e.touches.length===1 && ignoreSingleTouchUntilEnd){{
        e.preventDefault();
        return;
    }}
    if(drag){{
        const t=e.touches?e.touches[0]:e;
        const dx=t.clientX-drag.x;
        const dy=t.clientY-drag.y;
        if(gestureMode===null && (Math.abs(dx)>5 || Math.abs(dy)>5)){{
            gestureMode = Math.abs(dy) > Math.abs(dx)*1.15 ? 'pan-y' : 'pan-x';
        }}
        // One-finger vertical movement should behave like a normal web page.
        // Do not preventDefault here; Android/Chrome then provides native momentum/inertia scrolling.
        if(gestureMode==='pan-y'){{
            drag.lastY = t.clientY;
            return;
        }}
        if(gestureMode==='pan-x'){{
            const rect=priceCanvas.getBoundingClientRect();
            const bnd=chartBounds(priceCanvas);
            const pxPerBar=Math.max(1,(bnd.right-bnd.left)/view.count);
            view.end=drag.end-dx/pxPerBar;
            clampView(priceCanvas); drawAll(); e.preventDefault();
        }}
    }}
}}
function end(e){{
    if(e.touches&&e.touches.length>0){{
        // Once a two-finger gesture has started, do not fall back into one-finger pan
        // when one finger lifts first. Wait until all fingers are off the screen.
        if(ignoreSingleTouchUntilEnd){{ pinch=null; drag=null; gestureMode=null; e.preventDefault(); }}
        return;
    }}
    const wasVertical = gestureMode==='pan-y';
    const wasPinch = ignoreSingleTouchUntilEnd;
    pinch=null; drag=null; gestureMode=null; ignoreSingleTouchUntilEnd=false;
    if(wasVertical || wasPinch) return;
    const now=Date.now();
    const src=e.changedTouches&&e.changedTouches.length?e.changedTouches[0]:e;
    const tx=Number.isFinite(src.clientX)?src.clientX:null, ty=Number.isFinite(src.clientY)?src.clientY:null;
    const sameSpot=tx!==null&&lastTapX!==null&&Math.hypot(tx-lastTapX,ty-lastTapY)<=24;
    if(now-lastTap<280 && sameSpot){{chartMode=chartMode==='line'?'candle':'line';lastTap=0;lastTapX=null;lastTapY=null;drawAll();return;}}
    lastTap=now;lastTapX=tx;lastTapY=ty;
}}
function wheel(e){{ const center=pointerToIndex(e.clientX); const rect=priceCanvas.getBoundingClientRect(); const bnd=chartBounds(priceCanvas); const frac=(e.clientX-rect.left-bnd.left)/Math.max(1,bnd.right-bnd.left); view.count=view.count*(e.deltaY>0?1.12:0.88); view.end=center+view.count*(1-frac)-1; clampView(priceCanvas); drawAll(); e.preventDefault(); }}
sma20Button.addEventListener('click',()=>{{showSma=!showSma;try{{localStorage.setItem('stockSwipeSma20',String(showSma));}}catch(e){{}}drawAll();}});
[priceCanvas,volumeCanvas].forEach(el=>{{ el.addEventListener('touchstart',start,{{passive:false}}); el.addEventListener('touchmove',move,{{passive:false}}); el.addEventListener('touchend',end,{{passive:false}}); el.addEventListener('touchcancel',end,{{passive:false}}); el.addEventListener('mousedown',start); el.addEventListener('mousemove',e=>{{if(drag)move(e);}}); el.addEventListener('mouseup',end); el.addEventListener('mouseleave',end); el.addEventListener('wheel',wheel,{{passive:false}}); }});
window.addEventListener('resize',drawAll); setTimeout(drawAll,50); setTimeout(drawAll,250);</script></body></html>
'''


if "idx" not in st.session_state:
    st.session_state.idx = 0

if "show_sma20" not in st.session_state:
    st.session_state.show_sma20 = False

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
    st.caption("The full-width 20-day SMA button is directly above the stock controls.")

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

    html = chart_html(d, ticker, show_sma=False)
    components.html(html, height=720, scrolling=True)

except Exception as e:
    st.error(str(e))
