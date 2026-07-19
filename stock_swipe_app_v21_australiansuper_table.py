# stock_swipe_app_v21_australiansuper_table.py
# Mobile-first ASX stock table with sticky columns, sortable headers,
# inline expandable charts, watchlists and action menus.
#
# Run:
#   pip install streamlit pandas openpyxl yfinance
#   streamlit run stock_swipe_app_v21_australiansuper_table.py

import io
import json
import math
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    import yfinance as yf
except Exception:
    yf = None


st.set_page_config(
    page_title="ASX Stock Table",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { height: 0rem; }
    .block-container {
        padding-top: 0.10rem;
        padding-left: 0.10rem;
        padding-right: 0.10rem;
        padding-bottom: 0.10rem;
        max-width: 100%;
    }
    iframe { width: 100%; border: none; display: block; }
    </style>
    """,
    unsafe_allow_html=True,
)

REQUIRED = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]
OPTIONAL = ["Company"]

DEFAULT_TEST_TICKERS = [
    "AMP.AX", "MQG.AX", "SIQ.AX", "MMS.AX", "ALD.AX", "CGF.AX", "SOL.AX", "RFF.AX", "WES.AX", "WOW.AX",
    "IFT.AX", "RHC.AX", "BHP.AX", "CBA.AX", "WBC.AX", "NAB.AX", "ANZ.AX", "CSL.AX", "PME.AX", "TLX.AX",
    "RMD.AX", "SHL.AX", "FPH.AX", "NEU.AX", "SIG.AX", "NXT.AX", "MAQ.AX", "MP1.AX", "360.AX", "WBT.AX",
    "DRO.AX", "EOS.AX", "ASB.AX", "MIN.AX", "PLS.AX", "LYC.AX", "SFR.AX", "PDN.AX", "DYL.AX", "WGX.AX",
    "NST.AX", "EVN.AX", "NEM.AX", "STO.AX", "WDS.AX", "WHC.AX", "NHC.AX", "REA.AX", "QBE.AX", "IAG.AX",
]

COMPANY_NAMES = {
    "AMP.AX": "AMP Limited",
    "MQG.AX": "Macquarie Group Limited",
    "SIQ.AX": "Smartgroup Corporation Ltd",
    "MMS.AX": "McMillan Shakespeare Limited",
    "ALD.AX": "Ampol Limited",
    "CGF.AX": "Challenger Limited",
    "SOL.AX": "Washington H Soul Pattinson and Company Limited",
    "RFF.AX": "Rural Funds Group",
    "WES.AX": "Wesfarmers Limited",
    "WOW.AX": "Woolworths Group Limited",
    "IFT.AX": "Infratil Limited",
    "RHC.AX": "Ramsay Health Care Limited",
    "BHP.AX": "BHP Group Limited",
    "CBA.AX": "Commonwealth Bank of Australia",
    "WBC.AX": "Westpac Banking Corporation",
    "NAB.AX": "National Australia Bank Limited",
    "ANZ.AX": "ANZ Group Holdings Limited",
    "CSL.AX": "CSL Limited",
    "PME.AX": "Pro Medicus Limited",
    "TLX.AX": "Telix Pharmaceuticals Limited",
    "RMD.AX": "ResMed Inc.",
    "SHL.AX": "Sonic Healthcare Limited",
    "FPH.AX": "Fisher & Paykel Healthcare Corporation Limited",
    "NEU.AX": "Neuren Pharmaceuticals Limited",
    "SIG.AX": "Sigma Healthcare Limited",
    "NXT.AX": "NEXTDC Limited",
    "MAQ.AX": "Macquarie Technology Group Limited",
    "MP1.AX": "Megaport Limited",
    "360.AX": "Life360 Inc.",
    "WBT.AX": "Weebit Nano Limited",
    "DRO.AX": "DroneShield Limited",
    "EOS.AX": "Electro Optic Systems Holdings Limited",
    "ASB.AX": "Austal Limited",
    "MIN.AX": "Mineral Resources Limited",
    "PLS.AX": "Pilbara Minerals Limited",
    "LYC.AX": "Lynas Rare Earths Limited",
    "SFR.AX": "Sandfire Resources Limited",
    "PDN.AX": "Paladin Energy Limited",
    "DYL.AX": "Deep Yellow Limited",
    "WGX.AX": "Westgold Resources Limited",
    "NST.AX": "Northern Star Resources Limited",
    "EVN.AX": "Evolution Mining Limited",
    "NEM.AX": "Newmont Corporation",
    "STO.AX": "Santos Limited",
    "WDS.AX": "Woodside Energy Group Limited",
    "WHC.AX": "Whitehaven Coal Limited",
    "NHC.AX": "New Hope Corporation Limited",
    "REA.AX": "REA Group Limited",
    "QBE.AX": "QBE Insurance Group Limited",
    "IAG.AX": "Insurance Australia Group Limited",
}


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "date": "Date",
        "datetime": "Date",
        "time": "Date",
        "ticker": "Ticker",
        "symbol": "Ticker",
        "code": "Ticker",
        "company": "Company",
        "company name": "Company",
        "name": "Company",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "adj close": "Close",
        "volume": "Volume",
        "vol": "Volume",
    }
    rename = {}
    for column in df.columns:
        key = str(column).strip().lower()
        if key in aliases:
            rename[column] = aliases[key]
    return df.rename(columns=rename)


def load_uploaded(file) -> pd.DataFrame:
    data = file.read()
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(io.BytesIO(data))
    else:
        df = pd.read_excel(io.BytesIO(data))

    df = normalise_columns(df)
    missing = [column for column in REQUIRED if column not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}. Need {REQUIRED}")

    keep = REQUIRED + [column for column in OPTIONAL if column in df.columns]
    df = df[keep].copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()

    for column in ["Open", "High", "Low", "Close", "Volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    return (
        df.dropna(subset=["Date", "Ticker", "Open", "High", "Low", "Close"])
        .sort_values(["Ticker", "Date"])
        .reset_index(drop=True)
    )


def _extract_bulk_ticker(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    if not isinstance(raw.columns, pd.MultiIndex):
        return raw.copy()

    level0 = [str(value).upper() for value in raw.columns.get_level_values(0)]
    level1 = [str(value).upper() for value in raw.columns.get_level_values(1)]
    ticker_upper = ticker.upper()

    try:
        if ticker_upper in level0:
            return raw.xs(ticker, axis=1, level=0, drop_level=True).copy()
        if ticker_upper in level1:
            return raw.xs(ticker, axis=1, level=1, drop_level=True).copy()
    except Exception:
        pass

    return pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=900)
def fetch_yahoo(tickers_text: str, period: str, interval: str) -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("yfinance is not installed. Add yfinance to requirements.txt")

    tickers = list(
        dict.fromkeys(
            ticker.strip().upper()
            for ticker in tickers_text.replace("\n", ",").split(",")
            if ticker.strip()
        )
    )
    if not tickers:
        return pd.DataFrame(columns=REQUIRED)

    frames: list[pd.DataFrame] = []
    missing: list[str] = []

    try:
        raw = yf.download(
            tickers=tickers,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )

        for ticker in tickers:
            ticker_data = _extract_bulk_ticker(raw, ticker)
            if ticker_data.empty:
                missing.append(ticker)
                continue

            ticker_data = ticker_data.reset_index()
            date_column = "Date" if "Date" in ticker_data.columns else "Datetime"
            if date_column not in ticker_data.columns:
                missing.append(ticker)
                continue

            required_market_columns = ["Open", "High", "Low", "Close", "Volume"]
            if any(column not in ticker_data.columns for column in required_market_columns):
                missing.append(ticker)
                continue

            keep = ticker_data[[date_column] + required_market_columns].copy()
            keep = keep.rename(columns={date_column: "Date"})
            keep["Ticker"] = ticker
            frames.append(keep[REQUIRED])
    except Exception:
        missing = tickers.copy()

    # A small fallback is useful when Yahoo omits one symbol from a bulk response.
    for ticker in missing:
        try:
            data = yf.download(
                ticker,
                period=period,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if data.empty:
                continue
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [column[0] for column in data.columns]
            data = data.reset_index()
            date_column = "Date" if "Date" in data.columns else "Datetime"
            keep = data[[date_column, "Open", "High", "Low", "Close", "Volume"]].copy()
            keep = keep.rename(columns={date_column: "Date"})
            keep["Ticker"] = ticker
            frames.append(keep[REQUIRED])
        except Exception:
            continue

    if not frames:
        return pd.DataFrame(columns=REQUIRED)

    df = pd.concat(frames, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return (
        df.dropna(subset=["Date", "Ticker", "Open", "High", "Low", "Close"])
        .drop_duplicates(subset=["Ticker", "Date"], keep="last")
        .sort_values(["Ticker", "Date"])
        .reset_index(drop=True)
    )


def add_indicators(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    data["SMA20"] = data["Close"].rolling(20).mean()
    data["SMA50"] = data["Close"].rolling(50).mean()
    data["SMA200"] = data["Close"].rolling(200).mean()
    data["VolumeSMA20"] = data["Volume"].rolling(20).mean()
    return data


def clean_number(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or pd.isna(value) or math.isinf(float(value)):
            return default
        return float(value)
    except Exception:
        return default


def build_stock_payload(df: pd.DataFrame, candles_to_load: int) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []

    uploaded_names: dict[str, str] = {}
    if "Company" in df.columns:
        names = df.dropna(subset=["Company"])[["Ticker", "Company"]].drop_duplicates("Ticker", keep="last")
        uploaded_names = {
            str(row["Ticker"]): str(row["Company"]).strip()
            for _, row in names.iterrows()
            if str(row["Company"]).strip()
        }

    for ticker in sorted(df["Ticker"].dropna().unique().tolist()):
        full = df[df["Ticker"] == ticker].copy().sort_values("Date")
        if len(full) < 2:
            continue

        full = add_indicators(full)
        last = full.iloc[-1]
        previous = full.iloc[-2]

        close = clean_number(last["Close"], 0.0) or 0.0
        previous_close = clean_number(previous["Close"], close) or close
        change = close - previous_close
        change_pct = (change / previous_close * 100.0) if previous_close else 0.0
        volume = clean_number(last["Volume"], 0.0) or 0.0
        value = close * volume

        year = full.tail(252)
        low_52 = clean_number(year["Low"].min(), close) or close
        high_52 = clean_number(year["High"].max(), close) or close
        range_width = max(high_52 - low_52, 1e-12)
        range_position = max(0.0, min(1.0, (close - low_52) / range_width))
        distance_high_pct = ((close / high_52) - 1.0) * 100.0 if high_52 else 0.0

        company = uploaded_names.get(ticker) or COMPANY_NAMES.get(ticker) or ticker.replace(".AX", "")
        code = ticker.replace(".AX", "")

        chart_rows: list[dict[str, Any]] = []
        for _, row in full.tail(candles_to_load).iterrows():
            open_price = clean_number(row["Open"])
            high_price = clean_number(row["High"])
            low_price = clean_number(row["Low"])
            close_price = clean_number(row["Close"])
            if None in [open_price, high_price, low_price, close_price]:
                continue
            chart_rows.append(
                {
                    "date": pd.Timestamp(row["Date"]).strftime("%d/%m/%y"),
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": clean_number(row["Volume"], 0.0) or 0.0,
                    "sma20": clean_number(row.get("SMA20")),
                }
            )

        payload.append(
            {
                "ticker": ticker,
                "code": code,
                "company": company,
                "price": close,
                "change": change,
                "changePct": change_pct,
                "volume": volume,
                "value": value,
                "low52": low_52,
                "high52": high_52,
                "rangePosition": range_position,
                "distanceHighPct": distance_high_pct,
                "aboveSma20": bool(pd.notna(last["SMA20"]) and close > float(last["SMA20"])),
                "aboveSma50": bool(pd.notna(last["SMA50"]) and close > float(last["SMA50"])),
                "volumeAboveAverage": bool(
                    pd.notna(last["VolumeSMA20"]) and volume > float(last["VolumeSMA20"])
                ),
                "sma20AboveSma50": bool(
                    pd.notna(last["SMA20"])
                    and pd.notna(last["SMA50"])
                    and float(last["SMA20"]) > float(last["SMA50"])
                ),
                "rows": chart_rows,
            }
        )

    return payload


def market_table_html(stock_payload: list[dict[str, Any]]) -> str:
    html = r'''<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
<style>
:root {
    --orange: #f36f16;
    --text: #30313a;
    --muted: #6d6e75;
    --line: #dedede;
    --row-a: #ffffff;
    --row-b: #f7f7f7;
    --header: #ffffff;
    --control: #f2f2f4;
    --sticky-shadow: rgba(0,0,0,0.10);
}
* { box-sizing: border-box; }
html, body {
    margin: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: #fff;
    color: var(--text);
    font-family: Arial, Helvetica, sans-serif;
    -webkit-tap-highlight-color: transparent;
}
.app {
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: #fff;
}
.controlbar {
    flex: 0 0 auto;
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
    gap: 7px;
    padding: 7px 7px 6px 7px;
    background: #fff;
    border-bottom: 1px solid var(--line);
    z-index: 50;
}
.controlbar select {
    width: 100%;
    min-width: 0;
    height: 38px;
    border: 1px solid #b8b8bd;
    border-radius: 7px;
    background: var(--control);
    color: var(--text);
    font-size: 14px;
    padding: 0 30px 0 10px;
}
.count-pill {
    min-width: 56px;
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #b8b8bd;
    border-radius: 7px;
    background: #fff;
    font-size: 13px;
    font-weight: 700;
    white-space: nowrap;
}
.table-shell {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
    overflow: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    background: #fff;
}
table {
    width: max-content;
    min-width: 1200px;
    border-collapse: separate;
    border-spacing: 0;
    table-layout: fixed;
}
th, td {
    height: 58px;
    border-bottom: 1px solid var(--line);
    padding: 8px 12px;
    vertical-align: middle;
    background: var(--row-a);
    white-space: nowrap;
    font-size: 14px;
}
tbody tr.stock-row.alt td { background: var(--row-b); }
th {
    position: sticky;
    top: 0;
    z-index: 20;
    height: 51px;
    background: var(--header);
    font-size: 13px;
    font-weight: 700;
    text-align: center;
    cursor: pointer;
    user-select: none;
    box-shadow: 0 1px 0 var(--line);
}
th:hover { background: #f8f8f8; }
.header-label {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
}
.sort-arrow { min-width: 10px; color: #777; font-size: 11px; }
.code-col { width: 116px; min-width: 116px; max-width: 116px; text-align: left; }
.company-col { width: 265px; min-width: 265px; max-width: 265px; text-align: left; overflow: hidden; text-overflow: ellipsis; }
.price-col { width: 112px; min-width: 112px; text-align: right; }
.change-col { width: 112px; min-width: 112px; text-align: right; }
.pct-col { width: 112px; min-width: 112px; text-align: right; }
.volume-col { width: 145px; min-width: 145px; text-align: right; }
.value-col { width: 150px; min-width: 150px; text-align: right; }
.range-col { width: 290px; min-width: 290px; text-align: left; }
.action-col { width: 78px; min-width: 78px; max-width: 78px; text-align: center; }
th.code-col, td.code-col {
    position: sticky;
    left: 0;
    z-index: 30;
    box-shadow: 6px 0 8px -8px var(--sticky-shadow);
}
th.action-col, td.action-col {
    position: sticky;
    right: 0;
    z-index: 30;
    box-shadow: -6px 0 8px -8px var(--sticky-shadow);
}
th.code-col, th.action-col { z-index: 45; background: #fff; }
tbody tr.stock-row td.code-col,
tbody tr.stock-row td.action-col { background: var(--row-a); }
tbody tr.stock-row.alt td.code-col,
tbody tr.stock-row.alt td.action-col { background: var(--row-b); }
.code-button {
    border: 0;
    background: transparent;
    color: #30313a;
    font: inherit;
    font-size: 15px;
    font-weight: 700;
    padding: 12px 4px;
    width: 100%;
    text-align: left;
    cursor: pointer;
}
.code-button:active { transform: scale(0.98); }
.liked-star { color: var(--orange); margin-left: 4px; font-size: 12px; }
.positive { color: #177b2c; }
.negative { color: #c92525; }
.value-wrap { display: flex; flex-direction: column; align-items: flex-end; gap: 5px; }
.value-bar-track { width: 100%; height: 3px; background: #efefef; }
.value-bar { height: 3px; background: var(--orange); min-width: 2px; }
.range-labels { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 8px; font-size: 12px; color: #3d3d43; }
.range-labels span:last-child { text-align: right; }
.range-distance { color: #777; font-size: 10px; text-align: center; }
.range-track { position: relative; height: 18px; margin-top: 2px; }
.range-line {
    position: absolute;
    left: 0;
    right: 0;
    top: 8px;
    height: 3px;
    background: #ffd8bf;
}
.range-fill {
    position: absolute;
    left: 0;
    top: 8px;
    height: 3px;
    background: var(--orange);
}
.range-dot {
    position: absolute;
    top: 1px;
    width: 17px;
    height: 17px;
    border-radius: 50%;
    background: var(--orange);
    transform: translateX(-50%);
}
.action-button {
    width: 42px;
    height: 42px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: #30313a;
    font-size: 25px;
    line-height: 1;
    cursor: pointer;
}
.action-button:hover, .action-button:focus { background: #e9e9e9; outline: none; }
.action-holder { position: relative; display: inline-block; }
.action-menu {
    display: none;
    position: absolute;
    right: 4px;
    top: 43px;
    min-width: 172px;
    overflow: hidden;
    border: 1px solid #c9c9c9;
    border-radius: 8px;
    background: #fff;
    box-shadow: 0 5px 18px rgba(0,0,0,0.18);
    z-index: 120;
    text-align: left;
}
.action-menu.up { top: auto; bottom: 43px; }
.action-menu.open { display: block; }
.action-menu button {
    display: block;
    width: 100%;
    border: 0;
    border-bottom: 1px solid #ededed;
    background: #fff;
    padding: 13px 14px;
    color: #2f3036;
    font-size: 14px;
    text-align: left;
    cursor: pointer;
}
.action-menu button:last-child { border-bottom: 0; }
.action-menu button:hover { background: #f3f3f3; }
.detail-row td {
    height: auto;
    padding: 0;
    border-bottom: 1px solid #bfbfbf;
    background: #efefef;
}
.chart-host {
    margin: 10px 0;
    width: 680px;
    max-width: calc(100vw - 18px);
    background: #fff;
    border: 1px solid #bababa;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.chart-toolbar {
    min-height: 38px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 5px 8px;
    border-bottom: 1px solid #dedede;
    background: #f5f4f1;
    color: #5f6066;
    font-size: 12px;
}
.chart-toolbar select {
    height: 28px;
    border: 1px solid #b9b9b9;
    border-radius: 5px;
    background: #fff;
    color: #555;
    font-size: 12px;
    padding: 0 24px 0 7px;
}
.chart-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 4px;
    min-height: 34px;
    align-items: center;
    padding: 4px 8px;
    color: #555;
    font-size: 12px;
    text-align: center;
    border-bottom: 1px solid #e5e5e5;
}
.chart-panel { margin: 0 7px 6px 7px; border: 1px solid #bdbdbd; background: #fff; }
.chart-panel-title {
    height: 24px;
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 0 7px;
    color: #666;
    font-size: 12px;
    border-bottom: 1px solid #e1e1e1;
    background: #fafaf8;
}
.legend-swatch { width: 16px; height: 12px; border-left: 8px solid #009735; border-right: 8px solid #d90000; }
.price-canvas { width: 100%; height: 320px; display: block; touch-action: pan-y pinch-zoom; }
.volume-canvas { width: 100%; height: 132px; display: block; touch-action: pan-y pinch-zoom; }
.empty-message { padding: 28px 16px; text-align: center; color: #666; font-size: 14px; }
.modal-backdrop {
    display: none;
    position: fixed;
    inset: 0;
    z-index: 300;
    background: rgba(0,0,0,0.35);
    align-items: center;
    justify-content: center;
    padding: 20px;
}
.modal-backdrop.open { display: flex; }
.modal {
    width: min(360px, 100%);
    border-radius: 10px;
    background: #fff;
    box-shadow: 0 8px 30px rgba(0,0,0,0.25);
    padding: 16px;
}
.modal h3 { margin: 0 0 12px 0; font-size: 18px; }
.modal label { display: block; margin: 10px 0 5px 0; font-size: 13px; color: #555; }
.modal select, .modal input {
    width: 100%;
    height: 40px;
    border: 1px solid #b9b9b9;
    border-radius: 6px;
    padding: 0 9px;
    font-size: 14px;
}
.modal-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 15px; }
.modal-actions button { height: 40px; border-radius: 7px; border: 1px solid #999; background: #eee; font-weight: 700; }
.modal-actions button.primary { background: #666; color: #fff; border-color: #666; }
@media (max-width: 620px) {
    .controlbar { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) 52px; gap: 5px; padding: 5px; }
    .controlbar select { height: 36px; font-size: 13px; }
    .count-pill { height: 36px; min-width: 52px; font-size: 12px; }
    th, td { height: 54px; padding: 7px 10px; font-size: 13px; }
    th { height: 49px; font-size: 12px; }
    .code-col { width: 105px; min-width: 105px; max-width: 105px; }
    .action-col { width: 66px; min-width: 66px; max-width: 66px; }
    .price-canvas { height: 300px; }
    .volume-canvas { height: 122px; }
}
</style>
</head>
<body>
<div class="app">
    <div class="controlbar">
        <select id="filterSelect" aria-label="Filters">
            <option value="all">Filters</option>
            <option value="aboveSma20">Above 20-day SMA</option>
            <option value="aboveSma50">Above 50-day SMA</option>
            <option value="volumeAboveAverage">Volume above 20-day average</option>
            <option value="sma20AboveSma50">20-day SMA above 50-day SMA</option>
        </select>
        <select id="watchlistSelect" aria-label="Watchlist"></select>
        <div id="countPill" class="count-pill">0</div>
    </div>

    <div id="tableShell" class="table-shell">
        <table id="stockTable">
            <thead>
                <tr>
                    <th class="code-col" data-sort="code"><span class="header-label">Code <span class="sort-arrow"></span></span></th>
                    <th class="company-col" data-sort="company"><span class="header-label">Company <span class="sort-arrow"></span></span></th>
                    <th class="price-col" data-sort="price"><span class="header-label">Price ($) <span class="sort-arrow"></span></span></th>
                    <th class="change-col" data-sort="change"><span class="header-label">Chg ($) <span class="sort-arrow"></span></span></th>
                    <th class="pct-col" data-sort="changePct"><span class="header-label">Chg (%) <span class="sort-arrow"></span></span></th>
                    <th class="volume-col" data-sort="volume"><span class="header-label">Volume <span class="sort-arrow"></span></span></th>
                    <th class="value-col" data-sort="value"><span class="header-label">Value <span class="sort-arrow"></span></span></th>
                    <th class="range-col" data-sort="distanceHighPct"><span class="header-label">52 week range <span class="sort-arrow"></span></span></th>
                    <th class="action-col"><span class="header-label">Action</span></th>
                </tr>
            </thead>
            <tbody id="stockBody"></tbody>
        </table>
    </div>
</div>

<div id="watchlistModal" class="modal-backdrop" role="dialog" aria-modal="true">
    <div class="modal">
        <h3>Add to watchlist</h3>
        <label for="existingWatchlist">Existing watchlist</label>
        <select id="existingWatchlist"></select>
        <label for="newWatchlist">Or create a new watchlist</label>
        <input id="newWatchlist" maxlength="40" placeholder="Watchlist name">
        <div class="modal-actions">
            <button id="cancelWatchlist">Cancel</button>
            <button id="confirmWatchlist" class="primary">Add</button>
        </div>
    </div>
</div>

<script>
const allStocks = __STOCK_DATA__;
const stockByTicker = new Map(allStocks.map(stock => [stock.ticker, stock]));
const tableShell = document.getElementById('tableShell');
const stockBody = document.getElementById('stockBody');
const filterSelect = document.getElementById('filterSelect');
const watchlistSelect = document.getElementById('watchlistSelect');
const countPill = document.getElementById('countPill');
const modal = document.getElementById('watchlistModal');
const existingWatchlist = document.getElementById('existingWatchlist');
const newWatchlist = document.getElementById('newWatchlist');
const cancelWatchlist = document.getElementById('cancelWatchlist');
const confirmWatchlist = document.getElementById('confirmWatchlist');
const storageKey = 'stockSwipeTableListsV21';

let state = {
    sortKey: 'code',
    sortDir: 1,
    filter: 'all',
    watchlist: 'None',
    expandedTicker: null,
    pendingWatchlistTicker: null,
};
let activeChart = null;
let lists = loadLists();

function loadLists() {
    try {
        const parsed = JSON.parse(localStorage.getItem(storageKey) || 'null');
        if (parsed && Array.isArray(parsed.liked) && parsed.watchlists && typeof parsed.watchlists === 'object') {
            return parsed;
        }
    } catch (error) {}
    return {liked: [], watchlists: {}};
}
function saveLists() {
    lists.liked = Array.from(new Set(lists.liked));
    try { localStorage.setItem(storageKey, JSON.stringify(lists)); } catch (error) {}
}
function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, character => ({
        '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;'
    }[character]));
}
function formatPrice(value) { return Number(value || 0).toFixed(3); }
function formatChange(value) {
    const number = Number(value || 0);
    return `${number < 0 ? '(' : ''}${Math.abs(number).toFixed(3)}${number < 0 ? ')' : ''}`;
}
function formatPct(value) {
    const number = Number(value || 0);
    return `${number < 0 ? '(' : ''}${Math.abs(number).toFixed(2)}%${number < 0 ? ')' : ''}`;
}
function formatInteger(value) { return Math.round(Number(value || 0)).toLocaleString('en-AU'); }
function formatMoneyCompact(value) {
    const number = Number(value || 0);
    if (number >= 1e9) return '$' + (number / 1e9).toFixed(2) + 'B';
    if (number >= 1e6) return '$' + (number / 1e6).toFixed(2) + 'M';
    if (number >= 1e3) return '$' + (number / 1e3).toFixed(1) + 'K';
    return '$' + Math.round(number).toLocaleString('en-AU');
}
function numberClass(value) {
    if (Number(value) > 0) return 'positive';
    if (Number(value) < 0) return 'negative';
    return '';
}
function maxVisibleValue(stocks) {
    return Math.max(1, ...stocks.map(stock => Number(stock.value) || 0));
}
function updateWatchlistOptions() {
    const previous = state.watchlist;
    const options = [
        ['None', 'None'],
        ['Liked', 'Liked'],
        ...Object.keys(lists.watchlists).sort((a,b) => a.localeCompare(b)).map(name => [name, name]),
        ['__create__', 'Create watchlist…'],
    ];
    watchlistSelect.innerHTML = options.map(([value,label]) => `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`).join('');
    state.watchlist = options.some(([value]) => value === previous) ? previous : 'None';
    watchlistSelect.value = state.watchlist;
}
function createWatchlist() {
    const name = window.prompt('Watchlist name:');
    if (!name) return;
    const clean = name.trim();
    if (!clean) return;
    if (!lists.watchlists[clean]) lists.watchlists[clean] = [];
    saveLists();
    state.watchlist = clean;
    updateWatchlistOptions();
    render();
}
function filteredStocks() {
    let result = allStocks.filter(stock => {
        if (state.filter === 'aboveSma20' && !stock.aboveSma20) return false;
        if (state.filter === 'aboveSma50' && !stock.aboveSma50) return false;
        if (state.filter === 'volumeAboveAverage' && !stock.volumeAboveAverage) return false;
        if (state.filter === 'sma20AboveSma50' && !stock.sma20AboveSma50) return false;
        if (state.watchlist === 'Liked' && !lists.liked.includes(stock.ticker)) return false;
        if (state.watchlist !== 'None' && state.watchlist !== 'Liked') {
            const members = lists.watchlists[state.watchlist] || [];
            if (!members.includes(stock.ticker)) return false;
        }
        return true;
    });

    result.sort((a,b) => {
        const key = state.sortKey;
        let left = a[key];
        let right = b[key];
        if (typeof left === 'string' || typeof right === 'string') {
            return String(left).localeCompare(String(right)) * state.sortDir;
        }
        const leftNumber = Number(left);
        const rightNumber = Number(right);
        if (!Number.isFinite(leftNumber) && !Number.isFinite(rightNumber)) return 0;
        if (!Number.isFinite(leftNumber)) return 1;
        if (!Number.isFinite(rightNumber)) return -1;
        return (leftNumber - rightNumber) * state.sortDir;
    });
    return result;
}
function updateHeaderArrows() {
    document.querySelectorAll('th[data-sort]').forEach(th => {
        const arrow = th.querySelector('.sort-arrow');
        arrow.textContent = th.dataset.sort === state.sortKey ? (state.sortDir === 1 ? '▲' : '▼') : '';
    });
}
function stockRowHtml(stock, index, maxValue) {
    const liked = lists.liked.includes(stock.ticker);
    const valueWidth = Math.max(2, Math.min(100, (Number(stock.value) / maxValue) * 100));
    const position = Math.max(1, Math.min(99, Number(stock.rangePosition) * 100));
    return `<tr class="stock-row ${index % 2 ? 'alt' : ''}" data-ticker="${escapeHtml(stock.ticker)}">
        <td class="code-col"><button class="code-button" data-expand="${escapeHtml(stock.ticker)}">${escapeHtml(stock.code)}${liked ? '<span class="liked-star">★</span>' : ''}</button></td>
        <td class="company-col" title="${escapeHtml(stock.company)}">${escapeHtml(stock.company)}</td>
        <td class="price-col">${formatPrice(stock.price)}</td>
        <td class="change-col ${numberClass(stock.change)}">${formatChange(stock.change)}</td>
        <td class="pct-col ${numberClass(stock.changePct)}">${formatPct(stock.changePct)}</td>
        <td class="volume-col">${formatInteger(stock.volume)}</td>
        <td class="value-col"><div class="value-wrap"><span>${formatMoneyCompact(stock.value)}</span><div class="value-bar-track"><div class="value-bar" style="width:${valueWidth}%"></div></div></div></td>
        <td class="range-col">
            <div class="range-labels"><span>$${formatPrice(stock.low52)}</span><span class="range-distance">${Math.abs(Number(stock.distanceHighPct)||0).toFixed(1)}% below</span><span>$${formatPrice(stock.high52)}</span></div>
            <div class="range-track"><div class="range-line"></div><div class="range-fill" style="width:${position}%"></div><div class="range-dot" style="left:${position}%"></div></div>
        </td>
        <td class="action-col">
            <div class="action-holder">
                <button class="action-button" data-menu="${escapeHtml(stock.ticker)}" aria-label="Actions for ${escapeHtml(stock.code)}">⋮</button>
                <div class="action-menu" data-action-menu="${escapeHtml(stock.ticker)}">
                    <button data-action="like" data-ticker="${escapeHtml(stock.ticker)}">${liked ? 'Unlike' : 'Like'}</button>
                    <button data-action="watchlist" data-ticker="${escapeHtml(stock.ticker)}">Add to watchlist</button>
                </div>
            </div>
        </td>
    </tr>`;
}
function detailRowHtml(stock) {
    const last = stock.rows[stock.rows.length - 1] || {high:0,low:0,close:0,date:''};
    return `<tr class="detail-row" data-detail="${escapeHtml(stock.ticker)}"><td colspan="9">
        <div class="chart-host" id="chartHost-${escapeHtml(stock.code)}">
            <div class="chart-toolbar">
                <span><strong>${escapeHtml(stock.code)} chart</strong></span>
                <select class="chart-mode" aria-label="Chart type"><option value="candle">Candle</option><option value="line">Line</option></select>
                <span>Drag / pinch zoom</span>
            </div>
            <div class="chart-stats"><span>H $${Number(last.high || 0).toFixed(2)}</span><span>L $${Number(last.low || 0).toFixed(2)}</span><span>C $${Number(last.close || 0).toFixed(2)}</span><span>${escapeHtml(last.date || '')}</span></div>
            <div class="chart-panel"><div class="chart-panel-title"><span class="legend-swatch"></span><span>Price</span></div><canvas class="price-canvas"></canvas></div>
            <div class="chart-panel"><div class="chart-panel-title"><span class="legend-swatch"></span><span>Volume</span><select class="volume-average" aria-label="Volume average"><option value="5">5-day average</option><option value="10">10-day average</option><option value="14" selected>14-day average</option><option value="20">20-day average</option><option value="30">30-day average</option><option value="50">50-day average</option></select></div><canvas class="volume-canvas"></canvas></div>
        </div>
    </td></tr>`;
}
function render() {
    closeMenus();
    const stocks = filteredStocks();
    const maxValue = maxVisibleValue(stocks);
    let html = '';
    stocks.forEach((stock,index) => {
        html += stockRowHtml(stock,index,maxValue);
        if (state.expandedTicker === stock.ticker) html += detailRowHtml(stock);
    });
    if (!stocks.length) html = '<tr><td colspan="9"><div class="empty-message">No stocks match the current filter or watchlist.</div></td></tr>';
    stockBody.innerHTML = html;
    countPill.textContent = String(stocks.length);
    updateHeaderArrows();

    if (state.expandedTicker && stocks.some(stock => stock.ticker === state.expandedTicker)) {
        const stock = stockByTicker.get(state.expandedTicker);
        const host = document.querySelector(`[data-detail="${CSS.escape(state.expandedTicker)}"] .chart-host`);
        positionChartHost(host);
        activeChart = createChart(host, stock);
    } else {
        state.expandedTicker = null;
        activeChart = null;
    }
}
function positionChartHost(host) {
    if (!host) return;
    const visibleWidth = tableShell.clientWidth;
    const chartWidth = Math.max(300, Math.min(720, visibleWidth - 14));
    host.style.width = chartWidth + 'px';
    host.style.marginLeft = (tableShell.scrollLeft + Math.max(7, (visibleWidth - chartWidth) / 2)) + 'px';
}
function closeMenus(exceptTicker=null) {
    document.querySelectorAll('.action-menu.open').forEach(menu => {
        if (menu.dataset.actionMenu !== exceptTicker) menu.classList.remove('open','up');
    });
}
function toggleMenu(ticker, button) {
    const menu = document.querySelector(`[data-action-menu="${CSS.escape(ticker)}"]`);
    if (!menu) return;
    const wasOpen = menu.classList.contains('open');
    closeMenus();
    if (wasOpen) return;
    const shellRect = tableShell.getBoundingClientRect();
    const buttonRect = button.getBoundingClientRect();
    menu.classList.toggle('up', buttonRect.bottom + 105 > shellRect.bottom);
    menu.classList.add('open');
}
function toggleLike(ticker) {
    if (lists.liked.includes(ticker)) lists.liked = lists.liked.filter(item => item !== ticker);
    else lists.liked.push(ticker);
    saveLists();
    render();
}
function openWatchlistModal(ticker) {
    state.pendingWatchlistTicker = ticker;
    const names = Object.keys(lists.watchlists).sort((a,b) => a.localeCompare(b));
    existingWatchlist.innerHTML = '<option value="">Choose a watchlist</option>' + names.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join('');
    newWatchlist.value = '';
    modal.classList.add('open');
    setTimeout(() => names.length ? existingWatchlist.focus() : newWatchlist.focus(), 30);
}
function closeWatchlistModal() {
    modal.classList.remove('open');
    state.pendingWatchlistTicker = null;
}
function confirmAddToWatchlist() {
    const ticker = state.pendingWatchlistTicker;
    if (!ticker) return;
    const typed = newWatchlist.value.trim();
    const selected = existingWatchlist.value;
    const name = typed || selected;
    if (!name) {
        window.alert('Choose a watchlist or enter a new name.');
        return;
    }
    if (!lists.watchlists[name]) lists.watchlists[name] = [];
    if (!lists.watchlists[name].includes(ticker)) lists.watchlists[name].push(ticker);
    saveLists();
    updateWatchlistOptions();
    closeWatchlistModal();
    render();
}
function toggleExpand(ticker) {
    const opening = state.expandedTicker !== ticker;
    state.expandedTicker = opening ? ticker : null;
    activeChart = null;
    render();
    if (opening) {
        setTimeout(() => {
            const row = document.querySelector(`[data-ticker="${CSS.escape(ticker)}"]`);
            if (row) row.scrollIntoView({behavior:'smooth', block:'center', inline:'nearest'});
        }, 80);
    }
}

function createChart(host, stock) {
    if (!host || !stock || !stock.rows.length) return null;
    const rows = stock.rows.map(row => ({...row}));
    const priceCanvas = host.querySelector('.price-canvas');
    const volumeCanvas = host.querySelector('.volume-canvas');
    const modeSelect = host.querySelector('.chart-mode');
    const volumeSelect = host.querySelector('.volume-average');
    const pctx = priceCanvas.getContext('2d');
    const vctx = volumeCanvas.getContext('2d');
    const savedKey = 'stockSwipeInlineViewV21:' + stock.ticker;
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(savedKey) || 'null'); } catch (error) {}
    let view = {
        count: saved && Number.isFinite(saved.count) ? saved.count : Math.min(80, rows.length + 20),
        end: saved && Number.isFinite(saved.end) ? saved.end : rows.length - 1 + 8,
        minCount: 8,
    };
    let chartMode = saved && saved.chartMode === 'line' ? 'line' : 'candle';
    let volumeAverageDays = saved && Number.isInteger(saved.volumeAverageDays) ? saved.volumeAverageDays : 14;
    let drag = null;
    let pinch = null;
    let gestureMode = null;
    let ignoreSingleTouchUntilEnd = false;

    function calculateVolumeAverage() {
        let total = 0;
        rows.forEach((row,index) => {
            total += Number(row.volume) || 0;
            if (index >= volumeAverageDays) total -= Number(rows[index-volumeAverageDays].volume) || 0;
            row.volumeAverage = index >= volumeAverageDays - 1 ? total / volumeAverageDays : null;
        });
    }
    function clamp(value, low, high) { return Math.max(low, Math.min(high, value)); }
    function setupCanvas(canvas, context) {
        const dpr = window.devicePixelRatio || 1;
        const width = canvas.clientWidth;
        const height = canvas.clientHeight;
        canvas.width = Math.max(1, Math.floor(width * dpr));
        canvas.height = Math.max(1, Math.floor(height * dpr));
        context.setTransform(dpr,0,0,dpr,0,0);
        context.imageSmoothingEnabled = false;
    }
    function bounds(canvas, axisPad=58) {
        return {left:9, right:canvas.clientWidth-axisPad, top:10, bottom:canvas.clientHeight-25};
    }
    function maxZoomOut(canvas) {
        const b = bounds(canvas);
        const total = rows.length + Math.max(60, Math.round(rows.length * 0.20));
        return Math.max(100, Math.min(total, Math.floor((b.right-b.left)/0.65)));
    }
    function clampView(canvas=priceCanvas) {
        view.count = clamp(view.count, view.minCount, maxZoomOut(canvas));
        const emptyLeft = Math.max(20, Math.round(view.count * 0.6));
        const emptyRight = Math.max(30, Math.round(view.count * 0.8));
        const minEnd = -emptyLeft + view.count - 1;
        const maxEnd = rows.length - 1 + emptyRight;
        view.end = clamp(view.end, minEnd, maxEnd);
    }
    function visibleMeta(canvas=priceCanvas) {
        clampView(canvas);
        const start = view.end - view.count + 1;
        const end = view.end;
        const low = Math.max(0, Math.floor(start)-2);
        const high = Math.min(rows.length-1, Math.ceil(end)+2);
        const data = [];
        for (let index=low; index<=high; index++) data.push({...rows[index], idx:index});
        return {start,end,data};
    }
    function xForIndex(index,left,right,meta) {
        return left + ((index-meta.start)/view.count)*(right-left);
    }
    function niceStep(range,targetTicks=6) {
        const rough = Math.max(range/targetTicks,1e-9);
        const power = Math.pow(10,Math.floor(Math.log10(rough)));
        const normal = rough/power;
        const multiplier = normal<=1?1:normal<=2?2:normal<=2.5?2.5:normal<=5?5:10;
        return multiplier*power;
    }
    function priceDecimals(step) {
        if (step>=1) return 0;
        if (step>=0.1) return 1;
        if (step>=0.01) return 2;
        if (step>=0.001) return 3;
        return 4;
    }
    function formatAxisPrice(value,step) { return Number(value).toFixed(priceDecimals(step)); }
    function niceVolume(value) {
        if (value>=1e9) return (value/1e9).toFixed(1)+'B';
        if (value>=1e6) return (value/1e6).toFixed(1)+'M';
        if (value>=1e3) return (value/1e3).toFixed(0)+'K';
        return String(Math.round(value));
    }
    function gridValues(minimum,maximum,step) {
        const values=[];
        const first=Math.ceil((minimum-1e-10)/step);
        const last=Math.floor((maximum+1e-10)/step);
        for(let index=first; index<=last; index++) values.push(index*step);
        return values;
    }
    function drawGrid(context,left,right,top,bottom,yValues,yFunction) {
        context.strokeStyle='#e6e6e6';
        context.lineWidth=0.65;
        yValues.forEach(value => {
            const y=Math.round(yFunction(value))+0.5;
            context.beginPath(); context.moveTo(left,y); context.lineTo(right,y); context.stroke();
        });
        const divisions=view.count<=16?8:view.count<=32?6:view.count<=80?5:4;
        for(let index=0; index<=divisions; index++) {
            const x=Math.round(left+(right-left)*index/divisions)+0.5;
            context.beginPath(); context.moveTo(x,top); context.lineTo(x,bottom); context.stroke();
        }
    }
    function chooseDateStep(visibleBars,maxLabels) {
        const required = Math.max(1, Math.ceil(visibleBars/Math.max(1,maxLabels)));
        const steps = [1,2,3,4,5,8,10,15,20,30,40,60,80,120,160,240];
        return steps.find(step => step >= required) || required;
    }
    function dateTicks(meta,left,right,context) {
        context.font='10px Arial';
        const sampleWidth = Math.ceil(context.measureText('00/00/00').width) + 15;
        const maxLabels = Math.max(2, Math.floor((right-left)/sampleWidth));
        const visibleBars = Math.max(1,meta.end-meta.start+1);
        const step = chooseDateStep(visibleBars,maxLabels);
        const ticks=[];
        let previousX=-Infinity;
        const first=Math.ceil(meta.start/step)*step;
        for(let index=first; index<=meta.end; index+=step) {
            const rounded=Math.round(index);
            const row=rows[rounded];
            if(!row) continue;
            const x=xForIndex(rounded,left,right,meta)+(right-left)/view.count/2;
            if(x<left+sampleWidth/2 || x>right-sampleWidth/2) continue;
            if(x-previousX<sampleWidth) continue;
            ticks.push({idx:rounded,label:row.date,x});
            previousX=x;
        }
        return ticks;
    }
    function persist() {
        try { localStorage.setItem(savedKey, JSON.stringify({count:view.count,end:view.end,chartMode,volumeAverageDays})); } catch (error) {}
    }
    function drawPrice() {
        setupCanvas(priceCanvas,pctx);
        const width=priceCanvas.clientWidth;
        const height=priceCanvas.clientHeight;
        const b=bounds(priceCanvas,58);
        const left=b.left,right=b.right,top=b.top,bottom=b.bottom;
        const meta=visibleMeta(priceCanvas);
        const data=meta.data.filter(row => row.idx>=meta.start-1 && row.idx<=meta.end+1);
        pctx.clearRect(0,0,width,height);
        pctx.fillStyle='#fff'; pctx.fillRect(0,0,width,height);
        const priceData=data.length?data:rows.map((row,index)=>({...row,idx:index})).slice(-50);
        let minPrice=Math.min(...priceData.map(row=>row.low));
        let maxPrice=Math.max(...priceData.map(row=>row.high));
        const rawRange=Math.max(maxPrice-minPrice,Math.abs(maxPrice)*0.01,0.01);
        const padding=rawRange*0.18;
        minPrice-=padding; maxPrice+=padding;
        const tickStep=niceStep(maxPrice-minPrice,view.count<=24?10:view.count<=70?7:5);
        minPrice=Math.floor(minPrice/tickStep)*tickStep;
        maxPrice=Math.ceil(maxPrice/tickStep)*tickStep;
        const values=gridValues(minPrice,maxPrice,tickStep);
        const y=value=>bottom-(value-minPrice)/(maxPrice-minPrice)*(bottom-top);
        drawGrid(pctx,left,right,top,bottom,values,y);
        const horizontalStep=(right-left)/view.count;
        const bodyWidth=Math.max(0.55,Math.min(horizontalStep*0.58,54));
        pctx.fillStyle='#666'; pctx.font='11px Arial'; pctx.textAlign='left'; pctx.textBaseline='middle';
        values.forEach(value=>pctx.fillText(formatAxisPrice(value,tickStep),right+5,y(value)));
        pctx.save(); pctx.beginPath(); pctx.rect(left,top,right-left,bottom-top); pctx.clip();
        if(chartMode==='line') {
            pctx.strokeStyle='#1679a5'; pctx.lineWidth=1.5; let started=false;
            data.forEach(row=>{
                const x=xForIndex(row.idx,left,right,meta)+horizontalStep/2;
                const yy=y(row.close);
                if(x<left-horizontalStep || x>right+horizontalStep) return;
                if(!started) { pctx.beginPath(); pctx.moveTo(x,yy); started=true; }
                else pctx.lineTo(x,yy);
            });
            if(started) pctx.stroke();
        } else {
            data.forEach(row=>{
                const x=xForIndex(row.idx,left,right,meta)+horizontalStep/2;
                if(x<left-bodyWidth/2 || x>right+bodyWidth/2) return;
                const up=row.close>=row.open;
                const colour=up?'#009735':'#d90000';
                const openY=y(row.open),closeY=y(row.close),highY=y(row.high),lowY=y(row.low);
                const bodyTop=Math.min(openY,closeY);
                const bodyBottom=Math.max(openY,closeY);
                const bodyHeight=Math.max(1,bodyBottom-bodyTop);
                pctx.strokeStyle=colour; pctx.lineWidth=0.72;
                pctx.beginPath(); pctx.moveTo(Math.round(x)+0.5,highY); pctx.lineTo(Math.round(x)+0.5,lowY); pctx.stroke();
                if(up) {
                    pctx.fillStyle='#fff'; pctx.strokeStyle=colour;
                    pctx.fillRect(x-bodyWidth/2,bodyTop,bodyWidth,bodyHeight);
                    pctx.strokeRect(x-bodyWidth/2,bodyTop,bodyWidth,bodyHeight);
                } else {
                    pctx.fillStyle=colour; pctx.fillRect(x-bodyWidth/2,bodyTop,bodyWidth,bodyHeight);
                }
            });
        }
        pctx.restore();
        const lastIndex=rows.length-1;
        const last=rows[lastIndex];
        const lastY=y(last.close);
        if(lastY>=top && lastY<=bottom) {
            pctx.strokeStyle='#1679a5'; pctx.lineWidth=0.8; pctx.setLineDash([4,3]);
            pctx.beginPath(); pctx.moveTo(left,lastY); pctx.lineTo(right,lastY); pctx.stroke(); pctx.setLineDash([]);
            pctx.fillStyle='#1679a5'; pctx.fillRect(right+2,lastY-10,48,20);
            pctx.fillStyle='#fff'; pctx.font='bold 11px Arial'; pctx.textAlign='center'; pctx.textBaseline='middle';
            pctx.fillText(formatAxisPrice(last.close,tickStep),right+26,lastY);
        }
        pctx.fillStyle='#6e6e6e'; pctx.font='10px Arial'; pctx.textAlign='center'; pctx.textBaseline='top';
        dateTicks(meta,left,right,pctx).forEach(tick => pctx.fillText(tick.label,tick.x,bottom+7));
    }
    function drawVolume() {
        setupCanvas(volumeCanvas,vctx);
        const width=volumeCanvas.clientWidth;
        const height=volumeCanvas.clientHeight;
        const b=bounds(volumeCanvas,50);
        const left=b.left,right=b.right,top=8,bottom=height-19;
        const meta=visibleMeta(volumeCanvas);
        const data=meta.data.filter(row=>row.idx>=meta.start-1 && row.idx<=meta.end+1);
        vctx.clearRect(0,0,width,height); vctx.fillStyle='#fff'; vctx.fillRect(0,0,width,height);
        vctx.strokeStyle='#e7e7e7'; vctx.lineWidth=0.65;
        for(let index=0;index<=3;index++) {
            const y=Math.round(top+(bottom-top)*index/3)+0.5;
            vctx.beginPath(); vctx.moveTo(left,y); vctx.lineTo(right,y); vctx.stroke();
        }
        const volData=data.length?data:rows.map((row,index)=>({...row,idx:index})).slice(-50);
        const averages=volData.map(row=>row.volumeAverage).filter(value=>value!==null && Number.isFinite(value));
        const maxVolume=Math.max(...volData.map(row=>row.volume),...(averages.length?averages:[1]),1);
        const horizontalStep=(right-left)/view.count;
        const barWidth=Math.max(0.5,Math.min(horizontalStep*0.56,56));
        data.forEach(row=>{
            const x=xForIndex(row.idx,left,right,meta)+horizontalStep/2;
            if(x<left-3 || x>right+3) return;
            const barHeight=Math.max(1,(row.volume/maxVolume)*(bottom-top)*0.9);
            vctx.fillStyle=row.close>=row.open?'#009735':'#d90000';
            vctx.fillRect(x-barWidth/2,bottom-barHeight,barWidth,barHeight);
        });
        vctx.save(); vctx.beginPath(); vctx.rect(left,top,right-left,bottom-top); vctx.clip();
        vctx.strokeStyle='#1679a5'; vctx.lineWidth=1.5; let started=false;
        data.forEach(row=>{
            const value=row.volumeAverage;
            if(value===null || !Number.isFinite(value)) { started=false; return; }
            const x=xForIndex(row.idx,left,right,meta)+horizontalStep/2;
            const y=bottom-(value/maxVolume)*(bottom-top)*0.9;
            if(x<left-horizontalStep || x>right+horizontalStep) return;
            if(!started) { vctx.beginPath(); vctx.moveTo(x,y); started=true; }
            else vctx.lineTo(x,y);
        });
        if(started) vctx.stroke();
        vctx.restore();
        vctx.fillStyle='#666'; vctx.font='11px Arial'; vctx.textAlign='left'; vctx.textBaseline='middle';
        vctx.fillText(niceVolume(maxVolume),right+5,top+3);
    }
    function drawAll() {
        modeSelect.value=chartMode;
        volumeSelect.value=String(volumeAverageDays);
        drawPrice(); drawVolume(); persist();
    }
    function pointerToIndex(clientX,canvas=priceCanvas) {
        const rect=canvas.getBoundingClientRect();
        const b=bounds(canvas);
        const fraction=(clientX-rect.left-b.left)/Math.max(1,b.right-b.left);
        return view.end-view.count+1+fraction*view.count;
    }
    function start(event) {
        gestureMode=null;
        if(event.touches && event.touches.length===2) {
            const first=event.touches[0],second=event.touches[1];
            const distance=Math.hypot(first.clientX-second.clientX,first.clientY-second.clientY);
            const midpoint=(first.clientX+second.clientX)/2;
            const rect=priceCanvas.getBoundingClientRect();
            const b=bounds(priceCanvas);
            const fraction=(midpoint-rect.left-b.left)/Math.max(1,b.right-b.left);
            pinch={distance,count:view.count,center:pointerToIndex(midpoint),fraction};
            drag=null; ignoreSingleTouchUntilEnd=true; event.preventDefault(); return;
        }
        if(ignoreSingleTouchUntilEnd) return;
        const point=event.touches?event.touches[0]:event;
        drag={x:point.clientX,y:point.clientY,end:view.end};
    }
    function move(event) {
        if(event.touches && event.touches.length===2) {
            const first=event.touches[0],second=event.touches[1];
            if(!pinch) start(event);
            const distance=Math.hypot(first.clientX-second.clientX,first.clientY-second.clientY);
            view.count=pinch.count*pinch.distance/Math.max(10,distance);
            view.end=pinch.center+view.count*(1-pinch.fraction)-1;
            clampView(priceCanvas); drawAll(); event.preventDefault(); return;
        }
        if(event.touches && event.touches.length===1 && ignoreSingleTouchUntilEnd) { event.preventDefault(); return; }
        if(!drag) return;
        const point=event.touches?event.touches[0]:event;
        const dx=point.clientX-drag.x;
        const dy=point.clientY-drag.y;
        if(gestureMode===null && (Math.abs(dx)>5 || Math.abs(dy)>5)) gestureMode=Math.abs(dy)>Math.abs(dx)*1.15?'pan-y':'pan-x';
        if(gestureMode==='pan-y') return;
        if(gestureMode==='pan-x') {
            const b=bounds(priceCanvas);
            const pixelsPerBar=Math.max(1,(b.right-b.left)/view.count);
            view.end=drag.end-dx/pixelsPerBar;
            clampView(priceCanvas); drawAll(); event.preventDefault();
        }
    }
    function end(event) {
        if(event.touches && event.touches.length>0) {
            if(ignoreSingleTouchUntilEnd) { pinch=null; drag=null; gestureMode=null; event.preventDefault(); }
            return;
        }
        pinch=null; drag=null; gestureMode=null; ignoreSingleTouchUntilEnd=false;
    }
    function wheel(event) {
        const center=pointerToIndex(event.clientX);
        const rect=priceCanvas.getBoundingClientRect();
        const b=bounds(priceCanvas);
        const fraction=(event.clientX-rect.left-b.left)/Math.max(1,b.right-b.left);
        view.count=view.count*(event.deltaY>0?1.12:0.88);
        view.end=center+view.count*(1-fraction)-1;
        clampView(priceCanvas); drawAll(); event.preventDefault();
    }
    calculateVolumeAverage();
    modeSelect.addEventListener('change',()=>{ chartMode=modeSelect.value==='line'?'line':'candle'; drawAll(); });
    volumeSelect.addEventListener('change',()=>{ volumeAverageDays=Number(volumeSelect.value)||14; calculateVolumeAverage(); drawAll(); });
    [priceCanvas,volumeCanvas].forEach(canvas=>{
        canvas.addEventListener('touchstart',start,{passive:false});
        canvas.addEventListener('touchmove',move,{passive:false});
        canvas.addEventListener('touchend',end,{passive:false});
        canvas.addEventListener('touchcancel',end,{passive:false});
        canvas.addEventListener('mousedown',start);
        canvas.addEventListener('mousemove',event=>{ if(drag) move(event); });
        canvas.addEventListener('mouseup',end);
        canvas.addEventListener('mouseleave',end);
        canvas.addEventListener('wheel',wheel,{passive:false});
    });
    setTimeout(drawAll,30);
    setTimeout(drawAll,180);
    return {drawAll, host};
}

document.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
        const key=th.dataset.sort;
        if(state.sortKey===key) state.sortDir*=-1;
        else {
            state.sortKey=key;
            state.sortDir=(key==='code' || key==='company')?1:-1;
        }
        render();
    });
});
filterSelect.addEventListener('change',()=>{ state.filter=filterSelect.value; state.expandedTicker=null; render(); });
watchlistSelect.addEventListener('change',()=>{
    if(watchlistSelect.value==='__create__') { createWatchlist(); return; }
    state.watchlist=watchlistSelect.value; state.expandedTicker=null; render();
});
stockBody.addEventListener('click',event=>{
    const expand=event.target.closest('[data-expand]');
    if(expand) { event.stopPropagation(); toggleExpand(expand.dataset.expand); return; }
    const menuButton=event.target.closest('[data-menu]');
    if(menuButton) { event.stopPropagation(); toggleMenu(menuButton.dataset.menu,menuButton); return; }
    const action=event.target.closest('[data-action]');
    if(action) {
        event.stopPropagation();
        if(action.dataset.action==='like') toggleLike(action.dataset.ticker);
        if(action.dataset.action==='watchlist') openWatchlistModal(action.dataset.ticker);
    }
});
document.addEventListener('click',event=>{
    if(!event.target.closest('.action-holder')) closeMenus();
});
cancelWatchlist.addEventListener('click',closeWatchlistModal);
confirmWatchlist.addEventListener('click',confirmAddToWatchlist);
modal.addEventListener('click',event=>{ if(event.target===modal) closeWatchlistModal(); });
tableShell.addEventListener('scroll',()=>{
    const host=document.querySelector('.detail-row .chart-host');
    if(host) positionChartHost(host);
    closeMenus();
},{passive:true});
window.addEventListener('resize',()=>{
    const host=document.querySelector('.detail-row .chart-host');
    if(host) positionChartHost(host);
    if(activeChart) activeChart.drawAll();
});

updateWatchlistOptions();
render();
</script>
</body>
</html>'''
    return html.replace("__STOCK_DATA__", json.dumps(stock_payload, separators=(",", ":")))


if "watchlist_text" not in st.session_state:
    st.session_state.watchlist_text = ", ".join(DEFAULT_TEST_TICKERS)

with st.sidebar:
    st.header("Data")
    source = st.radio("Source", ["Yahoo tickers", "Upload spreadsheet"])

    if source == "Yahoo tickers":
        tickers_text = st.text_area("Tickers", key="watchlist_text", height=240)
        period = st.selectbox("History", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
        interval = st.selectbox("Interval", ["1d", "1wk"], index=0)
        uploaded = None
    else:
        uploaded = st.file_uploader("Upload CSV/XLSX", type=["csv", "xlsx", "xls"])
        tickers_text = ""
        period = "1y"
        interval = "1d"

    st.header("Chart")
    candles_to_load = st.slider("Data loaded into each chart", 60, 520, 220, step=20)
    st.caption("The main screen uses a fixed sortable header. Tap a ticker to open or close its chart.")

try:
    if source == "Upload spreadsheet":
        if uploaded is None:
            st.info("Upload a spreadsheet with Date, Ticker, Open, High, Low, Close and Volume.")
            st.stop()
        market_data = load_uploaded(uploaded)
    else:
        with st.spinner("Loading stock data…"):
            market_data = fetch_yahoo(tickers_text, period, interval)
        if market_data.empty:
            st.warning("No data returned. For ASX stocks, include .AX after the ticker.")
            st.stop()

    payload = build_stock_payload(market_data, candles_to_load)
    if not payload:
        st.warning("No stocks had enough valid data to display.")
        st.stop()

    components.html(market_table_html(payload), height=840, scrolling=False)

except Exception as error:
    st.error(str(error))
