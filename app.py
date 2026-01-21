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
# 回測時間設定（固定 1 年）
# ===================================================================
LOOKBACK_1Y = 365
end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d") + timedelta(days=1)
start_1y = end_dt - timedelta(days=LOOKBACK_1Y)


# ===================================================================
# 天數顯示工具（🔥 修正版：不再顯示空白）
# ===================================================================
def format_days(x):
    if x is None:
        return "未達"
    if x > 100:
        return "百"
    return int(x)


# ===================================================================
# 多交易回測引擎（🔥 完整穩定修正版 🔥）
# ===================================================================
def format_reach_status(days, reach_date, reach_price, trade_status="已結束"):
    """
    處理達標顯示邏輯：
    1. 超過 100 天未達標 -> '百無'
    2. 交易結束仍未達標 -> '未達'
    3. 達標 -> 顯示 '第N天 (價格, 日期)'
    """
    if days is not None:
        if days > 100:
            return "百無"
        return f"第 {days} 天 ({reach_price}, {reach_date})"
    
    # 若尚未標記天數，判斷是回測時間太短還是真的沒達到
    if trade_status == "持倉中":
        return "未達"
    return "未達"

def backtest_all_trades(df):
    df = df.copy()
    df.index = pd.to_datetime(df.index)

    trades = []
    equity = [1.0]

    in_trade = False
    entry_idx = None
    entry_price = None
    observe_count = 0

    # 紀錄達標資訊
    reach_10_days = reach_20_days = reach_m10_days = None
    reach_10_info = reach_20_info = reach_m10_info = (None, None)

    for i in range(len(df)):
        op, last, sz, scz = get_four_dimension_advice(df, i)
        status, _ = map_status(op, sz)
        current_price = df.iloc[i]["Close"]
        current_date = df.index[i].strftime("%Y-%m-%d")

        # === 進場 ===
        if not in_trade and status == "⭐ 多單進場":
            in_trade = True
            entry_idx = i
            entry_price = current_price
            observe_count = 0
            reach_10_days = reach_20_days = reach_m10_days = None
            reach_10_info = reach_20_info = reach_m10_info = (None, None)
            continue

        # === 持倉中 ===
        if in_trade:
            days_held = i - entry_idx + 1 # 包含進場當天為第1天
            
            # 檢查是否達標 (僅紀錄第一次達標)
            if reach_10_days is None and current_price >= entry_price * 1.10:
                reach_10_days = days_held
                reach_10_info = (current_price, current_date)
            
            if reach_20_days is None and current_price >= entry_price * 1.20:
                reach_20_days = days_held
                reach_20_info = (current_price, current_date)
                
            if reach_m10_days is None and current_price <= entry_price * 0.90:
                reach_m10_days = days_held
                reach_m10_info = (current_price, current_date)

            # === 出場條件檢查 ===
            exit_flag = False
            if "空單進場" in status or sz < -1:
                exit_flag = True
            elif "觀望" in status:
                observe_count += 1
                if observe_count >= 5:
                    exit_flag = True
            else:
                observe_count = 0

            # 如果達到最後一筆資料，強制平倉並標記為「持倉中」的未達狀態判斷
            is_final_row = (i == len(df) - 1)
            
            if exit_flag or is_final_row:
                trade_status = "持倉中" if (is_final_row and not exit_flag) else "已結束"
                
                exit_idx = i
                exit_price = current_price
                total_ret = (exit_price / entry_price - 1) * 100

                trades.append({
                    "進場日": df.index[entry_idx].strftime("%Y-%m-%d"),
                    "進場價": entry_price,
                    "出場日": df.index[exit_idx].strftime("%Y-%m-%d"),
                    "出場價": exit_price,
                    "交易天數": days_held,
                    "報酬率%": round(total_ret, 2),
                    "+10% 達標": format_reach_status(reach_10_days, reach_10_info[1], reach_10_info[0], trade_status),
                    "+20% 達標": format_reach_status(reach_20_days, reach_20_info[1], reach_20_info[0], trade_status),
                    "-10% 達標": format_reach_status(reach_m10_days, reach_m10_info[1], reach_m10_info[0], trade_status),
                })

                equity.append(equity[-1] * (1 + total_ret / 100))
                in_trade = False
                observe_count = 0

    if not trades:
        return None, None

    df_trades = pd.DataFrame(trades)
    
    # 彙整統計
    summary = {
        "交易次數": len(df_trades),
        "勝率%": round((df_trades["報酬率%"] > 0).mean() * 100, 2),
        "平均報酬%": round(df_trades["報酬率%"].mean(), 2),
        "最大獲利%": round(df_trades["報酬率%"].max(), 2),
        "最大虧損%": round(df_trades["報酬率%"].min(), 2),
    }

    return df_trades, pd.DataFrame([summary])



