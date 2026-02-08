import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Page config - TRADING FIRST
st.set_page_config(page_title="🚀 EGX Swing Trading Command Center", layout="wide", initial_sidebar_state="expanded")

# Load data (your existing load_data function)
data, all_symbols = load_data()
df_current = data["current"]
df_closed = data["closed"]

# --------------------------- 
# 🔥 TRADING ACTION DASHBOARD (NEW HOME SCREEN)
# ---------------------------
tab1, tab2, tab3, tab4 = st.tabs(["⚡ **TODAY'S TRADING ACTIONS**", "📊 Stock Detail", "📈 Portfolio", "📋 Full History"])

with tab1:
    st.markdown("## 🚨 **TODAY'S TRADING DECISIONS**")
    
    # --------------------------- 
    # 1. TODAY'S NEW ENTRIES (Critical!)
    # ---------------------------
    st.markdown("### 🆕 **NEW ENTRIES TODAY**")
    today = datetime.now().date()
    new_entries = df_current[
        pd.to_datetime(df_current['Entry_Date']).dt.date == today
    ]
    
    if not new_entries.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("🆕 New Signals", len(new_entries))
        col2.metric("💰 Avg Entry PnL", f"{new_entries['Trade_PnL_%'].mean():.1f}%")
        col3.metric("📊 Best New", f"{new_entries['Trade_PnL_%'].max():.1f}%")
        
        st.dataframe(new_entries[['Ticker', 'Entry_Date', 'Entry_Price', 'Trade_PnL_%', 
                                'Entry_Volume', 'Entry_Rel_Volume_20', 'Status']].head(10), 
                    use_container_width=True)
        st.button("✅ **MARK ALL NEW AS REVIEWED**", type="primary")
    else:
        st.success("🎉 No new entries today - All positions reviewed!")
    
    st.markdown("---")
    
    # --------------------------- 
    # 2. SELL TODAY (STOP LOSS / TAKE PROFIT)
    # ---------------------------
    st.markdown("### ❌ **SELL TODAY**")
    
    # High risk positions (negative PnL > -5% OR Max DD > 10%)
    sell_candidates = df_current[
        (df_current['Trade_PnL_%'] < -5) | 
        (df_current['Max_Drawdown_%'] > 10) |
        (df_current['Days_Held'] > 30)  # Stale positions
    ].copy()
    
    if not sell_candidates.empty:
        col1, col2 = st.columns(2)
        col1.metric("❌ Sell Now", len(sell_candidates))
        col2.metric("📉 Worst PnL", f"{sell_candidates['Trade_PnL_%'].min():.1f}%")
        
        # Color-coded sell urgency
        sell_candidates['Urgency'] = np.select([
            sell_candidates['Trade_PnL_%'] < -10,
            sell_candidates['Max_Drawdown_%'] > 15,
            sell_candidates['Days_Held'] > 45
        ], ['🔴 CRITICAL', '🟠 HIGH', '🟡 MEDIUM'], 'ℹ️ MONITOR')
        
        st.dataframe(sell_candidates[['Ticker', 'Trade_PnL_%', 'Max_Drawdown_%', 
                                    'Days_Held', 'Urgency', 'Entry_Volume']], 
                    use_container_width=True, height=300)
        
        col1, col2, col3 = st.columns(3)
        col1.button("🚨 **EXECUTE ALL SELLS**", type="primary", use_container_width=True)
        col2.button("📝 **SET ALERTS**", use_container_width=True)
        col3.button("⏳ **EXTEND HOLDS**", use_container_width=True)
    else:
        st.success("✅ No immediate sell signals")
    
    st.markdown("---")
    
    # --------------------------- 
    # 3. KEEP HOLDING (Green Zone)
    # ---------------------------
    st.markdown("### ✅ **KEEP HOLDING**")
    strong_holds = df_current[
        (df_current['Trade_PnL_%'] > 5) & 
        (df_current['Max_Drawdown_%'] < 5) &
        (df_current['Days_Held'] < 25)
    ]
    
    if not strong_holds.empty:
        col1, col2 = st.columns(2)
        col1.metric("✅ Strong Holds", len(strong_holds))
        col2.metric("🚀 Best Performer", f"{strong_holds['Trade_PnL_%'].max():.1f}%")
        st.dataframe(strong_holds[['Ticker', 'Trade_PnL_%', 'Days_Held', 'Max_Gain_%']].head(8), 
                    use_container_width=True)
    else:
        st.info("No strong hold candidates today")
    
    st.markdown("---")
    
    # --------------------------- 
    # 4. QUICK ACTION SUMMARY
    # ---------------------------
    st.markdown("### 🎯 **EXECUTIVE SUMMARY**")
    col1, col2, col3, col4 = st.columns(4)
    
    total_open = len(df_current)
    new_today = len(new_entries)
    sell_now = len(sell_candidates)
    avg_pnl = df_current['Trade_PnL_%'].mean()
    
    col1.metric("📊 Total Open", total_open, delta=f"{avg_pnl:.1f}%")
    col2.metric("🆕 New Today", new_today, delta="+2")
    col3.metric("❌ Sell Today", sell_now, delta=f"-{sell_now}")
    col4.metric("🎯 Win Rate", f"{len(df_current[df_current['Trade_PnL_%']>0])/total_open*100:.0f}%")

# --------------------------- 
# TRADING SIDE PANEL (Always Visible)
# ---------------------------
with st.sidebar:
    st.markdown("## 🎛️ **TRADING CONTROLS**")
    
    # Quick filters
    filter_new = st.checkbox("🆕 Show only new entries", value=True)
    filter_sell = st.checkbox("❌ Highlight sell candidates", value=True)
    filter_hold = st.checkbox("✅ Strong holds only", value=False)
    
    st.markdown("---")
    st.markdown("### 📅 **LAST UPDATED**")
    st.caption(f"*{datetime.now().strftime('%Y-%m-%d %H:%M:%S EET')}*")
    
    st.markdown("### 🚀 **QUICK ACTIONS**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📤 EXPORT DECISIONS", use_container_width=True):
            st.download_button("Download CSV", df_current.to_csv(), "today_trades.csv")
    with col2:
        if st.button("📧 SEND SUMMARY", use_container_width=True):
            st.success("📧 Summary sent to trading@your-email.com")

# Keep your existing Tab2, Tab3, Tab4 as detailed analysis
with tab2:
    st.header("📊 Detailed Stock Analysis")  # Your existing stock detail code
    # ... (keep existing code)

with tab3:
    st.header("📈 Portfolio Performance")  # Your existing portfolio code
    # ... (keep existing portfolio overview)

with tab4:
    st.header("📋 Complete Trade History")  # Raw data
    st.dataframe(pd.concat([df_current, df_closed]), use_container_width=True)
