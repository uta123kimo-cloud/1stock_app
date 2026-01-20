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

        # =====================================================
        # 進場邏輯（允許趨勢初期與強勢突破）
        # =====================================================
        if not in_trade:

            # ⭐ 強勢突破
            if status == "⭐ 多單進場":

                in_trade = True
                entry_idx = i
                entry_price = price

            # ✅ 趨勢延續第一天也可進場
            elif status == "✅ 多單續抱":

                # 避免連續多天重複進場，只吃第一次
                if i == 0:
                    continue
                prev_op, _, prev_sz, _ = get_four_dimension_advice(df, i-1)
                prev_status, _ = map_status(prev_op, prev_sz)

                if prev_status not in ["⭐ 多單進場", "✅ 多單續抱"]:
                    in_trade = True
                    entry_idx = i
                    entry_price = price

            if in_trade:
                observe_count = 0
                reach_10 = reach_20 = reach_m10 = None
                continue   # 進場當天不檢查出場


        # =====================================================
        # 持倉中處理
        # =====================================================
        if in_trade:

            days = i - entry_idx + 1
            ret = (price / entry_price - 1) * 100

            # ---------- 價格目標天數統計 ----------
            if reach_10 is None and ret >= 10:
                reach_10 = days
            if reach_20 is None and ret >= 20:
                reach_20 = days
            if reach_m10 is None and ret <= -10:
                reach_m10 = days

            # =================================================
            # 出場判斷機制（三層）
            # =================================================
            exit_flag = False

            # (A) 強制反向出場
            if "空單進場" in status or sz < -1:
                exit_flag = True

            # (B) 觀望累積 5 天出場
            elif "觀望" in status:
                observe_count += 1
                if observe_count >= 5:
                    exit_flag = True

            else:
                observe_count = 0

            # (C) 保護性最長持倉（防止死單）
            if days >= 120:   # 最多持倉 120 天
                exit_flag = True

            # =================================================
            # 出場執行
            # =================================================
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

                # 重置狀態
                in_trade = False
                observe_count = 0
                entry_idx = None
                entry_price = None
                reach_10 = reach_20 = reach_m10 = None


    # =====================================================
    # 最後一筆尚未出場 → 強制在最後一天平倉（關鍵修正）
    # =====================================================
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


    # =====================================================
    # 若一年真的沒有交易（理論上現在不會發生）
    # =====================================================
    if not trades:
        return None, None


    # =====================================================
    # 統計區
    # =====================================================
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
