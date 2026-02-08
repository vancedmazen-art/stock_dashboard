import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import os
import numpy as np

# --------------------------- 
# LOAD DATA (your filtered version - perfect!)
# ---------------------------
@st.cache_data
def load_data():
    try:
        if not os.path.exists("Complete_Trades_Metrics.xlsx"):
            st.error("❌ Complete_Trades_Metrics.xlsx missing!")
            st.stop()
            return {}, [], []
        
        closed_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=0)
        closed_trades = closed_trades[closed_trades['Entry_Crosses_Resistance'] == True]
        current_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=1)
        current_trades = current_trades[current_trades['Entry_Crosses_Resistance'] == True]
        
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
        
        st.success(f"✅ Loaded {len(current_trades)} current + {len(closed_trades)} closed trades")
        return {"closed": closed_trades, "current": current_trades}, all_tickers
        
    except Exception as e:
        st.error(f"❌ Load failed: {e}")
        st.stop()
        return {}, [], []

st.set_page_config(page_title="🚀 EGX Trading Dashboard", layout="wide")
data, all_symbols = load_data()
df_current = data["current"]
df_closed = data["closed"]

# --------------------------- 
# HELPER FUNCTIONS
# ---------------------------
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
            ts = news.get("published")
            if ts:
                result.append({"title": title, "url": f"https://www.tradingview.com{url}", "provider": provider})
        if len(result) >= max_items: break
    return result

# --------------------------- 
# 🔥 4-TAB DASHBOARD
# ---------------------------
tab1, tab2, tab3, tab4 = st.tabs(["⚡ **TODAY'S ACTIONS**", "📊 **STOCK DETAIL**", "📈 **PORTFOLIO**", "📋 **FULL HISTORY**"])

# TAB 1: TODAY'S ACTIONS (unchanged)
with tab1:
    st.markdown("### 🚨 **TODAY'S TRADING DECISIONS**")
    
    df_current['Entry_Date'] = pd.to_datetime(df_current['Entry_Date'], errors='coerce').dt.date
    max_entry_date = df_current['Entry_Date'].max()
    new_buys = df_current[df_current['Entry_Date'].dt.date == max_entry_date].copy()
    
    st.markdown("#### 🆕 **Fresh BUYS**")
    col1, col2, col3 = st.columns(3)
    col1.metric("🆕 New Buys", len(new_buys))
    col2.metric("💰 Best PnL", f"{new_buys['Trade_PnL_%'].max():.1f}%" if len(new_buys)>0 else "-")
    col3.metric("📊 Avg PnL", f"{new_buys['Trade_PnL_%'].mean():.1f}%" if len(new_buys)>0 else "-")
    st.dataframe(new_buys[['Ticker', 'Entry_Date', 'Entry_Price', 'Trade_PnL_%', 'Entry_Volume', 'Status']], use_container_width=True, height=200)
    
    df_closed['Exit_Date'] = pd.to_datetime(df_closed['Exit_Date'], errors='coerce').dt.date
    max_exit_date = df_closed['Exit_Date'].max()
    close_now = df_closed[df_closed['Exit_Date'].dt.date == max_exit_date].copy()
    
    st.markdown("#### ❌ **CLOSE NOW**")
    col1, col2, col3 = st.columns(3)
    col1.metric("❌ Closed Today", len(close_now))
    col2.metric("💰 Best PnL", f"{close_now['Trade_PnL_%'].max():.1f}%" if len(close_now)>0 else "-")
    col3.metric("📊 Avg PnL", f"{close_now['Trade_PnL_%'].mean():.1f}%" if len(close_now)>0 else "-")
    st.dataframe(close_now[['Ticker', 'Exit_Date', 'Exit_Price', 'Trade_PnL_%', 'Days_Held', 'Exit_Reason']], use_container_width=True, height=200)
    
    holds = df_current[df_current['Entry_Date'].dt.date != max_entry_date].copy()
    st.markdown("#### ✅ **HOLDS**")
    col1, col2, col3 = st.columns(3)
    col1.metric("✅ Holds", len(holds))
    col2.metric("💰 Best PnL", f"{holds['Trade_PnL_%'].max():.1f}%" if len(holds)>0 else "-")
    col3.metric("📊 Avg PnL", f"{holds['Trade_PnL_%'].mean():.1f}%" if len(holds)>0 else "-")
    st.dataframe(holds[['Ticker', 'Entry_Date', 'Trade_PnL_%', 'Days_Held', 'Status']], use_container_width=True, height=300)

