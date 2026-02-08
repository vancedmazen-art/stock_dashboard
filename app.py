import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import os

# ---------------------------  
# Page Config
# ---------------------------
st.set_page_config(
    page_title="Stock Analysis Dashboard",
    layout="wide"
)

# --------------------------- 
# Load Data from Excel
# ---------------------------
@st.cache_data
def load_data():
    try:
        if not os.path.exists("Complete_Trades_Metrics.xlsx"):
            st.error("❌ Complete_Trades_Metrics.xlsx missing from repo root!")
            return pd.DataFrame()
        
        # Read both sheets
        trades_df = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="Open_Trades")  # Adjust sheet name if needed
        company_map = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="Sheet2")  # Adjust sheet name if needed
        
        # Ensure Ticker column exists
        if "Ticker" not in trades_df.columns:
            st.error(f"❌ 'Ticker' column missing from trades sheet. Found: {list(trades_df.columns)}")
            return pd.DataFrame()
            
        # Process company map (adjust column names based on your Sheet2)
        if "Symbol" in company_map.columns:
            company_map["Ticker"] = company_map["Symbol"].str.replace("EGX:", "", regex=False)
        elif "Company" in company_map.columns:
            company_map["Ticker"] = company_map["Company"].str.replace("EGX:", "", regex=False)
        else:
            st.warning("No Symbol/Company column found in company map - skipping merge")
            return trades_df
        
        # Merge data
        df = trades_df.merge(company_map, on="Ticker", how="left")
        return df
        
    except Exception as e:
        st.error(f"❌ Data load failed: {e}")
        return pd.DataFrame()

# Load and validate data
df = load_data()

if df.empty:
    st.error("❌ No data loaded! Upload Complete_Trades_Metrics.xlsx to repo root.")
    st.stop()

if "Ticker" not in df.columns:
    st.error(f"❌ Missing 'Ticker' column. Available: {list(df.columns)}")
    st.stop()

st.success(f"✅ Loaded {len(df)} trades from {len(df['Ticker'].unique())} stocks")

# --------------------------- 
# Sentiment Engine (unchanged)
# ---------------------------
def calculate_sentiment(row):
    score = 0
    if pd.notna(row.get("Trade_PnL_%")):
        score += 2 if row["Trade_PnL_%"] > 0 else -2
    # Adapt to your Excel columns - adjust as needed
    if pd.notna(row.get("Entry_Rel_Volume_20")) and row["Entry_Rel_Volume_20"] > 1.5:
        score += 1
    for key in ["Entry_Market_Structure", "Entry_Crosses_Resistance"]:
        if row.get(key, False):
            score += 1

    if score >= 4: return "🟢 Strong Bullish"
    elif score >= 2: return "🟢 Bullish" 
    elif score >= 0: return "🟡 Neutral"
    elif score >= -2: return "🔴 Bearish"
    else: return "🔴 Strong Bearish"

# --------------------------- 
# Tabs
# ---------------------------
tab1, tab2 = st.tabs(["📊 Trade Detail", "📈 Portfolio Summary"])

with tab1:
    symbols = sorted(df["Ticker"].unique())
    selected_symbol = st.selectbox("🔍 Choose Stock:", symbols)
    
    # Filter & get latest trade
    stock_df = df[df["Ticker"] == selected_symbol]
    latest = stock_df.sort_values("Entry_Date", ascending=False).iloc[0]  # Most recent trade
    
    latest_sentiment = calculate_sentiment(latest)
    
    left_col, right_col = st.columns([3, 1])
    
    with left_col:
        company_name = latest.get("Company Name", "Unknown") or "Unknown Company"
        st.markdown(f"""
            <h1 style='margin-bottom:0;'>📈 {selected_symbol}</h1>
            <h3 style='color:gray;margin-top:0;'>{company_name}</h3>
            <h4 style='color:#4CAF50;'>{latest.get("Status", "CLOSED")}</h4>
        """, unsafe_allow_html=True)

        # Key trade metrics from your Excel
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Trade PnL", f"{latest.get('Trade_PnL_%', 0):.1f}%")
        col2.metric("Days Held", latest.get("Days_Held", 0))
        col3.metric("Entry Price", f"{latest.get('Entry_Price', 0):.2f}")
        col4.metric("Exit Price", f"{latest.get('Exit_Price', 0):.2f}")
        
        st.markdown(f"**Sentiment:** {latest_sentiment}")
        st.markdown(f"**Exit Reason:** {latest.get('Exit_Reason', '-')}")
        
        # TradingView chart
        st.subheader("📈 TradingView Chart")
        iframe_url = f"https://s.tradingview.com/widgetembed/?symbol=EGX:{selected_symbol}&interval=D&theme=Light&style=9"
        st.components.v1.iframe(iframe_url, height=500)

    with right_col:
        st.subheader("📋 Trade Metrics")
        for col in ["Max_Gain_%", "Max_Drawdown_%", "Entry_Volume", "Status"]:
            if col in latest:
                val = latest[col]
                st.markdown(f"**{col}:** {val}")

with tab2:
    st.subheader("📊 Portfolio Summary")
    
    # Key portfolio metrics
    total_trades = len(df)
    winners = len(df[df["Trade_PnL_%"] > 0])
    win_rate = (winners / total_trades * 100) if total_trades > 0 else 0
    avg_pnl = df["Trade_PnL_%"].mean()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Trades", total_trades)
    col2.metric("Win Rate", f"{win_rate:.1f}%")
    col3.metric("Avg PnL", f"{avg_pnl:.1f}%")
    col4.metric("Best Trade", f"{df['Trade_PnL_%'].max():.1f}%")
    
    # Top performers
    st.markdown("### 🟢 Top 5 Winners")
    top_winners = df.nlargest(5, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held"]]
    st.table(top_winners)
    
    st.markdown("### 🔴 Biggest Losers") 
    top_losers = df.nsmallest(5, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held"]]
    st.table(top_losers)
