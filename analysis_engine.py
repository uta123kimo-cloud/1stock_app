# ====== analysis_engine.py ======
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta
import warnings
import logging

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

WATCH_LIST = [
    "3030","3706","8096","2313","4958","2330","2317","2454","2308","2382","2303","3711",
    "2412","2357","3231","2379","3008","2395","3045","2327","2408","2377","6669","2301"
]

def get_slope_poly(series, window=5):
    if len(series) < window:
        return 0
    y = series.values[-window:]
    x = np.arange(window)
    slope, _ = np.polyfit(x, y, 1)
    base = y[0] if y[0] != 0 else 1
    return (slope / base) * 100

def get_taiwan_symbol(symbol):
    s = str(symbol).strip()
    if not s.isdigit(): return s
    for suffix in [".TW", ".TWO"]:
        try:
            t = yf.Ticker(f"{s}{suffix}")
            if not t.history(period="1d").empty: return f"{s}{suffix}"
        except: pass
    return f"{s}.TW"

def get_indicator_data(symbol, start_dt, end_dt):
    try:
        df = yf.download(symbol, start=start_dt, end=end_dt, progress=False, auto_adjust=True)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # PVO、VRI、Slope 計算 [cite: 2026-01-04]
        df['PVO'] = ((ta.ema(df['Volume'], 12) - ta.ema(df['Volume'], 26)) / (ta.ema(df['Volume'], 26) + 1e-6)) * 100
        df['VRI'] = (ta.sma(df['Volume'].where(df['Close'].diff() > 0, 0), 14) / (ta.sma(df['Volume'], 14) + 1e-6)) * 100
        df['Slope'] = df['Close'].rolling(5).apply(lambda x: get_slope_poly(x, 5))
        df['Score'] = df['Slope'] * 0.6 + df['PVO'] * 0.2 + df['VRI'] * 0.2
        return df.dropna()
    except: return None

def get_advice(df, idx):
    win = 60
    s_hist = df['Slope'].iloc[max(0, idx-win):idx+1]
    sc_hist = df['Score'].iloc[max(0, idx-win):idx+1]
    z_slope = (df.iloc[idx]['Slope'] - s_hist.mean()) / (s_hist.std() + 1e-6)
    z_score = (df.iloc[idx]['Score'] - sc_hist.mean()) / (sc_hist.std() + 1e-6)
    tag = "強勢" if z_slope > 1.5 else "空頭" if z_slope < -1.0 else "觀望"
    return tag, round(z_slope, 2), round(z_score, 2)

def run_analysis(target_date, lookback_days, limit_count):
    end_dt = datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)
    start_dt = end_dt - timedelta(days=lookback_days)
    tickers = WATCH_LIST[:limit_count]
    results = []
    for t in tickers:
        symbol = get_taiwan_symbol(t)
        df = get_indicator_data(symbol, start_dt, end_dt)
        if df is None or len(df) < 10: continue
        idx = len(df) - 1
        tag, z_slope, z_score = get_advice(df, idx)
        results.append({
            "股票": t, "日期": df.iloc[idx].name.strftime('%Y-%m-%d'),
            "狀態": tag, "收盤價": round(df.iloc[idx]['Close'], 2),
            "Slope%": round(df.iloc[idx]['Slope'], 2), "Slope_Z": z_slope,
            "Score": round(df.iloc[idx]['Score'], 2), "Score_Z": z_score, "_df": df
        })
    return pd.DataFrame(results)

# 重要：這就是解決 app.py 第 9 行報錯的關鍵！
def main():
    # 預設執行最近 60 天的分析 [cite: 2026-01-04]
    today_str = datetime.now().strftime('%Y-%m-%d')
    return run_analysis(today_str, 60, 10)

if __name__ == "__main__":
    print(main())
