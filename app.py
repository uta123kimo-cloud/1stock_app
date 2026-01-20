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
# 回測時間設定（固定 1 年 = 365 天）
# ===================================================================
LOOKBACK_1Y = 365
end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d") + timedelta(days=1)
start_1y = end_dt - timedelta(days=LOOKBACK_1Y)


# ===================================================================
# 天數顯示轉換工具（>100 顯示為「百」）
# ===================================================================
def format_days(x):
    if x is None:
        return ""
    if x > 100:
        return "百"
    return int(x)


# ===================================================================
# 多交易回測引擎（完整版）
# ===================================================================
def backtest_all_trades(df):

    trades = []
    equity = [1.0]

    in_trade = False
    entry_idx = None
    entry_price = None
    observe_count = 0

    reach_10 = reach_20 = reach_m10 = None

    for i in range(len(df)):
        op, last, sz, scz = get_four_dimension_advice(df, i)
        status, _ = map_status(op, sz)
        price = df.iloc[i]["Close"]

        # === 進場 ===
        if not in_trade and status == "⭐ 多單進場":
            in_trade = True
            entry_idx = i
            entry_price = price
            observe_count = 0
            reach_10 = reach_20 = reach_m10 = None
            continue

        if in_trade:
            ret = (price / entry_price - 1) * 100
            days = i - entry_idx

            # === 價格達標天數（不管訊號）===
            if reach_10 is None and ret >= 10:
                reach_10 = days
            if reach_20 is None and ret >= 20:
                reach_20 = days
            if reach_m10 is None and ret <= -10:
                reach_m10 = days

            # === 出場條件：連續 5 天觀望 或 出現空單 ===
            if "空單進場" in status or sz < -1:
                exit_idx = i
            else:
                if "觀望" in status:
                    observe_count += 1
                else:
                    observe_count = 0

                if observe_count < 5:
                    continue
                exit_idx = i

            exit_price = price
            trade_days = exit_idx - entry_idx
            total_ret = (exit_price / entry_price - 1) * 100

            trades.append({
                "進場日": df.iloc[entry_idx].name.strftime("%Y-%m-%d"),
                "出場日": df.iloc[exit_idx].name.strftime("%Y-%m-%d"),
                "交易天數": format_days(trade_days),
                "報酬率%": round(total_ret, 2),
                "+10% 天數": format_days(reach_10),
                "+20% 天數": format_days(reach_20),
                "-10% 天數": format_days(reach_m10),
            })

            equity.append(equity[-1] * (1 + total_ret / 100))

            in_trade = False
            observe_count = 0

    if not trades:
        return None, None

    df_trades = pd.DataFrame(trades)
    df_trades.index = pd.to_datetime(df_trades["進場日"])
    df_trades.index.name = "進場日(索引)"

    win_rate = (df_trades["報酬率%"] > 0).mean() * 100
    avg_ret = df_trades["報酬率%"].mean()
    max_win = df_trades["報酬率%"].max()
    max_loss = df_trades["報酬率%"].min()

    equity_curve = np.array(equity)
    peak = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - peak) / peak
    max_dd = drawdown.min() * 100

    summary = {
        "交易次數": len(df_trades),
        "勝率%": round(win_rate, 2),
        "平均報酬%": round(avg_ret, 2),
        "最大獲利%": round(max_win, 2),
        "最大虧損%": round(max_loss, 2),
        "最大回撤%": round(max_dd, 2),
    }

    return df_trades, pd.DataFrame([summary])


# ===================================================================
# 主畫面
# ===================================================================
st.title("🛡️ SJ 四維量價分析系統")

# ============================================================
# 預設首頁顯示四大指數
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

        curr = df.iloc[-1]
        op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
        status, _ = map_status(op, sz)

        price = curr["Close"]
        if ".TW" in sym:
            price = int(round(price, 0))
        else:
            price = round(price, 2)

        col.markdown(f"""
        **{name}**  
        收盤：{price}  
        狀態：{status}  
        PVO：{curr['PVO']:.2f}  
        VRI：{curr['VRI']:.2f}  
        Slope_Z：{sz:.2f}  
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
        if ".TW" in symbol:
            df["Close"] = df["Close"].round(0).astype(int)
        else:
            df["Close"] = df["Close"].round(2)

        op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
        status, _ = map_status(op, sz)
        curr = df.iloc[-1]

        st.markdown(f"""
        ### 🎯 {ticker_input} 當前狀態（截至 {target_date}）  
        狀態：**{status}**  
        操作建議：{op}  
        """)

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("收盤價", f"{curr['Close']}")
        col2.metric("PVO", f"{curr['PVO']:.2f}")
        col3.metric("VRI", f"{curr['VRI']:.2f}")
        col4.metric("Slope_Z", f"{sz:.2f}")
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
