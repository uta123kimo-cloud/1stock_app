import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta

# ===========================================================================
# 1. 核心指標計算 (嚴格對齊您的 2308 PVO 計算邏輯)
# ===========================================================================
def get_slope_poly(data, window):
    if len(data) < window: return 0
    y = data.values
    x = np.arange(window)
    coeffs = np.polyfit(x, y, 1)
    return (coeffs[0] / y[0]) * 100 if y[0] != 0 else 0

def get_taiwan_symbol(ticker):
    ticker = str(ticker).strip()
    if ticker.isdigit():
        if len(ticker) == 4: return f"{ticker}.TW"
        elif len(ticker) == 6: return f"{ticker}.TWO"
    return ticker

def get_indicator_data(symbol, start_dt, end_dt):
    try:
        df = yf.download(symbol, start=start_dt, end=end_dt, progress=False, auto_adjust=True)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).strip() for c in df.columns]

        # PVO 計算 (完全採用您的公式)
        ev12 = ta.ema(df['Volume'], length=12)
        ev26 = ta.ema(df['Volume'], length=26)
        df['PVO'] = ((ev12 - ev26) / (ev26 + 1e-6)) * 100
        
        # VRI 計算
        df['VRI'] = (ta.sma(df['Volume'].where(df['Close'].diff() > 0, 0), 14) / (ta.sma(df['Volume'], 14) + 1e-6)) * 100
        
        # Slope 與 Score
        df['Slope'] = df['Close'].rolling(5).apply(lambda x: get_slope_poly(x, 5))
        df['Score'] = (df['PVO'] * 0.2) + (df['VRI'] * 0.2) + (df['Slope'] * 0.6)
        return df.dropna()
    except: return None

# ===========================================================================
# 2. 核心決策引擎 (維持原邏輯架構)
# ===========================================================================
def get_four_dimension_advice(df, c_idx):
    window = 60
    if c_idx < window + 2: return "數據不足", "---", 0.0, 0.0
    
    hist_slopes = df['Slope'].iloc[max(0, c_idx-window):c_idx+1]
    hist_scores = df['Score'].iloc[max(0, c_idx-window):c_idx+1]

    sz = (df.iloc[c_idx]['Slope'] - hist_slopes.mean()) / (hist_slopes.std() + 1e-6)
    scz = (df.iloc[c_idx]['Score'] - hist_scores.mean()) / (hist_scores.std() + 1e-6)

    v = df.iloc[c_idx]['VRI']
    pd = df.iloc[c_idx]['PVO'] - df.iloc[c_idx-1]['PVO']

    try:
        is_u = df.iloc[c_idx]['Slope'] > df.iloc[c_idx-1]['Slope'] > df.iloc[c_idx-2]['Slope']
    except: is_u = False

    def direction_gate(s_z, score_z, is_up):
        if s_z > 0.6 or (is_up and score_z > 0): return "做多"
        elif s_z < -1.0 or (not is_up and score_z < -0.8): return "做空"
        return "觀望"

    current_dir = direction_gate(sz, scz, is_u)

    last_action_display = "---"
    if current_dir != "觀望":
        first_date = "---"
        for offset in range(1, 150):
            p_idx = c_idx - offset
            if p_idx < window: break
            h_win = df['Slope'].iloc[p_idx-window:p_idx+1]
            h_sz = (df.iloc[p_idx]['Slope'] - h_win.mean()) / (h_win.std() + 1e-6)
            h_win_sc = df['Score'].iloc[p_idx-window:p_idx+1]
            h_scz = (df.iloc[p_idx]['Score'] - h_win_sc.mean()) / (h_win_sc.std() + 1e-6)
            try: h_up = df.iloc[p_idx]['Slope'] > df.iloc[p_idx-1]['Slope'] > df.iloc[p_idx-2]['Slope']
            except: h_up = False
            if direction_gate(h_sz, h_scz, h_up) == current_dir:
                first_date = f"{df.index[p_idx].strftime('%m/%d')} {current_dir}"
            else: break
        last_action_display = first_date if first_date != "---" else f"今日{current_dir}"

    def detailed_gate(s_z, vri, p_d, is_up):
        if s_z > 0.6:
            if s_z > 1.5 and p_d > 5: return "🚀 強力買進"
            return "💎 波段持有"
        if is_up: return "🔎 準備翻多"
        return "☕ 觀望整理"

    curr_op = detailed_gate(sz, v, pd, is_u)
    return curr_op, last_action_display, sz, scz

