import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta

# ===========================================================================
# 1. 基礎工具函數 (包含您使用的 Slope 計算)
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

# ===========================================================================
# 2. 數據獲取與指標計算 (嚴格校準 PVO 與 EMA)
# ===========================================================================
def get_indicator_data(symbol, start_dt, end_dt):
    try:
        # 為了讓 EMA 計算精確，多抓 60 天數據作為緩衝
        adj_start = start_dt - timedelta(days=60)
        df = yf.download(symbol, start=adj_start, end=end_dt, progress=False, auto_adjust=True)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).strip() for c in df.columns]

        # PVO 100% 對齊您的公式
        ev12 = ta.ema(df['Volume'], length=12)
        ev26 = ta.ema(df['Volume'], length=26)
        df['PVO'] = ((ev12 - ev26) / (ev26 + 1e-6)) * 100
        
        # VRI
        df['VRI'] = (ta.sma(df['Volume'].where(df['Close'].diff() > 0, 0), 14) / (ta.sma(df['Volume'], 14) + 1e-6)) * 100
        
        # Slope & Score
        df['Slope'] = df['Close'].rolling(5).apply(lambda x: get_slope_poly(x, 5))
        df['Score'] = (df['PVO'] * 0.2) + (df['VRI'] * 0.2) + (df['Slope'] * 0.6)
        
        # 僅回傳基準日之後的數據以維持 Z-Score 一致性
        return df.loc[start_dt.strftime('%Y-%m-%d'):].dropna()
    except Exception:
        return None

# ===========================================================================
# 3. 核心決策引擎 (維持您提供的原邏輯架構)
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
            try:
                h_up = df.iloc[p_idx]['Slope'] > df.iloc[p_idx-1]['Slope'] > df.iloc[p_idx-2]['Slope']
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
# 4. 主介面 (視覺強化與強勢度排列)
# ===========================================================================
st.set_page_config(page_title="2026 四維量價戰情室", layout="wide")

# CSS 注入：強制放大表格字體與大盤卡片字體
st.markdown("""
    <style>
    /* 表格內容與標題字體 */
    .stDataFrame div[data-testid="stTable"] { font-size: 18px !important; }
    div[data-testid="stExpander"] p { font-size: 18px !important; }
    /* 大盤卡片文字大小 */
    .metric-container { background-color: #f0f2f6; padding: 16px; border-radius: 14px; border: 2px solid #d1d5db; }
    .big-status { font-size: 16px !important; font-weight: bold; color: #1e40af; }
    .metric-value { font-size: 16px !important; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

def main():
    st.title("🛡️ 2026 四維量價判斷系統")

    with st.sidebar:
        st.header("🎯 操控台")
        target_date = st.date_input("基準日", datetime.now())
        st.divider()
        ticker_input = st.text_input("個股診斷代碼", "2330")
        single_btn = st.button("單股分析")
        st.divider()
        full_btn = st.button("啟動全市場清單掃描")

    # 設定日期
    lookback = 180
    end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d") + timedelta(days=1)
    start_dt = end_dt - timedelta(days=lookback)

    # --- 第一部分：大盤與 0050 狀態 (補齊項目) ---
    st.subheader("🌏 市場大盤環境監控 (Benchmark)")
    b_cols = st.columns(2)
    benchmarks = {"加權指數": "^TWII", "台灣 50": "0050.TW"}
    
    for i, (name, code) in enumerate(benchmarks.items()):
        b_df = get_indicator_data(code, start_dt, end_dt)
        if b_df is not None and not b_df.empty:
            op, last, sz, _ = get_four_dimension_advice(b_df, len(b_df)-1)
            curr = b_df.iloc[-1]
            with b_cols[i]:
                st.markdown(f"""
                <div class="metric-container">
                    <div class="big-status">{name} ({code}) : {op}</div>
                    <div style="font-size: 20px; color: #555;">訊號起點: {last}</div>
                    <hr>
                    <table style="width:100%; text-align:center; font-size:24px;">
                        <tr>
                            <td><b>價位</b></td><td><b>PVO</b></td><td><b>VRI</b></td><td><b>斜率Z</b></td>
                        </tr>
                        <tr>
                            <td class="metric-value">{curr['Close']:.0f}</td>
                            <td class="metric-value">{curr['PVO']:.1f}</td>
                            <td class="metric-value">{curr['VRI']:.1f}</td>
                            <td class="metric-value">{sz:.2f}</td>
                        </tr>
                    </table>
                </div>
                """, unsafe_allow_html=True)

    # --- 第二部分：全市場強勢度排列 (大字體 + 狀態排序) ---
    if full_btn:
        st.divider()
        st.subheader("📋 全市場強勢度排序清單 (狀態與斜率雙重排列)")
        
        # 這裡建議放入您的 Watchlist
        watchlist = ["2330", "2317", "2454", "2308", "2382", "3231", "3037", "2603", "2881", "2882", "1513", "1504"]
        
        results = []
        # 定義排列優先級
        status_rank = {"🚀 強力買進": 1, "💎 波段持有": 2, "🔎 準備翻多": 3, "☕ 觀望整理": 4}

        with st.spinner("正在掃描並計算強勢度..."):
            for t in watchlist:
                df = get_indicator_data(get_taiwan_symbol(t), start_dt, end_dt)
                if df is not None and len(df) > 65:
                    op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
                    curr = df.iloc[-1]
                    results.append({
                        "股票代號": t,
                        "操作狀態": op,
                        "起點訊號": last,
                        "現價": f"{curr['Close']:.2f}",
                        "PVO": f"{curr['PVO']:.2f}",
                        "VRI": f"{curr['VRI']:.1f}",
                        "斜率Z": round(sz, 2),
                        "綜合評分Z": round(scz, 2),
                        "_rank": status_rank.get(op, 99)
                    })

        if results:
            res_df = pd.DataFrame(results).sort_values(by=["_rank", "斜率Z"], ascending=[True, False])
            # 移除隱藏的排序欄位
            display_df = res_df.drop(columns=["_rank"])
            st.dataframe(display_df, use_container_width=True, height=600)
        else:
            st.warning("數據獲取失敗，請確認日期是否為交易日。")

    # --- 第三部分：單股診斷 ---
    if single_btn:
        st.divider()
        symbol = get_taiwan_symbol(ticker_input)
        df = get_indicator_data(symbol, start_dt, end_dt)
        if df is not None:
            op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
            st.markdown(f"### 🎯 {ticker_input} 深度分析結果")
            st.markdown(f"<span class='big-status'>{op}</span> (訊號起點：{last})", unsafe_allow_html=True)
            st.write(df.tail(5))

if __name__ == "__main__":
    main()
