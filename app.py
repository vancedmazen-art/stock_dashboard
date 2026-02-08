import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import os
import numpy as np

# --------------------------- 
# COMPLETE LOAD DATA (unchanged)
# ---------------------------
@st.cache_data
def load_data():
    try:
        if not os.path.exists("Complete_Trades_Metrics.xlsx"):
            st.error("❌ Complete_Trades_Metrics.xlsx missing!")
            st.stop()
            return {}, [], []
        
        closed_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=0)
        current_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=1)
        
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

# --------------------------- 
# INIT
# ---------------------------
st.set_page_config(page_title="🚀 EGX Swing Trading Dashboard", layout="wide")
data, all_symbols = load_data()
if not data or not all_symbols:
    st.stop()

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

# ✅ FIXED: News functions (shortened)
CAIRO_TZ = pytz.timezone("Africa/Cairo")

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
                published_dt = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.UTC).astimezone(CAIRO_TZ)
                result.append({
                    "title": title, "url": f"https://www.tradingview.com{url}",
                    "provider": provider, "published": published_dt.strftime("%Y-%m-%d %H:%M")
                })
        if len(result) >= max_items: break
    return result

# --------------------------- 
# 🔥 MAIN DASHBOARD - 4 TABS
# ---------------------------
tab1, tab2, tab3, tab4 = st.tabs(["⚡ **TODAY'S ACTIONS**", "📊 **STOCK DETAIL**", "📈 **PORTFOLIO**", "📋 **HISTORY**"])

# 🔥 TAB 1: TODAY'S TRADING ACTIONS (✅ FIXED DATES)
with tab1:
    st.markdown("### 🚨 **TODAY'S TRADING DECISIONS**")
    today = datetime.now().date()
    
    # 1. NEW BUYS TODAY
    st.markdown("#### 🆕 **NEW BUY SIGNALS**")
    new_buys = df_current[
        pd.to_datetime(df_current['Entry_Date'], errors='coerce').dt.date == today
    ].copy()
    
    if not new_buys.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("🆕 New Buys", len(new_buys))
        col2.metric("💰 Best PnL", f"{new_buys['Trade_PnL_%'].max():.1f}%")
        col3.metric("📊 Avg PnL", f"{new_buys['Trade_PnL_%'].mean():.1f}%")
        st.dataframe(new_buys[['Ticker', 'Entry_Date', 'Entry_Price', 'Trade_PnL_%', 'Entry_Volume']], 
                    use_container_width=True)
        st.success("✅ **BUY ALL NEW**")
    else:
        st.info("🎉 No new buy signals")
    
    st.markdown("---")
    
    # 2. ✅ FIXED: CLOSE SIGNALS (No timedelta error)
    st.markdown("#### ❌ **CLOSE POSITIONS**")
    # **SMART LOGIC** - Reads your sheet's close signals
    close_signals = df_current[
        (df_current['Exit_Reason'] != 'OPEN') |                    # 🎯 YOUR STRATEGY SIGNAL
        (df_current['Status'] != 'OPEN') |                         # Status changed
        (df_current['Trade_PnL_%'] < -8) |                         # 🛑 Stop loss  
        (df_current['Days_Held'] > 25)                             # ⏰ Time stop (FIXED!)
    ].copy()
    
    close_signals['Close_Reason'] = np.select([
        close_signals['Exit_Reason'] != 'OPEN',
        close_signals['Trade_PnL_%'] < -8,
        close_signals['Days_Held'] > 25
    ], ['🎯 STRATEGY SIGNAL', '🛑 STOP LOSS', '⏰ TIME EXIT'], 'ℹ️ MONITOR')
    
    if not close_signals.empty:
        col1, col2 = st.columns(2)
        col1.metric("❌ Close Now", len(close_signals))
        col2.metric("📉 Worst PnL", f"{close_signals['Trade_PnL_%'].min():.1f}%")
        
        st.dataframe(close_signals[['Ticker', 'Trade_PnL_%', 'Days_Held', 'Close_Reason', 
                                  'Entry_Price', 'Exit_Reason']], 
                    use_container_width=True, height=300)
        
        col1, col2 = st.columns(2)
        col1.button("🚨 **CLOSE ALL**", type="primary", use_container_width=True)
        col2.button("📝 **REVIEW**", use_container_width=True)
    else:
        st.success("✅ No close signals today")
    
    st.markdown("---")
    
    # 3. STRONG HOLDS
    st.markdown("#### ✅ **STRONG HOLDS**")
    strong_holds = df_current[
        (df_current['Trade_PnL_%'] > 3) & 
        (df_current['Max_Drawdown_%'] < 6) &
        (df_current['Days_Held'] < 20) &
        (df_current['Exit_Reason'] == 'OPEN')
    ].copy()
    
    if not strong_holds.empty:
        col1, col2 = st.columns(2)
        col1.metric("✅ Holds", len(strong_holds))
        col2.metric("🚀 Best", f"{strong_holds['Trade_PnL_%'].max():.1f}%")
        st.dataframe(strong_holds[['Ticker', 'Trade_PnL_%', 'Days_Held']], use_container_width=True)
    
    # 4. SUMMARY
    st.markdown("#### 🎯 **SUMMARY**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🆕 Buy", len(new_buys))
    col2.metric("❌ Close", len(close_signals))
    col3.metric("✅ Hold", len(strong_holds))
    col4.metric("📊 Open", len(df_current))

