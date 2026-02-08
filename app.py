import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import os
import numpy as np

# --------------------------- 
# 1. COMPLETE LOAD DATA FUNCTION
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
        
        st.success(f"✅ Loaded {len(current_trades)} current + {len(closed_trades)} closed trades from {len(all_tickers)} stocks")
        return {"closed": closed_trades, "current": current_trades}, all_tickers
        
    except Exception as e:
        st.error(f"❌ Load failed: {e}")
        st.stop()
        return {}, [], []

# --------------------------- 
# 2. INIT + CONFIG
# ---------------------------
st.set_page_config(page_title="🚀 EGX Swing Trading Dashboard", layout="wide")
data, all_symbols = load_data()
if not data or not all_symbols:
    st.stop()

df_current = data["current"]
df_closed = data["closed"]

# --------------------------- 
# 3. HELPER FUNCTIONS
# ---------------------------
def safe_display(value):
    if pd.isna(value) or value is None or value == "":
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.1f}"
    return str(value)

CAIRO_TZ = pytz.timezone("Africa/Cairo")
KEYWORD_EMOJI_RULES = [
    (["bankruptcy", "default", "collapse"], "💥"),
    (["loss", "decline", "drop"], "🔻🐻"),
    (["rise", "up", "positive"], "✅📈🐂"),
    (["profit", "earnings"], "⬆💰"),
    (["dividend"], "💰"),
    (["acquire", "merger"], "🤝"),
    (["growth", "expansion"], "🚀")
]

def pick_emoji(headline: str) -> str:
    h = headline.lower()
    emojis = []
    for keywords, emoji in KEYWORD_EMOJI_RULES:
        if any(k in h for k in keywords): 
            emojis.append(emoji)
            break
    return "".join(emojis) if emojis else "📰"

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
                    "provider": provider, "published": published_dt.strftime("%Y-%m-%d %H:%M"), 
                    "emoji": pick_emoji(title)
                })
        if len(result) >= max_items: break
    return result

# --------------------------- 
# 4. PERFECT 4-TAB DASHBOARD
# ---------------------------
tab1, tab2, tab3, tab4 = st.tabs(["⚡ **TODAY'S ACTIONS**", "📊 **STOCK DETAIL**", "📈 **PORTFOLIO**", "📋 **HISTORY**"])

# 🔥 TAB 1: TODAY'S TRADING ACTIONS (SMART CLOSE DETECTION)
with tab1:
    st.markdown("### 🚨 **TODAY'S TRADING DECISIONS**")
    
    today = datetime.now().date()
    
    # 1. NEW BUY SIGNALS
    st.markdown("#### 🆕 **NEW BUY SIGNALS TODAY**")
    new_buys = df_current[
        pd.to_datetime(df_current['Entry_Date']).dt.date == today
    ].copy()
    
    if not new_buys.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("🆕 New Buys", len(new_buys))
        col2.metric("💰 Best PnL", f"{new_buys['Trade_PnL_%'].max():.1f}%")
        col3.metric("📊 Avg PnL", f"{new_buys['Trade_PnL_%'].mean():.1f}%")
        st.dataframe(new_buys[['Ticker', 'Entry_Date', 'Entry_Price', 'Trade_PnL_%', 'Entry_Volume', 'Status']], use_container_width=True)
        st.success("✅ **BUY ALL NEW SIGNALS**")
    else:
        st.info("🎉 No new buy signals today")
    
    st.markdown("---")
    
    # 2. CLOSE SIGNALS (Reads your sheet's logic!)
    st.markdown("#### ❌ **CLOSE POSITIONS TODAY**")
    close_signals = df_current[
        (df_current['Exit_Reason'] != 'OPEN') |           # Your strategy says CLOSE
        (df_current['Status'] != 'OPEN') |                # Status changed  
        (df_current['Trade_PnL_%'] < -8) |                # Stop loss hit
        (pd.to_datetime(df_current['Entry_Date']).dt.date + pd.Timedelta(days=25) <= datetime.now())  # Time stop
    ].copy()
    
    close_signals['Close_Reason'] = np.select([
        close_signals['Exit_Reason'] != 'OPEN',
        close_signals['Trade_PnL_%'] < -8,
        pd.to_datetime(close_signals['Entry_Date']).dt.date + pd.Timedelta(days=25) <= datetime.now()
    ], ['🎯 STRATEGY SIGNAL', '🛑 STOP LOSS', '⏰ TIME EXIT'], 'ℹ️ MONITOR')
    
    if not close_signals.empty:
        col1, col2 = st.columns(2)
        col1.metric("❌ Close Today", len(close_signals))
        col2.metric("📉 Worst PnL", f"{close_signals['Trade_PnL_%'].min():.1f}%")
        
        st.dataframe(close_signals[['Ticker', 'Trade_PnL_%', 'Days_Held', 'Close_Reason', 
                                  'Entry_Price', 'Exit_Reason']], use_container_width=True, height=300)
        
        col1, col2 = st.columns(2)
        col1.button("🚨 **CLOSE ALL**", type="primary", use_container_width=True)
        col2.button("📝 **DEFER**", use_container_width=True)
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
    st.markdown("#### 🎯 **EXECUTIVE SUMMARY**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🆕 Buy", len(new_buys))
    col2.metric("❌ Close", len(close_signals))
    col3.metric("✅ Hold", len(strong_holds))
    col4.metric("📊 Open", len(df_current))

