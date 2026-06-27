
# stock_swipe_app.py
# Mobile-friendly ASX stock chart swiper with crisp CommSec-style candles.
#
# Run:
#   pip install streamlit pandas openpyxl yfinance
#   streamlit run stock_swipe_app.py
#
# Input:
#   1) Type Yahoo tickers, e.g. VNT.AX, SRG.AX, WGX.AX
#   2) Or upload CSV/XLSX with columns:
#      Date, Ticker, Open, High, Low, Close, Volume

import io
import json
import math
from datetime import datetime

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
    .block-container {
        padding-top: 0.45rem;
        padding-left: 0.35rem;
        padding-right: 0.35rem;
        padding-bottom: 0.2rem;
        max-width: 100%;
    }
    h1, h2, h3 { margin-top: 0.2rem; margin-bottom: 0.2rem; }
    div[data-testid="stMetric"] {
        background: #f7f7f5;
        border: 1px solid #e2e2df;
        padding: 5px 7px;
        border-radius: 8px;
    }
    button[kind="primary"], button[kind="secondary"] {
        width: 100%;
        height: 2.6rem;
        border-radius: 10px;
    }
    .stSelectbox { margin-bottom: 0.25rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

REQUIRED = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
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
    for c in df.columns:
        key = str(c).strip().lower()
        if key in aliases:
            rename[c] = aliases[key]
    return df.rename(columns=rename)


def load_uploaded(file) -> pd.DataFrame:
    name = file.name.lower()
    data = file.read()
    if name.endswith(".csv"):
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

    df = df.dropna(subset=["Date", "Ticker", "Open", "High", "Low", "Close"])
    return df.sort_values(["Ticker", "Date"])


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
    df = df.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    return df.sort_values(["Ticker", "Date"])


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


def chart_html(d: pd.DataFrame, ticker: str, show_sma: bool = True) -> str:
    d = add_indicators(d).copy()

    candle_data = []
    volume_data = []
    sma20_data = []
    sma50_data = []
    sma200_data = []

    for _, r in d.iterrows():
        t = int(pd.Timestamp(r["Date"]).timestamp())
        o = clean_number(r["Open"])
        h = clean_number(r["High"])
        l = clean_number(r["Low"])
        c = clean_number(r["Close"])
        v = clean_number(r["Volume"], 0)

        if None in [o, h, l, c]:
            continue

        is_up = c >= o
        candle_data.append({"time": t, "open": o, "high": h, "low": l, "close": c})
        volume_data.append({
            "time": t,
            "value": v,
            "color": "#00b050" if is_up else "#ff1f1f",
        })

        if show_sma:
            s20 = clean_number(r.get("SMA20"))
            s50 = clean_number(r.get("SMA50"))
            s200 = clean_number(r.get("SMA200"))

            if s20 is not None:
                sma20_data.append({"time": t, "value": s20})
            if s50 is not None:
                sma50_data.append({"time": t, "value": s50})
            if s200 is not None:
                sma200_data.append({"time": t, "value": s200})

    last = d.iloc[-1]
    prev = d.iloc[-2] if len(d) > 1 else last
    close = float(last["Close"])
    change = close - float(prev["Close"])
    change_pct = (change / float(prev["Close"]) * 100) if float(prev["Close"]) else 0
    arrow = "▲" if change >= 0 else "▼"
    change_colour = "#138a22" if change >= 0 else "#d60000"

    high = float(last["High"])
    low = float(last["Low"])
    date_text = pd.Timestamp(last["Date"]).strftime("%-d/%-m/%Y") if hasattr(pd.Timestamp(last["Date"]), "strftime") else ""

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
    html, body {{
        margin: 0;
        padding: 0;
        background: #ffffff;
        font-family: Arial, Helvetica, sans-serif;
        overflow: hidden;
        touch-action: pan-x pan-y;
    }}
    .wrap {{
        width: 100%;
        height: 100vh;
        background: white;
        box-sizing: border-box;
    }}
    .topbar {{
        display: flex;
        align-items: baseline;
        gap: 8px;
        padding: 4px 7px 2px 7px;
        border-bottom: 1px solid #eee;
        white-space: nowrap;
        overflow: hidden;
    }}
    .ticker {{
        font-weight: 700;
        font-size: 22px;
        color: #000;
    }}
    .price {{
        font-weight: 700;
        font-size: 20px;
        color: #000;
    }}
    .change {{
        font-weight: 700;
        font-size: 18px;
        color: {change_colour};
    }}
    .toolbar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #707070;
        background: #f5f4f1;
        font-size: 14px;
        padding: 5px 7px;
        border-bottom: 1px solid #e2e2df;
    }}
    .ohlc {{
        display: flex;
        justify-content: space-around;
        font-size: 13px;
        color: #5b5b5b;
        padding: 2px 4px;
    }}
    #chart {{
        width: 100%;
        height: calc(100vh - 78px);
    }}
