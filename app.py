# ========================= app.py =========================
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
# 回測時間設定
# ===================================================================
LOOKBACK_1Y = 365
end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d") + timedelta(days=1)
start_1y = end_dt - timedelta(days=LOOKBACK_1Y)


# ===================================================================
# 天數顯示轉換工具
# ===================================================================
def format_days(x):
    if x is None:
        return ""
    if x > 100:
        return "百"
    return int(x)


# ===================================================================
# 多交易回測引擎（⭐ 正式修正版 ⭐）
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

        # === 持倉中 ===
        if in_trade:

            days = i - entry_idx + 1   # ⭐ 修正：從第 1 天開始算
            ret = (price / entry_price - 1) * 100

            # === 價格達標天數（不管最後出場輸贏）===
            if reach_10 is None and ret >= 10:
                reach_10 = days
            if reach_20 is None and ret >= 20:
                reach_20 = days
            if reach_m10 is None and ret <= -10:
                reach_m10 = days

            # === 出場條件 ===
            exit_flag = False

            # 反向訊號
            if "空單進場" in status or sz < -1:
                exit_flag = True

            # 連續 5 天觀望
            elif "觀望" in status:
                observe_count += 1
                if observe_count >= 5:
                    exit_flag = True
            else:
                observe_count = 0

            # === 出場執行 ===
            if exit_flag:

                exit_idx = i
                exit_price = price
                trade_days = exit_idx - entry_idx + 1
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
                entry_idx = None
                entry_price = None
                reach_10 = reach_20 = reach_m10 = None


    # ⭐ 最後一筆尚未出場 → 強制平倉（關鍵修正）
    if in_trade:

        exit_idx = len(df) - 1
        exit_price = df.iloc[-1]["Close"]
        trade_days = exit_idx - entry_idx + 1
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


    if not trades:
        return None, None

    df_trades = pd.DataFrame(trades)

    win_rate = (df_trades["報酬率%"] > 0).mean() * 100
    avg_ret = df_trades["報酬率%"].mean()
    max_win = df_trades["報酬率%"].max()
    max_loss = df_trades["報酬率%"].min()

    summary = {
        "交易次數": len(df_trades),
        "勝率%": round(win_rate, 2),
        "平均報酬%": round(avg_ret, 2),
        "最大獲利%": round(max_win, 2),
        "最大虧損%": round(max_loss, 2),
    }

    return df_trades, pd.DataFrame([summary])
