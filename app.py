import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 直接使用你既有模組（完全不破壞架構）
from analysis_engine import get_indicator_data, get_taiwan_symbol
from backtest_5d import get_four_dimension_advice

# ===================================================================
# UI 基本設定
# ===================================================================
st.set_page_config(page_title="SJ 四維量價戰情室", layout="wide")

# 字體與版面控制（你要求的字級）
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
# 狀態分類系統（依你給的六類訊號）
# ===================================================================
def map_status(op_text, slope_z):
    """
    回傳：
    顯示狀態、排序權重
    """
    # 買入訊號
    if "強力買進" in op_text or slope_z > 1.5:
        return "⭐ 多單進場", 1
    if "波段持有" in op_text or 0.5 < slope_z <= 1.5:
        return "✅ 多單續抱", 2

    # 賣出 / 保守訊號
    if slope_z < -1.0:
        return "❌ 迴避", 6
    if -1.0 <= slope_z < -0.3:
        return "⏸️ 空單觀望", 5
    if abs(slope_z) <= 0.3:
        return "⚠️ 觀望", 4

    # 預設
    return "⚠️ 觀望", 4

# ===================================================================
# 側邊欄選單（你要求的三模式）
# ===================================================================
with st.sidebar:
    st.title("🎯 分析模式")

    mode = st.radio(
        "選擇分析類型",
        ["單股分析", "台股市場分析", "美股市場分析"]
    )

    st.divider()
    target_date = st.date_input("分析基準日", datetime.now())

    st.divider()
    ticker_input = st.text_input("單股代號（單股模式用）", "2330")

    run_btn = st.button("開始分析")

# ===================================================================
# 固定回測 180 天（你指定）
# ===================================================================
LOOKBACK_DAYS = 180
end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d") + timedelta(days=1)
start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)

# ===================================================================
# 讀取 Config 名單（台股 / 美股）
# ===================================================================
# 你之後可以放在 config.py / config_a.py
TAIWAN_LIST = [
    "2330", "2317", "2454", "2308", "2382", "3231", "3037",
    "2603", "2881", "2882", "1513", "1504"
]

US_LIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA",
    "GOOGL", "AMD", "AVGO", "NFLX"
]

# ===================================================================
# 主畫面
# ===================================================================
st.title("🛡️ SJ 四維量價分析系統")

# ============================================================
# 模式一：單股分析
# ============================================================
if run_btn and mode == "單股分析":

    st.subheader("📌 單股即時決策分析")

    symbol = get_taiwan_symbol(ticker_input)
    df = get_indicator_data(symbol, start_dt, end_dt)

    if df is None or len(df) < 70:
        st.warning("資料不足或代號錯誤")
    else:
        op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
        status, _ = map_status(op, sz)

        curr = df.iloc[-1]

        st.markdown(f"""
        ### 🎯 {ticker_input} 分析結果  
        **狀態：{status}**  
        操作建議：{op}  
        訊號起點：{last}  
        """)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("收盤價", f"{curr['Close']:.2f}")
        col2.metric("PVO", f"{curr['PVO']:.2f}")
        col3.metric("VRI", f"{curr['VRI']:.2f}")
        col4.metric("Slope_Z", f"{sz:.2f}")

        st.divider()
        st.subheader("📊 最近 5 日指標")
        st.dataframe(df.tail(5), use_container_width=True)

# ============================================================
# 模式二：台股市場分析（全名單掃描 + 依強到弱排序）
# ============================================================
if run_btn and mode == "台股市場分析":

    st.subheader("🇹🇼 台股市場全名單掃描（依強度排序）")

    results = []

    with st.spinner("掃描台股中..."):
        for t in TAIWAN_LIST:
            symbol = get_taiwan_symbol(t)
            df = get_indicator_data(symbol, start_dt, end_dt)

            if df is None or len(df) < 70:
                continue

            op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
            status, rank = map_status(op, sz)
            curr = df.iloc[-1]

            results.append({
                "股票": t,
                "狀態": status,
                "操作建議": op,
                "訊號起點": last,
                "現價": round(curr['Close'], 2),
                "Slope_Z": round(sz, 2),
                "Score_Z": round(scz, 2),
                "_rank": rank
            })

    if results:
        df_show = pd.DataFrame(results).sort_values(
            by=["_rank", "Slope_Z"],
            ascending=[True, False]
        ).drop(columns=["_rank"])

        st.dataframe(df_show, use_container_width=True, height=650)
    else:
        st.warning("沒有可用資料")

# ============================================================
# 模式三：美股市場分析（全名單掃描 + 依強到弱排序）
# ============================================================
if run_btn and mode == "美股市場分析":

    st.subheader("🇺🇸 美股市場全名單掃描（依強度排序）")

    results = []

    with st.spinner("掃描美股中..."):
        for t in US_LIST:
            df = get_indicator_data(t, start_dt, end_dt)

            if df is None or len(df) < 70:
                continue

            op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
            status, rank = map_status(op, sz)
            curr = df.iloc[-1]

            results.append({
                "股票": t,
                "狀態": status,
                "操作建議": op,
                "訊號起點": last,
                "現價": round(curr['Close'], 2),
                "Slope_Z": round(sz, 2),
                "Score_Z": round(scz, 2),
                "_rank": rank
            })

    if results:
        df_show = pd.DataFrame(results).sort_values(
            by=["_rank", "Slope_Z"],
            ascending=[True, False]
        ).drop(columns=["_rank"])

        st.dataframe(df_show, use_container_width=True, height=650)
    else:
        st.warning("沒有可用資料")