# ===========================================================================
# 3. Streamlit UI (視覺強化版)
# ===========================================================================
st.set_page_config(page_title="2026 四維量價戰情室", layout="wide")

# CSS 強制放大表格字體
st.markdown("""
    <style>
    .stDataFrame div[data-testid="stTable"] { font-size: 20px !important; }
    .stMetric label { font-size: 20px !important; font-weight: bold !important; }
    .stMetric div[data-testid="stMetricValue"] { font-size: 32px !important; }
    .big-status { font-size: 24px !important; font-weight: bold; color: #FF4B4B; }
    </style>
""", unsafe_allow_html=True)

def main():
    st.title("🛡️ 2026 四維量價判斷系統")
    
    with st.sidebar:
        st.header("🎯 操控面板")
        target_date = st.date_input("分析基準日", datetime.now())
        st.divider()
        ticker_input = st.text_input("輸入個股代碼", "2330")
        single_btn = st.button("單股狙擊")
        st.divider()
        full_btn = st.button("全市場掃描")

    lookback = 180
    end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d") + timedelta(days=1)
    start_dt = end_dt - timedelta(days=lookback)

    # --- 1. 大盤基準資訊 ---
    st.subheader("🌏 市場環境評估 (Benchmark)")
    b_cols = st.columns(2)
    benchmarks = {"加權指數": "^TWII", "台灣 50": "0050.TW"}
    
    for i, (name, code) in enumerate(benchmarks.items()):
        b_df = get_indicator_data(code, start_dt, end_dt)
        if b_df is not None:
            op, last, sz, _ = get_four_dimension_advice(b_df, len(b_df)-1)
            curr = b_df.iloc[-1]
            with b_cols[i]:
                st.markdown(f"<div class='big-status'>{name} ({code}) : {op}</div>", unsafe_allow_html=True)
                st.write(f"**起點：** {last}")
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("現價", f"{curr['Close']:.0f}")
                c2.metric("PVO", f"{curr['PVO']:.1f}")
                c3.metric("VRI", f"{curr['VRI']:.1f}")
                c4.metric("斜率Z", f"{sz:.2f}")
                c5.metric("Slope%", f"{curr['Slope']:.2f}")

    # --- 2. 單股狙擊處理 ---
    if single_btn:
        st.divider()
        symbol = get_taiwan_symbol(ticker_input)
        df = get_indicator_data(symbol, start_dt, end_dt)
        if df is not None:
            op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
            st.subheader(f"🎯 個股分析結果: {ticker_input}")
            st.markdown(f"<span class='big-status'>{op} (起點: {last})</span>", unsafe_allow_html=True)
            st.write(df.tail(5))
        else:
            st.error("代碼查無數據")

    # --- 3. 全市場掃描處理 ---
    if full_btn:
        st.divider()
        st.subheader("📋 全市場強勢度排序清單 (字體放大版)")
        watchlist = ["2330", "2317", "2454", "2308", "2382", "3231", "2881", "2882"] # 可自行增加
        results = []
        rank_order = {"🚀 強力買進": 1, "💎 波段持有": 2, "🔎 準備翻多": 3, "☕ 觀望整理": 4}

        with st.spinner("掃描中..."):
            for t in watchlist:
                df = get_indicator_data(get_taiwan_symbol(t), start_dt, end_dt)
                if df is not None:
                    op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
                    curr = df.iloc[-1]
                    results.append({
                        "股票": t,
                        "操作狀態": op,
                        "前次行動": last,
                        "收盤價": f"{curr['Close']:.2f}",
                        "PVO": f"{curr['PVO']:.2f}",
                        "VRI": f"{curr['VRI']:.1f}",
                        "斜率Z": sz,
                        "_rank": rank_order.get(op, 99)
                    })
        
        if results:
            res_df = pd.DataFrame(results).sort_values(by=["_rank", "斜率Z"], ascending=[True, False])
            st.dataframe(res_df.drop(columns=["_rank"]), use_container_width=True, height=600)

if __name__ == "__main__":
    main()
