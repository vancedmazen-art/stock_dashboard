import streamlit as st
import pandas as pd
import plotly.express as px

# ---------------------------
# Load CSV
# ---------------------------
df = pd.read_csv("StockQuotes.csv")

# ---------------------------
# Preprocess
# ---------------------------
# Convert Report_Date (varchar) to datetime
df['Report_Date'] = pd.to_datetime(df['Report_Date'], format='%Y%m%d')

# ---------------------------
# Streamlit UI
# ---------------------------
st.title("📊 Stock Analysis Dashboard")

# Select a symbol
symbols = df['Ticker'].unique()
symbol = st.selectbox("Select Stock Symbol:", symbols)

# Filter data
stock_df = df[df['Ticker'] == symbol].sort_values('Report_Date')

# Show data
st.subheader(f"Data for {symbol}")
st.dataframe(stock_df.tail(10))  # last 10 rows

# Plot Last_Close Price
fig = px.line(
    stock_df, 
    x='Report_Date', 
    y='Last_Close', 
    title=f"{symbol} Last Close Price",
    labels={'Report_Date': 'Date', 'Last_Close': 'Last Close'}
)
st.plotly_chart(fig, use_container_width=True)
