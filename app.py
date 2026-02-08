import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import os
import numpy as np

# --------------------------- 
# LOAD DATA (unchanged)
# ---------------------------
@st.cache_data
def load_data():
    try:
        if not os.path.exists("Complete_Trades_Metrics.xlsx"):
            st.error("❌ Complete_Trades_Metrics.xlsx missing!")
            st.stop()
            return {}, [], []
        
        closed_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=0)
        closed_trades = closed_trades[closed_trades['Entry_Crosses_Resistance'] == 'TRUE']
        current_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=1)
        current_trades = current_trades[current_trades['Entry_Crosses_Resistance'] == 'TRUE']
        
        
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
                pytz.timezone("Africa/Cairo")
                result.append({"title": title, "url": f"https://www.tradingview.com{url}", "provider": provider})
        if len(result) >= max_items: break
    return result

# --------------------------- 
# 🔥 TAB 1: EXACT LOGIC YOU REQUESTED
# ---------------------------
tab1, tab2, tab3, tab4 = st.tabs(["⚡ **TODAY'S ACTIONS**", "📊 **STOCK DETAIL**", "📈 **PORTFOLIO**", "📋 **HISTORY**"])

with tab1:
    st.markdown("### 🚨 **TODAY'S TRADING DECISIONS**")
    
    # ✅ NEW BUYS: Open trades with MAX Entry_Date (today's signals)
    st.markdown("#### 🆕 **NEW BUYS** (Max Entry_Date in Open Trades)")
    df_current['Entry_Date'] = pd.to_datetime(df_current['Entry_Date'], errors='coerce')
    max_entry_date = df_current['Entry_Date'].max().date()
    new_buys = df_current[df_current['Entry_Date'].dt.date == max_entry_date].copy()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🆕 New Buys", len(new_buys))
    col2.metric("💰 Best PnL", f"{new_buys['Trade_PnL_%'].max():.1f}%" if len(new_buys)>0 else "-")
    col3.metric("📊 Avg PnL", f"{new_buys['Trade_PnL_%'].mean():.1f}%" if len(new_buys)>0 else "-")
    
    st.dataframe(new_buys[['Ticker', 'Entry_Date', 'Entry_Price', 'Trade_PnL_%', 'Entry_Volume', 'Status']], 
                use_container_width=True, height=200)
    
    st.markdown("---")
    
    # ✅ CLOSE NOW: Closed trades with MAX Exit_Date (today's closes)
    st.markdown("#### ❌ **CLOSE NOW** (Max Exit_Date in Closed Trades)")
    df_closed['Exit_Date'] = pd.to_datetime(df_closed['Exit_Date'], errors='coerce')
    max_exit_date = df_closed['Exit_Date'].max().date()
    close_now = df_closed[df_closed['Exit_Date'].dt.date == max_exit_date].copy()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("❌ Closed Today", len(close_now))
    col2.metric("💰 Best PnL", f"{close_now['Trade_PnL_%'].max():.1f}%" if len(close_now)>0 else "-")
    col3.metric("📊 Avg PnL", f"{close_now['Trade_PnL_%'].mean():.1f}%" if len(close_now)>0 else "-")
    
    st.dataframe(close_now[['Ticker', 'Exit_Date', 'Exit_Price', 'Trade_PnL_%', 'Days_Held', 'Exit_Reason']], 
                use_container_width=True, height=200)
    
    st.markdown("---")
    
    # ✅ HOLDS: ALL OTHER open trades (not new buys)
    st.markdown("#### ✅ **HOLDS** (Open trades excluding new buys)")
    holds = df_current[df_current['Entry_Date'].dt.date != max_entry_date].copy()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("✅ Holds", len(holds))
    col2.metric("💰 Best PnL", f"{holds['Trade_PnL_%'].max():.1f}%" if len(holds)>0 else "-")
    col3.metric("📊 Avg PnL", f"{holds['Trade_PnL_%'].mean():.1f}%" if len(holds)>0 else "-")
    
    st.dataframe(holds[['Ticker', 'Entry_Date', 'Trade_PnL_%', 'Days_Held', 'Status']], 
                use_container_width=True, height=300)
    
    # 🎯 SUMMARY
    st.markdown("#### 🎯 **EXECUTIVE SUMMARY**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🆕 NEW BUYS", len(new_buys), delta=f"+{len(new_buys)}")
    col2.metric("❌ CLOSED", len(close_now), delta=f"-{len(close_now)}")
    col3.metric("✅ HOLDS", len(holds))
    col4.metric("📊 TOTAL OPEN", len(df_current))

# 🔥 TAB 2: STOCK DETAIL
with tab2:
    selected_symbol = st.selectbox("🔍 Choose Stock:", all_symbols)
    current_stock_df = df_current[df_current["Ticker"] == selected_symbol]
    
    left_col, right_col = st.columns([3, 1])
    with left_col:
        st.markdown(f"### 📈 {selected_symbol}")
        if len(current_stock_df) > 0:
            st.dataframe(current_stock_df[['Entry_Date', 'Trade_PnL_%', 'Days_Held']], use_container_width=True)
        st.components.v1.iframe(f"https://s.tradingview.com/widgetembed/?symbol=EGX:{selected_symbol}&interval=D&theme=Light&style=9", height=400)
        st.markdown("### 📰 **NEWS**")
        news_items = fetch_latest_news(selected_symbol)
        if news_items:
            for n in news_items:
                st.markdown(f"**{n['title']}** - {n['provider']}")
    
    with right_col:
        if len(current_stock_df) > 0:
            latest = current_stock_df.iloc[0]
            st.metric("PnL", f"{safe_display(latest['Trade_PnL_%'])}%")
            st.metric("Days", safe_display(latest['Days_Held']))

# 🔥 TAB 3: PORTFOLIO  
with tab3:
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

# 🔥 TAB 4: FULL HISTORY
with tab4:
    st.markdown("### 📋 **ALL TRADES**")
    full_history = pd.concat([df_current, df_closed])
    st.dataframe(full_history, use_container_width=True, height=600)

# SIDEBAR
with st.sidebar:
    st.markdown("### 🎛️ **STATUS**")
    st.info(f"🆕 New: {len(new_buys)} | ❌ Closed: {len(close_now)} | ✅ Holds: {len(holds)}")
    st.caption(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M EET')}")
