import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

from analysis_engine import get_indicator_data, get_taiwan_symbol, get_advice
from backtest_5d import get_four_dimension_advice
from config import WATCH_LIST as TAIWAN_LIST
from configA import WATCH_LIST as US_LIST

# ===================================================================
# UI 設定
# ===================================================================
st.set_page_config(page_title="SJ 四維量價戰情室", layout="wide")
st.markdown("""
<style>
h1 {font-size:20px !important;}
h2 {font-size:20px !important;}
h3 {font-size:20px !important;}
p, label, span, div {font-size:16px !important;}
table td {font-size:14px !important;}
</style>
""", unsafe_allow_html=True)

# ===================================================================
# 狀態分類（完全不改）
# ===================================================================
def map_status(op_text, slope_z):
    if "做空" in op_text or "空單" in op_text:
        if slope_z < -1.0:
            return "🔻 空單進場", 1
        else:
            return "⚠️ 空頭觀望", 4
    if slope_z > 1.5:
        return "⭐ 多單進場", 1
    if 0.5 < slope_z <= 1.5:
        return "✅ 多單續抱", 2
    if abs(slope_z) <= 0.3:
        return "⚠️ 空手觀望", 4
    if slope_z > 0:
        return "⚠️ 多頭觀望", 4
    else:
        return "⚠️ 空頭觀望", 4

STATUS_RANK = {
    "⭐ 多單進場": 1,
    "✅ 多單續抱": 2,
    "⚠️ 多頭觀望": 3,
    "⚠️ 空手觀望": 4,
    "🔻 空單進場": 5,
    "⚠️ 空頭觀望": 6,
}

# ===================================================================
# 20 日個股擴散率模組
# ===================================================================
def calc_trend_stability(df, window=20):
    if df is None or len(df) < window + 2:
        return None, 0, window

    count_long = 0
    for i in range(len(df) - window, len(df)):
        op, last, sz, scz = get_four_dimension_advice(df, i)
        status, _ = map_status(op, sz)
        if status in ["⭐ 多單進場", "✅ 多單續抱"]:
            count_long += 1
    ratio = round(count_long / window * 100, 1)
    return ratio, count_long, window

def interpret_trend_stability(ratio):
    if ratio is None:
        return "未提供", "—"
    if ratio > 70:
        return "🔥 強勢主升段", "可續抱 / 加碼"
    elif ratio >= 50:
        return "⭐ 穩定多頭", "正常波段操作"
    elif ratio >= 30:
        return "⚠️ 震盪偏多", "低買高賣"
    elif ratio >= 15:
        return "🧊 弱勢整理", "觀望為主"
    else:
        return "❄️ 空頭或底部", "型態觀察"

def calc_last5_trend_series(df, window=20, days=5):
    series = []
    if df is None or len(df) < window + days + 2:
        return series
    for k in range(days, 0, -1):
        idx = len(df) - k
        sub_df = df.iloc[:idx+1]
        ratio, _, _ = calc_trend_stability(sub_df, window)
        series.append(ratio)
    return series

# ===================================================================
# 側邊欄（不改）
# ===================================================================
with st.sidebar:
    st.title("🎯 分析模式")
    mode = st.radio("選擇分析類型", ["單股分析", "台股市場分析", "美股市場分析"])
    st.divider()
    target_date = st.date_input("分析基準日", datetime.now())
    st.divider()
    ticker_input = st.text_input("單股代號", "2330")
    run_btn = st.button("開始分析")

# ===================================================================
# 時間設定（不改）
# ===================================================================
LOOKBACK_1Y = 365
if isinstance(target_date, datetime):
    end_dt = target_date + timedelta(days=1)
else:
    end_dt = datetime.strptime(str(target_date), "%Y-%m-%d") + timedelta(days=1)
start_1y = end_dt - timedelta(days=LOOKBACK_1Y)

# ===================================================================
# 工具函式（不改）
# ===================================================================
def safe_get_value(curr, key, prev=None):
    val = curr.get(key, None)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "未提供"
    if prev is not None:
        prev_val = prev.get(key, None)
        if prev_val is None or (isinstance(prev_val, float) and np.isnan(prev_val)):
            arrow_val = "→"
        else:
            arrow_val = "↑" if val > prev_val else "↓" if val < prev_val else "→"
        return f"{val:.2f} {arrow_val}"
    return round(val, 2)

