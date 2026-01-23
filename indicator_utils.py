
# ====== analysis_engine.py ======

import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
# --- 放在程式最上方 ---
from datetime import datetime, date

# 定義 target_date
target_date = date.today()  # 或 datetime.now().date()

# base_dt 轉換成 datetime
base_dt = datetime.combine(target_date, datetime.min.time()) if isinstance(target_date, date) else target_date

print(base_dt)

import warnings
import logging

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

WATCH_LIST = [
    "3030", "3706", "8096", "2313", "4958",
    "2330", "2317", "2454", "2308", "2382", "2303", "3711", "2412", "2357", "3231",
    "2379", "3008", "2395", "3045", "2327", "2408", "2377", "6669", "2301", "3034",
    "2345", "2474", "3037", "4938", "3443", "2353", "2324", "2603", "2609", "1513",
    "3293", "3680", "3529", "3131", "5274", "6223", "6805", "3017", "3324", "6515",
    "3661", "3583", "6139", "3035", "1560", "8299", "3558", "6187", "3406", "3217",
    "6176", "6415", "6206", "8069", "3264", "5269", "2360", "6271", "3189", "6438",
    "8358", "6231", "2449", "3030", "8016", "6679", "3374", "3014", "3211",
    "6213", "2404", "2480", "3596", "6202", "5443", "5347", "5483", "6147",
    "2313", "3037", "8046", "2368", "4958", "2383", "6269", "5469", "5351", "8096",
    "4909", "8050", "6153", "6505", "1802", "3708", "8213", "1325",
    "2344", "6239", "3260", "4967", "6414", "2337",
    "3551", "2436", "2375", "2492", "2456", "3229", "6173", "3533"
]

BENCHMARK_TICKER = "0050.TW"

def get_slope_poly(series, window=5):
    if len(series) < window:
        return 0
    y = series.values[-window:]
    x = np.arange(window)
    slope, _ = np.polyfit(x, y, 1)
    return (slope / (y[0] if y[0] != 0 else 1)) * 100

def get_taiwan_symbol(symbol):
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

def get_indicator_data(symbol, start_dt, end_dt):
    try:
        df = yf.download(symbol, start=start_dt, end=end_dt,
                         progress=False, auto_adjust=True)
        if df.empty:
            return None

        df['PVO'] = ((ta.ema(df['Volume'], 12) - ta.ema(df['Volume'], 26))
                     / (ta.ema(df['Volume'], 26) + 1e-6)) * 100
        df['VRI'] = (ta.sma(df['Volume'].where(df['Close'].diff() > 0, 0), 14)
                     / (ta.sma(df['Volume'], 14) + 1e-6)) * 100
        df['Slope'] = df['Close'].rolling(5).apply(
            lambda x: get_slope_poly(x, 5))
        df['Score'] = df['Slope'] * 0.6 + df['PVO'] * 0.2 + df['VRI'] * 0.2

        return df.dropna()
    except:
        return None

def get_advice(df, idx):
    win = 60
    s_hist = df['Slope'].iloc[max(0, idx-win):idx+1]
    sc_hist = df['Score'].iloc[max(0, idx-win):idx+1]

    z_slope = (df.iloc[idx]['Slope'] - s_hist.mean()) / (s_hist.std() + 1e-6)
    z_score = (df.iloc[idx]['Score'] - sc_hist.mean()) / (sc_hist.std() + 1e-6)

    if z_slope > 1.5:
        tag = "強勢"
    elif z_slope < -1.0:
        tag = "空頭"
    else:
        tag = "觀望"

    return tag, round(z_slope, 2), round(z_score, 2)

def run_analysis(target_date, lookback_days, limit_count):
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
        day = df.iloc[idx]

        tag, z_slope, z_score = get_advice(df, idx)

        results.append({
            "股票": t,
            "日期": day.name.strftime('%Y-%m-%d'),
            "狀態": tag,
            "收盤價": round(day['Close'], 2),
            "Slope%": round(day['Slope'], 2),
            "Slope_Z": z_slope,
            "Score": round(day['Score'], 2),
            "Score_Z": z_score,
            "_df": df
        })

    return pd.DataFrame(results)
