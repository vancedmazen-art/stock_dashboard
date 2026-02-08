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
        
        # Load SHEET 0 (closed trades history)
        closed_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=0)
        
        # Load SHEET 1 (current/open trades)
        current_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=1)
        
        # Load company map
        if os.path.exists("egx_company_map.csv"):
            company_map = pd.read_csv("egx_company_map.csv")
            if "Symbol" in company_map.columns:
                company_map["Ticker"] = company_map["Symbol"].str.replace("EGX:", "", regex=False)
            closed_trades = closed_trades.merge(company_map, on="Ticker", how="left")
            current_trades = current_trades.merge(company_map, on="Ticker", how="left")
        
        # ✅ ALL STOCKS in dropdown (union of both sheets + company map)
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
# Sentiment Engine
# ---------------------------
def calculate_sentiment(row):
    score = 0
    pnl = row.get("Trade_PnL_%")
    if pd.notna(pnl):
        score += 2 if pnl > 0 else -2
    
    rel_vol = row.get("Entry_Rel_Volume_20")
    if pd.notna(rel_vol) and rel_vol > 1.5:
        score += 1
        
    for key in ["Entry_Market_Structure", "Entry_Crosses_Resistance"]:
        if pd.notna(row.get(key)) and row[key]:
            score += 1

    if score >= 4: return "🟢 Strong Bullish"
    elif score >= 2: return "🟢 Bullish"
    elif score >= 0: return "🟡 Neutral"
    elif score >= -2: return "🔴 Bearish"
    return "🔴 Strong Bearish"

# --------------------------- 
# NEWS SECTION (unchanged)
# ---------------------------
CAIRO_TZ = pytz.timezone("Africa/Cairo")
KEYWORD_EMOJI_RULES = [
    (["bankruptcy", "default", "collapse", "scandal"], "💥"),
    (["loss", "decline", "drop", "fall", "deficit", "down", "negative", "bear", "lower", "decrease"], "🔻🐻"),
    (["rise", "up", "positive", "bull", "higher", "increase"], "✅📈🐂"),
    (["profit", "strong earnings", "strong results", "beat estimates", "surge"], "⬆💰💰💰"),
    (["dividend", "payout", "distribution"], "💰"),
    (["loan", "bond", "treasury"], "💳"),
    (["upgrade"], "⬆️"),
    (["downgrade"], "⬇️"),
    (["acquire", "acquisition", "merger", "takeover", "m&a"], "🤝"),
    (["partnership", "agreement", "deal", "collaboration", "capital"], "🤝"),
    (["expansion", "growth", "project", "invest", "develop", "establish"], "🚀"),
    (["layoffs", "cut", "reduce", "reduction"], "⚠️"),
    (["launch", "introduces", "introduced"], "🆕"),
    (["approval", "permit", "licence", "license", "regulation"], "📜"),
    (["ceo", "cfo", "board", "appoint", "appoints", "management"], "👔"),
    (["forecast", "guidance"], "📈"),
]

def pick_emoji(headline: str) -> str:
    h = headline.lower()
    emojis = []
    for keywords, emoji in KEYWORD_EMOJI_RULES:
        if any(k in h for k in keywords):
            if emoji not in emojis:
                emojis.append(emoji)
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
            title, url, provider, ts = news.get("title", ""), news.get("storyPath", ""), news.get("provider", {}).get("name", ""), news.get("published")
            if not ts: continue
            published_dt = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.UTC).astimezone(CAIRO_TZ)
            result.append({
                "title": title, "url": f"https://www.tradingview.com{url}",
                "provider": provider, "published": published_dt.strftime("%Y-%m-%d %H:%M"), "emoji": pick_emoji(title)
            })
        if len(result) >= max_items: break
    return result

# --------------------------- 
# Main Dashboard - ALL REQUIREMENTS ✅
# ---------------------------
tab1, tab2 = st.tabs(["📊 Stock Detail", "📈 Portfolio Overview"])

with tab1:
    # ✅ ALL STOCKS in dropdown
    selected_symbol = st.selectbox("🔍 Choose Stock:", all_symbols)
    
    # ✅ Current trades (0, 1, or 2+)
    current_stock_df = df_current[df_current["Ticker"] == selected_symbol]
    num_current = len(current_stock_df)
    
    left_col, right_col = st.columns([3, 1])
    
    with left_col:
        # Company name from ANY data source
        company_name = safe_display(
            pd.concat([df_current, df_closed]).query(f"Ticker == '{selected_symbol}'")['Company Name'].dropna().iloc[0] 
            if len(pd.concat([df_current, df_closed]).query(f"Ticker == '{selected_symbol}'")) > 0 
            else selected_symbol
        )
        
        st.markdown(f"""
            <h1 style='margin-bottom:0;'>📈 {selected_symbol}</h1>
            <h3 style='color:gray;margin-top:0;'>{company_name}</h3>
        """, unsafe_allow_html=True)
        
        # ✅ Handle 0, 1, or multiple current trades
        if num_current == 0:
            st.warning("⚠️ No Current Open Trades")
        elif num_current == 1:
            latest_current = current_stock_df.iloc[0]
            sentiment = calculate_sentiment(latest_current)
            st.success(f"🟢 1 Open Trade | {sentiment}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("PnL", f"{safe_display(latest_current.get('Trade_PnL_%'))}%")
            col2.metric("Days", safe_display(latest_current.get("Days_Held")))
            col3.metric("Entry", safe_display(latest_current.get("Entry_Price")))
            col4.metric("Exit", safe_display(latest_current.get("Exit_Price")))
            
            st.markdown(f"**Status:** {safe_display(latest_current.get('Status'))}")
            st.markdown(f"**Entry Vol:** {safe_display(latest_current.get('Entry_Volume'))}")
            st.markdown(f"**Crosses R:** {safe_display(latest_current.get('Entry_Crosses_Resistance'))}")
            
        else:  # 2+ trades
            st.error(f"🔴 {num_current} Open Trades!")
            for idx, trade in current_stock_df.iterrows():
                with st.expander(f"Trade {idx+1}: PnL {safe_display(trade.get('Trade_PnL_%'))}%"):
                    st.json({k: safe_display(v) for k, v in trade.items() if k != 'Ticker'})

        # Chart + News + Closed History
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

        # ✅ ALL COLUMNS for closed trades
        st.subheader(f"📋 Closed Trades History ({len(df_closed[df_closed['Ticker']==selected_symbol])} trades)")
        closed_stock_df = df_closed[df_closed["Ticker"] == selected_symbol].sort_values("Entry_Date", ascending=False)
        
        if not closed_stock_df.empty:
            # Show ALL columns
            st.dataframe(closed_stock_df, use_container_width=True, height=400)
        else:
            st.info("No closed trades.")

    with right_col:
        st.subheader("📋 Key Metrics")
        if num_current > 0:
            latest_current = current_stock_df.iloc[0]
            for key, value in {
                "Max Gain": latest_current.get("Max_Gain_%"),
                "Max DD": latest_current.get("Max_Drawdown_%"),
                "Entry Vol": latest_current.get("Entry_Volume"),
                "Rel Vol": latest_current.get("Entry_Rel_Volume_20")
            }.items():
                st.markdown(f"**{key}:** {safe_display(value)}")

with tab2:
    # ✅ TOP GAINERS & LOSERS from CLOSED trades (Sheet 0)
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
