import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

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
# 狀態分類
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
# 回測時間設定
# ===================================================================
LOOKBACK_1Y = 365
if isinstance(target_date, datetime):
    end_dt = target_date + timedelta(days=1)
else:
    end_dt = datetime.strptime(str(target_date), "%Y-%m-%d") + timedelta(days=1)
start_1y = end_dt - timedelta(days=LOOKBACK_1Y)

# ===================================================================
# 安全取得指標值 & 收盤價格式化
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
        return f"{val:.2f} {arrow_val}" if isinstance(val, (int,float)) else val
    return round(val,2) if isinstance(val, (int,float)) else val

def format_price(symbol, price):
    if ".TW" in symbol or ".TWO" in symbol:
        return int(round(price,0)) if price is not None else "未提供"
    return round(price,2) if price is not None else "未提供"

# ===================================================================
# 主畫面
# ===================================================================
st.title("🛡️ SJ 四維量價分析系統")

# ============================================================
# 首頁四大指數（含 ↑ ↓ 與正確小數，增加 PVO/VRI 與昨日比較箭頭）
# ============================================================
st.subheader("📊 主要指數即時狀態")
INDEX_LIST = {
    "台股大盤": "^TWII",
    "0050": "0050.TW",
    "那斯達克": "^IXIC",
    "費半": "^SOX"
}

cols = st.columns(4)

for col, (name, sym) in zip(cols, INDEX_LIST.items()):
    df = get_indicator_data(sym, start_1y, end_dt)

    if df is not None and len(df) > 50:

        curr = df.iloc[-1].to_dict()
        prev = df.iloc[-2].to_dict()

        op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
        status, _ = map_status(op, sz)

        price = format_price(sym, curr.get("Close", np.nan))

        col.markdown(f"""
        **{name}**  
        收盤：{price}  
        狀態：{status}  
        PVO：{safe_get_value(curr, 'PVO', prev)}  
        VRI：{safe_get_value(curr, 'VRI', prev)}  
        Slope_Z：{safe_get_value(curr, 'Slope_Z', {'Slope_Z': get_four_dimension_advice(df, len(df)-2)[2]})}  
        """)
# ============================================================
# 單股分析（僅顯示當前狀態 + PVO/VRI/Slope_Z/Score_Z）
# ============================================================
if run_btn and mode=="單股分析":
    st.subheader("📌 單股即時分析")
    symbol = get_taiwan_symbol(ticker_input)
    df = get_indicator_data(symbol, start_1y, end_dt)
    if df is None or len(df)<150:
        st.warning("資料不足")
    else:
        df["Close"] = df["Close"].apply(lambda x: format_price(symbol,x))
        op, last, sz, scz = get_four_dimension_advice(df,len(df)-1)
        status, _ = map_status(op, sz)
        curr = df.iloc[-1].to_dict()
        prev = df.iloc[-2].to_dict()
        st.markdown(f"### 🎯 {ticker_input} 當前狀態（截至 {target_date}）\n狀態：**{status}**\n操作建議：{op}")
        col1,col2,col3,col4,col5 = st.columns(5)
        col1.metric("收盤價", f"{curr.get('Close','未提供')}")
        col2.metric("PVO", safe_get_value(curr,'PVO',prev))
        col3.metric("VRI", safe_get_value(curr,'VRI',prev))
        col4.metric("Slope_Z", safe_get_value(curr,'Slope_Z',{'Slope_Z': get_four_dimension_advice(df,len(df)-2)[2]}))
        col5.metric("Score_Z", f"{scz:.2f}")

# ============================================================
# 台股市場分析 / 美股市場分析（增加 PVO/VRI + 狀態統計 + 昨日比較箭頭）
# ============================================================
if run_btn and mode in ["台股市場分析","美股市場分析"]:
    st.subheader("📊 市場整體強弱分析")
    watch = TAIWAN_LIST if mode=="台股市場分析" else US_LIST
    results = []
    status_count = {}
    prev_status_count = {}

    for sym in watch:
        symbol = get_taiwan_symbol(sym)
        df = get_indicator_data(symbol, start_1y, end_dt)
        if df is None or len(df)<150:
            continue
        op, last, sz, scz = get_four_dimension_advice(df,len(df)-1)
        status, _ = map_status(op, sz)
        curr = df.iloc[-1].to_dict()
        results.append({
            "代號": sym,
            "收盤": format_price(symbol,curr.get("Close",np.nan)),
            "狀態": status,
            "PVO": safe_get_value(curr,'PVO',None),
            "VRI": safe_get_value(curr,'VRI',None),
            "Slope_Z": round(sz,2),
            "Score_Z": round(scz,2),
        })
        status_count[status] = status_count.get(status,0)+1

        # 昨日比較
        if len(df)>1:
            op_prev, _, sz_prev, _ = get_four_dimension_advice(df,len(df)-2)
            status_prev, _ = map_status(op_prev, sz_prev)
            prev_status_count[status_prev] = prev_status_count.get(status_prev,0)+1

    # 顯示結果表
    if results:
        st.dataframe(pd.DataFrame(results),use_container_width=True)
        # 狀態統計
        count_df = pd.DataFrame([
            {"狀態": k, "數量": v, "昨日比較": f"{v - prev_status_count.get(k,0)} ↑" if v - prev_status_count.get(k,0)>0 else f"{v - prev_status_count.get(k,0)}"} 
            for k,v in status_count.items()
        ])
        st.subheader("📈 狀態統計")
        st.dataframe(count_df,use_container_width=True)
    else:
        st.warning("市場清單沒有可用資料")