# 🔥 TAB 2: STOCK DETAIL (Your original + News)
with tab2:
    selected_symbol = st.selectbox("🔍 Choose Stock:", all_symbols)
    current_stock_df = df_current[df_current["Ticker"] == selected_symbol]
    num_current = len(current_stock_df)
    
    left_col, right_col = st.columns([3, 1])
    
    with left_col:
        company_name = safe_display(
            pd.concat([df_current, df_closed]).query(f"Ticker == '{selected_symbol}'")['Company Name'].dropna().iloc[0] 
            if len(pd.concat([df_current, df_closed]).query(f"Ticker == '{selected_symbol}'")) > 0 else selected_symbol
        )
        
        st.markdown(f"""
            <h1 style='margin-bottom:0;'>📈 {selected_symbol}</h1>
            <h3 style='color:gray;margin-top:0;'>{company_name}</h3>
        """, unsafe_allow_html=True)
        
        if num_current > 0:
            st.success(f"🟢 {num_current} Open Trade{'s' if num_current > 1 else ''}")
            display_cols = ['Entry_Date', 'Entry_Price', 'Current_Price', 'Exit_Price', 'Trade_PnL_%', 'Days_Held']
            available_cols = [col for col in display_cols if col in current_stock_df.columns]
            
            open_trades_table = current_stock_df[available_cols].copy()
            for col in open_trades_table.columns:
                if open_trades_table[col].dtype in ['float64', 'int64']:
                    open_trades_table[col] = open_trades_table[col].apply(safe_display)
            open_trades_table['Trade_PnL_%'] = open_trades_table['Trade_PnL_%'].astype(str) + '%'
            
            st.dataframe(open_trades_table.sort_values('Entry_Date', ascending=False), use_container_width=True, height=200)
        else:
            st.warning("⚠️ No Current Open Trades")
        
        st.subheader("📈 TradingView Chart")
        st.components.v1.iframe(f"https://s.tradingview.com/widgetembed/?symbol=EGX:{selected_symbol}&interval=D&theme=Light&style=9", height=400)
        
        st.subheader("📰 Latest News")
        news_items = fetch_latest_news(selected_symbol)
        if news_items:
            for n in news_items:
                st.markdown(f"{n['emoji']} **{n['title']}** | {n['provider']} | {n['published']} | [Read]({n['url']})")
                st.divider()
        else:
            st.info("No news found.")
        
        st.subheader(f"📋 Closed Trades History ({len(df_closed[df_closed['Ticker']==selected_symbol])} trades)")
        closed_stock_df = df_closed[df_closed["Ticker"] == selected_symbol].sort_values("Entry_Date", ascending=False)
        if not closed_stock_df.empty:
            st.dataframe(closed_stock_df, use_container_width=True, height=400)

    with right_col:
        st.subheader("📋 Key Metrics")
        if num_current > 0:
            latest_trade = current_stock_df.iloc[0]
            metrics = {
                "Max Gain": f"{safe_display(latest_trade.get('Max_Gain_%'))}%",
                "Max DD": f"{safe_display(latest_trade.get('Max_Drawdown_%'))}%",
                "Entry Vol": safe_display(latest_trade.get('Entry_Volume')),
                "Rel Vol": safe_display(latest_trade.get('Entry_Rel_Volume_20'))
            }
            for name, value in metrics.items():
                st.markdown(f"**{name}:** {value}")

# 🔥 TAB 3: PORTFOLIO
with tab3:
    st.markdown("### 📈 **PORTFOLIO OVERVIEW**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Open", len(df_current))
    col2.metric("Closed", len(df_closed))
    col3.metric("Closed Win Rate", f"{len(df_closed[df_closed['Trade_PnL_%']>0])/len(df_closed)*100:.1f}%" if len(df_closed)>0 else "0%")
    col4.metric("Avg PnL", f"{df_closed['Trade_PnL_%'].mean():.1f}%")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🟢 **TOP CLOSED GAINERS**")
        top_gainers = df_closed.nlargest(10, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held"]]
        top_gainers['Trade_PnL_%'] = top_gainers['Trade_PnL_%'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(top_gainers, use_container_width=True)
    
    with col2:
        st.markdown("### 🔴 **TOP CLOSED LOSERS**")
        top_losers = df_closed.nsmallest(10, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held"]]
        top_losers['Trade_PnL_%'] = top_losers['Trade_PnL_%'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(top_losers, use_container_width=True)

# 🔥 TAB 4: FULL HISTORY  
with tab4:
    st.markdown("### 📋 **COMPLETE TRADE HISTORY**")
    full_history = pd.concat([df_current, df_closed])
    st.dataframe(full_history, use_container_width=True, height=600)

# --------------------------- 
# SIDEBAR CONTROLS
# ---------------------------
with st.sidebar:
    st.markdown("## 🎛️ **TRADING CONTROLS**")
    st.caption(f"**Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S EET')}")
    
    if st.button("📤 **EXPORT TODAY'S ACTIONS**"):
        actions_df = pd.concat([new_buys, close_signals, strong_holds])
        st.download_button("Download CSV", actions_df.to_csv(), "trading_actions.csv")
