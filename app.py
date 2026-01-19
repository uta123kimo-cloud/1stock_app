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
# 2. 輔助函式：時態排序與單股分析
# ==========================================

def get_status_rank(status_text):
    """
    定義排序權重：數字越小排越前面
    順序：強力買進 > 強勢多頭 > 多頭持有 > 準備翻多 > 多頭觀望 > 空頭觀望 > 空手 > 空頭趨勢
    """
    if "強力買進" in status_text: return 1
    if "強勢多頭" in status_text: return 2
    if "多頭持有" in status_text: return 3
    if "準備翻多" in status_text: return 4
    if "多頭觀望" in status_text: return 5  # 雖然是多頭，但有疑慮，排在持有之後
    if "空頭觀望" in status_text: return 6
    if "空手" in status_text: return 7
    return 8  # 空頭趨勢

def analyze_single_stock_data(ticker, target_date, lookback_days=180):
    """
    調用 analysis_engine 的底層函式來分析單一股票
    """
    # 計算日期區間
    end_dt = datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)
    start_dt = end_dt - timedelta(days=lookback_days)
    
    # 取得標準代號 (處理 .TW)
    symbol = engine.get_taiwan_symbol(ticker)
    
    # 抓取數據
    df = engine.get_indicator_data(symbol, start_dt, end_dt)
    
    if df is None or len(df) < 5:
        return None, None
        
    # 取出最新一筆與前一筆
    latest_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    # 為了配合 get_market_status，我們需要把 Series 轉為 dict 並補上 Slope_Z 等計算好的欄位
    # 注意：get_indicator_data 回傳的 df 已經包含 'Slope', 'Score', 'PVO', 'VRI'
    # 但 'Slope_Z' 和 'Score_Z' 是在 get_advice (或是 run_analysis 裡) 算出來的
    # 所以我們這裡要手動算一次 Z-Score
    
    idx = len(df) - 1
    tag, z_slope, z_score = engine.get_advice(df, idx)
    
    # 組合數據包
    data_packet = latest_row.to_dict()
    data_packet['Slope_Z'] = z_slope
    data_packet['Score_Z'] = z_score
    data_packet['Slope%'] = latest_row['Slope'] # 對齊欄位名稱
    data_packet['收盤價'] = latest_row['Close']
    
    return data_packet, prev_row

# ==========================================
# 3. 核心決策邏輯
# ==========================================
def get_market_status(row, prev_row):
    """
    依照使用者定義的規則判斷股票時態
    """
    sz = row['Slope_Z']
    scz = row['Score_Z']
    vri = row['VRI']
    pvo = row['PVO']
    
    # 計算 PVO Delta
    if prev_row is not None:
        pvo_delta = pvo - prev_row['PVO']
        # 兼容不同的欄位名稱 (Slope vs Slope%)
        curr_slope = row.get('Slope') if 'Slope' in row else row.get('Slope%')
        prev_slope = prev_row['Slope']
        is_slope_up = curr_slope > prev_slope
    else:
        pvo_delta = 0
        is_slope_up = False

    # A. 做多訊號
    is_long_signal = (sz > 0.6) or (is_slope_up and scz > 0)

    if is_long_signal:
        if sz > 1.5:
            if pvo_delta > 5:
                return "🚀 強力買進", "color: #FF0000; font-weight: bold; background-color: #ffe6e6;"
            else:
                return "🔥 強勢多頭", "color: #FF4500; font-weight: bold;"
        elif sz > 0.5:
            if vri > 90 or pvo_delta < -2:
                return "⚠️ 多頭觀望", "color: #FF8C00;"
            else:
                return "💎 多頭持有", "color: #C71585;"
        else:
            return "🔎 準備翻多", "color: #32CD32;"

    # B. 空頭訊號
    elif sz < -1.0:
        if is_slope_up:
            return "📉 空頭觀望", "color: #1E90FF;"
        else:
            return "💀 空頭趨勢", "color: #00008B; font-weight: bold;"

    # C. 盤整
    else:
        return "☕ 空手觀望", "color: #808080;"

