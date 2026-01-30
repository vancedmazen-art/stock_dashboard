import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import streamlit.components.v1 as components

# ---------------------------
# Page Config
# ---------------------------
st.set_page_config(
    page_title="Stock Analysis Dashboard",
    layout="wide"
)

# ---------------------------
# Load Data + Company Map
# ---------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("StockQuotes.csv")
    company_map = pd.read_csv("egx_company_map.csv")
    # Strip EGX: prefix to match your tickers
    company_map["Ticker"] = company_map["Symbol"].str.replace("EGX:", "", regex=False)
    df = df.merge(company_map, on="Ticker", how="left")
    return df

df = load_data()

# ---------------------------
# Sidebar: Stock Selector + Horizontal Metrics
# ---------------------------
st.sidebar.header("🔍 Stock Selector")
symbols = sorted(df["Ticker"].unique())
selected_symbol = st.sidebar.selectbox("Choose Stock:", symbols)

# Filter stock
stock_df = df[df["Ticker"] == selected_symbol]
latest = stock_df.sort_values("Report_Date").iloc[-1]

# ---------------------------
# Sentiment Engine
# ---------------------------
def calculate_sentiment(row):
    score = 0
    if pd.notna(row.get("Unrealized_PnL_%")):
        if row["Unrealized_PnL_%"] > 0:
            score += 2
        elif row["Unrealized_PnL_%"] < 0:
            score -= 2
    if pd.notna(row.get("Rel_Volume")) and row["Rel_Volume"] > 1.5:
        score += 1
    if row.get("HMA_above_EMA", False):
        score += 1
    if row.get("Accumulation", False):
        score += 1
    if row.get("RSI_Divergence", False):
        score += 1
    if row.get("Market_Structure", False):
        score += 1

    if score >= 4:
        return "🟢 Strong Bullish"
    elif score >= 2:
        return "🟢 Bullish"
    elif score >= 0:
        return "🟡 Neutral"
    elif score >= -2:
        return "🔴 Bearish"
    else:
        return "🔴 Strong Bearish"

# Add sentiment to latest row
latest_sentiment = calculate_sentiment(latest)
latest["Sentiment"] = latest_sentiment

# Display metrics horizontally in sidebar
st.sidebar.subheader("📋 Full Stock Metrics")
metrics = latest.to_dict()
cols = st.sidebar.columns(len(metrics))
for i, (metric, value) in enumerate(metrics.items()):
    # Format floats nicely
    if isinstance(value, float):
        value_str = f"{value:.2f}"
    else:
        value_str = str(value)
    cols[i].metric(metric, value_str)

# ---------------------------
# Main Page: Stock Info
# ---------------------------
company_name = latest.get("Company Name") or "Unknown Company"
sector = latest.get("Sector") or "Unknown Sector"
industry = latest.get("Industry/Subsector") or "Unknown Industry"
sentiment = latest_sentiment

st.markdown(
    f"""
    <h1 style="margin-bottom:0;">📈 {selected_symbol}</h1>
    <h3 style="color:gray;margin-top:0;">{company_name}</h3>
    <h4 style="color:#4CAF50;margin-top:5px;">🏭 Sector: {sector} | 🏷 Industry: {industry}</h4>
    """,
    unsafe_allow_html=True
)

# ---------------------------
# Trade Status
# ---------------------------
st.subheader("💼 Trade Status")
status_col1, status_col2, status_col3 = st.columns(3)
status_col1.metric("In Trade", "YES ✅" if latest["In_Trade"] else "NO ❌")
status_col2.metric(
    "Days In Trade",
    int(latest["Days_In_Trade"]) if pd.notna(latest["Days_In_Trade"]) else "-"
)
status_col3.metric(
    "Entry Price",
    f"{latest['Entry_Price']:.2f}" if pd.notna(latest["Entry_Price"]) else "-"
)

st.divider()

# ---------------------------
# Summary Cards
# ---------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Last Close", f"{latest['Last_Close']:.2f}" if pd.notna(latest["Last_Close"]) else "-")
col2.metric("Daily %", f"{latest['Gain_Loss_Today_%']:.2f}%" if pd.notna(latest["Gain_Loss_Today_%"]) else "-")
col3.metric("Unrealized PnL", f"{latest['Unrealized_PnL_%']:.2f}%" if pd.notna(latest["Unrealized_PnL_%"]) else "-")
col4.metric("Sentiment", sentiment)

st.divider()

# ---------------------------
# TradingView Chart
# ---------------------------
st.subheader("📈 TradingView Live Chart")
tradingview_symbol = f"EGX:{selected_symbol}"
iframe_url = f"https://s.tradingview.com/widgetembed/?frameElementId=tradingview_{selected_symbol}&symbol={tradingview_symbol}&interval=D&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[]&theme=Light&style=1&timezone=Etc%2FUTC"
components.iframe(iframe_url, height=600, width=1200)

# ---------------------------
# Latest 3 News Section
# ---------------------------
st.subheader("📰 Latest News")

# ---------------------------
# News Fetching Function
# ---------------------------
DISCORD_WEBHOOK_URL = ""  # Optional: remove if not needed

API_URL = (
    "https://news-mediator.tradingview.com/news-flow/v2/news?"
    "filter=lang%3Aen&filter=market%3Astock&filter=market_country%3AEG&client=screener"
)

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

DEFAULT_EMOJI = "📰"

def pick_emoji(headline: str) -> str:
    h = headline.lower()
    emojis = []
    for keywords, emoji in KEYWORD_EMOJI_RULES:
        if any(k in h for k in keywords):
            if emoji not in emojis:
                emojis.append(emoji)
    if not emojis:
        return DEFAULT_EMOJI
    return "".join(emojis)

def fetch_latest_news(symbol: str, max_items=3):
    try:
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
            if not ts:
                continue
            published_dt = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.UTC).astimezone(CAIRO_TZ)
            published_str = published_dt.strftime("%Y-%m-%d %H:%M:%S")
            emoji = pick_emoji(title)
            result.append({
                "title": title,
                "url": f"https://www.tradingview.com{url}",
                "provider": provider,
                "published": published_str,
                "emoji": emoji
            })
        if len(result) >= max_items:
            break
    return result

news_items = fetch_latest_news(selected_symbol)
if news_items:
    for n in news_items:
        st.markdown(f"{n['emoji']} **{n['title']}**  \nSource: {n['provider']} | Published: {n['published']}  \n[Read More]({n['url']})")
else:
    st.info("No news found for this stock.")
