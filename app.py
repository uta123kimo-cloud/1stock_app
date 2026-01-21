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


# （前面 import / UI / sidebar 全部維持不變）
# -------------------------------------------------

# ===================================================================
# 天數顯示工具（修正版）
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
def backtest_all_trades(df):

    df = df.copy()
    df.index = pd.to_datetime(df.index)

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

            days = i - entry_idx + 1
            ret = (price / entry_price - 1) * 100

            # === 價格達標紀錄（盤中達標就記）===
            if reach_10 is None and ret >= 10:
                reach_10 = days
            if reach_20 is None and ret >= 20:
                reach_20 = days
            if reach_m10 is None and ret <= -10:
                reach_m10 = days

            # === 出場條件 ===
            exit_flag = False

            if "空單進場" in status or sz < -1:
                exit_flag = True
            elif "觀望" in status:
                observe_count += 1
                if observe_count >= 5:
                    exit_flag = True
            else:
                observe_count = 0

            # === 出場 ===
            if exit_flag:

                exit_idx = i
                exit_price = price
                trade_days = exit_idx - entry_idx + 1
                total_ret = (exit_price / entry_price - 1) * 100

                # 🔧 出場前最後補一次是否達標（關鍵修正）
                if reach_10 is None and total_ret >= 10:
                    reach_10 = trade_days
                if reach_20 is None and total_ret >= 20:
                    reach_20 = trade_days
                if reach_m10 is None and total_ret <= -10:
                    reach_m10 = trade_days

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


    # 🔥 最後一筆尚未出場 → 強制平倉（同樣補達標）
    if in_trade:

        exit_idx = len(df) - 1
        exit_price = df.iloc[-1]["Close"]
        trade_days = exit_idx - entry_idx + 1
        total_ret = (exit_price / entry_price - 1) * 100

        if reach_10 is None and total_ret >= 10:
            reach_10 = trade_days
        if reach_20 is None and total_ret >= 20:
            reach_20 = trade_days
        if reach_m10 is None and total_ret <= -10:
            reach_m10 = trade_days

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
])


# ===================================================================
# 主畫面
# ===================================================================
st.title("🛡️ SJ 四維量價分析系統")

# ============================================================
# 台股 / 美股 市場分析（🔥 排序 + 狀態統計 + 補齊指標 🔥）
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
