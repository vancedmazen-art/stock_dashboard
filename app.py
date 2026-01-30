import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime
import pytz

# --------------------------------
# CONFIG
# --------------------------------
NEWS_API_URL = (
    "https://news-mediator.tradingview.com/news-flow/v2/news?"
    "filter=lang%3Aen&filter=market%3Astock&filter=market_country%3AEG&client=screener"
)

CAIRO_TZ = pytz.timezone("Africa/Cairo")

# --------------------------------
# Emoji Rules (Your Logic)
# --------------------------------
KEYWORD_EMOJI_RULES = [

    (["bankruptcy", "default", "collapse", "scandal"], "💥"),

    (["loss", "decline", "drop", "fall", "deficit", "down", "negative",
      "bear", "lower", "decrease", "recession"], "🔻🐻"),

    (["rise", "up", "positive", "bull", "higher", "increase"], "✅📈🐂"),

    (["profit", "strong earnings", "beat estimates", "surge"], "⬆💰"),

    (["dividend", "payout"], "💰"),

    (["acquire", "merger", "deal"], "🤝"),

    (["expansion", "growth", "invest"], "🚀"),

    (["cut", "reduce", "layoffs"], "⚠️"),

    (["launch", "introduces"], "🆕"),

    (["approval", "license"], "📜"),

    (["ceo", "cfo", "board"], "👔"),

]

DEFAULT_EMOJI = "📰"


def pick_emoji(headline):

    h = headline.lower()
    emojis = []

    for keywords, emoji in KEYWORD_EMOJI_RULES:
        if any(k in h for k in keywords):
            if emoji not in emojis:
                emojis.append(emoji)

    return "".join(emojis) if emojis else DEFAULT_EMOJI


# --------------------------------
# News Fetcher
# --------------------------------
@st.cache_data(ttl=300)
def fetch_news():

    r = requests.get(NEWS_API_URL, timeout=10)
    r.raise_for_status()

    return r.json().get("items", [])


def get_stock_news(ticker):

    items = fetch_news()
    results = []

    for news in items:

        related = news.get("relatedSymbols", [])

        symbols = []
        for s in related:
            sym = s.get("symbol", "")
            if sym.startswith("EGX:"):
                symbols.append(sym.replace("EGX:", ""))

        if ticker not in symbols:
            continue

        ts = news.get("published")
        dt = datetime.utcfromtimestamp(ts).replace(
            tzinfo=pytz.UTC).astimezone(CAIRO_TZ)

        title = news.get("title", "")
        url = "https://www.tradingview.com" + news.get("storyPath", "")
        provider = news.get("provider", {}).get("name", "")

        emoji = pick_emoji(title)

        results.append({
            "title": title,
            "url": url,
            "provider": provider,
            "date": dt.strftime("%Y-%m-%d %H:%M"),
            "emoji": emoji
        })

    return sorted(results, key=lambda x: x["date"], reverse=True)[:3]


# --------------------------------
# Load Data
# --------------------------------
df = pd.read_csv("StockQuotes.csv")

df['Report_Date'] = pd.to_datetime(df['Report_Date'], format='%Y%m%d')


# --------------------------------
# UI
# --------------------------------
st.set_page_config(
    page_title="Stock Dashboard",
    layout="wide"
)

st.title("📊 Egyptian Stock Market Dashboard")


# Sidebar
st.sidebar.header("Settings")

symbols = sorted(df['Ticker'].unique())
symbol = st.sidebar.selectbox("Select Stock", symbols)


# --------------------------------
# Filter Data
# --------------------------------
stock_df = df[df['Ticker'] == symbol].sort_values('Report_Date')
latest = stock_df.iloc[-1]


# --------------------------------
# KPIs
# --------------------------------
c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Last Close", f"{latest['Last_Close']:.2f}")
c2.metric("PnL %", f"{latest['Unrealized_PnL_%']:.2f}")
c3.metric("Rel Volume", f"{latest['Rel_Volume']:.2f}")
c4.metric("Score", f"{latest['Score']:.1f}")
c5.metric("In Trade", "YES" if latest['In_Trade'] else "NO")


# --------------------------------
# Chart
# --------------------------------
fig = px.line(
    stock_df,
    x="Report_Date",
    y="Last_Close",
    title=f"{symbol} Price"
)

# Support / Resistance
if latest['Support']:
    fig.add_hline(y=latest['Support'], line_dash="dot", annotation_text="Support")

if latest['Resistance']:
    fig.add_hline(y=latest['Resistance'], line_dash="dot", annotation_text="Resistance")

if latest['Last_Exit_High']:
    fig.add_hline(
        y=latest['Last_Exit_High'],
        line_dash="dash",
        annotation_text="Last Exit High"
    )

st.plotly_chart(fig, use_container_width=True)


# --------------------------------
# News Section
# --------------------------------
st.subheader("📰 Latest News")

news = get_stock_news(symbol)

if not news:
    st.info("No recent news found.")
else:
    for n in news:

        st.markdown(
            f"""
### {n['emoji']} {n['title']}

**Source:** {n['provider']}  
**Date:** {n['date']}  

👉 [Read more]({n['url']})
---
"""
        )


# --------------------------------
# Table
# --------------------------------
with st.expander("📋 Full Data Table"):
    st.dataframe(stock_df, use_container_width=True)