</style>
</head>
<body>
<div class="wrap">
    <div class="topbar">
        <span class="ticker">{ticker.replace(".AX", ":ASX")}</span>
        <span class="price">${close:.3f}</span>
        <span class="change">{arrow} ${abs(change):.3f} ({change_pct:.2f}%)</span>
    </div>

    <div class="toolbar">
        <span>Daily</span>
        <span>Candlestick</span>
        <span>Pinch / drag enabled</span>
    </div>

    <div class="ohlc">
        <span>H ${high:.2f}</span>
        <span>L ${low:.2f}</span>
        <span>C ${close:.2f}</span>
        <span>{date_text}</span>
    </div>

    <div id="chart"></div>
</div>

<script>
const candles = {json.dumps(candle_data)};
const volumes = {json.dumps(volume_data)};
const sma20 = {json.dumps(sma20_data)};
const sma50 = {json.dumps(sma50_data)};
const sma200 = {json.dumps(sma200_data)};

const chartEl = document.getElementById('chart');

const chart = LightweightCharts.createChart(chartEl, {{
    width: chartEl.clientWidth,
    height: chartEl.clientHeight,
    layout: {{
        background: {{ color: '#ffffff' }},
        textColor: '#8a8a8a',
        fontSize: 12,
        fontFamily: 'Arial, Helvetica, sans-serif'
    }},
    grid: {{
        vertLines: {{ color: '#dddddd', style: 0, visible: true }},
        horzLines: {{ color: '#dddddd', style: 0, visible: true }}
    }},
    rightPriceScale: {{
        borderColor: '#cfcfcf',
        scaleMargins: {{
            top: 0.05,
            bottom: 0.28
        }}
    }},
    timeScale: {{
        borderColor: '#cfcfcf',
        rightOffset: 2,
        barSpacing: 12,
        minBarSpacing: 5,
        fixLeftEdge: false,
        fixRightEdge: false,
        lockVisibleTimeRangeOnResize: true,
        rightBarStaysOnScroll: false,
        timeVisible: false,
        secondsVisible: false
    }},
    handleScroll: {{
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true
    }},
    handleScale: {{
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true
    }},
    crosshair: {{
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: {{ color: '#999999', width: 1, style: 3 }},
        horzLine: {{ color: '#999999', width: 1, style: 3 }}
    }}
}});

const candleSeries = chart.addCandlestickSeries({{
    upColor: '#ffffff',
    downColor: '#ff1f1f',
    borderUpColor: '#22c645',
    borderDownColor: '#ff1f1f',
    wickUpColor: '#22c645',
    wickDownColor: '#ff1f1f',
    priceLineColor: '#1278a8',
    priceLineWidth: 2,
    priceLineVisible: true,
    lastValueVisible: true
}});
candleSeries.setData(candles);

const volumeSeries = chart.addHistogramSeries({{
    priceFormat: {{ type: 'volume' }},
    priceScaleId: '',
    scaleMargins: {{
        top: 0.78,
        bottom: 0.00
    }}
}});
volumeSeries.setData(volumes);

if (sma20.length > 0) {{
    const s20 = chart.addLineSeries({{
        color: '#777777',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false
    }});
    s20.setData(sma20);
}}

if (sma50.length > 0) {{
    const s50 = chart.addLineSeries({{
        color: '#b0b0b0',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false
    }});
    s50.setData(sma50);
}}

if (sma200.length > 0) {{
    const s200 = chart.addLineSeries({{
        color: '#d0d0d0',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false
    }});
    s200.setData(sma200);
}}

if (candles.length > 5) {{
    const barsToShow = Math.min(45, candles.length);
    chart.timeScale().setVisibleLogicalRange({{
        from: candles.length - barsToShow,
        to: candles.length + 1
    }});
}}

function resizeChart() {{
    chart.applyOptions({{
        width: chartEl.clientWidth,
        height: chartEl.clientHeight
    }});
}}
window.addEventListener('resize', resizeChart);
setTimeout(resizeChart, 250);
</script>
</body>
</html>
"""


def latest_stats(d: pd.DataFrame) -> dict:
    d = add_indicators(d)
    last = d.iloc[-1]
    prev = d.iloc[-2] if len(d) > 1 else last
    return {
        "close": float(last["Close"]),
        "day_pct": ((float(last["Close"]) / float(prev["Close"])) - 1) * 100 if float(prev["Close"]) else 0,
        "dist_52w": last.get("Dist52wPct", float("nan")),
        "atr_pct": last.get("ATRPct", float("nan")),
    }


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
    candles_to_load = st.slider("Data loaded into chart", 60, 520, 180, step=20)
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
        selected = st.selectbox(
            "Ticker",
            filtered,
            index=st.session_state.idx,
            label_visibility="collapsed",
        )
        st.session_state.idx = filtered.index(selected)

    with col_next:
        if st.button("▶", type="primary", use_container_width=True):
            st.session_state.idx = (st.session_state.idx + 1) % len(filtered)

    ticker = filtered[st.session_state.idx]
    full_d = df[df["Ticker"] == ticker].copy().sort_values("Date")
    d = full_d.tail(candles_to_load)

    html = chart_html(d, ticker, show_sma=show_sma)
    components.html(html, height=760, scrolling=False)

except Exception as e:
    st.error(str(e))
