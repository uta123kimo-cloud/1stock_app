import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import analysis_engine as engine  # 確保 analysis_engine.py 與此檔案在同一路徑

# ==========================================
# 1. 頁面基礎配置
# ==========================================
st.set_page_config(
    page_title="2026 專業量化策略分析系統",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. 核心分析邏輯與排序函式
# ==========================================

def get_status_rank(status_text):
    """定義顯示權重：數字越小越前面"""
    ranks = {
        "🚀 強力買進": 1,
        "🔥 強勢多頭": 2,
        "💎 多頭持有": 3,
        "🔎 準備翻多": 4,
        "⚠️ 多頭觀望": 5,
        "📉 空頭觀望": 6,
        "☕ 空手觀望": 7,
        "💀 空頭趨勢": 8
    }
    return ranks.get(status_text, 9)

def get_market_status(row, prev_row):
    """分析師核心邏輯對齊"""
    sz = row.get('Slope_Z', 0)
    scz = row.get('Score_Z', 0)
    vri = row.get('VRI', 0)
    pvo = row.get('PVO', 0)
    
    # 取得 PVO 變化與 Slope 動向
    pvo_delta = pvo - prev_row['PVO'] if prev_row is not None else 0
    curr_slope = row.get('Slope') if 'Slope' in row else row.get('Slope%', 0)
    prev_slope = prev_row['Slope'] if prev_row is not None else 0
    is_slope_up = curr_slope > prev_slope

    # A. 做多門檻
    is_long_signal = (sz > 0.6) or (is_slope_up and scz > 0)

    if is_long_signal:
        if sz > 1.5:
            return ("🚀 強力買進", "color: #FF0000; font-weight: bold; background-color: #ffe6e6;") if pvo_delta > 5 else \
                   ("🔥 強勢多頭", "color: #FF4500; font-weight: bold;")
        elif sz > 0.5:
            return ("⚠️ 多頭觀望", "color: #FF8C00;") if (vri > 90 or pvo_delta < -2) else \
                   ("💎 多頭持有", "color: #C71585;")
        return ("🔎 準備翻多", "color: #32CD32;")
    elif sz < -1.0:
        return ("📉 空頭觀望", "color: #1E90FF;") if is_slope_up else ("💀 空頭趨勢", "color: #00008B; font-weight: bold;")
    return ("☕ 空手觀望", "color: #808080;")

def analyze_ticker(ticker, target_date):
    """單股數據抓取與 Z-Score 計算"""
    lookback = 180
    end_dt = datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)
    start_dt = end_dt - timedelta(days=lookback)
    symbol = engine.get_taiwan_symbol(ticker)
    df = engine.get_indicator_data(symbol, start_dt, end_dt)
    
    if df is None or len(df) < 2:
        return None, None
    
    tag, z_slope, z_score = engine.get_advice(df, len(df)-1)
    latest = df.iloc[-1].to_dict()
    latest.update({'Slope_Z': z_slope, 'Score_Z': z_score, '股票': ticker, '收盤價': latest['Close']})
    return latest, df.iloc[-2]

# ==========================================
# 3. Streamlit 介面
# ==========================================
def main():
    st.title("🛡️ 2026 四維量價判斷系統")

    # --- 側邊欄：獨立面板 ---
    with st.sidebar:
        st.header("🎯 個股狙擊面板")
        single_ticker = st.text_input("輸入代碼 (例: 2330)", "")
        single_run = st.button("單股即時分析")

        st.divider()

        st.header("🌐 全市場掃描面板")
        target_date = st.date_input("基準日期", datetime.now())
        full_run = st.button("啟動全市場分析 (180D)")

    # --- 處理：單股分析 ---
    if single_run and single_ticker:
        with st.spinner(f"正在分析 {single_ticker}..."):
            data, prev = analyze_ticker(single_ticker, target_date.strftime('%Y-%m-%d'))
            if data:
                status, style = get_market_status(data, prev)
                st.subheader(f"📊 {single_ticker} 技術診斷報告")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("建議", status.split(" ")[1])
                c2.metric("Slope_Z", f"{data['Slope_Z']:.2f}")
                c3.metric("VRI (成交量活躍)", f"{data['VRI']:.1f}")
                c4.metric("PVO Delta", f"{data['PVO'] - prev['PVO']:+.2f}")
                st.markdown(f"**操作時態：** <span style='{style} font-size:20px;'>{status}</span>", unsafe_allow_html=True)
                st.divider()
            else:
                st.error("代碼錯誤或數據不足")

    # --- 處理：全市場掃描 ---
    if full_run:
        st.subheader("🌏 市場環境評估")
        # 大盤指標
        m_cols = st.columns(2)
        for i, (m_name, m_code) in enumerate({"加權指數": "^TWII", "台灣 50": "0050.TW"}.items()):
            m_data, m_prev = analyze_ticker(m_code, target_date.strftime('%Y-%m-%d'))
            if m_data:
                m_status, m_style = get_market_status(m_data, m_prev)
                m_cols[i].markdown(f"**{m_name}** | {m_status}", unsafe_allow_html=True)
                m_cols[i].caption(f"Slope_Z: {m_data['Slope_Z']:.2f} | VRI: {m_data['VRI']:.1f}")

        st.divider()

        with st.spinner("掃描所有監控個股並進行強勢排序..."):
            df_results = engine.run_analysis(target_date.strftime('%Y-%m-%d'), 180, 100)
            if not df_results.empty:
                processed_list = []
                for _, row in df_results.iterrows():
                    hist = row.get('_df')
                    if hist is not None and len(hist) >= 2:
                        latest = hist.iloc[-1]
                        prev = hist.iloc[-2]
                        
                        # 合成分析數據
                        analysis_row = row.to_dict()
                        analysis_row.update({'VRI': latest['VRI'], 'PVO': latest['PVO'], 'Slope': latest['Slope']})
                        
                        status, style = get_market_status(analysis_row, prev)
                        processed_list.append({
                            "股票": row['股票'],
                            "操作建議": status,
                            "收盤價": f"{row['收盤價']:.2f}",
                            "Slope_Z": row['Slope_Z'],
                            "PVO_D": latest['PVO'] - prev['PVO'],
                            "VRI": f"{latest['VRI']:.1f}",
                            "Score_Z": f"{row['Score_Z']:.2f}",
                            "_rank": get_status_rank(status),
                            "_style": style
                        })

                res_df = pd.DataFrame(processed_list).sort_values(by=['_rank', 'Slope_Z'], ascending=[True, False])

                # 視覺化輸出
                st.subheader(f"📋 強勢度排序表 (基準日: {target_date})")
                cols_to_show = ["股票", "操作建議", "收盤價", "Slope_Z", "PVO_D", "VRI", "Score_Z"]
                
                # 數值格式化顯示
                res_df['PVO_D'] = res_df['PVO_D'].apply(lambda x: f"{x:+.1f}")
                res_df['Slope_Z'] = res_df['Slope_Z'].apply(lambda x: f"{x:.2f}")

                st.dataframe(
                    res_df[cols_to_show].style.apply(lambda x: [res_df.loc[x.name, '_style']] * len(cols_to_show), axis=1),
                    use_container_width=True, height=600
                )
            else:
                st.warning("查無分析結果。")

if __name__ == "__main__":
    main()
