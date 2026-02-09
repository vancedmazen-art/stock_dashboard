import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import os
import numpy as np

# ---------------------------
# LOAD ALL 3 SHEETS + Strategy Metrics
# ---------------------------
def load_data():
    try:
        if not os.path.exists("Complete_Trades_Metrics.xlsx"):
            st.error("❌ Complete_Trades_Metrics.xlsx missing!")
            st.stop()
            return {}, [], [], pd.DataFrame()
        
        # Sheet 0: Closed trades
        closed_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=0)
        # Sheet 1: Current trades  
        current_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=1)
        # 🔥 SHEET 3: STRATEGY METRICS (NEW!)
        strategy_metrics = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=3)
        refresh_df = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=4)
        refresh_date_obj = pd.to_datetime(refresh_df['refresh_date'].date())
        
        if os.path.exists("egx_company_map.csv"):
            company_map = pd.read_csv("egx_company_map.csv")
            if "Symbol" in company_map.columns:
                company_map["Ticker"] = company_map["Symbol"].str.replace("EGX:", "", regex=False)
                closed_trades = closed_trades.merge(company_map, on="Ticker", how="left")
                current_trades = current_trades.merge(company_map, on="Ticker", how="left")
        
        all_tickers = pd.concat([
            closed_trades['Ticker'].dropna(),
            current_trades['Ticker'].dropna()
        ]).drop_duplicates().sort_values().str.strip().tolist()
        
        st.success(f"✅ Loaded {len(current_trades)} current + {len(closed_trades)} closed + Strategy metrics")
        return {"closed": closed_trades, "current": current_trades}, all_tickers, strategy_metrics
        
    except Exception as e:
        st.error(f"❌ Load failed: {e}")
        st.stop()
        return {}, [], [], pd.DataFrame()

st.set_page_config(page_title="🚀 EGX Trading Dashboard", layout="wide")

# 🔥 REFRESH BUTTON
col1, col2 = st.columns([3,1])
with col2:
    if st.button("🔄 **FORCE RELOAD**", type="primary"):
        st.rerun()

data, all_symbols, df_strategy = load_data()
df_current = data["current"].copy()
df_closed = data["closed"].copy()

# 🔥 FILTER EGX30 DATA
df_current_egx30 = df_current[df_current['Ticker'] == 'EGX30'].copy()
df_closed_egx30 = df_closed[df_closed['Ticker'] == 'EGX30'].copy()
df_strategy_egx30 = df_strategy[df_strategy['Ticker'] == 'EGX30'].copy()

# Filter other tickers (exclude EGX30)
df_current_other = df_current[df_current['Ticker'] != 'EGX30'].copy()
df_closed_other = df_closed[df_closed['Ticker'] != 'EGX30'].copy()
all_symbols_other = [s for s in all_symbols if s != 'EGX30']

# --------------------------- 
# FIX PYARROW
# ---------------------------
def fix_pyarrow_df(df):
    df_display = df.copy()
    date_cols = ['Entry_Date', 'Exit_Date']
    for col in date_cols:
        if col in df_display.columns:
            df_display[col] = pd.to_datetime(df_display[col], errors='coerce').dt.strftime('%Y-%m-%d')
    for col in df_display.select_dtypes(include=['object']).columns:
        df_display[col] = df_display[col].astype(str)
    return df_display

def safe_display(value):
    if pd.isna(value) or value is None or value == "":
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.1f}"
    return str(value)

def fetch_latest_news(symbol: str, max_items=3):
    try:
        API_URL = "https://news-mediator.tradingview.com/news-flow/v2/news?filter=lang%3Aen&filter=market%3Astock&filter=market_country%3AEG&client=screener"
        r = requests.get(API_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
    except: 
        return []
    
    items = data.get("items", [])
    result = []
    for news in items:
        related_symbols = [s.get("symbol", "").replace("EGX:", "") for s in news.get("relatedSymbols", [])]
        if symbol in related_symbols:
            title = news.get("title", "")
            url = news.get("storyPath", "")
            provider = news.get("provider", {}).get("name", "")
            result.append({"title": title, "url": f"https://www.tradingview.com{url}", "provider": provider})
        if len(result) >= max_items: break
    return result

# 🔥 DATE PROCESSING
df_current_internal = df_current_other.copy()
df_closed_internal = df_closed_other.copy()
df_current_internal['Entry_Date'] = pd.to_datetime(df_current_internal['Entry_Date'], errors='coerce').dt.date
df_closed_internal['Entry_Date'] = pd.to_datetime(df_closed_internal['Entry_Date'], errors='coerce').dt.date
df_closed_internal['Exit_Date'] = pd.to_datetime(df_closed_internal['Exit_Date'], errors='coerce').dt.date

# --------------------------- 
# 🔥 5-TAB DASHBOARD (Added EGX30 tab)
# ---------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⚡ **TODAY'S ACTIONS**", 
    "📊 **STOCK DETAIL**", 
    "📈 **PORTFOLIO**", 
    "📋 **HISTORY**",
    "📊 **Overall Market Sentiment**"
])

