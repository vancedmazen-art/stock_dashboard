import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
import pytz
import streamlit.components.v1 as components


# ====================================
# CONFIG
# ====================================

NEWS_API_URL = (
    "https://news-mediator.tradingview.com/news-flow/v2/news?"
    "filter=lang%3Aen&filter=market%3Astock&filter=market_country%3AEG&client=screener"
)

CAIRO_TZ = pytz.timezone("Africa/Cairo")

REFRESH_SEC = 300   # 5 minutes


# ====================================
# PAGE SETUP
# ====================================

st.set_page_config(
    page_title="EGX Trading Terminal",
    layout="wide"
)


# ====================================
# AUTO REFRESH
# ====================================

st_autorefresh = st.experimental_rerun

last_refresh = st.session_state.get("last_refresh")

if not last_refresh or (datetime.now() - last_refresh).seconds > REFRESH_SEC:
    st.session_state["last_refresh"] = datetime.now()


# ====================================
# EMOJI RULES
# ====================================

KEYWORD_EMOJI_RULES = [

    (["bankruptcy", "default", "collapse", "scandal"], "💥"),

    (["loss", "decline", "drop", "fall", "deficit",
      "bear", "recession"], "🔻🐻"),

    (["rise", "up", "positive", "bull",
      "increase"], "✅📈🐂"),

    (["profit", "beat estimates", "surge"], "⬆💰"),

    (["dividend"], "💰"),

    (["merger", "acquire", "deal"], "🤝"),

    (["growth", "expand", "invest"], "🚀"),

    (["cut", "layoff"], "⚠️"),

    (["launch"], "🆕"),

    (["approval", "license"], "📜"),

    (["ceo", "cfo", "board"], "👔"),
]

DEFAULT_EMOJI = "📰"


def pick_emoji(headline):

    h = headline.lower()
    emojis = []

    for keys, emo in KEYWORD_EMOJI_RULES:
        if any(k in h for k in keys):
            emojis.append(emo)

    return "".join(set(emojis)) if emojis else DEFAULT_EMOJI


# ====================================
# NEWS
# ====================================

@st.cache_data(ttl=REFRESH_SEC)
def fetch_news():

    r = requests.get(NEWS_API_URL, timeout=10)
    r.raise_for_status()

    return r.json().get("items", [])


def get_stock_news(ticker):

    items = fetch_news()
    res = []

    for n in items:

        related = n.get("relatedSymbols", [])

        syms = []
        for s in related:
            sym = s.get("symbol", "")
            if sym.startswith("EGX:"):
                syms.append(sym.replace("EGX:", ""))

        if ticker not in syms:
            continue

        ts = n.get("published")

        dt = datetime.utcfromtimestamp(ts).replace(
            tzinfo=pytz.UTC).astimezone(CAIRO_TZ)

        title = n.get("title", "")
        url = "https://www.tradingview.com" + n.get("storyPath", "")
        provider = n.get("provider", {}).get("name", "")

        emoji = pick_emoji(title)

        is_breaking = datetime.now(CAIRO_TZ) - dt < timedelta(hours=1)

        res.append({
            "title": title,
            "url": url,
            "provider": provider,
            "dt": dt,
            "display": dt.strftime("%Y-%m-%d %H:%M"),
            "emoji": emoji,
            "breaking": is_breaking
        })

    return sorted(res, key=lambda x: x["dt"], reverse=True)[:3]


# ====================================
# LOAD DATA
# ====================================

df = pd.read_csv("StockQuotes.csv")

df["Report_Date"] = pd.to_datetime(df["Report_Date"], format="%Y%m%d")


# ====================================
# SIDEBAR
# ====================================

st.sidebar.title("📌 Controls")

symbols = sorted(df["Ticker"].unique())
symbol = st.sidebar.selectbox("Select Stock", symbols)

st.sidebar.markdown("---")
st.sidebar.info("🔄 Auto refresh every 5 min")


# ====================================
# FILTER
# ====================================

stock = df[df["Ticker"] == symbol].sort_values("Report_Date")
latest = stock.iloc[-1]


# ====================================
# KPI BAR
# ====================================

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Last Close", f"{latest['Last_Close']:.2f}")
c2.metric("PnL %", f"{latest['Unrealized_PnL_%']:.2f}")
c3.metric("Rel Vol", f"{latest['Rel_Volume']:.2f}")
c4.metric("Score", f"{latest['Score']:.1f}")
c5.metric("In Trade", "YES" if latest['In_Trade'] else "NO")


# ====================================
# TRADINGVIEW WIDGET
# ====================================

st.subheader("📈 Live Chart (TradingView)")

tv_html = f"""
<!-- TradingView Widget BEGIN -->
<div class="tradingview-widget-container">
  <div id="tv_{symbol}"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "width": "100%",
    "height": 500,
    "symbol": "EGX:{symbol}",
    "interval": "D",
    "timezone": "Africa/Cairo",
    "theme": "light",
    "style": "1",
    "locale": "en",
    "toolbar_bg": "#f1f3f6",
    "enable_publishing": false,
    "allow_symbol_change": false,
    "container_id": "tv_{symbol}"
  }});
  </script>
</div>
<!-- TradingView Widget END -->
"""

components.html(tv_html, height=520)


# ====================================
# INTERNAL PRICE CHART
# ====================================

st.subheader("📊 Historical Price")

fig = px.line(
    stock,
    x="Report_Date",
    y="Last_Close",
    title=f"{symbol} Price History"
)

if latest["Support"]:
    fig.add_hline(y=latest["Support"], line_dash="dot", annotation_text="Support")

if latest["Resistance"]:
    fig.add_hline(y=latest["Resistance"], line_dash="dot", annotation_text="Resistance")

if latest["Last_Exit_High"]:
    fig.add_hline(
        y=latest["Last_Exit_High"],
        line_dash="dash",
        annotation_text="Last Exit"
    )

st.plotly_chart(fig, use_container_width=True)


# ====================================
# NEWS
# ====================================

st.subheader("📰 Latest News")

news = get_stock_news(symbol)

if not news:
    st.info("No recent news.")
else:

    for n in news:

        badge = "🚨 BREAKING" if n["breaking"] else ""

        st.markdown(f"""
### {n['emoji']} {n['title']} {badge}

**Source:** {n['provider']}  
**Time:** {n['display']}  

👉 [Read More]({n['url']})
---
""")


# ====================================
# TABLE
# ====================================

with st.expander("📋 Full Data"):

    st.dataframe(stock, use_container_width=True)
