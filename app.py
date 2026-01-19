import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import analysis_engine as engine  # 確保 analysis_engine.py 在同一目錄下

# ==========================================
# 1. 頁面配置
# ==========================================
st.set_page_config(
    page_title="2026 專業股票分析終端",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. 核心分析師決策邏輯 (包含三種觀望時態)
# ==========================================
def get_market_status(row, prev_row):
    """
    依照使用者定義的規則判斷股票時態：
    - 做多門檻：Slope_Z > 0.6 或 (Slope 持續上升 且 Score_Z > 0)
    - 強勢標籤：Slope_Z > 1.5
    - 持有標籤：0.5 < Slope_Z <= 1.5
    - 強力買進：Slope_Z > 1.5 且 PVO Delta > 5
    - 觀望細分：多頭觀望 / 空頭觀望 / 空手觀望
    """
    # 這裡的 row 已經經過處理，包含了 VRI 和 PVO
    sz = row['Slope_Z']
    scz = row['Score_Z']
    vri = row['VRI']  # 修正後這裡取得到值了
    pvo = row['PVO']  # 修正後這裡取得到值了
    
    # 提取前一日數據 (計算變化量)
    if prev_row is not None:
        pvo_delta = pvo - prev_row['PVO']
        # 判斷 Slope 是否持續上升 (今日斜率 > 昨日斜率)
        # 注意：prev_row 是原始 dataframe row，欄位名是 'Slope' 不是 'Slope%'
        current_slope = row.get('Slope') if 'Slope' in row else row.get('Slope%')
        prev_slope = prev_row['Slope']
        is_slope_up = current_slope > prev_slope
    else:
        pvo_delta = 0
        is_slope_up = False

    # -------------------------------------------------------
    # 邏輯判斷樹
    # -------------------------------------------------------
    
    # A. 判斷是否符合「做多門檻」
    is_long_signal = (sz > 0.6) or (is_slope_up and scz > 0)

    if is_long_signal:
        # --- 多頭區域 ---
        if sz > 1.5:
            if pvo_delta > 5:
                return "🚀 強力買進", "color: #FF0000; font-weight: bold; background-color: #FFEEEE;"
            else:
                return "🔥 強勢多頭", "color: #FF4500; font-weight: bold;"
        
        elif sz > 0.5:
            if vri > 90 or pvo_delta < -2:
                return "⚠️ 多頭觀望", "color: #FF8C00;"
            else:
                return "💎 多頭持有", "color: #C71585;"
        
        else:
            return "🔎 準備翻多", "color: #32CD32;"

    # B. 判斷是否為「空頭」區域
    elif sz < -1.0:
        if is_slope_up:
            return "📉 空頭觀望", "color: #1E90FF;"
        else:
            return "💀 空頭趨勢", "color: #00008B; font-weight: bold;"

    # C. 其餘情況
    else:
        return "☕ 空手觀望", "color: #808080;"

# ==========================================
# 3. Streamlit 主程式
# ==========================================
def main():
    st.title("📈 2026 全方位股票掃描系統")
    st.markdown(
        """
        <div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 20px;">
            <strong>系統邏輯說明：</strong><br>
            1. <strong>回測週期</strong>：固定 180 天 (半年線架構)<br>
            2. <strong>強力買進</strong>：Slope_Z > 1.5 且 PVO 增幅 > 5<br>
            3. <strong>觀望狀態</strong>：細分為 <span style="color:#FF8C00">多頭觀望</span>(過熱)、
               <span style="color:#1E90FF">空頭觀望</span>(止跌)、<span style="color:#808080">空手觀望</span>(無趨勢)
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.sidebar:
        st.header("📊 分析參數")
        target_date = st.date_input("分析基準日", datetime.now())
        st.info("🔒 設定已鎖定：\n- 回測天數：180天\n- 掃描範圍：所有監控個股")
        lookback_days = 180
        limit_count = 100
        run_btn = st.button("🚀 啟動全市場掃描", use_container_width=True)

    if run_btn:
        status_placeholder = st.empty()
        status_placeholder.info(f"正在分析全市場股票... 基準日: {target_date}")
        
        try:
            df_results = engine.run_analysis(
                target_date.strftime('%Y-%m-%d'), 
                lookback_days, 
                limit_count
            )
            
            if df_results.empty:
                status_placeholder.error("❌ 查無數據，請確認該日期是否為交易日。")
            else:
                status_placeholder.success(f"✅ 分析完成！共掃描 {len(df_results)} 檔股票")
                
                final_display_data = []
                
                for _, row in df_results.iterrows():
                    # --- 關鍵修正區塊 ---
                    # 取得該股票的歷史 DataFrame
                    hist_df = row.get('_df')
                    
                    if hist_df is None or len(hist_df) < 2:
                        continue # 資料不足，跳過

                    # 1. 從歷史數據中撈出最新的完整指標 (包含 VRI, PVO)
                    latest_data = hist_df.iloc[-1]
                    prev_row = hist_df.iloc[-2]

                    # 2. 建立一個「合成的」資料字典，補足 row 缺少的欄位
                    # 這樣 get_market_status 就不會報 KeyError
                    analysis_row = row.to_dict()
                    analysis_row['VRI'] = latest_data['VRI']
                    analysis_row['PVO'] = latest_data['PVO']
                    analysis_row['Slope'] = latest_data['Slope'] # 用於斜率比較
                    
                    # 執行分析師邏輯 (傳入修正後的 analysis_row)
                    status_text, style_css = get_market_status(analysis_row, prev_row)
                    
                    # 計算 PVO 變化量
                    pvo_val = latest_data['PVO']
                    pvo_d = pvo_val - prev_row['PVO']
                    
                    final_display_data.append({
                        "股票代號": row['股票'],
                        "操作建議": status_text,
                        "收盤價": f"{row['收盤價']:.2f}",
                        "Slope%": f"{row['Slope%']:.2f}",
                        "Slope_Z": f"{row['Slope_Z']:.2f}",
                        "PVO": f"{pvo_val:.1f}",
                        "P_Delta": f"{pvo_d:+.1f}",
                        "VRI": f"{latest_data['VRI']:.1f}", # 這裡改用 latest_data
                        "Score_Z": f"{row['Score_Z']:.2f}",
                        "_style": style_css
                    })
                
                res_df = pd.DataFrame(final_display_data)
                
                # --- 統計儀表板 ---
                if not res_df.empty:
                    col1, col2, col3, col4 = st.columns(4)
                    buy_cnt = len(res_df[res_df['操作建議'].str.contains("強力買進|強勢|持有")])
                    wait_bull_cnt = len(res_df[res_df['操作建議'].str.contains("多頭觀望")])
                    wait_bear_cnt = len(res_df[res_df['操作建議'].str.contains("空頭觀望|空手")])
                    bear_cnt = len(res_df[res_df['操作建議'].str.contains("空頭趨勢")])
                    
                    col1.metric("🔴 多頭訊號", f"{buy_cnt} 檔")
                    col2.metric("🟠 多頭觀望", f"{wait_bull_cnt} 檔")
                    col3.metric("⚪ 空手/搶反彈", f"{wait_bear_cnt} 檔")
                    col4.metric("🔵 空頭趨勢", f"{bear_cnt} 檔")
                    
                    st.divider()

                    # --- 表格顯示 ---
                    display_cols = ["股票代號", "操作建議", "收盤價", "Slope_Z", "P_Delta", "PVO", "VRI", "Score_Z"]
                    st.dataframe(
                        res_df[display_cols].style.apply(
                            lambda x: [res_df.loc[x.name, '_style']] * len(display_cols), 
                            axis=1
                        ),
                        use_container_width=True,
                        height=800
                    )
                else:
                    st.warning("所有股票數據不足，無法生成報告。")

        except Exception as e:
            st.error(f"系統發生錯誤: {str(e)}")
            with st.expander("查看錯誤Traceback"):
                import traceback
                st.text(traceback.format_exc())

if __name__ == "__main__":
    main()
