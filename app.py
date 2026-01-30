import streamlit as st
import pandas as pd

# ---------------------------
# Page Config
# ---------------------------
st.set_page_config(
    page_title="Stock Analysis Dashboard",
    layout="wide"
)

# ---------------------------
# Load Data
# ---------------------------
@st.cache_data
def load_data():
    return pd.read_csv("StockQuotes.csv")

df = load_data()


# ---------------------------
# Sidebar
# ---------------------------
st.sidebar.header("🔍 Stock Selector")

symbols = sorted(df["Ticker"].unique())

selected_symbol = st.sidebar.selectbox(
    "Choose Stock:",
    symbols
)


# ---------------------------
# Filter Data
# ---------------------------
stock_df = df[df["Ticker"] == selected_symbol]

latest = stock_df.sort_values("Report_Date").iloc[-1]


# ---------------------------
# Company Name (If Exists)
# ---------------------------
company_name = latest.get("Company_Name", "Unknown Company")


# ---------------------------
# Title Section
# ---------------------------
st.markdown(
    f"""
    <h1 style="margin-bottom:0;">
        📈 {selected_symbol}
    </h1>
    <h3 style="color:gray;margin-top:0;">
        {company_name}
    </h3>
    """,
    unsafe_allow_html=True
)

st.divider()


# ---------------------------
# Sentiment Engine
# ---------------------------
def calculate_sentiment(row):

    score = 0

    # Profit
    if row["Unrealized_PnL_%"] and row["Unrealized_PnL_%"] > 0:
        score += 2
    elif row["Unrealized_PnL_%"] and row["Unrealized_PnL_%"] < 0:
        score -= 2

    # Volume
    if row["Rel_Volume"] and row["Rel_Volume"] > 1.5:
        score += 1

    # Trend
    if row["HMA_above_EMA"]:
        score += 1

    if row["Accumulation"]:
        score += 1

    # RSI
    if row["RSI_Divergence"]:
        score += 1

    # Market structure
    if row["Market_Structure"]:
        score += 1

    # Final sentiment
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


sentiment = calculate_sentiment(latest)


# ---------------------------
# Summary Cards
# ---------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("Last Close", f"{latest['Last_Close']:.2f}")
col2.metric("Daily %", f"{latest['Gain_Loss_Today_%']:.2f}%")
col3.metric("Unrealized PnL", f"{latest['Unrealized_PnL_%']:.2f}%")
col4.metric("Sentiment", sentiment)


st.divider()


# ---------------------------
# Full Data View
# ---------------------------
st.subheader("📋 Full Stock Metrics")

display_df = latest.to_frame(name="Value").reset_index()
display_df.columns = ["Metric", "Value"]

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ---------------------------
# Trade Status
# ---------------------------
st.subheader("💼 Trade Status")

status_col1, status_col2, status_col3 = st.columns(3)

status_col1.metric(
    "In Trade",
    "YES ✅" if latest["In_Trade"] else "NO ❌"
)

status_col2.metric(
    "Days In Trade",
    int(latest["Days_In_Trade"])
    if not pd.isna(latest["Days_In_Trade"])
    else "-"
)

status_col3.metric(
    "Entry Price",
    f"{latest['Entry_Price']:.2f}"
    if not pd.isna(latest["Entry_Price"])
    else "-"
)


st.divider()


# ---------------------------
# Historical Table
# ---------------------------
st.subheader("🕒 Historical Records")

st.dataframe(
    stock_df.sort_values("Report_Date", ascending=False),
    use_container_width=True
)
