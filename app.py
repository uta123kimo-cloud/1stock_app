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
            # ⚠️ 不能 continue，當天就開始算

        # === 持倉中 ===
        if in_trade:

            # 交易天數（從第 1 天開始）
            days = i - entry_idx + 1
            ret = (price / entry_price - 1) * 100

            # === 價格達標天數（不管訊號）===
            if reach_10 is None and ret >= 10:
                reach_10 = days
            if reach_20 is None and ret >= 20:
                reach_20 = days
            if reach_m10 is None and ret <= -10:
                reach_m10 = days

            # === 出場條件判斷 ===
            exit_flag = False

            # 反向強制出場
            if "空單進場" in status or sz < -1:
                exit_flag = True
            else:
                # 觀望累積出場
                if "觀望" in status:
                    observe_count += 1
                else:
                    observe_count = 0

                if observe_count >= 5:
                    exit_flag = True

            # === 出場 ===
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