# ==========================================
# 4. Streamlit 主程式
# ==========================================
def main():
    st.title("📈 2026 全方位股票掃描系統")
    
    # --- 側邊欄：參數與單股查詢 ---
    with st.sidebar:
        st.header("🔍 單股即時分析")
        single_ticker = st.text_input("輸入台股代碼 (如 2330)", placeholder="輸入代碼後按 Enter")
        
        st.divider()
        st.header("📊 全市場掃描參數")
        target_date = st.date_input("分析基準日", datetime.now())
        st.info("🔒 參數已鎖定：回測 180 天")
        lookback_days = 180
        limit_count = 100
        
        run_btn = st.button("🚀 啟動全市場掃描", use_container_width=True)

    # --- 區塊一：單股查詢結果 (優先顯示) ---
    if single_ticker:
        st.subheader(f"🔎 個股診斷：{single_ticker}")
        try:
            row_data, prev_row = analyze_single_stock_data(single_ticker, target_date.strftime('%Y-%m-%d'), lookback_days)
            
            if row_data:
                status, style = get_market_status(row_data, prev_row)
                
                # 顯示單股卡片
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("狀態", status.split(" ")[1]) # 只顯示文字
                col2.metric("Slope_Z", f"{row_data['Slope_Z']:.2f}")
                col3.metric("PVO", f"{row_data['PVO']:.1f}", f"{row_data['PVO'] - prev_row['PVO']:.1f}")
                col4.metric("VRI", f"{row_data['VRI']:.1f}")
                col5.metric("收盤價", f"{row_data['收盤價']:.2f}")
                
                st.markdown(f"**分析師建議：** <span style='{style} font-size: 18px;'>{status}</span>", unsafe_allow_html=True)
            else:
                st.error("查無資料，請確認代碼或日期。")
        except Exception as e:
            st.error(f"查詢失敗: {e}")
        st.divider()

    # --- 區塊二：全市場掃描與大盤 ---
    if run_btn:
        status_placeholder = st.empty()
        status_placeholder.info(f"正在分析全市場股票... 基準日: {target_date}")
        
        try:
            # 1. 執行個股掃描
            df_results = engine.run_analysis(
                target_date.strftime('%Y-%m-%d'), 
                lookback_days, 
                limit_count
            )
            
            if df_results.empty:
                status_placeholder.error("❌ 查無數據，請確認該日期是否為交易日。")
            else:
                status_placeholder.success(f"✅ 分析完成！共掃描 {len(df_results)} 檔股票")
                
                # --- 新增：大盤與 0050 趨勢儀表板 ---
                st.subheader("🌏 台灣市場趨勢溫度計")
                benchmarks = {"加權指數": "^TWII", "台灣50": "0050.TW"}
                b_cols = st.columns(len(benchmarks))
                
                for idx, (name, code) in enumerate(benchmarks.items()):
                    b_data, b_prev = analyze_single_stock_data(code, target_date.strftime('%Y-%m-%d'), lookback_days)
                    if b_data:
                        b_status, b_style = get_market_status(b_data, b_prev)
                        with b_cols[idx]:
                            st.markdown(f"### {name} ({code})")
                            st.markdown(f"<div style='padding:10px; border-radius:5px; border:1px solid #ddd;'>"
                                        f"<h4 style='margin:0; {b_style}'>{b_status}</h4>"
                                        f"<hr style='margin:5px 0;'>"
                                        f"<div>Slope_Z: <b>{b_data['Slope_Z']:.2f}</b></div>"
                                        f"<div>PVO: <b>{b_data['PVO']:.1f}</b></div>"
                                        f"<div>VRI: <b>{b_data['VRI']:.1f}</b></div>"
                                        f"</div>", unsafe_allow_html=True)

                st.divider()

                # --- 處理掃描結果並排序 ---
                final_display_data = []
                
                for _, row in df_results.iterrows():
                    hist_df = row.get('_df')
                    if hist_df is None or len(hist_df) < 2: continue

                    # 補齊數據
                    latest_data = hist_df.iloc[-1]
                    prev_row = hist_df.iloc[-2]
                    
                    analysis_row = row.to_dict()
                    analysis_row['VRI'] = latest_data['VRI']
                    analysis_row['PVO'] = latest_data['PVO']
                    analysis_row['Slope'] = latest_data['Slope']
                    
                    status_text, style_css = get_market_status(analysis_row, prev_row)
                    
                    # 計算排序權重
                    rank_score = get_status_rank(status_text)
                    
                    final_display_data.append({
                        "股票代號": row['股票'],
                        "操作建議": status_text,
                        "收盤價": f"{row['收盤價']:.2f}",
                        "Slope_Z": row['Slope_Z'], # 保留數值以供排序用 (顯示時再轉字串)
                        "PVO": f"{latest_data['PVO']:.1f}",
                        "P_Delta": f"{latest_data['PVO'] - prev_row['PVO']:+.1f}",
                        "VRI": f"{latest_data['VRI']:.1f}",
                        "_style": style_css,
                        "_rank": rank_score # 隱藏欄位：排序用
                    })
                
                res_df = pd.DataFrame(final_display_data)
                
                # --- 執行排序：先依狀態權重(_rank)，再依動能(Slope_Z) ---
                if not res_df.empty:
                    # 依 _rank (升冪) -> Slope_Z (降冪) 排序
                    res_df = res_df.sort_values(by=['_rank', 'Slope_Z'], ascending=[True, False])
                    
                    # 統計儀表板
                    col1, col2, col3, col4 = st.columns(4)
                    buy_cnt = len(res_df[res_df['_rank'] <= 3]) # 強力買進~多頭持有
                    wait_cnt = len(res_df[res_df['_rank'].isin([4, 5])]) # 準備翻多+多頭觀望
                    bear_cnt = len(res_df[res_df['_rank'] >= 6])
                    
                    col1.metric("🔴 多頭強勢", f"{buy_cnt} 檔")
                    col2.metric("🟠 觀望/整理", f"{wait_cnt} 檔")
                    col3.metric("🔵 空頭/空手", f"{bear_cnt} 檔")

                    # 格式化顯示 DataFrame (把數值轉回字串，並隱藏排序欄位)
                    display_df = res_df.drop(columns=['_rank'])
                    display_df['Slope_Z'] = display_df['Slope_Z'].apply(lambda x: f"{x:.2f}")

                    # 顯示表格
                    st.subheader("📋 趨勢掃描清單 (依強勢度排序)")
                    display_cols = ["股票代號", "操作建議", "收盤價", "Slope_Z", "P_Delta", "PVO", "VRI"]
                    
                    st.dataframe(
                        display_df[display_cols].style.apply(
                            lambda x: [display_df.loc[x.name, '_style']] * len(display_cols), 
                            axis=1
                        ),
                        use_container_width=True,
                        height=800
                    )
                else:
                    st.warning("所有股票數據不足，無法生成報告。")

        except Exception as e:
            st.error(f"系統發生錯誤: {str(e)}")
            with st.expander("查看錯誤詳情"):
                import traceback
                st.text(traceback.format_exc())

if __name__ == "__main__":
    main()
