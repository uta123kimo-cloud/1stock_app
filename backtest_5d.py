
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

import unicodedata
import warnings
import logging

# 屏蔽 yfinance 錯誤訊息，防止干擾顯示格式
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

# ===================================================================
# 1. 核心參數
# ===================================================================
WATCH_LIST = ["4576", "3706", "3005", "2313","5347","6239","8046","6438","2337","2408","ASPI","3037","1560","2408","3264","2337","3711","1802","2404","3237","2375","6173"]
BENCHMARK_TICKER = "0050.TW"
TARGET_DATE = "2026-01-12"
LOOKBACK_DAYS = 360

# ===================================================================
# 2. 輔助工具
# ===================================================================
def align_text(text, width):
    text = str(text)
    cur_len = sum(2 if unicodedata.east_asian_width(c) in ('W','F','A') else 1 for c in text)
    return text + ' ' * max(0, width - cur_len)

def get_slope_poly(series, window=5):
    if len(series) < window: return 0
    y, x = series.values[-window:], np.arange(window)
    slope, _ = np.polyfit(x, y, 1)
    return (slope / (y[0] if y[0] != 0 else 1)) * 100

def get_taiwan_symbol(symbol):
    s = str(symbol).replace('$','').strip()
    if not s.isdigit(): return s
    for suffix in [".TW", ".TWO"]:
        target = f"{s}{suffix}"
        try:
            t = yf.Ticker(target)
            if not t.history(period="1d").empty:
                return target
        except:
            continue
    return f"{s}.TW"

# ===================================================================
# 3. 核心決策引擎
# ===================================================================
def get_four_dimension_advice(df, c_idx):
    window = 60
    hist_slopes = df['Slope'].iloc[max(0,c_idx-window):c_idx+1]
    hist_scores = df['Score'].iloc[max(0,c_idx-window):c_idx+1]
    sz = (df.iloc[c_idx]['Slope'] - hist_slopes.mean()) / (hist_slopes.std() + 1e-6)
    scz = (df.iloc[c_idx]['Score'] - hist_scores.mean()) / (hist_scores.std() + 1e-6)
    v = df.iloc[c_idx]['VRI']
    pd = df.iloc[c_idx]['PVO'] - df.iloc[c_idx-1]['PVO']
    try:
        is_u = df.iloc[c_idx]['Slope'] > df.iloc[c_idx-1]['Slope'] > df.iloc[c_idx-2]['Slope']
    except: is_u = False

    def direction_gate(s_z, score_z, is_up):
        if s_z>0.6 or (is_up and score_z>0): return "做多"
        elif s_z<-1.0 or (not is_up and score_z<-0.8): return "做空"
        return "觀望"

    current_dir = direction_gate(sz, scz, is_u)
    last_action_display = "---"
    if current_dir != "觀望":
        first_date = "---"
        for offset in range(1,150):
            p_idx = c_idx - offset
            if p_idx < window: break
            h_win = df['Slope'].iloc[p_idx-window:p_idx+1]
            h_sz = (df.iloc[p_idx]['Slope'] - h_win.mean()) / (h_win.std()+1e-6)
            h_win_sc = df['Score'].iloc[p_idx-window:p_idx+1]
            h_scz = (df.iloc[p_idx]['Score'] - h_win_sc.mean()) / (h_win_sc.std()+1e-6)
            h_up = df.iloc[p_idx]['Slope'] > df.iloc[p_idx-1]['Slope'] > df.iloc[p_idx-2]['Slope']
            if direction_gate(h_sz,h_scz,h_up) == current_dir:
                first_date = f"{df.index[p_idx].strftime('%m/%d')} {current_dir}"
            else: break
        last_action_display = first_date if first_date != "---" else f"今日{current_dir}"

    def detailed_gate(s_z, vri, p_d, is_up):
        if s_z>0.6:
            if s_z>1.5 and p_d>5: return "強力買進"
            return "波段持有"
        if is_up: return "準備翻多"
        return "觀望整理"

    curr_op = detailed_gate(sz,v,pd,is_u)
    return curr_op, last_action_display, sz, scz

# ===================================================================
# 4. 取得指標資料
# ===================================================================
def get_indicator_data(symbol, start_dt, end_dt):
    try:
        df = yf.download(symbol, start=start_dt, end=end_dt, progress=False, auto_adjust=True)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).strip() for c in df.columns]
        ev12, ev26 = ta.ema(df['Volume'],12), ta.ema(df['Volume'],26)
        df['PVO'] = ((ev12-ev26)/(ev26+1e-6))*100
        df['VRI'] = (ta.sma(df['Volume'].where(df['Close'].diff()>0,0),14)/(ta.sma(df['Volume'],14)+1e-6))*100
        df['Slope'] = df['Close'].rolling(5).apply(lambda x: get_slope_poly(x,5))
        df['Score'] = df['PVO']*0.2 + df['VRI']*0.2 + df['Slope']*0.6
        return df.dropna()
    except: return None

# ===================================================================
# 5. 主程式
# ===================================================================
def main():
    print(f"系統訊息：邏輯對齊分析啟動... [目標日: {TARGET_DATE}]\n")
    end_dt = datetime.strptime(TARGET_DATE,"%Y-%m-%d")+timedelta(days=1)
    start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
    tickers = [BENCHMARK_TICKER]+WATCH_LIST
    all_data = {t: get_indicator_data(get_taiwan_symbol(t),start_dt,end_dt) for t in tickers}

    w={"n":8,"d":12,"last":16,"a":10,"st":12,"o":16,"num":10}
    header=["名稱","日期","前次行動","建議","PVO狀態","VRI狀態","操作建議","現價","PVO","VRI","斜率%","斜率Z","評分","評分Z"]
    h_str = ""
    for i,h in enumerate(header):
        width = w["num"] if i>=7 else w[list(w.keys())[min(i,6)]]
        h_str += align_text(h,width)
    print(h_str)

    for ticker, df in all_data.items():
        if df is None or len(df)<5: continue
        name = ticker.split('.')[0]
        for i in reversed(range(5)):
            c_idx = len(df)-1-i
            if c_idx<2: continue
            day, prev = df.iloc[c_idx], df.iloc[c_idx-1]
            op_a,last_a,z_sl,z_sc = get_four_dimension_advice(df,c_idx)
            action="觀望"
            if ticker==BENCHMARK_TICKER: action="基準"
            elif z_sl>0.5: action="🔥強勢" if z_sl>1.5 else "💎持有"
            elif z_sl<-1.0: action="📉空頭"
            p_delta = day['PVO']-prev['PVO']
            p_s="主力點火" if p_delta>10 else ("資金流入" if day['PVO']>0 else "怠速縮量")
            v_s="健康水溫" if 40<=day['VRI']<=70 else ("擁擠過熱" if day['VRI']>90 else "情緒整理")
            row=[name,day.name.strftime('%Y/%m/%d'),last_a,action,p_s,v_s,op_a,
                 f"{day['Close']:.2f}",f"{day['PVO']:.2f}",f"{day['VRI']:.2f}",
                 f"{day['Slope']:.2f}",f"{z_sl:.2f}",f"{day['Score']:.2f}",f"{z_sc:.2f}"]
            r_str=""
            for j,r in enumerate(row):
                width=w["num"] if j>=7 else w[list(w.keys())[min(j,6)]]
                r_str+=align_text(r,width)
            print(r_str)
        print("-"*175)

if __name__=="__main__":
    main()
