import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import streamlit.components.v1 as components
import openai  # Make sure to install openai: pip install openai

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
        score += 2 if row["Unrealized_PnL_%"] > 0 else -2
    if pd.notna(row.get("Rel_Volume")) and row["Rel_Volume"] > 1.5:
        score += 1
    for key in ["HMA_above_EMA", "Accumulation", "RSI_Divergence", "Market_Structure"]:
        if row.get(key, False):
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
# Tabs: Stock Detail + Market Aggregates + AI Chat
# ---------------------------
tab1, tab2, tab3 = st.tabs(["📊 Stock Detail", "📈 Market Aggregates", "🤖 AI Chat"])

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

        st.markdown(
            f"<h1 style='margin-bottom:0;'>📈 {selected_symbol}</h1>"
            f"<h3 style='color:gray;margin-top:0;'>{company_name}</h3>"
            f"<h4 style='color:#4CAF50;margin-top:5px;'>🏭 Sector: {sector} | 🏷 Industry: {industry}</h4>",
            unsafe_allow_html=True
        )

        if latest["In_Trade"]:
            st.subheader("💼 Trade Status")
            status_col1, status_col2, status_col3 = st.columns(3)
            status_col1.metric("In Trade", "YES ✅")
            status_col2.metric("Days In Trade", int(latest["Days_In_Trade"]) if pd.notna(latest["Days_In_Trade"]) else "-")
            status_col3.metric("Entry Price", f"{latest['Entry_Price']:.2f}" if pd.notna(latest["Entry_Price"]) else "-")

            if "Entry_Date" in latest and pd.notna(latest["Entry_Date"]):
                st.markdown(f"**Entry Date:** {latest['Entry_Date']}")

            st.divider()

            # Summary Cards
            last_close = latest['Last_Close'] if pd.notna(latest['Last_Close']) else "-"
            unrealized_pnl = f"{latest['Unrealized_PnL_%']:.2f}%" if pd.notna(latest["Unrealized_PnL_%"]) else "-"
            score = latest.get("Score", "-")
            rsi_div = "Yes ✅" if latest.get("RSI_Divergence", False) else "No ❌"

            price = latest['Last_Close'] if pd.notna(latest['Last_Close']) else None
            support = latest.get("Support")
            resistance = latest.get("Resistance")

            dist_support_pct_str = f"{((price - support) / support) * 100:.2f}%" if price and support else "-"
            dist_resistance_pct_str = f"{((resistance - price) / resistance) * 100:.2f}%" if price and resistance else "-"

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
            st.markdown(f"**Sentiment:** {latest_sentiment}")
            st.markdown(f"**Distance to Support:** {dist_support_pct_str} | **Distance to Resistance:** {dist_resistance_pct_str}")

        st.divider()

        # TradingView Chart
        st.subheader("📈 TradingView Live Chart")
        tradingview_symbol = f"EGX:{selected_symbol}"
        iframe_url = f"https://s.tradingview.com/widgetembed/?frameElementId=tradingview_{selected_symbol}&symbol={tradingview_symbol}&interval=D&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[]&theme=Light&style=1&timezone=Etc%2FUTC"
        components.iframe(iframe_url, height=600, width=900)

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

        for col, display_name in metric_names.items():
            if col in latest:
                val = latest[col]
                val_str = "-" if pd.isna(val) else f"{val:.2f}" if isinstance(val, float) else "Yes ✅" if isinstance(val, bool) and val else "No ❌" if isinstance(val, bool) else str(val)
                st.markdown(f"**{display_name}:** {val_str}")

# ---------------------------
# Tab 2: Market Aggregates
# ---------------------------
with tab2:
    st.subheader("📊 Market Aggregates")

    in_trade_count = df[df["In_Trade"]].shape[0]
    st.metric("Stocks Currently in Trade", in_trade_count)

    # Top Gainers / Losers / Near Support / ATR
    top_gainers = df.sort_values("Unrealized_PnL_%", ascending=False).head(3)
    top_losers = df.sort_values("Unrealized_PnL_%", ascending=True).head(3)
    df["Dist_To_Support_%"] = ((df["Last_Close"] - df["Support"]) / df["Support"]).abs()
    top_support = df.sort_values("Dist_To_Support_%").head(3)
    top_atr = df.sort_values("ATR_Volatility_%", ascending=False).head(3)

    st.markdown("### 🟢 Top 3 Gainers")
    st.table(top_gainers[["Ticker", "Company Name", "Unrealized_PnL_%", "Last_Close"]])

    st.markdown("### 🔴 Top 3 Losers")
    st.table(top_losers[["Ticker", "Company Name", "Unrealized_PnL_%", "Last_Close"]])

    st.markdown("### ⚠️ Top 3 Near Support")
    st.table(top_support[["Ticker", "Company Name", "Last_Close", "Support", "Dist_To_Support_%"]])

    st.markdown("### 📈 Top 3 ATR")
    st.table(top_atr[["Ticker", "Company Name", "ATR_Volatility_%", "Last_Close"]])

# ---------------------------
# Tab 3: AI Chat (Updated for openai>=1.0)
# ---------------------------
with tab3:
    st.subheader("🤖 Ask the AI about stocks")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_input = st.text_input("Your question here:")

    if st.button("Send") and user_input.strip():
        import os
        from openai import OpenAI

        # Make sure your OPENAI_API_KEY is set in environment
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Stock context
        stock_summary = latest.to_dict()
        system_msg = f"You are a stock assistant. Here is the latest data for {selected_symbol}: {stock_summary}"

        st.session_state.chat_history.append({"role": "system", "content": system_msg})
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=st.session_state.chat_history,
                temperature=0.7,
                max_tokens=500
            )
            ai_answer = response.choices[0].message.content
            st.session_state.chat_history.append({"role": "assistant", "content": ai_answer})
            st.markdown(f"**AI:** {ai_answer}")
        except Exception as e:
            st.error(f"AI request failed: {e}")
