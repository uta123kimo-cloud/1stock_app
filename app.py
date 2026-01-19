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
    # 提取當前數據
    sz = row['Slope_Z']
    scz = row['Score_Z']
    vri = row['VRI']
    pvo = row['PVO']
    
    # 提取前一日數據 (計算變化量)
    if prev_row is not None:
        pvo_delta = pvo - prev_row['PVO']
        # 判斷 Slope 是否持續上升 (今日斜率 > 昨日斜率)
        is_slope_up = row['Slope%'] > prev_row['Slope%']
    else:
        pvo_delta = 0
        is_slope_up = False

    # -------------------------------------------------------
    # 邏輯判斷樹
    # -------------------------------------------------------
    
    # A. 判斷是否符合「做多門檻」
    # 條件：標準差 > 0.6 或 (斜率向上且評分轉正)
    is_long_signal = (sz > 0.6) or (is_slope_up and scz > 0)

    if is_long_signal:
        # --- 多頭區域 ---
        
        # 1. 強勢判斷 (Slope_Z > 1.5)
        if sz > 1.5:
            if pvo_delta > 5:
                # 滿足強力買進：斜率極陡 + 資金動能爆發
                return "🚀 強力買進", "color: #FF0000; font-weight: bold; background-color: #FFEEEE;"
            else:
                return "🔥 強勢多頭", "color: #FF4500; font-weight: bold;"
        
        # 2. 持有判斷 (0.5 < Slope_Z <= 1.5)
        elif sz > 0.5: # 這裡用 > 0.5 涵蓋持有區間
            # 檢查是否需要轉為「多頭觀望」 (例如過熱或動能背離)
            if vri > 90 or pvo_delta < -2:
                return "⚠️ 多頭觀望", "color: #FF8C00;"  # 橘色：雖在多方但有疑慮
            else:
                return "💎 多頭持有", "color: #C71585;"  # 紫紅色：穩健持有
        
        # 3. 弱勢多頭 (位於邊緣)
        else:
            return "🔎 準備翻多", "color: #32CD32;"  # 綠色：起漲初期

    # B. 判斷是否為「空頭」區域
    elif sz < -1.0:
        # --- 空頭區域 ---
        
        if is_slope_up:
            # 斜率雖然還是負的深，但開始向上勾頭 -> 空頭觀望 (搶反彈或空單回補)
            return "📉 空頭觀望", "color: #1E90FF;" # 寶藍色
        else:
            return "💀 空頭趨勢", "color: #00008B; font-weight: bold;" # 深藍色

    # C. 其餘情況 -> 空手觀望
    else:
        # --- 盤整區域 ---
        return "☕ 空手觀望", "color: #808080;" # 灰色

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

    # --- 側邊欄控制 ---
    with st.sidebar:
        st.header("📊 分析參數")
        
        # 1. 日期選擇
        target_date = st.date_input("分析基準日", datetime.now())
        
        # 2. 固定參數顯示 (使用者不可改，確保策略一致性)
        st.info("🔒 設定已鎖定：\n- 回測天數：180天\n- 掃描範圍：所有監控個股")
        lookback_days = 180
        limit_count = 100  # 設定一個足夠大的數字以包含所有 watchlist
        
        # 3. 執行按鈕
        run_btn = st.button("🚀 啟動全市場掃描", use_container_width=True)

    # --- 主要執行區塊 ---
    if run_btn:
        status_placeholder = st.empty()
        status_placeholder.info(f"正在分析全市場股票... 基準日: {target_date}")
        
        try:
            # 呼叫後端引擎
            # 注意：run_analysis 必須回傳包含 '_df' 的 DataFrame
            df_results = engine.run_analysis(
                target_date.strftime('%Y-%m-%d'), 
                lookback_days, 
                limit_count
            )
            
            if df_results.empty:
                status_placeholder.error("❌ 查無數據，請確認該日期是否為交易日。")
            else:
                status_placeholder.success(f"✅ 分析完成！共掃描 {len(df_results)} 檔股票")
                
                # --- 處理數據並應用判斷邏輯 ---
                final_display_data = []
                
                for _, row in df_results.iterrows():
                    # 取出該股票的歷史數據 (由 analysis_engine 回傳的 _df 欄位)
                    hist_df = row.get('_df')
                    
                    # 取得前一天的 row 用於計算 PVO Delta 和 Slope 變化
                    prev_row = None
                    if hist_df is not None and len(hist_df) >= 2:
                        # hist_df 的最後一筆是當天(row)，倒數第二筆是前一天
                        prev_row = hist_df.iloc[-2]
                    
                    # 執行分析師邏輯
                    status_text, style_css = get_market_status(row, prev_row)
                    
                    # 計算 PVO 變化量顯示用
                    pvo_val = row['PVO']
                    pvo_prev = prev_row['PVO'] if prev_row is not None else pvo_val
                    pvo_d = pvo_val - pvo_prev
                    
                    final_display_data.append({
                        "股票代號": row['股票'],
                        "操作建議": status_text,
                        "收盤價": f"{row['收盤價']:.2f}",
                        "Slope%": f"{row['Slope%']:.2f}",
                        "Slope_Z": f"{row['Slope_Z']:.2f}",
                        "PVO": f"{pvo_val:.1f}",
                        "P_Delta": f"{pvo_d:+.1f}", # 顯示正負號
                        "VRI": f"{row['VRI']:.1f}",
                        "Score_Z": f"{row['Score_Z']:.2f}",
                        "_style": style_css # 隱藏欄位，用於樣式
                    })
                
                # 轉為 DataFrame
                res_df = pd.DataFrame(final_display_data)
                
                # --- 統計數據儀表板 ---
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

                # --- 顯示樣式化表格 ---
                # 使用 Pandas Styler 進行顏色標記
                def style_dataframe(df):
                    return df.style.apply(lambda x: [x['_style']] * len(x), axis=1)\
                             .format(precision=2)

                # 為了顯示，隱藏 _style 欄位但保留其作用
                display_cols = ["股票代號", "操作建議", "收盤價", "Slope_Z", "P_Delta", "PVO", "VRI", "Score_Z"]
                st.dataframe(
                    res_df[display_cols].style.apply(
                        lambda x: [res_df.loc[x.name, '_style']] * len(display_cols), 
                        axis=1
                    ),
                    use_container_width=True,
                    height=800
                )

        except Exception as e:
            st.error(f"系統發生錯誤: {str(e)}")
            with st.expander("查看錯誤詳情"):
                st.write(e)

if __name__ == "__main__":
    main()
