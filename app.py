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
# Load Data + Company Map
# ---------------------------
@st.cache_data
def load_data():
    try:
        if not os.path.exists("Complete_Trades_Metrics.xlsx"):
            st.error("❌ Complete_Trades_Metrics.xlsx missing!")
            return pd.DataFrame()
        
        trades_df = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=1)
        
        if os.path.exists("egx_company_map.csv"):
            company_map = pd.read_csv("egx_company_map.csv")
            if "Symbol" in company_map.columns:
                company_map["Ticker"] = company_map["Symbol"].str.replace("EGX:", "", regex=False)
            df = trades_df.merge(company_map, on="Ticker", how="left")
        else:
            df = trades_df.copy()
        
        if "Ticker" not in df.columns:
            st.error(f"❌ 'Ticker' column missing!")
            return pd.DataFrame()
            
        st.success(f"✅ Loaded {len(df)} trades")
        return df
        
    except Exception as e:
        st.error(f"❌ Load failed: {e}")
        return pd.DataFrame()

df = load_data()
if df.empty:
    st.stop()

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
# NEWS SECTION (Your Original Code Restored!)
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
        API_URL = (
            "https://news-mediator.tradingview.com/news-flow/v2/news?"
            "filter=lang%3Aen&filter=market%3Astock&filter=market_country%3AEG&client=screener"
        )
        r = requests.get(API_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        st.warning(f"Failed to fetch news: {e}")
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
            if not ts: continue
                
            published_dt = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.UTC).astimezone(CAIRO_TZ)
            published_str = published_dt.strftime("%Y-%m-%d %H:%M")
            
            emoji = pick_emoji(title)
            result.append({
                "title": title, "url": f"https://www.tradingview.com{url}",
                "provider": provider, "published": published_str, "emoji": emoji
            })
        if len(result) >= max_items:
            break
    return result

# --------------------------- 
# Main Dashboard with NEWS!
# ---------------------------
tab1, tab2 = st.tabs(["📊 Stock Detail", "📈 Portfolio Overview"])

with tab1:
    symbols = sorted(df["Ticker"].unique())
    selected_symbol = st.selectbox("🔍 Choose Stock:", symbols)
    
    stock_df = df[df["Ticker"] == selected_symbol]
    latest = stock_df.sort_values("Entry_Date", ascending=False).iloc[0]
    
    sentiment = calculate_sentiment(latest)
    
    left_col, right_col = st.columns([3, 1])
    
    with left_col:
        company_name = safe_display(latest.get("Company Name", selected_symbol))
        st.markdown(f"""
            <h1 style='margin-bottom:0;'>📈 {selected_symbol}</h1>
            <h3 style='color:gray;margin-top:0;'>{company_name}</h3>
            <h4 style='color:#4CAF50;'>{sentiment}</h4>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("PnL", f"{safe_display(latest.get('Trade_PnL_%'))}%")
        col2.metric("Days", safe_display(latest.get("Days_Held")))
        col3.metric("Entry", safe_display(latest.get("Entry_Price")))
        col4.metric("Exit", safe_display(latest.get("Exit_Price")))

        st.markdown(f"**Status:** {safe_display(latest.get('Status'))}")
        st.markdown(f"**Exit Reason:** {safe_display(latest.get('Exit_Reason'))}")

        st.subheader("📈 TradingView Chart")
        iframe_url = f"https://s.tradingview.com/widgetembed/?symbol=EGX:{selected_symbol}&interval=D&theme=Light&style=9"
        st.components.v1.iframe(iframe_url, height=500)
        
        # 🔥 NEWS SECTION HERE!
        st.subheader("📰 Latest News")
        news_items = fetch_latest_news(selected_symbol)
        if news_items:
            for n in news_items:
                st.markdown(
                    f"{n['emoji']} **{n['title']}**  \n"
                    f"Source: {n['provider']} | {n['published']}  \n"
                    f"[Read More]({n['url']})"
                )
                st.divider()
        else:
            st.info("No news found for this stock.")

    with right_col:
        st.subheader("📋 Key Metrics")
        metrics = {
            "Max Gain %": latest.get("Max_Gain_%"),
            "Max DD %": latest.get("Max_Drawdown_%"),
            "Entry Vol": latest.get("Entry_Volume"),
            "Rel Vol": latest.get("Entry_Rel_Volume_20")
        }
        for name, value in metrics.items():
            st.markdown(f"**{name}:** {safe_display(value)}")

with tab2:
    st.subheader("📊 Portfolio Stats")
    
    total_trades = len(df)
    winners = len(df[df["Trade_PnL_%"] > 0])
    win_rate = (winners/total_trades*100) if total_trades > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Trades", total_trades)
    col2.metric("Win Rate", f"{win_rate:.1f}%")
    col3.metric("Avg PnL", f"{df['Trade_PnL_%'].mean():.1f}%")
    col4.metric("Best Trade", f"{df['Trade_PnL_%'].max():.1f}%")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🟢 Top 5 Winners")
        top5 = df.nlargest(5, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held"]]
        st.dataframe(top5, use_container_width=True)
    
    with col2:
        st.markdown("### 🔴 Top 5 Losers")
        bottom5 = df.nsmallest(5, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held"]]
        st.dataframe(bottom5, use_container_width=True)