# 🔥 TAB 1: TODAY'S ACTIONS + Best_Strategy (EGX30 excluded)
with tab1:
    st.markdown("### 🚨 **TODAY'S TRADING DECISIONS**")
    
    max_entry_date = df_current_internal['Entry_Date'].max()
    new_buys = df_current_other[df_current_internal['Entry_Date'] == refresh_date_obj].copy()
    
    # 🔥 MERGE Best_Strategy from sheet 3
    new_buys_with_strategy = new_buys.merge(df_strategy[['Ticker', 'Best_Strategy']], on='Ticker', how='left')
    
    st.markdown("#### 🆕 **Fresh BUYS**")
    col1, col2, col3 = st.columns(3)
    col1.metric("🆕 New Buys", len(new_buys))
    col2.metric("💰 Best PnL", f"{new_buys['Trade_PnL_%'].max():.1f}%" if len(new_buys)>0 else "-")
    col3.metric("📊 Avg PnL", f"{new_buys['Trade_PnL_%'].mean():.1f}%" if len(new_buys)>0 else "-")
    st.dataframe(fix_pyarrow_df(new_buys_with_strategy[['Ticker','BUY_REASON', 'Entry_Date', 'Entry_Price', 'Trade_PnL_%', 
                                                       'Entry_Volume', 'Status','Entry_Crosses_Resistance', 'Best_Strategy']]), 
                use_container_width=True, height=200)
    
    max_exit_date = df_closed_internal['Exit_Date'].max()
    close_now = df_closed_other[df_closed_internal['Exit_Date'] == refresh_date_obj].copy()
    
    st.markdown("#### ❌ **CLOSE NOW**")
    col1, col2, col3 = st.columns(3)
    col1.metric("❌ Closed Today", len(close_now))
    col2.metric("💰 Best PnL", f"{close_now['Trade_PnL_%'].max():.1f}%" if len(close_now)>0 else "-")
    col3.metric("📊 Avg PnL", f"{close_now['Trade_PnL_%'].mean():.1f}%" if len(close_now)>0 else "-")
    st.dataframe(fix_pyarrow_df(close_now[['Ticker', 'Entry_Date', 'Exit_Price', 'Trade_PnL_%', 'Days_Held','Entry_Crosses_Resistance', 'BUY_REASON']]), 
                use_container_width=True, height=200)
    
    holds = df_current_other[df_current_internal['Entry_Date'] != refresh_date_obj].copy()
    holds_with_strategy = holds.merge(df_strategy[['Ticker', 'Best_Strategy']], on='Ticker', how='left')
    
    st.markdown("#### ✅ **HOLDS**")
    col1, col2, col3 = st.columns(3)
    col1.metric("✅ Holds", len(holds))
    col2.metric("🚀 Best PnL", f"{holds['Trade_PnL_%'].max():.1f}%" if len(holds)>0 else "-")
    col3.metric("📊 Avg PnL", f"{holds['Trade_PnL_%'].mean():.1f}%" if len(holds)>0 else "-")
    st.dataframe(fix_pyarrow_df(holds_with_strategy[['Ticker', 'BUY_REASON', 'Entry_Date', 'Trade_PnL_%', 'Days_Held', 
                                                    'Status','Entry_Crosses_Resistance','Current_Crosses_Resistance', 'Best_Strategy']]), use_container_width=True, height=300)

