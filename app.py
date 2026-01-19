# ====== app.py ======

import streamlit as st
import pandas as pd
from datetime import datetime

from analysis_engine import run_analysis
from config import WATCH_LIST


# --------------------
# Streamlit 基本設定（手機友善）
# --------------------
st.set_page_config(
    page_title="📈 股票分析 App",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 股票多因子分析（手機版）")
st.caption("Slope / PVO / VRI / Score 綜合判斷")


# --------------------
# Sidebar（操作區）
# --------------------
st.sidebar.header("⚙️ 分析設定")

target_date = st.sidebar.date_input(
    "分析日期",
    value=datetime.today()
)

lookback_days = st.sidebar.slider(
    "回溯天數",
    min_value=30,
    max_value=180,
    value=60,
    step=10
)

limit_count = st.sidebar.slider(
    "觀察股票數",
    min_value=5,
    max_value=len(WATCH_LIST),
    value=20,
    step=5
)

run_btn = st.sidebar.button("🚀 執行分析")


# --------------------
# 執行分析
# --------------------
@st.cache_data(show_spinner=False)
def load_data(date_str, lookback, limit):
    return run_analysis(date_str, lookback, limit)


if run_btn:
    with st.spinner("📡 分析中，請稍候..."):
        df = load_data(
            date_str=target_date.strftime("%Y-%m-%d"),
            lookback=lookback_days,
            limit=limit_count
        )
else:
    df = pd.DataFrame()


# --------------------
# 沒資料保護
# --------------------
if df.empty:
    st.info("👈 請在左側設定條件後，點擊「執行分析」")
    st.stop()


# --------------------
# 分類資料
# --------------------
df_strong = df[df["狀態"] == "強勢"]
df_weak = df[df["狀態"] == "空頭"]
df_wait = df[df["狀態"] == "觀望"]


# --------------------
# Tabs（手機最重要）
# --------------------
tab1, tab2, tab3 = st.tabs([
    f"🔥 強勢 ({len(df_strong)})",
    f"🐻 空頭 ({len(df_weak)})",
    f"⏳ 觀望 ({len(df_wait)})"
])


# --------------------
# 單股展開卡片
# --------------------
def render_stock_cards(data: pd.DataFrame):
    for _, row in data.iterrows():
        with st.expander(f"{row['股票']} ｜ {row['狀態']} ｜ 收盤 {row['收盤價']}"):
            st.markdown(f"""
            **📅 日期**：{row['日期']}  
            **💰 收盤價**：{row['收盤價']}  

            **📈 Slope%**：{row['Slope%']}  
            **📊 Score**：{row['Score']}  

            **Z-Slope**：{row['Slope_Z']}  
            **Z-Score**：{row['Score_Z']}  
            """)

            # 顯示原始 dataframe（進階用）
            with st.expander("📄 技術指標明細"):
                st.dataframe(
                    row["_df"].tail(20),
                    use_container_width=True,
                    height=300
                )


# --------------------
# Tab 內容
# --------------------
with tab1:
    if df_strong.empty:
        st.warning("目前沒有強勢股")
    else:
        render_stock_cards(df_strong)

with tab2:
    if df_weak.empty:
        st.warning("目前沒有空頭股")
    else:
        render_stock_cards(df_weak)

with tab3:
    if df_wait.empty:
        st.warning("目前沒有觀望股")
    else:
        render_stock_cards(df_wait)


# --------------------
# Footer
# --------------------
st.divider()
st.caption("© Stock Analysis Engine · Streamlit App")

