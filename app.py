import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta
import analysis_engine as engine 

# ===========================================================================
# 3. 核心決策引擎 (嚴格維持您的原邏輯架構)
# ===========================================================================
def get_four_dimension_advice(df, c_idx):
    window = 60
    # 確保索引安全
    if c_idx < window + 2: return "數據不足", "---", 0.0, 0.0
    
    hist_slopes = df['Slope'].iloc[max(0, c_idx-window):c_idx+1]
    hist_scores = df['Score'].iloc[max(0, c_idx-window):c_idx+1]

    sz = (df.iloc[c_idx]['Slope'] - hist_slopes.mean()) / (hist_slopes.std() + 1e-6)
    scz = (df.iloc[c_idx]['Score'] - hist_scores.mean()) / (hist_scores.std() + 1e-6)

    v = df.iloc[c_idx]['VRI']
    pd_val = df.iloc[c_idx]['PVO'] - df.iloc[c_idx-1]['PVO']

    try:
        # 連續三日斜率上升判斷
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
            else:
                break
        last_action_display = first_date if first_date != "---" else f"今日{current_dir}"

    def detailed_gate(s_z, vri, p_d, is_up):
        if s_z > 0.6:
            if s_z > 1.5 and p_d > 5: return "🚀 強力買進"
            return "💎 波段持有"
        if is_up: return "🔎 準備翻多"
        return "☕ 觀望整理"

    curr_op = detailed_gate(sz, v, pd_val, is_u)
    
    # 針對 ^TWII 特別修正標籤 (如 user 要求: ⚠️ 多頭觀望)
    if curr_op == "💎 波段持有" and (v > 90 or pd_val < -2):
        curr_op = "⚠️ 多頭觀望"

    return curr_op, last_action_display, sz, scz

# ==========================================
# 4. UI 與視覺強化
# ==========================================
st.set_page_config(page_title="2026 量化戰情室", layout="wide")

# 強制放大字體 CSS
st.markdown("""
    <style>
    .big-font { font-size:22px !important; font-weight: bold; }
    .status-card { padding: 15px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 10px; }
    [data-testid="stMetricValue"] { font-size: 28px !important; }
    .stDataFrame div { font-size: 18px !important; }
    </style>
""", unsafe_allow_html=True)

def main():
    st.title("🛡️ 2026 四維量價判斷系統")

    with st.sidebar:
        st.header("🎯 操控台")
        target_date = st.date_input("基準日", datetime.now())
        st.divider()
        ticker_input = st.text_input("個股狙擊 (代碼)", "2330")
        single_btn = st.button("單股分析")
        st.divider()
        full_btn = st.button("啟動全市場掃描")

    lookback = 180
    end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d") + timedelta(days=1)
    start_dt = end_dt - timedelta(days=lookback)

    # --- 大盤資訊顯示 (不論按哪個按鈕都顯示基準) ---
    st.subheader("🌏 市場大盤趨勢溫度計")
    b_cols = st.columns(2)
    benchmarks = {"加權指數": "^TWII", "台灣 50": "0050.TW"}
    
    for i, (name, code) in enumerate(benchmarks.items()):
        b_df = engine.get_indicator_data(code, start_dt, end_dt)
        if b_df is not None:
            op, last, sz, _ = get_four_dimension_advice(b_df, len(b_df)-1)
            day = b_df.iloc[-1]
            with b_cols[i]:
                st.markdown(f"""<div class='status-card'>
                    <span class='big-font'>{name} ({code})</span><br>
                    <span style='color:red; font-size:24px;'>{op}</span> (起點：{last})
                </div>""", unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("現價", f"{day['Close']:.0f}")
                c2.metric("PVO", f"{day['PVO']:.1f}")
                c3.metric("VRI", f"{day['VRI']:.1f}")
                c4.metric("斜率Z", f"{sz:.2f}")

    # --- 邏輯：單股 ---
    if single_btn:
        st.divider()
        symbol = engine.get_taiwan_symbol(ticker_input)
        df = engine.get_indicator_data(symbol, start_dt, end_dt)
        if df is not None:
            op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
            st.markdown(f"### 🎯 個股診斷：{ticker_input} -> <span style='color:red;'>{op}</span>", unsafe_allow_html=True)
            st.write(f"**前次行動日期：** {last} | **綜合評分Z：** {scz:.2f}")
        else:
            st.error("代碼錯誤")

    # --- 邏輯：全掃描 ---
    if full_btn:
        st.divider()
        st.subheader("📋 全市場強勢度排序清單")
        with st.spinner("掃描中..."):
            df_results = engine.run_analysis(target_date.strftime('%Y-%m-%d'), lookback, 100)
            if not df_results.empty:
                final_data = []
                # 排序權重字典
                rank_map = {"🚀 強力買進": 1, "💎 波段持有": 2, "⚠️ 多頭觀望": 3, "🔎 準備翻多": 4, "☕ 觀望整理": 5}
                
                for _, row in df_results.iterrows():
                    hist = row.get('_df')
                    if hist is not None and len(hist) >= 65:
                        op, last, sz, scz = get_four_dimension_advice(hist, len(hist)-1)
                        final_data.append({
                            "股票": row['股票'],
                            "操作狀態": op,
                            "前次行動": last,
                            "現價": f"{row['收盤價']:.2f}",
                            "斜率Z": sz,
                            "PVO": f"{hist.iloc[-1]['PVO']:.1f}",
                            "VRI": f"{hist.iloc[-1]['VRI']:.1f}",
                            "_rank": rank_map.get(op, 9)
                        })
                
                res_df = pd.DataFrame(final_data).sort_values(by=["_rank", "斜率Z"], ascending=[True, False])
                
                # 顯示大字體表格
                st.dataframe(
                    res_df.drop(columns=["_rank"]), 
                    use_container_width=True, 
                    height=800
                )

if __name__ == "__main__":
    main()
