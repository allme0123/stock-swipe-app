
# stock_swipe_app.py
# Streamlit mobile-friendly stock chart swiper
#
# Run:
#   pip install streamlit pandas plotly openpyxl yfinance
#   streamlit run stock_swipe_app.py
#
# Input options:
#   1) Upload CSV/XLSX with columns like:
#      Date, Ticker, Open, High, Low, Close, Volume
#   2) Or type tickers and fetch from Yahoo Finance, e.g.:
#      BHP.AX, CBA.AX, WGX.AX, VNT.AX

import io
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

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
    .block-container {padding-top: 0.8rem; padding-left: 0.7rem; padding-right: 0.7rem;}
    div[data-testid="stMetric"] {background: rgba(127,127,127,0.08); padding: 8px; border-radius: 10px;}
    button[kind="primary"] {width: 100%;}
    button[kind="secondary"] {width: 100%;}
    .stTabs [data-baseweb="tab-list"] {gap: 6px;}
    </style>
    """,
    unsafe_allow_html=True,
)

REQUIRED = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    aliases = {
        "date": "Date",
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
    df = df.rename(columns=rename)
    return df


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
    df = df.sort_values(["Ticker", "Date"])
    return df


@st.cache_data(show_spinner=False)
def fetch_yahoo(tickers_text: str, period: str, interval: str) -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("yfinance is not installed. Run: pip install yfinance")
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
    d["Vol20"] = d["Volume"].rolling(20).mean()
    return d


def chart_for(d: pd.DataFrame, ticker: str, show_sma: bool, show_volume: bool):
    d = add_indicators(d)
    rows = 2 if show_volume else 1
    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.72, 0.28] if show_volume else [1.0],
    )
    fig.add_trace(
        go.Candlestick(
            x=d["Date"],
            open=d["Open"],
            high=d["High"],
            low=d["Low"],
            close=d["Close"],
            name=ticker,
        ),
        row=1,
        col=1,
    )
    if show_sma:
        fig.add_trace(go.Scatter(x=d["Date"], y=d["SMA20"], name="20 SMA", line=dict(width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=d["Date"], y=d["SMA50"], name="50 SMA", line=dict(width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=d["Date"], y=d["SMA200"], name="200 SMA", line=dict(width=1)), row=1, col=1)

    if show_volume:
        fig.add_trace(go.Bar(x=d["Date"], y=d["Volume"], name="Volume"), row=2, col=1)
        fig.add_trace(go.Scatter(x=d["Date"], y=d["Vol20"], name="20d vol avg", line=dict(width=1)), row=2, col=1)

    fig.update_layout(
        title=ticker,
        height=720,
        margin=dict(l=8, r=8, t=42, b=8),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        dragmode="pan",
    )
    return fig, d


def latest_stats(d: pd.DataFrame) -> dict:
    d = add_indicators(d)
    last = d.iloc[-1]
    prev = d.iloc[-2] if len(d) > 1 else last
    return {
        "close": last["Close"],
        "day_pct": ((last["Close"] / prev["Close"]) - 1) * 100 if prev["Close"] else 0,
        "dist_52w": last.get("Dist52wPct", float("nan")),
        "atr_pct": last.get("ATRPct", float("nan")),
        "date": last["Date"],
    }


if "idx" not in st.session_state:
    st.session_state.idx = 0
if "watchlist_text" not in st.session_state:
    st.session_state.watchlist_text = "BHP.AX, CBA.AX, WGX.AX, VNT.AX, SRG.AX, QBE.AX, NXT.AX, MAQ.AX"

st.title("Stock Swipe Charts")

with st.sidebar:
    st.header("Data")
    source = st.radio("Source", ["Yahoo tickers", "Upload spreadsheet"], horizontal=False)

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

    st.header("Chart")
    candles_to_show = st.slider("Candles to show", 30, 260, 120, step=10)
    show_sma = st.toggle("Show moving averages", value=True)
    show_volume = st.toggle("Show volume", value=True)

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
            st.warning("No data returned. For ASX stocks, use .AX, e.g. VNT.AX.")
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

    col_prev, col_select, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("◀ Prev", use_container_width=True):
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
        if st.button("Next ▶", type="primary", use_container_width=True):
            st.session_state.idx = (st.session_state.idx + 1) % len(filtered)

    ticker = filtered[st.session_state.idx]
    d = df[df["Ticker"] == ticker].copy().sort_values("Date").tail(candles_to_show)
    fig, dd = chart_for(d, ticker, show_sma, show_volume)
    stats = latest_stats(df[df["Ticker"] == ticker].copy().sort_values("Date"))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Close", f"{stats['close']:.3f}", f"{stats['day_pct']:.2f}%")
    m2.metric("52w distance", "n/a" if pd.isna(stats["dist_52w"]) else f"{stats['dist_52w']:.1f}%")
    m3.metric("ATR %", "n/a" if pd.isna(stats["atr_pct"]) else f"{stats['atr_pct']:.2f}%")
    m4.metric("Chart", f"{st.session_state.idx + 1}/{len(filtered)}")

    st.plotly_chart(fig, use_container_width=True, config={
        "scrollZoom": True,
        "displayModeBar": False,
        "responsive": True,
    })

    st.caption("Phone use: tap Next/Prev, or use the ticker dropdown. Plotly lets you pinch/zoom and drag the chart.")

except Exception as e:
    st.error(str(e))
