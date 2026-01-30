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
# Load Data + Company Map
# ---------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("StockQuotes.csv")
    company_map = pd.read_csv("egx_company_map.csv")
    # Strip EGX: prefix to match your tickers
    company_map["Ticker"] = company_map["Symbol"].str.replace("EGX:", "", regex=False)
    # Merge on Ticker
    df = df.merge(
        company_map,
        on="Ticker",
        how="left"
    )
    return df

df = load_data()

# ---------------------------
# Sidebar
# ---------------------------
st.sidebar.header("🔍 Stock Selector")
symbols = sorted(df["Ticker"].unique())
selected_symbol = st.sidebar.selectbox("Choose Stock:", symbols)

# ---------------------------
# Filter Data
# ---------------------------
stock_df = df[df["Ticker"] == selected_symbol]
latest = stock_df.sort_values("Report_Date").iloc[-1]

# ---------------------------
# Company Info
# ---------------------------
company_name = latest.get("Company Name") or "Unknown Company"
sector = latest.get("Sector") or "Unknown Sector"
industry = latest.get("Industry/Subsector") or "Unknown Industry"

# ---------------------------
# Title Section
# ---------------------------
st.markdown(
    f"""
    <h1 style="margin-bottom:0;">📈 {selected_symbol}</h1>
    <h3 style="color:gray;margin-top:0;">{company_name}</h3>
    <h4 style="color:#4CAF50;margin-top:5px;">🏭 Sector: {sector} | 🏷 Industry: {industry}</h4>
    """,
    unsafe_allow_html=True
)

st.divider()

# ---------------------------
# Sentiment Engine
# ---------------------------
def calculate_sentiment(row):
    score = 0
    if pd.notna(row["Unrealized_PnL_%"]):
        if row["Unrealized_PnL_%"] > 0:
            score += 2
        elif row["Unrealized_PnL_%"] < 0:
            score -= 2
    if pd.notna(row["Rel_Volume"]) and row["Rel_Volume"] > 1.5:
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

sentiment = calculate_sentiment(latest)

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
# Full Data View
# ---------------------------
st.subheader("📋 Full Stock Metrics")
display_df = latest.to_frame(name="Value").reset_index()
display_df.columns = ["Metric", "Value"]
st.dataframe(display_df, use_container_width=True, hide_index=True)

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
# Historical Table
# ---------------------------
st.subheader("🕒 Historical Records")
st.dataframe(
    stock_df.sort_values("Report_Date", ascending=False),
    use_container_width=True
)