# ===================================================================
# 主畫面
# ===================================================================
st.title("🛡️ SJ 四維量價分析系統")

# ============================================================
# 首頁四大指數
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

        df.index = pd.to_datetime(df.index)

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
        status, _ = map_status(op, sz)

        def arrow(v, p):
            if v > p: return "↑"
            if v < p: return "↓"
            return "→"

        price = round(curr["Close"], 0) if ".TW" in sym else round(curr["Close"], 2)

        col.markdown(f"""
        **{name}**  
        收盤：{price}  
        狀態：{status}  
        PVO：{curr['PVO']:.2f} {arrow(curr['PVO'], prev['PVO'])}  
        VRI：{curr['VRI']:.2f} {arrow(curr['VRI'], prev['VRI'])}  
        Slope_Z：{sz:.2f} {arrow(sz, get_four_dimension_advice(df, len(df)-2)[2])}  
        """)


# ============================================================
# 單股分析
# ============================================================
if run_btn and mode == "單股分析":

    st.subheader("📌 單股即時分析 + 一年完整交易回測")

    symbol = get_taiwan_symbol(ticker_input)
    df = get_indicator_data(symbol, start_1y, end_dt)

    if df is None or len(df) < 150:
        st.warning("資料不足")
    else:
        df = df.copy()
        df.index = pd.to_datetime(df.index)

        df["Close"] = df["Close"].round(0).astype(int) if ".TW" in symbol else df["Close"].round(2)

        op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
        status, _ = map_status(op, sz)
        curr = df.iloc[-1]
        prev = df.iloc[-2]

        def arrow(v, p):
            if v > p: return "↑"
            if v < p: return "↓"
            return "→"

        st.markdown(f"""
        ### 🎯 {ticker_input} 當前狀態（截至 {target_date}）  
        狀態：**{status}**  
        操作建議：{op}  
        """)

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("收盤價", f"{curr['Close']}")
        col2.metric("PVO", f"{curr['PVO']:.2f} {arrow(curr['PVO'], prev['PVO'])}")
        col3.metric("VRI", f"{curr['VRI']:.2f} {arrow(curr['VRI'], prev['VRI'])}")
        col4.metric("Slope_Z", f"{sz:.2f} {arrow(sz, get_four_dimension_advice(df, len(df)-2)[2])}")
        col5.metric("Score_Z", f"{scz:.2f}")

        # === 回測區 ===
        st.divider()
        st.subheader("📊 最近一年所有交易明細")

        df_trades, df_summary = backtest_all_trades(df)

        if df_trades is None:
            st.info("一年內沒有完整交易紀錄")
        else:
            st.dataframe(df_trades, use_container_width=True, height=400)
            st.dataframe(df_summary, use_container_width=True)


# ============================================================
# 市場分析
# ============================================================
if run_btn and mode in ["台股市場分析", "美股市場分析"]:

    title = "🇹🇼 台股市場全名單掃描（依強度排序）" if mode == "台股市場分析" else "🇺🇸 美股市場全名單掃描（依強度排序）"
    st.subheader(title)

    watch = TAIWAN_LIST if mode == "台股市場分析" else US_LIST
    st.caption(f"掃描股票數量：{len(watch)} 檔")

    results = []

    with st.spinner("市場掃描中，請稍候..."):

        for t in watch:

            symbol = get_taiwan_symbol(t) if mode == "台股市場分析" else t
            df = get_indicator_data(symbol, start_1y, end_dt)

            if df is None or len(df) < 70:
                continue

            op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
            status, rank = map_status(op, sz)
            curr = df.iloc[-1]

            results.append({
                "股票": t,
                "狀態": status,
                "操作建議": op,
                "現價": round(curr["Close"], 2),
                "PVO": round(curr["PVO"], 2),
                "VRI": round(curr["VRI"], 2),
                "Slope_Z": round(sz, 2),
                "Score_Z": round(scz, 2),
                "_rank": rank
            })

    if results:

        df_show = pd.DataFrame(results)

        # === 狀態統計 ===
        status_count = df_show["狀態"].value_counts()
        st.markdown("### 📊 狀態統計")
        st.dataframe(status_count.rename("數量"))

        # === 排序（強 → 弱）===
        df_show = df_show.sort_values(
            by=["_rank", "Slope_Z"],
            ascending=[True, False]
        ).drop(columns=["_rank"])

        st.divider()
        st.subheader("📈 市場掃描結果（依強度排序）")
        st.dataframe(df_show, use_container_width=True, height=700)

    else:
        st.warning("市場清單沒有可用資料")
