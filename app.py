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
    page_title="EGX Trading Dashboard", 
    layout="wide"
)

# --------------------------- 
# Load Data + Company Map
# ---------------------------
@st.cache_data
def load_data():
    try:
        # Check trades file first (Excel)
        if not os.path.exists("Complete_Trades_Metrics.xlsx"):
            st.error("❌ Complete_Trades_Metrics.xlsx missing!")
            return pd.DataFrame()
        
        # Read trades data (first sheet)
        trades_df = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name=0)
        
        # Try to load company map (CSV)
        if os.path.exists("egx_company_map.csv"):
            company_map = pd.read_csv("egx_company_map.csv")
            if "Symbol" in company_map.columns:
                company_map["Ticker"] = company_map["Symbol"].str.replace("EGX:", "", regex=False)
            elif "Company" in company_map.columns:
                company_map["Ticker"] = company_map["Company"]
            else:
                st.warning("No Symbol/Company column in egx_company_map.csv")
                company_map = None
        else:
            st.warning("⚠️ egx_company_map.csv not found - basic mode")
            company_map = None
        
        # Ensure Ticker exists
        if "Ticker" not in trades_df.columns:
            st.error(f"❌ 'Ticker' column missing. Found: {list(trades_df.columns)[:5]}...")
            return pd.DataFrame()
        
        # Merge if company map available
        df = trades_df.copy()
        if company_map is not None:
            df = df.merge(company_map, on="Ticker", how="left")
        
        st.success(f"✅ Loaded {len(df)} trades from {len(df['Ticker'].unique())} stocks")
        return df
        
    except Exception as e:
        st.error(f"❌ Data load failed: {e}")
        return pd.DataFrame()

# Load data
df = load_data()
if df.empty:
    st.stop()

# --------------------------- 
# Sentiment Engine
# ---------------------------
def calculate_sentiment(row):
    score = 0
    if pd.notna(row.get("Trade_PnL_%")):
        score += 2 if row["Trade_PnL_%"] > 0 else -2
    if pd.notna(row.get("Entry_Rel_Volume_20")) and row["Entry_Rel_Volume_20"] > 1.5:
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
# Tabs
# ---------------------------
tab1, tab2 = st.tabs(["📊 Stock Detail", "📈 Portfolio Overview"])

with tab1:
    symbols = sorted(df["Ticker"].unique())
    selected_symbol = st.selectbox("🔍 Choose Stock:", symbols)
    
    # Filter stock trades
    stock_df = df[df["Ticker"] == selected_symbol]
    latest_trade = stock_df.sort_values("Entry_Date", ascending=False).iloc[0]
    
    sentiment = calculate_sentiment(latest_trade)
    
    left_col, right_col = st.columns([3, 1])
    
    with left_col:
        company_name = latest_trade.get("Company Name", "Unknown") or selected_symbol
        st.markdown(f"""
            <h1 style='margin-bottom:0;'>📈 {selected_symbol}</h1>
            <h3 style='color:gray;margin-top:0;'>{company_name}</h3>
            <h4 style='color:#4CAF50;margin-top:5px;'>{sentiment}</h4>
        """, unsafe_allow_html=True)

        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Trade PnL", f"{latest_trade.get('Trade_PnL_%', 0):.1f}%")
        col2.metric("Days Held", int(latest_trade.get("Days_Held", 0)))
        col3.metric("Entry", f"{latest_trade.get('Entry_Price', 0):.2f}")
        col4.metric("Exit", f"{latest_trade.get('Exit_Price', 0):.2f}")

        st.markdown(f"**Status:** {latest_trade.get('Status', 'N/A')}")
        st.markdown(f"**Exit Reason:** {latest_trade.get('Exit_Reason', 'N/A')}")

        # TradingView
        st.subheader("📈 TradingView Chart")
        iframe_url = (
            f"https://s.tradingview.com/widgetembed/?"
            f"symbol=EGX:{selected_symbol}&interval=D&"
            f"theme=Light&style=9&timezone=Etc%2FUTC"
        )
        st.components.v1.iframe(iframe_url, height=500)

    with right_col:
        st.subheader("📋 Trade Metrics")
        metrics = {
            "Max Gain": latest_trade.get("Max_Gain_%", 0),
            "Max DD": latest_trade.get("Max_Drawdown_%", 0),
            "Entry Vol": latest_trade.get("Entry_Volume", 0),
            "Rel Vol": latest_trade.get("Entry_Rel_Volume_20", 0)
        }
        for name, value in metrics.items():
            st.markdown(f"**{name}:** {value:.1f if isinstance(value, float) else value}")

with tab2:
    st.subheader("📊 Portfolio Performance")
    
    # Portfolio stats
    total_trades = len(df)
    winners = len(df[df["Trade_PnL_%"] > 0])
    win_rate = winners / total_trades * 100
    avg_win = df[df["Trade_PnL_%"] > 0]["Trade_PnL_%"].mean()
    avg_loss = df[df["Trade_PnL_%"] < 0]["Trade_PnL_%"].mean()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Trades", total_trades)
    col2.metric("Win Rate", f"{win_rate:.1f}%")
    col3.metric("Avg PnL", f"{df['Trade_PnL_%'].mean():.1f}%")
    col4.metric("Best Trade", f"{df['Trade_PnL_%'].max():.1f}%")
    
    # Top performers
    st.markdown("### 🟢 Top 5 Winners")
    top_winners = df.nlargest(5, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held", "Exit_Reason"]]
    st.dataframe(top_winners, use_container_width=True)
    
    st.markdown("### 🔴 Biggest 5 Losers")
    top_losers = df.nsmallest(5, "Trade_PnL_%")[["Ticker", "Trade_PnL_%", "Days_Held", "Exit_Reason"]]
    st.dataframe(top_losers, use_container_width=True)
    
    # Exit reason distribution
    if "Exit_Reason" in df.columns:
        st.markdown("### 📋 Exit Reasons")
        exit_counts = df["Exit_Reason"].value_counts()
        st.bar_chart(exit_counts)
