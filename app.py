import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import os
import numpy as np

# --------------------------- 
# COMPLETE load_data FUNCTION (THIS WAS MISSING!)
# ---------------------------
@st.cache_data
def load_data():
    try:
        if not os.path.exists("Complete_Trades_Metrics.xlsx"):
            st.error("❌ Complete_Trades_Metrics.xlsx missing!")
            st.stop()
            return {}, [], []
        
        # Load SHEET 0 (closed trades)
        closed_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=0)
        # Load SHEET 1 (current trades)  
        current_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=1)
        
        # Company map merge
        if os.path.exists("egx_company_map.csv"):
            company_map = pd.read_csv("egx_company_map.csv")
            if "Symbol" in company_map.columns:
                company_map["Ticker"] = company_map["Symbol"].str.replace("EGX:", "", regex=False)
                closed_trades = closed_trades.merge(company_map, on="Ticker", how="left")
                current_trades = current_trades.merge(company_map, on="Ticker", how="left")
        
        # ALL unique tickers for dropdown
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
# LOAD DATA (NOW WORKS!)
# ---------------------------
st.set_page_config(page_title="🚀 EGX Trading Dashboard", layout="wide")
data, all_symbols = load_data()
if not data or not all_symbols:
    st.stop()

df_current = data["current"]
df_closed = data["closed"]

# --------------------------- 
# ALL YOUR FUNCTIONS (Safe Display, News, etc.)
# ---------------------------
def safe_display(value):
    if pd.isna(value) or value is None or value == "":
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.1f}"
    return str(value)

# News functions (your complete news code here)
CAIRO_TZ = pytz.timezone("Africa/Cairo")
KEYWORD_EMOJI_RULES = [
    (["bankruptcy", "default", "collapse", "scandal"], "💥"),
    (["loss", "decline", "drop", "fall", "deficit"], "🔻🐻"),
    (["rise", "up", "positive", "bull", "higher"], "✅📈🐂"),
    (["profit", "strong earnings", "beat estimates"], "⬆💰💰💰"),
    (["dividend", "payout"], "💰"),
    (["upgrade"], "⬆️"),(["downgrade"], "⬇️"),
    (["acquire", "merger"], "🤝"),(["growth", "expansion"], "🚀")
]

def pick_emoji(headline: str) -> str:
    h = headline.lower()
    emojis = []
    for keywords, emoji in KEYWORD_EMOJI_RULES:
        if any(k in h for k in keywords): emojis.append(emoji)
    return "".join(emojis) if emojis else "📰"

def fetch_latest_news(symbol: str, max_items=3):
    try:
        API_URL = "https://news-mediator.tradingview.com/news-flow/v2/news?filter=lang%3Aen&filter=market%3Astock&filter=market_country%3AEG&client=screener"
        r = requests.get(API_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
    except: return []
    
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
# PERFECT 4-TAB DASHBOARD (Trading + News + Everything)
# ---------------------------
tab1, tab2, tab3, tab4 = st.tabs(["⚡ **TODAY'S ACTIONS**", "📊 **STOCK DETAIL**", "📈 **PORTFOLIO**", "📋 **HISTORY**"])

with tab1:
    st.markdown("### 🚨 **TODAY'S TRADING DECISIONS**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 Open", len(df_current))
    col2.metric("📋 Closed", len(df_closed))
    col3.metric("🟢 Win Rate", f"{len(df_closed[df_closed['Trade_PnL_%']>0])/len(df_closed)*100:.0f}%")
    col4.metric("💰 Avg PnL", f"{df_closed['Trade_PnL_%'].mean():.1f}%")

with tab2:
    selected_symbol = st.selectbox("🔍 Choose Stock:", all_symbols)
    current_stock_df = df_current[df_current["Ticker"] == selected_symbol]
    
    left_col, right_col = st.columns([3, 1])
    with left_col:
        st.markdown(f"### 📈 {selected_symbol}")
        if len(current_stock_df) > 0:
            st.dataframe(current_stock_df[['Entry_Date', 'Trade_PnL_%', 'Days_Held', 'Entry_Price']].head(), use_container_width=True)
        st.components.v1.iframe(f"https://s.tradingview.com/widgetembed/?symbol=EGX:{selected_symbol}&interval=D&theme=Light&style=9", height=400)
        
        st.markdown("### 📰 **LATEST NEWS**")
        news_items = fetch_latest_news(selected_symbol)
        if news_items:
            for n in news_items:
                st.markdown(f"{n['emoji']} **{n['title']}**")
                st.caption(f"{n['provider']} | {n['published']}")
                st.divider()

with tab3:
    st.markdown("### 📈 **PORTFOLIO OVERVIEW**")
    col1, col2 = st.columns(2)
    with col1: 
        st.markdown("**🟢 TOP CLOSED GAINERS**")
        top_gainers = df_closed.nlargest(10, "Trade_PnL_%")[["Ticker", "Trade_PnL_%"]]
        top_gainers['Trade_PnL_%'] = top_gainers['Trade_PnL_%'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(top_gainers, use_container_width=True)
    with col2:
        st.markdown("**🔴 TOP CLOSED LOSERS**")
        top_losers = df_closed.nsmallest(10, "Trade_PnL_%")[["Ticker", "Trade_PnL_%"]]
        top_losers['Trade_PnL_%'] = top_losers['Trade_PnL_%'].apply(lambda x: f"{x:.1f}%")
        st.dataframe(top_losers, use_container_width=True)

with tab4:
    st.markdown("### 📋 **COMPLETE TRADE HISTORY**")
    st.dataframe(pd.concat([df_current, df_closed]), use_container_width=True)
