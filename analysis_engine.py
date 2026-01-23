# =====================================================
# SJ 分析引擎 - 修正版（刪除動態安裝 pip，保留原有架構）
# =====================================================

# --------------------
# 套件導入
# --------------------
import sys
import warnings
import logging
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta

# --------------------
# yfinance 導入 (移除 subprocess 安裝)
# --------------------
import yfinance as yf

# --------------------
# 從專案 config 導入
# --------------------
try:
    from config import WATCH_LIST
except ImportError:
    WATCH_LIST = ["2330", "2454", "AAPL", "NVDA"]  # 備援名單

# --------------------
# 環境與警告設定
# --------------------
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore")

# --------------------
# 時間初始化（解決 base_dt / target_date 問題）
# --------------------
target_date = date.today()
base_dt = datetime.combine(target_date, datetime.min.time()) if isinstance(target_date, date) else target_date
print(f"分析基準日 base_dt: {base_dt}")

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
    s = str(symbol).strip()
    if not s.isdigit():
        return s
    for suffix in [".TW", ".TWO"]:
        try:
            t = yf.Ticker(f"{s}{suffix}")
            if not t.history(period="1d").empty:
                return f"{s}{suffix}"
        except Exception:
            continue
    return f"{s}.TW"

def get_indicator_data(symbol, start_dt, end_dt):
    try:
        df = yf.download(symbol, start=start_dt, end=end_dt, progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        # PVO
        ema12_vol = df["Volume"].ewm(span=12, adjust=False).mean()
        ema26_vol = df["Volume"].ewm(span=26, adjust=False).mean()
        df["PVO"] = ((ema12_vol - ema26_vol) / (ema26_vol + 1e-6)) * 100
        # VRI
        vol_up = df["Volume"].where(df["Close"].diff() > 0, 0)
        df["VRI"] = (vol_up.rolling(14).mean() / (df["Volume"].rolling(14).mean() + 1e-6)) * 100
        # Slope
        df["Slope"] = df["Close"].rolling(5).apply(lambda x: get_slope_poly(x, 5), raw=False)
        # Score
        df["Score"] = df["Slope"] * 0.6 + df["PVO"] * 0.2 + df["VRI"] * 0.2
        return df.dropna()
    except Exception as e:
        print(f"Error calculating indicators for {symbol}: {e}")
        return None

def get_advice(df: pd.DataFrame, idx: int):
    win = 60
    slope_hist = df["Slope"].iloc[max(0, idx - win): idx + 1]
    score_hist = df["Score"].iloc[max(0, idx - win): idx + 1]
    z_slope = (df.iloc[idx]["Slope"] - slope_hist.mean()) / (slope_hist.std() + 1e-6)
    z_score = (df.iloc[idx]["Score"] - score_hist.mean()) / (score_hist.std() + 1e-6)
    if z_slope > 1.5:
        tag = "強勢"
    elif z_slope < -1.0:
        tag = "空頭"
    else:
        tag = "觀望"
    return tag, round(float(z_slope), 2), round(float(z_score), 2)

# --------------------
# 主分析函式
# --------------------
def run_analysis(target_date: date, lookback_days: int, limit_count: int):
    if isinstance(target_date, str):
        target_dt_obj = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        target_dt_obj = datetime.combine(target_date, datetime.min.time()) if isinstance(target_date, date) else target_date

    end_dt = target_dt_obj + timedelta(days=1)
    start_dt = end_dt - timedelta(days=lookback_days + 100)  # 多抓資料

    tickers = WATCH_LIST[:limit_count]
    results = []

    for t in tickers:
        symbol = get_taiwan_symbol(t)
        df = get_indicator_data(symbol, start_dt, end_dt)
        if df is None or len(df) < 20:
            continue
        idx = len(df) - 1
        tag, z_slope, z_score = get_advice(df, idx)
        results.append({
            "股票": t,
            "日期": df.index[idx].strftime("%Y-%m-%d"),
            "狀態": tag,
            "收盤價": round(df.iloc[idx]["Close"], 2),
            "Slope%": round(df.iloc[idx]["Slope"], 2),
            "Slope_Z": z_slope,
            "Score": round(df.iloc[idx]["Score"], 2),
            "Score_Z": z_score,
            "_df": df
        })
    return pd.DataFrame(results)

def main():
    today = date.today()
    return run_analysis(
        target_date=today,
        lookback_days=150,
        limit_count=len(WATCH_LIST)
    )

if __name__ == "__main__":
    res_df = main()
    if not res_df.empty:
        print(res_df.drop(columns=['_df']).head())
