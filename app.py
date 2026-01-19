
# =========================
# 你的 Streamlit App 程式碼
# =========================
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from analysis_engine import main as run_analysis_engine
from indicator_utils import get_indicator_data
from backtest_5d import get_four_dimension_advice

st.set_page_config(page_title="股票分析App", layout="wide")

st.title("📈 股票分析手機版 App")
st.sidebar.header("設定條件")

# 側邊欄控制
target_date = st.sidebar.date_input("觀察日期", pd.to_datetime("2026-01-12"))
observe_num = st.sidebar.slider("觀察股數", min_value=3, max_value=20, value=5)
sigma_multiplier = st.sidebar.slider("標準差門檻倍數", min_value=0.5, max_value=3.0, value=1.2, step=0.1)

st.sidebar.markdown("---")
st.sidebar.text("策略運行中...")

# 這裡先用示範資料
sample_data = pd.DataFrame({
    "symbol":["2330","2317","2454","2308","2382","3037"],
    "price":[560, 120, 92, 58, 42, 85],
    "score":[95,88,80,75,60,82],
    "status":["強勢","強勢","觀望","空頭","空頭","觀望"]
})

tab1, tab2, tab3 = st.tabs(["強勢", "空頭", "觀望"])

with tab1:
    st.header("🔥 強勢股")
    df = sample_data[sample_data['status']=="強勢"].head(observe_num)
    st.dataframe(df)

with tab2:
    st.header("📉 空頭股")
    df = sample_data[sample_data['status']=="空頭"].head(observe_num)
    st.dataframe(df)

with tab3:
    st.header("⏳ 觀望股")
    df = sample_data[sample_data['status']=="觀望"].head(observe_num)
    st.dataframe(df)

st.markdown("---")
symbol_selected = st.selectbox("🔍 選擇股票查看細節", sample_data['symbol'])

if symbol_selected:
    st.subheader(f"{symbol_selected} 技術指標與建議")
    st.info("📌 範例資料，實際請用 analysis_engine 計算結果")
