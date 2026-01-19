import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta
import analysis_engine as engine 

# ===========================================================================
# 3. 核心決策引擎 (完全對齊您的原始邏輯)
# ===========================================================================
def get_four_dimension_advice(df, c_idx):
    window = 60
    # 這裡確保索引不會越界
    if c_idx < window + 2: return "數據不足", "---", 0, 0
    
    hist_slopes = df['Slope'].iloc[max(0, c_idx-window):c_idx+1]
    hist_scores = df['Score'].iloc[max(0, c_idx-window):c_idx+1]

    sz = (df.iloc[c_idx]['Slope'] - hist_slopes.mean()) / (hist_slopes.std() + 1e-6)
    scz = (df.iloc[c_idx]['Score'] - hist_scores.mean()) / (hist_scores.std() + 1e-6)

    v = df.iloc[c_idx]['VRI']
    pd_val = df.iloc[c_idx]['PVO'] - df.iloc[c_idx-1]['PVO']

    # 您的原邏輯：連續三日斜率上升
    try:
        is_u = df.iloc[c_idx]['Slope'] > df.iloc[c_idx-1]['Slope'] > df.iloc[c_idx-2]['Slope']
    except: is_u = False

    # 方向閘門
    def direction_gate(s_z, score_z, is_up):
        if s_z > 0.6 or (is_up and score_z > 0): return "做多"
        elif s_z < -1.0 or (not is_up and score_z < -0.8): return "做空"
        return "觀望"

    current_dir = direction_gate(sz, scz, is_u)

    # 歷史行動追蹤 (回溯 150 天)
    last_action_display = "---"
    if current_dir != "觀望":
        first_date = "---"
        for offset in range(1, 150):
            p_idx = c_idx - offset
            if p_idx < window + 2: break

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

    # 操作建議細分
    def detailed_gate(s_z, vri, p_d, is_up):
        if s_z > 0.6:
            if s_z > 1.5 and p_d > 5: return "🚀 強力買進"
            return "💎 波段持有"
        if is_up: return "🔎 準備翻多"
        # 增加您要求的細分標籤
        if s_z < -1.0: return "📉 空頭趨勢"
        return "☕ 觀望整理"

    curr_op = detailed_gate(sz, v, pd_val, is_u)
    
    # 額外判斷「多頭觀望」
    if curr_op == "💎 波段持有" and (v > 90 or pd_val < -2):
        curr_op = "⚠️ 多頭觀望"
    elif s_z < -1.0 and is_u:
        curr_op = "📉 空頭觀望"

    return curr_op, last_action_display, sz, scz

# ==========================================
# 4. Streamlit UI 介面
# ==========================================
st.set_page_config(page_title="2026 量化交易終端", layout="wide")

def main():
    st.title("📊 2026 四維量價判斷系統 (邏輯完全對齊版)")

    with st.sidebar:
        st.header("🎯 模式選擇")
        mode = st.radio("功能", ["個股狙擊", "全市場掃描"])
        target_date = st.date_input("基準日期", datetime.now())
        
        if mode == "個股狙擊":
            ticker = st.text_input("輸入代碼 (2330)", "2330")
            btn = st.button("執行診斷")
        else:
            btn = st.button("啟動全掃描 (180D)")

    if btn:
        lookback = 180
        end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d") + timedelta(days=1)
        start_dt = end_dt - timedelta(days=lookback)

        if mode == "個股狙擊":
            symbol = engine.get_taiwan_symbol(ticker)
            df = engine.get_indicator_data(symbol, start_dt, end_dt)
            if df is not None:
                op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
                st.subheader(f"個股報告: {ticker}")
                col1, col2, col3 = st.columns(3)
                col1.metric("目前建議", op)
                col2.metric("前次行動", last)
                col3.metric("Slope_Z", f"{sz:.2f}")
                st.dataframe(df.tail(10))
            else:
                st.error("查無資料")

        else:
            # 大盤指標優先
            st.subheader("🌏 市場大盤環境")
            m_cols = st.columns(2)
            for i, m_code in enumerate(["^TWII", "0050.TW"]):
                m_df = engine.get_indicator_data(m_code, start_dt, end_dt)
                if m_df is not None:
                    m_op, m_last, m_sz, _ = get_four_dimension_advice(m_df, len(m_df)-1)
                    m_cols[i].info(f"**{m_code}**: {m_op} (起始於 {m_last})")

            st.divider()
            
            # 全清單掃描
            df_results = engine.run_analysis(target_date.strftime('%Y-%m-%d'), lookback, 100)
            if not df_results.empty:
                final_rows = []
                for _, row in df_results.iterrows():
                    hist = row.get('_df')
                    if hist is not None and len(hist) >= 5:
                        op, last, sz, scz = get_four_dimension_advice(hist, len(hist)-1)
                        # 加入 PVO Delta 計算
                        pd_val = hist.iloc[-1]['PVO'] - hist.iloc[-2]['PVO']
                        
                        final_rows.append({
                            "股票": row['股票'],
                            "操作建議": op,
                            "前次行動": last,
                            "現價": f"{row['收盤價']:.2f}",
                            "Slope_Z": sz,
                            "PVO_D": f"{pd_val:+.1f}",
                            "VRI": f"{hist.iloc[-1]['VRI']:.1f}",
                            "Score_Z": scz
                        })
                
                res_df = pd.DataFrame(final_rows).sort_values(by="Slope_Z", ascending=False)
                st.dataframe(res_df, use_container_width=True, height=600)

if __name__ == "__main__":
    main()