# 🔥 TAB 2: STOCK DETAIL + SHEET 3 METRICS (EGX30 excluded)
with tab2:
    selected_symbol = st.selectbox("🔍 Choose Stock:", all_symbols_other)
    
    current_stock_df = df_current_other[df_current_other["Ticker"] == selected_symbol]
    stock_history = df_closed_other[df_closed_other["Ticker"] == selected_symbol].sort_values("Entry_Date", ascending=False)
    
    # 🔥 SHEET 3 STRATEGY METRICS for this stock
    strategy_for_stock = df_strategy[df_strategy["Ticker"] == selected_symbol]
    
    left_col, right_col = st.columns([3, 1])
    
    with left_col:
        st.markdown(f"### 📈 **{selected_symbol}**")
        
        if len(current_stock_df) > 0:
            st.markdown("#### 🟢 **CURRENT TRADES**")
            st.dataframe(fix_pyarrow_df(current_stock_df[['Entry_Date','BUY_REASON', 'Entry_Price', 'Trade_PnL_%', 
                                                         'Days_Held', 'Status']]), use_container_width=True, height=200)
        else:
            st.info("⚠️ No current open trades")
        
        st.markdown("#### 📊 **CHART**")
        st.components.v1.iframe(f"https://s.tradingview.com/widgetembed/?symbol=EGX:{selected_symbol}&interval=D&theme=Light&style=9", height=400)
        
        st.markdown("#### 📰 **NEWS**")
        news_items = fetch_latest_news(selected_symbol)
        if news_items:
            for n in news_items:
                st.markdown(f"**{n['title']}**")
                st.caption(f"{n['provider']}")
                st.divider()
        
        st.markdown(f"#### 📋 **HISTORY** ({len(stock_history)} closed trades)")
        if len(stock_history) > 0:
            st.dataframe(fix_pyarrow_df(stock_history), use_container_width=True, height=250)
    
    with right_col:
        st.markdown("#### 🎯 **STRATEGY METRICS**")
        if len(strategy_for_stock) > 0:
            strat = strategy_for_stock.iloc[0]
            st.metric("🏆 Best Strategy", strat['Best_Strategy'])
            st.metric("📊 Score", f"{safe_display(strat['score'])}")
            st.metric("✅ Win Rate", f"{safe_display(strat['win_rate'])}%")
            st.metric("🎯 Median PnL", f"{safe_display(strat['median_pnl'])}%")
            st.metric("📈 Total Trades", safe_display(strat['total_trades']))
        else:
            st.info("No strategy metrics")
        
        st.markdown("---")
        st.markdown("#### 📊 **TRADE METRICS**")
        if len(current_stock_df) > 0:
            latest = current_stock_df.iloc[0]
            st.metric("💰 PnL", f"{safe_display(latest['Trade_PnL_%'])}%")
            st.metric("⏳ Days", safe_display(latest['Days_Held']))

