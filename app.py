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
    company_map["Ticker"] = company_map["Symbol"].str.replace("EGX:", "", regex=False)
    df = df.merge(company_map, on="Ticker", how="left")
    return df

df = load_data()

# ---------------------------
# Sidebar: Stock Selector
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

latest_sentiment = calculate_sentiment(latest)
latest["Sentiment"] = latest_sentiment

# ---------------------------
# Tabs: Stock Detail + Market Aggregates
# ---------------------------
tab1, tab2 = st.tabs(["📊 Stock Detail", "📈 Market Aggregates"])

# ---------------------------
# Tab 1: Stock Detail
# ---------------------------
with tab1:
    left_col, right_col = st.columns([3, 1])

    with left_col:
        # Stock Header
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
        # Only show Trade Status + Summary if in trade
        # ---------------------------
        if latest["In_Trade"]:
            st.subheader("💼 Trade Status")
            status_col1, status_col2, status_col3 = st.columns(3)
            status_col1.metric("In Trade", "YES ✅")
            status_col2.metric(
                "Days In Trade",
                int(latest["Days_In_Trade"]) if pd.notna(latest["Days_In_Trade"]) else "-"
            )
            status_col3.metric(
                "Entry Price",
                f"{latest['Entry_Price']:.2f}" if pd.notna(latest["Entry_Price"]) else "-"
            )

            if "Entry_Date" in latest and pd.notna(latest["Entry_Date"]):
                st.markdown(f"**Entry Date:** {latest['Entry_Date']}")

            st.divider()

            # Summary Cards
            last_close = latest['Last_Close'] if pd.notna(latest['Last_Close']) else "-"
            daily_pct = f"{latest['Gain_Loss_Today_%']:.2f}%" if pd.notna(latest["Gain_Loss_Today_%"]) else "-"
            unrealized_pnl = f"{latest['Unrealized_PnL_%']:.2f}%" if pd.notna(latest["Unrealized_PnL_%"]) else "-"
            score = latest.get("Score", "-")
            rsi_div = "Yes ✅" if latest.get("RSI_Divergence", False) else "No ❌"

            # Distance to Support/Resistance
            price = latest['Last_Close'] if pd.notna(latest['Last_Close']) else None
            support = latest.get("Support")
            resistance = latest.get("Resistance")

            if price and support:
                dist_support_pct_str = f"{((price - support) / support) * 100:.2f}%"
            else:
                dist_support_pct_str = "-"

            if price and resistance:
                dist_resistance_pct_str = f"{((resistance - price) / resistance) * 100:.2f}%"
            else:
                dist_resistance_pct_str = "-"

            # Price relation to S/R
            if price and support and resistance:
                if price < support:
                    price_vs_sr = "Below Support 🔻"
                elif price > resistance:
                    price_vs_sr = "Above Resistance ⬆️"
                elif abs(price - support) / support < 0.01:
                    price_vs_sr = "Near Support ⚠️"
                elif abs(price - resistance) / resistance < 0.01:
                    price_vs_sr = "Near Resistance ⚠️"
                else:
                    price_vs_sr = "Between Support & Resistance"
            else:
                price_vs_sr = "-"

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Last Close", last_close)
            col2.metric("Unrealized PnL", unrealized_pnl)
            col3.metric("Score", score)
            col4.metric("RSI Divergence", rsi_div)

            st.markdown(f"**Price Position:** {price_vs_sr}")
            st.markdown(f"**Sentiment:** {sentiment}")
            st.markdown(f"**Distance to Support:** {dist_support_pct_str} | **Distance to Resistance:** {dist_resistance_pct_str}")

        st.divider()

        # TradingView Chart
        st.subheader("📈 TradingView Live Chart")
        tradingview_symbol = f"EGX:{selected_symbol}"
        iframe_url = f"https://s.tradingview.com/widgetembed/?frameElementId=tradingview_{selected_symbol}&symbol={tradingview_symbol}&interval=D&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[]&theme=Light&style=1&timezone=Etc%2FUTC"
        components.iframe(iframe_url, height=600, width=900)

        st.divider()

        # Latest 3 News
        st.subheader("📰 Latest News")
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
            return "".join(emojis) if emojis else DEFAULT_EMOJI

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
                st.markdown(
                    f"{n['emoji']} **{n['title']}**  \n"
                    f"Source: {n['provider']} | Published: {n['published']}  \n"
                    f"[Read More]({n['url']})"
                )
        else:
            st.info("No news found for this stock.")

    with right_col:
        st.subheader("📋 Full Stock Metrics")
        metric_names = {
            "In_Trade": "In Trade",
            "Last_Close": "Last Close",
            "Gain_Loss_Today_%": "Daily % Gain/Loss",
            "Entry_Price": "Entry Price",
            "Days_In_Trade": "Days In Trade",
            "Unrealized_PnL_%": "Unrealized PnL %",
            "Rel_Volume": "Relative Volume",
            "HMA_above_EMA": "HMA Above EMA",
            "Accumulation": "Accumulation",
            "RSI_Divergence": "RSI Divergence",
            "Market_Structure": "Market Structure",
            "Score": "Score",
            "Support": "Support",
            "Resistance": "Resistance",
            "ATR_Volatility_%": "ATR"
        }

        metrics_to_show = []
        for col, display_name in metric_names.items():
            if col in latest:
                val = latest[col]
                if pd.isna(val):
                    val_str = "-"
                elif isinstance(val, float):
                    val_str = f"{val:.2f}"
                elif isinstance(val, bool):
                    val_str = "Yes ✅" if val else "No ❌"
                else:
                    val_str = str(val)
                metrics_to_show.append((display_name, val_str))

        for name, value in metrics_to_show:
            st.markdown(f"**{name}:** {value}")

# ---------------------------
# Tab 2: Market Aggregates
# ---------------------------
with tab2:
    st.subheader("📊 Market Aggregates")

    # Total stocks in trade
    in_trade_count = df[df["In_Trade"]].shape[0]
    st.metric("Stocks Currently in Trade", in_trade_count)

    # Top Gainers
    top_gainers = df.sort_values("Gain_Loss_Today_%", ascending=False).head(3)
    st.markdown("### 🟢 Top 3 Gainers")
    st.table(top_gainers[["Ticker", "Company Name", "Gain_Loss_Today_%", "Last_Close"]])

    # Top Losers
    top_losers = df.sort_values("Gain_Loss_Today_%", ascending=True).head(3)
    st.markdown("### 🔴 Top 3 Losers")
    st.table(top_losers[["Ticker", "Company Name", "Gain_Loss_Today_%", "Last_Close"]])

    # Top Near Support
    df["Dist_To_Support_%"] = ((df["Last_Close"] - df["Support"]) / df["Support"]).abs()
    top_support = df.sort_values("Dist_To_Support_%").head(3)
    st.markdown("### ⚠️ Top 3 Near Support")
    st.table(top_support[["Ticker", "Company Name", "Last_Close", "Support", "Dist_To_Support_%"]])

    # Top ATR
    top_atr = df.sort_values("ATR_Volatility_%", ascending=False).head(3)
    st.markdown("### 📈 Top 3 ATR")
    st.table(top_atr[["Ticker", "Company Name", "ATR_Volatility_%", "Last_Close"]])
