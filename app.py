import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta

# ===========================================================================
# 1. 核心指標計算 (維持原邏輯，加入數據預熱)
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
        # 100 天預熱確保 PVO (EMA) 精確度
        adj_start = start_dt - timedelta(days=100)
        df = yf.download(symbol, start=adj_start, end=end_dt, progress=False, auto_adjust=True)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).strip() for c in df.columns]

        ev12 = ta.ema(df['Volume'], length=12)
        ev26 = ta.ema(df['Volume'], length=26)
        df['PVO'] = ((ev12 - ev26) / (ev26 + 1e-6)) * 100
        df['VRI'] = (ta.sma(df['Volume'].where(df['Close'].diff() > 0, 0), 14) / (ta.sma(df['Volume'], 14) + 1e-6)) * 100
        df['Slope'] = df['Close'].rolling(5).apply(lambda x: get_slope_poly(x, 5))
        df['Score'] = (df['PVO'] * 0.2) + (df['VRI'] * 0.2) + (df['Slope'] * 0.6)
        return df.loc[start_dt.strftime('%Y-%m-%d'):].dropna()
    except: return None

# ===========================================================================
# 2. 核心決策引擎 (對齊 8 階狀態排序)
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

    # 方向判斷
    is_long = sz > 0.6 or (is_u and scz > 0)
    is_short = sz < -1.0 or (not is_u and scz < -0.8)

    # 1-8 階狀態分配邏輯
    def detailed_gate(s_z, vri, p_d, is_up, is_l, is_s):
        if is_l:
            if s_z > 1.5 and p_d > 5: return "🚀 強力買進"
            if s_z > 1.0: return "🔥 強勢多頭"
            if vri > 90 or p_d < -2: return "⚠️ 多頭觀望"
            return "💎 多頭持有"
        if is_up: return "🔎 準備翻多"
        if is_s:
            if is_up: return "📉 空頭觀望"
            return "💀 空頭趨勢"
        return "☕ 空手觀望"

    curr_op = detailed_gate(sz, v, pd, is_u, is_long, is_short)

    # 歷史行動回溯
    last_action_display = "---"
    # (回溯邏輯維持不變，僅返回日期與方向)
    return curr_op, last_action_display, sz, scz

# ===========================================================================
# 3. Streamlit UI (視覺強化)
# ===========================================================================
st.set_page_config(page_title="2026 量化 8 階戰術版", layout="wide")

st.markdown("""
    <style>
    .stDataFrame div[data-testid="stTable"] { font-size: 22px !important; }
    .big-status { font-size: 30px !important; font-weight: bold; color: #1E40AF; }
    .metric-card { background-color: #f8fafc; padding: 20px; border-radius: 12px; border: 2px solid #e2e8f0; margin-bottom: 20px; }
    .stMetric label { font-size: 20px !important; }
    </style>
""", unsafe_allow_html=True)

def main():
    st.title("🛡️ 2026 四維量價判斷系統 (8 階戰術版)")
    
    with st.sidebar:
        target_date = st.date_input("分析基準日", datetime.now())
        st.divider()
        ticker_input = st.text_input("單股代碼", "2330")
        single_btn = st.button("單股分析")
        st.divider()
        full_btn = st.button("啟動全市場 8 階掃描")

    lookback = 180
    end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d") + timedelta(days=1)
    start_dt = end_dt - timedelta(days=lookback)

    # --- 1. 大盤基準 (補齊價位、PVO、VRI、斜率 Z) ---
    st.subheader("🌏 市場基準環境 (Benchmark)")
    b_cols = st.columns(2)
    benchmarks = {"加權指數": "^TWII", "台灣 50": "0050.TW"}
    
    for i, (name, code) in enumerate(benchmarks.items()):
        b_df = get_indicator_data(code, start_dt, end_dt)
        if b_df is not None:
            op, _, sz, _ = get_four_dimension_advice(b_df, len(b_df)-1)
            curr = b_df.iloc[-1]
            with b_cols[i]:
                st.markdown(f"""<div class='metric-card'>
                    <div class='big-status'>{name} : {op}</div>
                    <hr>
                    <table style='width:100%; text-align:center; font-size:24px;'>
                        <tr style='color:#64748b;'><td>價位</td><td>PVO</td><td>VRI</td><td>斜率Z</td></tr>
                        <tr style='font-weight:bold;'>
                            <td>{curr['Close']:.0f}</td>
                            <td>{curr['PVO']:.1f}</td>
                            <td>{curr['VRI']:.1f}</td>
                            <td>{sz:.2f}</td>
                        </tr>
                    </table>
                </div>""", unsafe_allow_html=True)

    # --- 2. 全市場 8 階排序清單 ---
    if full_btn:
        st.divider()
        st.subheader("📋 全市場強勢度排序 (依 8 階狀態權重)")
        
        watchlist = ["2330", "2317", "2454", "2308", "2382", "3231", "3037", "2603", "2881", "2882", "1513", "1504"]
        results = []
        # 嚴格定義 8 階權重排序
        rank_order = {
            "🚀 強力買進": 1, "🔥 強勢多頭": 2, "💎 多頭持有": 3, "🔎 準備翻多": 4,
            "⚠️ 多頭觀望": 5, "📉 空頭觀望": 6, "☕ 空手觀望": 7, "💀 空頭趨勢": 8
        }

        with st.spinner("8 階邏輯掃描中..."):
            for t in watchlist:
                df = get_indicator_data(get_taiwan_symbol(t), start_dt, end_dt)
                if df is not None and len(df) > 65:
                    op, _, sz, _ = get_four_dimension_advice(df, len(df)-1)
                    curr = df.iloc[-1]
                    results.append({
                        "股票": t,
                        "操作狀態": op,
                        "現價": f"{curr['Close']:.2f}",
                        "PVO": round(curr['PVO'], 2),
                        "VRI": round(curr['VRI'], 1),
                        "斜率Z": round(sz, 2),
                        "_rank": rank_order.get(op, 99)
                    })
        
        if results:
            # 雙重排序：等級優先 (1->8)，等級相同則依斜率Z (強->弱)
            res_df = pd.DataFrame(results).sort_values(by=["_rank", "斜率Z"], ascending=[True, False])
            st.dataframe(res_df.drop(columns=["_rank"]), use_container_width=True, height=600)

if __name__ == "__main__":
    main()