# 🔥 TAB 3: PORTFOLIO + TOP STRATEGIES (EGX30 excluded)
with tab3:
    st.markdown("### 📈 **PORTFOLIO OVERVIEW**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 Open", len(df_current_other))
    col2.metric("📋 Closed", len(df_closed_other))
    col3.metric("✅ Win Rate", f"{len(df_closed_other[df_closed_other['Trade_PnL_%']>0])/len(df_closed_other)*100:.1f}%" if len(df_closed_other)>0 else "0%")
    col4.metric("💰 Avg PnL", f"{df_closed_other['Trade_PnL_%'].mean():.1f}%")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🟢 **TOP GAINERS**")
        top_gainers = fix_pyarrow_df(df_closed_other.nlargest(10, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held"]])
        top_gainers['Trade_PnL_%'] = top_gainers['Trade_PnL_%'].apply(lambda x: f"{float(x):.1f}%")
        st.dataframe(top_gainers, use_container_width=True)
    
    with col2:
        st.markdown("### 🏆 **TOP STRATEGIES**")
        top_strategies = fix_pyarrow_df(df_strategy[df_strategy['Ticker'] != 'EGX30'].nlargest(10, "score")[['Ticker', 'Best_Strategy', 'score', 'win_rate']])
        st.dataframe(top_strategies, use_container_width=True)

# 🔥 TAB 4: FULL HISTORY (EGX30 excluded)
with tab4:
    st.markdown("### 📋 **COMPLETE HISTORY**")
    full_history = fix_pyarrow_df(pd.concat([df_current_other, df_closed_other]).sort_values("Entry_Date", ascending=False))
    st.dataframe(full_history, use_container_width=True, height=600)

# 🔥 TAB 5: OVERALL MARKET SENTIMENT (EGX30 ONLY) - COMPREHENSIVE
# 🔥 TAB 5: OVERALL MARKET SENTIMENT (EGX30 ONLY) - REFINED LAYOUT
with tab5:

    st.markdown("## 📊 **EGX30 – Market Overview & Sentiment**")
    open_trades = len(df_current_egx30)
    if open_trades > 0:
        sentiment_text = "🟢 Positive"
        sentiment_emoji = "🚀📈"
    else:
        sentiment_text = "🔴 Neutral / Cautious"
        sentiment_emoji = "⚠️📉"
    st.markdown(
        f"### {sentiment_emoji} Market Sentiment: **{sentiment_text}**"
    )
    st.divider()


    # =========================
    # 🔹 MAIN BODY (LEFT / RIGHT)
    # =========================
    left, right = st.columns([2.2, 1])

    # =========================
    # 📈 LEFT SIDE (CHART + TABLES)
    # =========================
    with left:

        # ----------- CHART -----------
        st.markdown("### 📈 **EGX30 Technical Chart**")

        st.components.v1.iframe(
            "https://s.tradingview.com/widgetembed/?symbol=EGX:EGX30&interval=D&theme=Light&style=9",
            height=480
        )

        st.divider()

        # ----------- OPEN TRADES -----------
        st.markdown("### 🟢 **Open Positions**")

        if len(df_current_egx30) > 0:

            st.dataframe(
                fix_pyarrow_df(
                    df_current_egx30[[
                        'Entry_Date',
                        'Entry_Price',
                        'Trade_PnL_%',
                        'Days_Held',
                        'Status',
                        'BUY_REASON'
                    ]]
                ),
                use_container_width=True,
                height=220
            )

        else:
            st.info("No open EGX30 trades")

        st.divider()

        # ----------- HISTORY -----------
        st.markdown("### 📋 **Closed History**")

        if len(df_closed_egx30) > 0:

            st.dataframe(
                fix_pyarrow_df(
                    df_closed_egx30
                    .sort_values("Exit_Date", ascending=False)[[
                        'Entry_Date',
                        'Exit_Date',
                        'Entry_Price',
                        'Exit_Price',
                        'Trade_PnL_%',
                        'Days_Held',
                        'Exit_Reason'
                    ]]
                ),
                use_container_width=True,
                height=260
            )

        else:
            st.info("No closed EGX30 trades")

    # =========================
    # 📊 RIGHT SIDE (METRICS + NEWS)
    # =========================
    with right:

        # ----------- STRATEGY BLOCK -----------
        st.markdown("### 🎯 **Strategy Health**")

        if len(df_strategy_egx30) > 0:

            strat = df_strategy_egx30.iloc[0]

            st.metric("🏆 Best", strat['Best_Strategy'])
            st.metric("📊 Score", safe_display(strat['score']))
            st.metric("✅ Win", f"{safe_display(strat['win_rate'])}%")
            st.metric("🎯 Median", f"{safe_display(strat['median_pnl'])}%")
            st.metric("📈 Trades", safe_display(strat['total_trades']))

        else:
            st.warning("No strategy metrics")

        st.divider()

        # ----------- SUPPORT / RESISTANCE -----------
        st.markdown("### 🧭 **Support / Resistance**")

        latest = None

        if len(df_current_egx30) > 0:
            latest = df_current_egx30.loc[
                df_current_egx30['Entry_Date'].idxmax()
            ]

        if latest is not None:

            has_support = 'Exit_Support' in latest and pd.notna(latest['Exit_Support'])
            has_resistance = 'Exit_Resistance' in latest and pd.notna(latest['Exit_Resistance'])

            if has_support:
                st.metric("🟢 Support", safe_display(latest['Exit_Support']))

            if has_resistance:
                st.metric("🔴 Resistance", safe_display(latest['Exit_Resistance']))

            # If neither exists
            if not has_support and not has_resistance:
                st.info("No support / resistance levels found")

        else:
            st.info("No open EGX30 trades")

        st.divider()


        # ----------- MARKET NEWS -----------
        st.markdown("### 📰 **Market News**")

        news = fetch_latest_news("EGX30", max_items=5)

        if news:

            for n in news:

                st.markdown(f"**{n['title']}**")
                st.caption(f"{n['provider']}")
                st.markdown(
                    f"[Read more]({n['url']})",
                    unsafe_allow_html=True
                )
                st.divider()

        else:
            st.info("No recent EGX30 news")


# 🔥 SIDEBAR (EGX30 excluded from counts)
new_buys_other = df_current_other[df_current_internal['Entry_Date'] == df_current_internal['Entry_Date'].max()]
close_now_other = df_closed_other[df_closed_internal['Exit_Date'] == df_closed_internal['Exit_Date'].max()]
holds_other = df_current_other[df_current_internal['Entry_Date'] != df_current_internal['Entry_Date'].max()]

with st.sidebar:
    st.markdown("### 🎛️ **TRADING STATUS**")
    st.info(f"🆕 New: {len(new_buys_other)} | ❌ Closed: {len(close_now_other)} | ✅ Holds: {len(holds_other)}")
    refresh_df = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=4)
    refresh_date = pd.to_datetime(refresh_df['refresh_date'].iloc[0]).strftime('%Y-%m-%d')
    st.caption(f"Updated: {refresh_date}")
    #st.divider()
    st.markdown(
        f"### {sentiment_emoji} Market Sentiment: **{sentiment_text}**"
    )
    #st.markdown("### 📊 **EGX30 STATUS**")
    #st.metric("📊 Open", len(df_current_egx30))
    #st.metric("📋 Closed", len(df_closed_egx30))
