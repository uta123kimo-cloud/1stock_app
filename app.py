import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from analysis_engine import get_indicator_data, get_taiwan_symbol
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
# 狀態分類
# ===================================================================
def map_status(op_text, slope_z):
    if "做空" in op_text or "空單" in op_text:
        return ("🔻 空單進場", 1) if slope_z < -1.0 else ("⚠️ 空頭觀望", 4)
    if slope_z > 1.5:
        return "⭐ 多單進場", 1
    if 0.5 < slope_z <= 1.5:
        return "✅ 多單續抱", 2
    if abs(slope_z) <= 0.3:
        return "⚠️ 空手觀望", 4
    if slope_z > 0:
        return "⚠️ 多頭觀望", 4
    return "⚠️ 空頭觀望", 4

# ===================================================================
# 側邊欄
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
# 天數顯示工具
# ===================================================================
def format_days(x):
    if x is None: return ""
    if x > 100: return "百"
    return int(x)

# ===================================================================
# 主程式按鈕觸發
# ===================================================================
if run_btn:
    # 計算日期區間
    end_dt = datetime.combine(target_date, datetime.min.time()) + timedelta(days=1)
    start_1y = end_dt - timedelta(days=365)

    st.title("🛡️ SJ 四維量價分析系統")

    # --- 首頁四大指數 ---
    st.subheader("📊 主要指數即時狀態")
    INDEX_LIST = {"台股大盤":"^TWII","0050":"0050.TW","那斯達克":"^IXIC","費半":"^SOX"}
    cols = st.columns(4)

    for col, (name, sym) in zip(cols, INDEX_LIST.items()):
        df = get_indicator_data(sym, start_1y, end_dt)
        if df is None or len(df)<50: continue

        curr = df.iloc[-1]
        prev = df.iloc[-2]
        op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
        status, _ = map_status(op, sz)

        def arrow(v,p):
            if pd.isna(v) or pd.isna(p) or v==0: return "未提供"
            if v>p: return "↑"
            if v<p: return "↓"
            return "→"

        price = round(curr["Close"],0) if ".TW" in sym else round(curr["Close"],2)
        pvo_str = f"{curr['PVO']:.2f}" if curr['PVO']!=0 and not pd.isna(curr['PVO']) else "未提供"
        vri_str = f"{curr['VRI']:.2f}" if curr['VRI']!=0 and not pd.isna(curr['VRI']) else "未提供"

        col.markdown(f"""
        **{name}**  
        收盤：{price}  
        狀態：{status}  
        PVO：{pvo_str} {arrow(curr['PVO'], prev['PVO'])}  
        VRI：{vri_str} {arrow(curr['VRI'], prev['VRI'])}  
        Slope_Z：{sz:.2f} {arrow(sz, get_four_dimension_advice(df, len(df)-2)[2])}  
        """)

    # --- 單股分析 ---
    if mode=="單股分析":
        st.subheader("📌 單股即時分析")

        symbol = get_taiwan_symbol(ticker_input)
        df = get_indicator_data(symbol, start_1y, end_dt)

        if df is None or len(df)<50:
            st.warning("資料不足")
        else:
            df["Close"] = df["Close"].round(0).astype(int) if ".TW" in symbol else df["Close"].round(2)
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
            status,_ = map_status(op, sz)

            def arrow(v,p):
                if pd.isna(v) or pd.isna(p) or v==0: return "未提供"
                if v>p: return "↑"
                if v<p: return "↓"
                return "→"

            st.markdown(f"""
            ### 🎯 {ticker_input} 當前狀態（截至 {target_date}）  
            狀態：**{status}**  
            操作建議：{op}  
            """)

            col1,col2,col3,col4,col5 = st.columns(5)
            col1.metric("收盤價", f"{curr['Close']}")
            col2.metric("PVO", f"{curr['PVO']:.2f}" if curr['PVO']!=0 and not pd.isna(curr['PVO']) else "未提供")
            col3.metric("VRI", f"{curr['VRI']:.2f}" if curr['VRI']!=0 and not pd.isna(curr['VRI']) else "未提供")
            col4.metric("Slope_Z", f"{sz:.2f}")
            col5.metric("Score_Z", f"{scz:.2f}")

    # --- 市場分析 ---
    if mode in ["台股市場分析","美股市場分析"]:
        st.subheader("📊 市場整體強弱分析")
        watch = TAIWAN_LIST if mode=="台股市場分析" else US_LIST
        results=[]
        for sym in watch:
            df = get_indicator_data(sym, start_1y, end_dt)
            if df is None or len(df)<50: continue
            curr = df.iloc[-1]
            op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
            status,_ = map_status(op, sz)
            results.append({
                "代號": sym,
                "收盤": round(curr["Close"],2),
                "狀態": status,
                "Slope_Z": round(sz,2),
                "Score_Z": round(scz,2)
            })
        if results:
            st.dataframe(pd.DataFrame(results), use_container_width=True)
        else:
            st.warning("市場清單沒有可用資料")