# 🔥 TAB 2: STOCK DETAIL (Your original)
with tab2:
    selected_symbol = st.selectbox("🔍 Choose Stock:", all_symbols)
    current_stock_df = df_current[df_current["Ticker"] == selected_symbol]
    
    left_col, right_col = st.columns([3, 1])
    
    with left_col:
        st.markdown(f"### 📈 {selected_symbol}")
        if len(current_stock_df) > 0:
            st.dataframe(current_stock_df[['Entry_Date', 'Trade_PnL_%', 'Days_Held', 'Entry_Price']].head(), 
                        use_container_width=True)
        st.components.v1.iframe(f"https://s.tradingview.com/widgetembed/?symbol=EGX:{selected_symbol}&interval=D&theme=Light&style=9", height=400)
        
        st.markdown("### 📰 **NEWS**")
        news_items = fetch_latest_news(selected_symbol)
        if news_items:
            for n in news_items:
                st.markdown(f"**{n['title']}**")
                st.caption(f"{n['provider']} | {n['published']}")
                st.divider()

    with right_col:
        if len(current_stock_df) > 0:
            latest = current_stock_df.iloc[0]
            st.metric("PnL", f"{safe_display(latest['Trade_PnL_%'])}%")
            st.metric("Days", safe_display(latest['Days_Held']))
            st.metric("Max Gain", f"{safe_display(latest.get('Max_Gain_%', 0))}%")

# 🔥 TAB 3: PORTFOLIO
with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🟢 **TOP GAINERS**")
        top_gainers = df_closed.nlargest(10, "Trade_PnL_%")[["Ticker", "Trade_PnL_%"]]
        top_gainers['Trade_PnL_%'] = top_gainers['Trade_PnL_%'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(top_gainers, use_container_width=True)
    with col2:
        st.markdown("### 🔴 **TOP LOSERS**")
        top_losers = df_closed.nsmallest(10, "Trade_PnL_%")[["Ticker", "Trade_PnL_%"]]
        top_losers['Trade_PnL_%'] = top_losers['Trade_PnL_%'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(top_losers, use_container_width=True)

# 🔥 TAB 4: HISTORY
with tab4:
    st.markdown("### 📋 **ALL TRADES**")
    st.dataframe(pd.concat([df_current, df_closed]), use_container_width=True, height=600)

# SIDEBAR
with st.sidebar:
    st.markdown("### 🎛️ **CONTROLS**")
    st.caption(f"**{datetime.now().strftime('%Y-%m-%d %H:%M EET')}**")