def format_price(symbol, price):
    if price is None or (isinstance(price,float) and np.isnan(price)):
        return "未提供"
    if ".TW" in symbol or ".TWO" in symbol:
        return int(round(price,0))
    return round(price,2)

def calc_market_heat(status_count, total):
    long_cnt = status_count.get("⭐ 多單進場",0) + status_count.get("✅ 多單續抱",0)
    if total == 0:
        return 0
    return int(long_cnt / total * 100)

# ===================================================================
# 主畫面
# ===================================================================
st.title("🛡️ SJ 四維量價分析系統")

# ============================================================
# 單股分析（補 Slope_Z + 近5日擴散率 + 圖表）
# ============================================================
if run_btn and mode=="單股分析":
    st.subheader("📌 單股即時分析")
    symbol = get_taiwan_symbol(ticker_input)
    df = get_indicator_data(symbol, start_1y, end_dt)
    if df is None or len(df)<50:
        st.warning("資料不足")
    else:
        op, last, sz, scz = get_four_dimension_advice(df,len(df)-1)
        status, _ = map_status(op, sz)
        curr = df.iloc[-1].to_dict()
        prev = df.iloc[-2].to_dict()

        # 🔥 擴散率
        trend_ratio, long_days, win_days = calc_trend_stability(df, 20)
        trend_text, trend_advice = interpret_trend_stability(trend_ratio)
        last5 = calc_last5_trend_series(df, 20, 5)
        last5_text = " , ".join([f"{x}%" for x in last5 if x is not None])

        st.markdown(
            f"### 🎯 {ticker_input} 當前狀態（截至 {target_date}）\n"
            f"狀態：**{status}**\n"
            f"操作建議：{op}\n"
            f"Slope_Z：**{sz:.2f}**\n\n"
            f"🔥 20日趨勢穩定度：**{trend_ratio}%**｜{trend_text}｜{trend_advice}\n"
            f"📈 近5日擴散率變化：[{last5_text}]"
        )

        col1,col2,col3,col4,col5,col6 = st.columns(6)
        col1.metric("收盤價", f"{format_price(symbol,curr.get('Close'))}")
        col2.metric("PVO", safe_get_value(curr,'PVO',prev))
        col3.metric("VRI", safe_get_value(curr,'VRI',prev))
        col4.metric("Slope_Z", f"{sz:.2f}")
        col5.metric("Score_Z", f"{scz:.2f}")
        col6.metric("20日擴散率", f"{trend_ratio}%")

        # ============================================================
        # 🔥 圖表：PVO/VRI vs 20日擴散率 + 最近5日標註
        # ============================================================
        pvo_series = df["PVO"] if "PVO" in df.columns else pd.Series(np.nan, index=df.index)
        vri_series = df["VRI"] if "VRI" in df.columns else pd.Series(np.nan, index=df.index)

        trend_series = pd.Series([calc_trend_stability(df.iloc[:i+1],20)[0] for i in range(len(df))], index=df.index)

        fig, ax1 = plt.subplots(figsize=(12,5))
        ax1.plot(df.index, pvo_series, color='blue', label='PVO', linewidth=1.5)
        ax1.plot(df.index, vri_series, color='green', label='VRI', linewidth=1.5)
        ax1.set_ylabel("PVO / VRI", color='black')
        ax1.tick_params(axis='y', labelcolor='black')
        ax1.set_title(f"{ticker_input} | PVO / VRI 與 20日擴散率同步圖")

        ax2 = ax1.twinx()
        ax2.plot(df.index, trend_series, color='red', label='20日擴散率', linewidth=2, linestyle='--', marker='o')
        ax2.set_ylabel("20日擴散率 (%)", color='red')
        ax2.tick_params(axis='y', labelcolor='red')

        # 標註最近5日
        for i, val in enumerate(last5):
            ax2.text(df.index[-5+i], val+1, f"{val}%", color='red', fontsize=10, ha='center')

        ax1.legend(loc='upper left')
        ax2.legend(loc='upper right')

        st.pyplot(fig)
