# ==================== APP.py ====================

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from analysis_engine import get_indicator_data, get_taiwan_symbol, get_advice
from backtest_5d import get_four_dimension_advice
from config import WATCH_LIST as TAIWAN_LIST
from configA import WATCH_LIST as US_LIST

# ===================================================================
st.set_page_config(page_title="SJ 四維量價戰情室", layout="wide")
st.markdown("""<style>h1,h2,h3,p,label,span,div{font-size:16px !important;} table td{font-size:14px !important;}</style>""", unsafe_allow_html=True)

# ===================================================================
def map_status(op_text, slope_z):
    if "做空" in op_text or "空單" in op_text:
        return ("🔻 空單進場", 1) if slope_z < -1 else ("⚠️ 空頭觀望", 4)
    if slope_z > 1.5: return ("⭐ 多單進場",1)
    if 0.5 < slope_z <= 1.5: return ("✅ 多單續抱",2)
    if abs(slope_z)<=0.3: return ("⚠️ 空手觀望",4)
    return ("⚠️ 多頭觀望",4) if slope_z>0 else ("⚠️ 空頭觀望",4)

# ===================================================================
with st.sidebar:
    st.title("🎯 分析模式")
    mode = st.radio("選擇分析類型", ["單股分析", "台股市場分析", "美股市場分析"])
    st.divider()
    target_date = st.date_input("分析基準日", datetime.now())
    st.divider()
    ticker_input = st.text_input("單股代號", "2330")
    run_btn = st.button("開始分析")

LOOKBACK_1Y = 365
end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d")+timedelta(days=1)
start_1y = end_dt - timedelta(days=LOOKBACK_1Y)

# ===================================================================
def safe_get_value(curr,key,prev=None):
    val = curr.get(key,None)
    if val is None or (isinstance(val,float) and np.isnan(val)): return "未提供"
    if prev is not None:
        prev_val = prev.get(key,None)
        arrow = "→" if prev_val is None else ("↑" if val>prev_val else "↓" if val<prev_val else "→")
        return f"{val:.2f} {arrow}" if isinstance(val,(int,float)) else val
    return round(val,0) if isinstance(val,(int,float)) else val

def format_price(symbol,price):
    return int(round(price,0)) if ".TW" in symbol or ".TWO" in symbol else round(price,2)

# ===================================================================
st.title("🛡️ SJ 四維量價分析系統")
INDEX_LIST = {"台股大盤":"^TWII","0050":"0050.TW","那斯達克":"^IXIC","費半":"^SOX"}
cols = st.columns(4)
for col,(name,sym) in zip(cols,INDEX_LIST.items()):
    df = get_indicator_data(sym,start_1y,end_dt)
    if df is not None and len(df)>50:
        curr = df.iloc[-1].to_dict()
        prev = df.iloc[-2].to_dict()
        op,last,sz,scz = get_four_dimension_advice(df,len(df)-1)
        status,_ = map_status(op,sz)
        price = format_price(sym,curr.get("Close",np.nan))
        col.markdown(f"**{name}**  \n收盤：{price}  \n狀態：{status}  \nPVO：{safe_get_value(curr,'PVO',prev)}  \nVRI：{safe_get_value(curr,'VRI',prev)}  \nSlope_Z：{safe_get_value(curr,'Slope_Z',{'Slope_Z':sz})}")

# ===================================================================
# 單股分析
if run_btn and mode=="單股分析":
    st.subheader("📌 單股即時分析 + 一年完整交易回測")
    symbol = get_taiwan_symbol(ticker_input)
    df = get_indicator_data(symbol,start_1y,end_dt)
    if df is None or len(df)<150: st.warning("資料不足")
    else:
        df["Close"] = df["Close"].apply(lambda x: format_price(symbol,x))
        op,last,sz,scz = get_four_dimension_advice(df,len(df)-1)
        status,_ = map_status(op,sz)
        curr = df.iloc[-1].to_dict()
        prev = df.iloc[-2].to_dict()
        st.markdown(f"### 🎯 {ticker_input} 當前狀態（截至 {target_date}）  \n狀態：**{status}**  \n操作建議：{op}")
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("收盤價",f"{curr.get('Close','未提供')}")
        c2.metric("PVO",safe_get_value(curr,'PVO',prev))
        c3.metric("VRI",safe_get_value(curr,'VRI',prev))
        c4.metric("Slope_Z",safe_get_value(curr,'Slope_Z',{'Slope_Z':sz}))
        c5.metric("Score_Z",f"{scz:.2f}")
        # 回測
        st.divider()
        st.subheader("📊 最近一年所有交易明細")
        from app_backtest import backtest_all_trades
        df_trades,df_summary = backtest_all_trades(df)
        if df_trades is None: st.info("一年內沒有完整交易紀錄")
        else:
            st.dataframe(df_trades,use_container_width=True,height=400)
            st.dataframe(df_summary,use_container_width=True)

# ===================================================================
# 市場分析
if run_btn and mode in ["台股市場分析","美股市場分析"]:
    st.subheader("📊 市場整體強弱分析")
    watch = TAIWAN_LIST if mode=="台股市場分析" else US_LIST
    results = []
    for sym in watch:
        sym_real = get_taiwan_symbol(sym)
        df = get_indicator_data(sym_real,start_1y,end_dt)
        if df is None or len(df)<150: continue
        op,last,sz,scz = get_four_dimension_advice(df,len(df)-1)
        status,_ = map_status(op,sz)
        curr = df.iloc[-1].to_dict()
        results.append({"代號":sym_real,"收盤":format_price(sym_real,curr.get("Close",np.nan)),"狀態":status,"Slope_Z":round(sz,2),"Score_Z":round(scz,2)})
    if results: st.dataframe(pd.DataFrame(results),use_container_width=True)
    else: st.warning("市場清單沒有可用資料")
