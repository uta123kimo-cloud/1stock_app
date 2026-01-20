import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# === 核心模組（完全保留你架構）===
from analysis_engine import get_indicator_data, get_taiwan_symbol
from backtest_5d import get_four_dimension_advice

# === 正確讀取名單 ===
from config import WATCH_LIST as TAIWAN_LIST
from configA import WATCH_LIST as US_LIST

# ===================================================================
# UI 基本設定
# ===================================================================
st.set_page_config(page_title="SJ 四維量價戰情室", layout="wide")

st.markdown("""
<style>
h1 {font-size:20px !important;}
h2 {font-size:20px !important;}
h3 {font-size:20px !important;}
p, label, span, div {font-size:16px !important;}
table td {font-size:14px !important;}
.stDataFrame {font-size:14px !important;}
</style>
""", unsafe_allow_html=True)

# ===================================================================
# 狀態分類系統（三態觀望 + 消除多空矛盾）
# ===================================================================
def map_status(op_text, slope_z):

    # 空方優先
    if "做空" in op_text or "空單" in op_text:
        if slope_z < -1.0:
            return "🔻 空單進場", 1
        else:
            return "⚠️ 空頭觀望", 4

    # 多方
    if slope_z > 1.5:
        return "⭐ 多單進場", 1
    if 0.5 < slope_z <= 1.5:
        return "✅ 多單續抱", 2

    # 三態觀望
    if abs(slope_z) <= 0.3:
        return "⚠️ 空手觀望", 4
    if slope_z > 0:
        return "⚠️ 多頭觀望", 4
    else:
        return "⚠️ 空頭觀望", 4


# ===================================================================
# 固定回測 180 天（掃描用） / 單股回測 1 年
# ===================================================================
LOOKBACK_DAYS = 180
LOOKBACK_1Y = 365

today = datetime.now()
end_dt = today + timedelta(days=1)
start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
start_1y = end_dt - timedelta(days=LOOKBACK_1Y)

# ===================================================================
# 指數工具（自動修正台股價格為整數）
# ===================================================================
def get_index_row(symbol, name):
    df = get_indicator_data(symbol, start_dt, end_dt)
    if df is None or len(df) < 70:
        return None

    # 台股價格修正為整數
    if ".TW" in symbol or symbol.startswith("^TW"):
        df["Close"] = df["Close"].round(0).astype(int)

    op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
    status, _ = map_status(op, sz)
    curr = df.iloc[-1]

    return {
        "指數": name,
        "狀態": status,
        "操作建議": op,
        "現價": round(curr["Close"], 2),
        "PVO": round(curr["PVO"], 2),
        "VRI": round(curr["VRI"], 2),
        "Slope_Z": round(sz, 2),
        "Score_Z": round(scz, 2),
    }

# ===================================================================
# 單股一年回測績效模組（你要求的完整版本）
# ===================================================================
def backtest_single_trade(df):

    in_trade = False
    entry_idx = None
    entry_price = None

    reach_10 = None
    reach_20 = None
    reach_m10 = None

    for i in range(len(df)):
        op, last, sz, scz = get_four_dimension_advice(df, i)
        status, _ = map_status(op, sz)

        price = df.iloc[i]["Close"]

        # 進場條件
        if not in_trade and (status == "⭐ 多單進場"):
            in_trade = True
            entry_idx = i
            entry_price = price
            continue

        # 持有中
        if in_trade:
            ret = (price / entry_price - 1) * 100
            days = i - entry_idx

            if reach_10 is None and ret >= 10:
                reach_10 = days
            if reach_20 is None and ret >= 20:
                reach_20 = days
            if reach_m10 is None and ret <= -10:
                reach_m10 = days

            # 出場條件：第一次進入觀望
            if "觀望" in status:
                exit_idx = i
                exit_price = price
                trade_days = exit_idx - entry_idx
                total_ret = (exit_price / entry_price - 1) * 100

                return {
                    "進場日": df.iloc[entry_idx].name.strftime("%Y-%m-%d"),
                    "出場日": df.iloc[exit_idx].name.strftime("%Y-%m-%d"),
                    "交易天數": trade_days,
                    "報酬率%": round(total_ret, 2),
                    "+10%天數": reach_10,
                    "+20%天數": reach_20,
                    "-10%天數": reach_m10,
                }

    return None


# ===================================================================
# 側邊欄
# ===================================================================
with st.sidebar:
    st.title("🎯 分析模式")

    mode = st.radio(
        "選擇分析類型",
        ["單股分析", "台股市場分析", "美股市場分析"]
    )

    st.divider()
    ticker_input = st.text_input("單股代號（單股模式用）", "2330")

    run_btn = st.button("開始分析")


# ===================================================================
# 主畫面
# ===================================================================
st.title("🛡️ SJ 四維量價分析系統")

# ============================================================
# 🔹 一開頁面就顯示固定指數（不需按按鈕）
# ============================================================
st.subheader("📈 市場指數即時狀態")

index_rows = []

# 台股
twii = get_index_row("^TWII", "台股大盤")
etf50 = get_index_row("0050.TW", "0050")

# 美股
nasdaq = get_index_row("^IXIC", "那斯達克")
sox = get_index_row("^SOX", "費半指數")

for row in [twii, etf50, nasdaq, sox]:
    if row:
        index_rows.append(row)

if index_rows:
    st.dataframe(pd.DataFrame(index_rows), use_container_width=True)

st.divider()

# ============================================================
# 模式一：單股分析（含一年回測績效）
# ============================================================
if run_btn and mode == "單股分析":

    st.subheader("📌 單股即時決策分析（含一年回測績效）")

    symbol = get_taiwan_symbol(ticker_input)
    df = get_indicator_data(symbol, start_1y, end_dt)

    if df is None or len(df) < 120:
        st.warning("資料不足或代號錯誤")
    else:
        # 台股價格修正為整數
        if ".TW" in symbol:
            df["Close"] = df["Close"].round(0).astype(int)

        op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
        status, _ = map_status(op, sz)
        curr = df.iloc[-1]

        st.markdown(f"""
        ### 🎯 {ticker_input} 分析結果  
        **狀態：{status}**  
        操作建議：{op}  
        訊號起點：{last}  
        """)

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("收盤價", f"{curr['Close']}")
        col2.metric("PVO", f"{curr['PVO']:.2f}")
        col3.metric("VRI", f"{curr['VRI']:.2f}")
        col4.metric("Slope_Z", f"{sz:.2f}")
        col5.metric("Score_Z", f"{scz:.2f}")

        # ===== 回測績效區 =====
        st.divider()
        st.subheader("📊 最近一年交易績效回測")

        perf = backtest_single_trade(df)

        if perf:
            st.dataframe(pd.DataFrame([perf]), use_container_width=True)
        else:
            st.info("最近一年內沒有完整的多單 → 觀望交易紀錄")

        st.divider()
        st.subheader("📊 最近 5 日指標")
        st.dataframe(df.tail(5), use_container_width=True)
