# ====== analysis_engine.py ======

import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta
import warnings
import logging

from config import WATCH_LIST   # ✅ 股票代號只從 config 來

# --------------------
# 基本設定
# --------------------
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
    """
    自動判斷 .TW / .TWO
    """
    s = str(symbol).strip()
    if not s.isdigit():
        return s

    for suffix in [".TW", ".TWO"]:
        try:
            t = yf.Ticker(f"{s}{suffix}")
            if not t.history(period="1d").empty:
                return f"{s}{suffix}"
        except Exception:
            pass

    return f"{s}.TW"


# --------------------
# 指標計算
# --------------------
def get_indicator_data(symbol, start_dt, end_dt):
    try:
        df = yf.download(
            symbol,
            start=start_dt,
            end=end_dt,
            progress=False,
            auto_adjust=True
        )

        if df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # === 技術指標 ===
        df["PVO"] = (
            (ta.ema(df["Volume"], 12) - ta.ema(df["Volume"], 26))
            / (ta.ema(df["Volume"], 26) + 1e-6)
        ) * 100

        df["VRI"] = (
            ta.sma(df["Volume"].where(df["Close"].diff() > 0, 0), 14)
            / (ta.sma(df["Volume"], 14) + 1e-6)
        ) * 100

        df["Slope"] = df["Close"].rolling(5).apply(
            lambda x: get_slope_poly(x, 5),
            raw=False
        )

        df["Score"] = (
            df["Slope"] * 0.6 +
            df["PVO"] * 0.2 +
            df["VRI"] * 0.2
        )

        return df.dropna()

    except Exception:
        return None


# --------------------
# 訊號判斷
# --------------------
def get_advice(df: pd.DataFrame, idx: int):
    win = 60

    slope_hist = df["Slope"].iloc[max(0, idx - win): idx + 1]
    score_hist = df["Score"].iloc[max(0, idx - win): idx + 1]

    z_slope = (
        (df.iloc[idx]["Slope"] - slope_hist.mean())
        / (slope_hist.std() + 1e-6)
    )

    z_score = (
        (df.iloc[idx]["Score"] - score_hist.mean())
        / (score_hist.std() + 1e-6)
    )

    if z_slope > 1.5:
        tag = "強勢"
    elif z_slope < -1.0:
        tag = "空頭"
    else:
        tag = "觀望"

    return tag, round(z_slope, 2), round(z_score, 2)


# --------------------
# 主分析引擎（回傳資料）
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


# --------------------
# 給 app.py 用的入口
# --------------------
def main():
    """
    提供給 app.py import 使用
    """
    today = datetime.now().strftime("%Y-%m-%d")
    return run_analysis(
        target_date=today,
        lookback_days=60,
        limit_count=len(WATCH_LIST)
    )


# --------------------
# CLI / Debug 用
# --------------------
if __name__ == "__main__":
    df = main()
    print(df.head())
