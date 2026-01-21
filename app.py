# ==================== analysis_engine.py ====================

import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta
import warnings, logging
from config import WATCH_LIST

logging.getLogger("yfinance").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore")

# --------------------
# 工具函式
# --------------------
def get_slope_poly(series, window=5):
    if len(series) < window:
        return 0.0
    y = series.values[-window:]
    x = np.arange(window)
    slope, _ = np.polyfit(x, y, 1)
    base = y[0] if y[0] != 0 else 1
    return (slope / base) * 100

def get_taiwan_symbol(symbol: str) -> str:
    """自動判斷 .TW / .TWO"""
    s = str(symbol).strip()
    if not s.isdigit():
        return s
    for suffix in [".TW", ".TWO"]:
        try:
            t = yf.Ticker(f"{s}{suffix}")
            if not t.history(period="1d").empty:
                return f"{s}{suffix}"
        except:
            pass
    return f"{s}.TW"

# --------------------
# 指標計算
# --------------------
def get_indicator_data(symbol, start_dt, end_dt):
    try:
        df = yf.download(symbol, start=start_dt, end=end_dt, progress=False, auto_adjust=True)
        if df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df["PVO"] = ((ta.ema(df["Volume"], 12) - ta.ema(df["Volume"], 26)) / (ta.ema(df["Volume"], 26) + 1e-6)) * 100
        df["VRI"] = (ta.sma(df["Volume"].where(df["Close"].diff() > 0, 0), 14) / (ta.sma(df["Volume"], 14) + 1e-6)) * 100
        df["Slope"] = df["Close"].rolling(5).apply(lambda x: get_slope_poly(x, 5), raw=False)
        df["Score"] = df["Slope"]*0.6 + df["PVO"]*0.2 + df["VRI"]*0.2

        return df.dropna()

    except:
        return None

# --------------------
# 多頭/空頭訊號判斷
# --------------------
def get_advice(df: pd.DataFrame, idx: int):
    win = 60
    slope_hist = df["Slope"].iloc[max(0, idx-win): idx+1]
    score_hist = df["Score"].iloc[max(0, idx-win): idx+1]
    z_slope = (df.iloc[idx]["Slope"] - slope_hist.mean()) / (slope_hist.std() + 1e-6)
    z_score = (df.iloc[idx]["Score"] - score_hist.mean()) / (score_hist.std() + 1e-6)

    if z_slope > 1.5:
        tag = "強勢"
    elif z_slope < -1.0:
        tag = "空頭"
    else:
        tag = "觀望"
    return tag, round(z_slope,2), round(z_score,2)

# --------------------
# 主分析引擎
# --------------------
def run_analysis(target_date: str, lookback_days: int, limit_count: int):
    end_dt = datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)
    start_dt = end_dt - timedelta(days=lookback_days)
    tickers = WATCH_LIST[:limit_count]
    results = []

    for t in tickers:
        symbol = get_taiwan_symbol(t)
        df = get_indicator_data(symbol, start_dt, end_dt)
        if df is None or len(df) < 10:
            continue
        idx = len(df)-1
        tag, z_slope, z_score = get_advice(df, idx)
        results.append({
            "代號": symbol,
            "狀態": tag,
            "收盤": df.iloc[idx]["Close"],
            "PVO": df.iloc[idx]["PVO"],
            "VRI": df.iloc[idx]["VRI"],
            "Slope_Z": z_slope,
            "Score_Z": z_score,
            "_df": df
        })

    return pd.DataFrame(results)


# ==================== APP.py ====================

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from analysis_engine import run_analysis, get_taiwan_symbol, get_advice
from config import WATCH_LIST as TAIWAN_LIST
from configA import WATCH_LIST as US_LIST

# --------------------
# UI 設定
# --------------------
st.set_page_config(page_title="SJ 四維量價戰情室", layout="wide")
st.markdown("""<style>h1,h2,h3,p,label,span,div{font-size:16px !important;} table td{font-size:14px !important;}</style>""", unsafe_allow_html=True)

# --------------------
with st.sidebar:
    st.title("🎯 分析模式")
    mode = st.radio("選擇分析類型", ["單股分析", "台股市場分析", "美股市場分析"])
    st.divider()
    target_date = st.date_input("分析基準日", datetime.now())
    st.divider()
    ticker_input = st.text_input("單股代號", "2330")
    run_btn = st.button("開始分析")

LOOKBACK_1Y = 365
end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d")+timedelta(days=1)
start_1y = end_dt - timedelta(days=LOOKBACK_1Y)

# --------------------
def safe_get_value(val):
    if val is None or (isinstance(val,float) and np.isnan(val)):
        return "未提供"
    return round(val,2)

def format_price(symbol,price):
    if price=="未提供": return price
    return int(round(price,0)) if ".TW" in symbol or ".TWO" in symbol else round(price,2)

# --------------------
# 市場分析 (台股 / 美股)
# --------------------
if run_btn and mode in ["台股市場分析","美股市場分析"]:
    st.subheader("📊 市場整體強弱分析")

    watch = TAIWAN_LIST if mode=="台股市場分析" else US_LIST
    results = run_analysis(target_date, LOOKBACK_1Y, len(watch))

    # 安全處理空值
    results["收盤"] = results["收盤"].apply(safe_get_value)
    results["PVO"] = results["PVO"].apply(safe_get_value)
    results["VRI"] = results["VRI"].apply(safe_get_value)

    # 狀態排序
    status_order = ["強勢","多單續抱","觀望","空頭"]
    results["狀態排序"] = results["狀態"].apply(lambda x: status_order.index(x) if x in status_order else 99)
    results = results.sort_values(by="狀態排序")

    # 狀態統計
    status_count = results["狀態"].value_counts().to_dict()

    st.markdown("### 🗂️ 狀態統計")
    for s in status_order:
        cnt = status_count.get(s,0)
        st.markdown(f"{s}: {cnt}")

    st.markdown("### 📋 市場明細")
    results_display = results[["代號","狀態","收盤","PVO","VRI","Slope_Z","Score_Z"]]
    st.dataframe(results_display,use_container_width=True)
