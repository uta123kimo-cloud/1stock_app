# --------------------------- 修正版 get_indicator_data 後處理 ---------------------------
def clean_indicator(df):
    # 若 PVO/VRI 欄位為 NaN 或 0 → 顯示「未提供」
    for col in ["PVO", "VRI"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: x if x and not np.isnan(x) else "未提供")
    return df

# --------------------------- 單股符號判斷 ---------------------------
def get_full_symbol(ticker):
    # 台股純數字 → 加 .TW；若已有 .TW 或 .TWO → 保留
    if ticker.isdigit():
        return f"{ticker}.TW"
    elif ticker.upper().endswith((".TW", ".TWO")):
        return ticker.upper()
    else:
        return ticker  # 美股原始代號保留

# --------------------------- 回測時間設定 ---------------------------
LOOKBACK_1Y = 365
end_dt = datetime.strptime(target_date.strftime('%Y-%m-%d'), "%Y-%m-%d") + timedelta(days=1)
start_1y = end_dt - timedelta(days=LOOKBACK_1Y)

# --------------------------- 指數顯示區 ---------------------------
for col, (name, sym) in zip(cols, INDEX_LIST.items()):
    df = get_indicator_data(sym, start_1y, end_dt)
    if df is None or len(df) < 50:
        col.markdown(f"**{name}**\n無資料")
        continue

    df = clean_indicator(df)
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
    status, _ = map_status(op, sz)

    def arrow(v, p):
        if v == "未提供": return ""
        if v > p: return "↑"
        if v < p: return "↓"
        return "→"

    price = round(curr["Close"], 0) if ".TW" in sym else round(curr["Close"], 2)
    pvo_val = f"{curr['PVO']}" if curr['PVO']=="未提供" else f"{curr['PVO']:.2f}"
    vri_val = f"{curr['VRI']}" if curr['VRI']=="未提供" else f"{curr['VRI']:.2f}"

    col.markdown(f"""
    **{name}**  
    收盤：{price}  
    狀態：{status}  
    PVO：{pvo_val} {arrow(curr['PVO'], prev['PVO'])}  
    VRI：{vri_val} {arrow(curr['VRI'], prev['VRI'])}  
    Slope_Z：{sz:.2f} {arrow(sz, get_four_dimension_advice(df, len(df)-2)[2])}  
    """)

# --------------------------- 單股分析修正 ---------------------------
if run_btn and mode == "單股分析":
    st.subheader("📌 單股即時分析 + 回測")

    symbol = get_full_symbol(ticker_input)
    df = get_indicator_data(symbol, start_1y, end_dt)
    if df is None or len(df) < 30:
        st.warning("資料不足")
    else:
        df = clean_indicator(df)
        df["Close"] = df["Close"].round(0).astype(int) if ".TW" in symbol else df["Close"].round(2)
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
        status, _ = map_status(op, sz)

        st.markdown(f"### 🎯 {ticker_input} 當前狀態（截至 {target_date}）\n狀態：**{status}**\n操作建議：{op}")

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("收盤價", f"{curr['Close']}")
        col2.metric("PVO", f"{curr['PVO']}" if curr['PVO']=="未提供" else f"{curr['PVO']:.2f}")
        col3.metric("VRI", f"{curr['VRI']}" if curr['VRI']=="未提供" else f"{curr['VRI']:.2f}")
        col4.metric("Slope_Z", f"{sz:.2f}")
        col5.metric("Score_Z", f"{scz:.2f}")

        # 回測
        st.divider()
        st.subheader("📊 交易回測")
        df_trades, df_summary = backtest_all_trades(df)
        if df_trades is None:
            st.info("一年內沒有完整交易紀錄")
        else:
            st.dataframe(df_trades, use_container_width=True, height=400)
            st.dataframe(df_summary, use_container_width=True)

# --------------------------- 市場分析修正 ---------------------------
if run_btn and mode in ["台股市場分析", "美股市場分析"]:
    st.subheader("📊 市場整體強弱分析")
    watch = TAIWAN_LIST if mode=="台股市場分析" else US_LIST
    results = []

    for sym in watch:
        df = get_indicator_data(sym, start_1y, end_dt)
        if df is None or len(df) < 30:
            continue
        df = clean_indicator(df)
        curr = df.iloc[-1]
        op, last, sz, scz = get_four_dimension_advice(df, len(df)-1)
        status, _ = map_status(op, sz)

        results.append({
            "代號": sym,
            "收盤": round(curr["Close"], 2),
            "狀態": status,
            "Slope_Z": round(sz, 2),
            "Score_Z": round(scz, 2),
            "PVO": curr["PVO"],
            "VRI": curr["VRI"],
        })

    if results:
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("市場清單沒有可用資料")