# 🔥 TAB 2: STOCK DETAIL + HISTORY FILTERED BY TICKER (NEW!)
with tab2:
    selected_symbol = st.selectbox("🔍 Choose Stock:", all_symbols)
    
    # Current trades for selected stock
    current_stock_df = df_current[df_current["Ticker"] == selected_symbol]
    
    # 🔥 HISTORY: Closed trades FILTERED by selected stock
    stock_history = df_closed[df_closed["Ticker"] == selected_symbol].sort_values("Entry_Date", ascending=False)
    
    left_col, right_col = st.columns([3, 1])
    
    with left_col:
        st.markdown(f"### 📈 **{selected_symbol}**")
        
        # Current open trades
        if len(current_stock_df) > 0:
            st.markdown("#### 🟢 **CURRENT TRADES**")
            st.dataframe(current_stock_df[['Entry_Date', 'Entry_Price', 'Trade_PnL_%', 'Days_Held', 'Status']], 
                        use_container_width=True, height=200)
        else:
            st.info("⚠️ No current open trades")
        
        # TradingView Chart
        st.markdown("#### 📊 **CHART**")
        st.components.v1.iframe(f"https://s.tradingview.com/widgetembed/?symbol=EGX:{selected_symbol}&interval=D&theme=Light&style=9", height=400)
        
        # News
        st.markdown("#### 📰 **NEWS**")
        news_items = fetch_latest_news(selected_symbol)
        if news_items:
            for n in news_items:
                st.markdown(f"**{n['title']}**")
                st.caption(f"{n['provider']}")
                st.divider()
        else:
            st.info("No news available")
        
        # 🔥 HISTORY FILTERED BY THIS STOCK (under chart!)
        st.markdown(f"#### 📋 **HISTORY** ({len(stock_history)} closed trades)")
        if len(stock_history) > 0:
            st.dataframe(stock_history, use_container_width=True, height=300)
        else:
            st.info("No closed trades for this stock")
    
    with right_col:
        st.markdown("#### 📊 **KEY METRICS**")
        if len(current_stock_df) > 0:
            latest = current_stock_df.iloc[0]
            st.metric("PnL", f"{safe_display(latest['Trade_PnL_%'])}%")
            st.metric("Days Held", safe_display(latest['Days_Held']))
            st.metric("Entry Vol", safe_display(latest.get('Entry_Volume', '-')))
            st.metric("Rel Vol", safe_display(latest.get('Entry_Rel_Volume_20', '-')))

# TAB 3: PORTFOLIO (unchanged)
with tab3:
    st.markdown("### 📈 **PORTFOLIO OVERVIEW**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Open", len(df_current))
    col2.metric("Closed", len(df_closed))
    col3.metric("Win Rate", f"{len(df_closed[df_closed['Trade_PnL_%']>0])/len(df_closed)*100:.1f}%" if len(df_closed)>0 else "0%")
    col4.metric("Avg PnL", f"{df_closed['Trade_PnL_%'].mean():.1f}%")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🟢 **TOP GAINERS**")
        top_gainers = df_closed.nlargest(15, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held"]]
        top_gainers['Trade_PnL_%'] = top_gainers['Trade_PnL_%'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(top_gainers, use_container_width=True)
    with col2:
        st.markdown("### 🔴 **TOP LOSERS**")
        top_losers = df_closed.nsmallest(15, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held"]]
        top_losers['Trade_PnL_%'] = top_losers['Trade_PnL_%'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(top_losers, use_container_width=True)

# TAB 4: FULL HISTORY (KEEP UNFILTERED)
with tab4:
    st.markdown("### 📋 **COMPLETE HISTORY** (All stocks)")
    full_history = pd.concat([df_current, df_closed]).sort_values("Entry_Date", ascending=False)
    st.dataframe(full_history, use_container_width=True, height=600)

# SIDEBAR
with st.sidebar:
    st.markdown("### 🎛️ **TRADING STATUS**")
    st.info(f"🆕 New: {len(new_buys)} | ❌ Closed: {len(close_now)} | ✅ Holds: {len(holds)}")
    st.caption(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M EET')}")
