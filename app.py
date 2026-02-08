import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import os
import numpy as np

# --------------------------- 
# Page Config
# ---------------------------
st.set_page_config(page_title="EGX Trading Dashboard", layout="wide")

# --------------------------- 
# Load BOTH Sheets + Company Map + ALL STOCKS
# ---------------------------
@st.cache_data
def load_data():
    try:
        if not os.path.exists("Complete_Trades_Metrics.xlsx"):
            st.error("❌ Complete_Trades_Metrics.xlsx missing!")
            return {}, pd.DataFrame(), pd.DataFrame()
        
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
        return {}, [], []

data, all_symbols = load_data()
if not data or not all_symbols:
    st.stop()

df_current = data["current"]
df_closed = data["closed"]

# --------------------------- 
# Safe Display Function
# ---------------------------
def safe_display(value):
    if pd.isna(value) or value is None or value == "":
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.1f}"
    return str(value)

# --------------------------- 
# Sentiment Engine + NEWS (unchanged)
# ---------------------------
def calculate_sentiment(row):
    score = 0
    pnl = row.get("Trade_PnL_%")
    if pd.notna(pnl): score += 2 if pnl > 0 else -2
    rel_vol = row.get("Entry_Rel_Volume_20")
    if pd.notna(rel_vol) and rel_vol > 1.5: score += 1
    for key in ["Entry_Market_Structure", "Entry_Crosses_Resistance"]:
        if pd.notna(row.get(key)) and row[key]: score += 1
    if score >= 4: return "🟢 Strong Bullish"
    elif score >= 2: return "🟢 Bullish"
    elif score >= 0: return "🟡 Neutral"
    elif score >= -2: return "🔴 Bearish"
    return "🔴 Strong Bearish"

CAIRO_TZ = pytz.timezone("Africa/Cairo")
KEYWORD_EMOJI_RULES = [
    (["bankruptcy", "default", "collapse", "scandal"], "💥"),(["loss", "decline", "drop"], "🔻🐻"),
    (["rise", "up", "positive", "bull"], "✅📈🐂"),(["profit", "earnings"], "⬆💰"),
    (["dividend"], "💰"),(["acquire", "merger"], "🤝"),(["growth", "expansion"], "🚀")
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
            title, url, provider, ts = news.get("title", ""), news.get("storyPath", ""), news.get("provider", {}).get("name", ""), news.get("published")
            if ts:
                published_dt = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.UTC).astimezone(CAIRO_TZ)
                result.append({"title": title, "url": f"https://www.tradingview.com{url}", "provider": provider, "published": published_dt.strftime("%Y-%m-%d %H:%M"), "emoji": pick_emoji(title)})
        if len(result) >= max_items: break
    return result

# --------------------------- 
# Main Dashboard - PERFECT VERSION
# ---------------------------
tab1, tab2 = st.tabs(["📊 Stock Detail", "📈 Portfolio Overview"])

with tab1:
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
        
        # ✅ ALWAYS PRINT ALL - BEAUTIFUL TABLE FORMAT
        if num_current == 0:
            st.warning("⚠️ No Current Open Trades")
        else:
            st.success(f"🟢 {num_current} Open Trade{'s' if num_current > 1 else ''}")
            
            # ✅ PERFECT TABLE - NO JSON!
            display_cols = ['Entry_Date', 'Entry_Price', 'Current_Price', 'Exit_Price', 'Trade_PnL_%', 
                          'Days_Held', 'Entry_Volume', 'Status', 'Exit_Reason', 'Max_Gain_%', 'Max_Drawdown_%']
            available_cols = [col for col in display_cols if col in current_stock_df.columns]
            
            open_trades_table = current_stock_df[available_cols].copy()
            for col in open_trades_table.columns:
                if open_trades_table[col].dtype in ['float64', 'int64']:
                    open_trades_table[col] = open_trades_table[col].apply(safe_display)
            
            # Add % symbols
            for col in ['Trade_PnL_%', 'Max_Gain_%', 'Max_Drawdown_%']:
                if col in open_trades_table.columns:
                    open_trades_table[col] = open_trades_table[col].astype(str) + '%'
            
            open_trades_table = open_trades_table.sort_values('Entry_Date', ascending=False)
            st.dataframe(open_trades_table, use_container_width=True, height=250)

        # Chart + News + Closed History (ALWAYS ALL COLUMNS)
        st.subheader("📈 TradingView Chart")
        st.components.v1.iframe(f"https://s.tradingview.com/widgetembed/?symbol=EGX:{selected_symbol}&interval=D&theme=Light&style=9", height=500)
        
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
            # ✅ ALWAYS SHOW ALL COLUMNS
            st.dataframe(closed_stock_df, use_container_width=True, height=400)
        else:
            st.info("No closed trades.")

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

with tab2:
    st.subheader("📊 Portfolio Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Open", len(df_current))
    col2.metric("Total Closed", len(df_closed))
    col3.metric("Closed Win Rate", f"{len(df_closed[df_closed['Trade_PnL_%']>0])/len(df_closed)*100:.1f}%" if len(df_closed)>0 else "0%")
    col4.metric("Avg Closed PnL", f"{df_closed['Trade_PnL_%'].mean():.1f}%")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🟢 TOP 5 Gainers (Closed)")
        top_gainers = df_closed.nlargest(5, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held", "Entry_Date", "Exit_Reason"]]
        st.dataframe(top_gainers, use_container_width=True)
    
    with col2:
        st.markdown("### 🔴 TOP 5 Losers (Closed)")
        top_losers = df_closed.nsmallest(5, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held", "Entry_Date", "Exit_Reason"]]
        st.dataframe(top_losers, use_container_width=True)
