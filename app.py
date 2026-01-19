import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta
import analysis_engine as engine  # 確保與 engine 在同一目錄

# ===========================================================================
# 1. 核心決策引擎 (精確修正 NameError 並對齊您的四維邏輯)
# ===========================================================================
def get_four_dimension_advice(df, c_idx):
    window = 60
    # 確保數據長度足以計算 Z-Score (需要 window + 緩衝)
    if c_idx < window + 5: 
        return "數據不足", "---", 0.0, 0.0
    
    # 擷取 60 日視窗數據計算 Z-Score
    hist_slopes = df['Slope'].iloc[max(0, c_idx-window):c_idx+1]
    hist_scores = df['Score'].iloc[max(0, c_idx-window):c_idx+1]

    # 計算今日 Z-Score
    sz = (df.iloc[c_idx]['Slope'] - hist_slopes.mean()) / (hist_slopes.std() + 1e-6)
    scz = (df.iloc[c_idx]['Score'] - hist_scores.mean()) / (hist_scores.std() + 1e-6)

    v = df.iloc[c_idx]['VRI']
    pvo_now = df.iloc[c_idx]['PVO']
    pd_val = pvo_now - df.iloc[c_idx-1]['PVO']

    # 判斷 Slope 是否連續三日上升 (對齊您的 is_u 邏輯)
    try:
        is_u = df.iloc[c_idx]['Slope'] > df.iloc[c_idx-1]['Slope'] > df.iloc[c_idx-2]['Slope']
    except: 
        is_u = False

    # 方向閘門 (direction_gate)
    def direction_gate(sz_val, score_z, is_up):
        if sz_val > 0.6 or (is_up and score_z > 0): return "做多"
        elif sz_val < -1.0 or (not is_up and score_z < -0.8): return "做空"
        return "觀望"

    current_dir = direction_gate(sz, scz, is_u)

    # 歷史行動追蹤 (回溯尋找訊號起點)
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

    # 操作建議細分 (這部分已修正變數名稱錯誤)
    def detailed_gate(sz_val, vri, p_d, is_up):
        if sz_val > 0.6:
            if sz_val > 1.5 and p_d > 5: return "🚀 強力買進"
            return "💎 波段持有"
        if is_up: return "🔎 準備翻多"
        if sz_val < -1.0: return "💀 空頭趨勢"
        return "☕ 觀望整理"

    curr_op = detailed_gate(sz, v, pd_val, is_u)
    
    # 邏輯補充：細分「觀望」與「警示」狀態
    if "波段持有" in curr_op and (v > 90 or pd_val < -2):
        curr_op = "⚠️ 多頭觀望"
    elif "空頭趨勢" in curr_op and is_u:
        curr_op = "📉 空頭觀望"

    return curr_op, last_action_display, sz, scz

# ==========================================
# 2. 介面配置與主程式邏輯
# ==========================================
st.set_page_config(page_title="2026 量化戰情室", layout="wide")

def main():
    st.title("🛡️ 2026 四維量價判斷系統")

    with st.sidebar:
        st.header("🎯 交易員控制面板")
        target_date = st.date_input("分析基準日", datetime.now())
        st.info("🔒 設定：回測 180 天 | Z-Score 視窗 60 天")
        
        st.divider()
        st.subheader("個股狙擊模式")
        ticker_input = st.text_input("輸入台股代碼", "2330")
        single_btn = st.button("單股即時診斷")
        
        st.divider()
        st.subheader("市場全掃模式")
        full_btn = st.button("啟動全市場掃描")

    # 設定日期區間
    lookback = 180
    end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d") + timedelta(days=1)
    start_dt = end_dt - timedelta(days=lookback)

    # --- 處理：單股診斷 ---
    if single_btn and ticker_input:
        with st.spinner(f"正在分析 {ticker_input}..."):
            symbol = engine.get_taiwan_symbol(ticker_input)
            df = engine.get_indicator_data(symbol, start_dt, end_dt)
            if df is not None and len(df) > 70:
                op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
                st.subheader(f"📊 {ticker_input} 技術診斷報告")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("當前建議", op)
                c2.metric("前次訊號", last)
                c3.metric("Slope_Z (趨勢強度)", f"{sz:.2f}")
                c4.metric("Score_Z (量價綜合)", f"{scz:.2f}")
                st.divider()
            else:
                st.error("代碼錯誤或數據長度不足 (需至少 70 交易日)。")

    # --- 處理：全市場掃描 ---
    if full_btn:
        st.subheader("🌏 市場大盤環境監測")
        m_cols = st.columns(2)
        benchmarks = {"加權指數": "^TWII", "台灣 50": "0050.TW"}
        
        for i, (m_name, m_code) in enumerate(benchmarks.items()):
            m_df = engine.get_indicator_data(m_code, start_dt, end_dt)
            if m_df is not None:
                m_op, m_last, m_sz, _ = get_four_dimension_advice(m_df, len(m_df)-1)
                with m_cols[i]:
                    st.info(f"**{m_name} ({m_code})**\n\n狀態：{m_op}\n\n起點：{m_last}")
            
        st.divider()

        with st.spinner("掃描全清單並執行強勢度排序..."):
            # 調用 engine 獲取基礎清單數據
            df_results = engine.run_analysis(target_date.strftime('%Y-%m-%d'), lookback, 100)
            
            if not df_results.empty:
                final_rows = []
                for _, row in df_results.iterrows():
                    hist = row.get('_df')
                    if hist is not None and len(hist) >= 65:
                        op, last, sz, scz = get_four_dimension_advice(hist, len(hist)-1)
                        pd_val = hist.iloc[-1]['PVO'] - hist.iloc[-2]['PVO']
                        
                        final_rows.append({
                            "股票": row['股票'],
                            "操作建議": op,
                            "前次行動": last,
                            "現價": f"{row['收盤價']:.2f}",
                            "Slope_Z": sz,
                            "PVO_D": f"{pd_val:+.1f}",
                            "VRI": f"{hist.iloc[-1]['VRI']:.1f}",
                            "Score_Z": f"{scz:.2f}"
                        })
                
                # 依據 Slope_Z 強勢排序 (從最強到最弱)
                res_df = pd.DataFrame(final_rows).sort_values(by="Slope_Z", ascending=False)
                
                st.subheader(f"📋 全市場強勢度清單")
                st.dataframe(res_df, use_container_width=True, height=800)
            else:
                st.warning("查無數據，請確認日期是否為交易日。")

if __name__ == "__main__":
    main()
