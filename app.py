import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import os
import numpy as np
import random
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# List of trading insights / fun facts
trading_facts = [
    "🧠 Discipline Wins: Following your rules beats predicting the market.",
    "⏳ Patience Pays: Sometimes the best trade is no trade at all.",
    "📊 Plan Before You Trade: Know your entry and exit before starting.",
    "🎢 Emotions Are the Enemy: Fear and greed cost more than market moves.",
    "💡 Risk Management: Never risk more than you can afford to lose.",
    "🔥 Trend Follower: The trend is your friend until it ends.",
    "⚡ Quick Decisions: Opportunities are fleeting, but rushing is dangerous."
]

selected_facts = random.choice(trading_facts)

# ---------------------------
# LOAD ALL 3 SHEETS + Strategy Metrics
# ---------------------------
def load_data():
    try:
        if not os.path.exists("Complete_Trades_Metrics.xlsx"):
            st.error("❌ Complete_Trades_Metrics.xlsx missing!")
            st.stop()
            return {}, [], pd.DataFrame(), None, None

        closed_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="Closed_Trades")
        current_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="Open_Trades")
        strategy_metrics = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="Best_Strategy_Summary")
        refresh_df = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="refresh_date")
        refresh_date_scalar = refresh_df['refresh_date'].iloc[0]
        refresh_date_obj = pd.to_datetime(refresh_date_scalar).date()
        refresh_date_str = refresh_date_scalar.strftime('%Y-%m-%d')

        if os.path.exists("egx_company_map.csv"):
            company_map = pd.read_csv("egx_company_map.csv")
            if "Symbol" in company_map.columns:
                company_map["Ticker"] = company_map["Symbol"].str.replace("EGX:", "", regex=False)
                closed_trades = closed_trades.merge(company_map, on="Ticker", how="left")
                current_trades = current_trades.merge(company_map, on="Ticker", how="left")

        all_tickers = pd.concat([
            closed_trades['Ticker'].dropna(),
            current_trades['Ticker'].dropna()
        ]).drop_duplicates().sort_values().str.strip().tolist()

        st.success("✅ Load Completed..")
        return {"closed": closed_trades, "current": current_trades}, all_tickers, strategy_metrics, refresh_date_obj, refresh_date_str

    except Exception as e:
        st.error(f"❌ Load failed: {e}")
        st.stop()
        return {}, [], pd.DataFrame(), None, None


st.set_page_config(page_title="🚀 EGX Trading Dashboard", layout="wide")

col1, col2 = st.columns([3, 1])
with col2:
    if st.button("🔄 **FORCE RELOAD**", type="primary"):
        st.rerun()

data, all_symbols, df_strategy, refresh_date_obj, refresh_date_str = load_data()
df_current = data["current"].copy()
df_closed = data["closed"].copy()

df_current_egx30 = df_current[df_current['Ticker'] == 'EGX30'].copy()
df_closed_egx30 = df_closed[df_closed['Ticker'] == 'EGX30'].copy()
df_strategy_egx30 = df_strategy[df_strategy['Ticker'] == 'EGX30'].copy()

df_current_other = df_current[df_current['Ticker'] != 'EGX30'].copy()
df_closed_other = df_closed[df_closed['Ticker'] != 'EGX30'].copy()
all_symbols_other = [s for s in all_symbols if s != 'EGX30']


# ---------------------------
# HELPERS
# ---------------------------
def fix_pyarrow_df(df):
    df_display = df.copy()
    for col in ['Entry_Date', 'Exit_Date']:
        if col in df_display.columns:
            df_display[col] = pd.to_datetime(df_display[col], errors='coerce').dt.strftime('%Y-%m-%d')
    for col in df_display.select_dtypes(include=['object']).columns:
        df_display[col] = df_display[col].astype(str)
    df_display.reset_index(drop=True, inplace=True)
    return df_display


def safe_display(value):
    if pd.isna(value) or value is None or value == "":
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.1f}"
    return str(value)


def fetch_latest_news(symbol: str, max_items=3):
    try:
        API_URL = (
            "https://news-mediator.tradingview.com/news-flow/v2/news?"
            "filter=lang%3Aen&filter=market%3Astock&filter=market_country%3AEG&client=screener"
        )
        r = requests.get(API_URL, timeout=10)
        r.raise_for_status()
        payload = r.json()
    except:
        return []

    result = []
    for news in payload.get("items", []):
        news_id = news.get("id")
        if not news_id:
            continue
        symbols = [
            s.get("symbol", "").replace("EGX:", "")
            for s in news.get("relatedSymbols", [])
            if s.get("symbol", "").startswith("EGX:")
        ]
        if symbol.upper() not in [s.upper() for s in symbols]:
            continue
        published_ts = news.get("published")
        try:
            CAIRO_TZ = pytz.timezone("Africa/Cairo")
            published_dt = datetime.utcfromtimestamp(published_ts).replace(tzinfo=pytz.UTC).astimezone(CAIRO_TZ)
            news_date = published_dt.strftime('%Y-%m-%d %H:%M')
        except:
            news_date = "Recent"
        result.append({
            "title": news.get("title", ""),
            "url": f"https://www.tradingview.com{news.get('storyPath', '')}",
            "provider": news.get("provider", {}).get("name", ""),
            "date": news_date,
            "id": news_id
        })
    return result[:max_items]


# ---------------------------
# 🎨 FRESH BUYS CARD COMPONENT
# ---------------------------
def render_fresh_buys_cards(df, selected_ticker):
    if df.empty:
        return "<p style='color:#6b7280;font-family:monospace;padding:20px'>No fresh buys today.</p>", []

    tickers = df['Ticker'].tolist()

    def fmt(v):
        try:
            return f"{float(v):.2f}"
        except:
            return str(v) if v else '—'

    def fmt1(v):
        try:
            return f"{float(v):.1f}"
        except:
            return str(v) if v else '—'

    cards_html = []
    for _, row in df.iterrows():
        ticker = row.get('Ticker', '')
        entry_price = row.get('Entry_Price', '')
        stop_loss = row.get('Stop_Loss', '')
        target = row.get('Target_Price', '')
        risk = row.get('Risk_%', '')
        reward = row.get('Reward_%', '')
        rr = row.get('RR_Ratio', '')
        breaks_tl = row.get('Breaks_Trendline', '')
        entry_date = str(row.get('Entry_Date', ''))[:10]
        is_selected = (ticker == selected_ticker)
        selected_class = "selected" if is_selected else ""
        tl_badge = '<span class="tl-badge">📐 TL Break</span>' if str(breaks_tl).strip().lower() in ['true', 'yes', '1'] else ''

        cards_html.append(f"""
        <div class="buy-card {selected_class}" onclick="selectTicker('{ticker}')">
            <div class="card-header">
                <span class="ticker-name">{ticker}</span>
                {tl_badge}
                <span class="entry-date">{entry_date}</span>
            </div>
            <div class="price-row">
                <span class="price-label">Entry</span>
                <span class="price-value">{fmt(entry_price)}</span>
            </div>
            <div class="metrics-grid">
                <div class="metric-item">
                    <div class="metric-label">Stop Loss</div>
                    <div class="metric-value loss">{fmt(stop_loss)}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Target</div>
                    <div class="metric-value gain">{fmt(target)}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Risk %</div>
                    <div class="metric-value loss">{fmt1(risk)}%</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">Reward %</div>
                    <div class="metric-value gain">{fmt1(reward)}%</div>
                </div>
            </div>
            <div class="rr-bar">
                <span class="rr-label">R:R</span>
                <span class="rr-value">{fmt1(rr)}</span>
            </div>
        </div>""")

    default_ticker = selected_ticker or (tickers[0] if tickers else '')

    html = f"""<!DOCTYPE html>
<html>
<head>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background: transparent;
    font-family: 'DM Mono', monospace;
    padding: 4px 2px 8px 2px;
}}
.cards-wrap {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 10px;
}}
.buy-card {{
    background: linear-gradient(145deg, #0f172a 0%, #0a1a12 100%);
    border: 1px solid #1e3a2a;
    border-radius: 14px;
    padding: 14px 15px 12px;
    cursor: pointer;
    transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
    position: relative;
    overflow: hidden;
    user-select: none;
}}
.buy-card::after {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #10b98160, transparent);
    opacity: 0;
    transition: opacity 0.15s;
}}
.buy-card:hover {{
    transform: translateY(-3px);
    border-color: #10b981;
    box-shadow: 0 8px 30px #10b98122, 0 0 0 1px #10b98140;
}}
.buy-card:hover::after {{ opacity: 1; }}
.buy-card.selected {{
    border-color: #10b981;
    box-shadow: 0 0 0 2px #10b98155, 0 8px 30px #10b98130;
    background: linear-gradient(145deg, #0f2318 0%, #091a10 100%);
}}
.buy-card.selected::after {{ opacity: 1; }}
.card-header {{
    display: flex;
    align-items: center;
    gap: 7px;
    margin-bottom: 10px;
    flex-wrap: wrap;
}}
.ticker-name {{
    font-family: 'Syne', sans-serif;
    font-size: 16px;
    font-weight: 800;
    color: #f0fdf4;
    letter-spacing: 0.04em;
}}
.tl-badge {{
    font-size: 9px;
    background: #10b98120;
    color: #10b981;
    border: 1px solid #10b98140;
    border-radius: 4px;
    padding: 2px 5px;
    letter-spacing: 0.05em;
}}
.entry-date {{
    margin-left: auto;
    font-size: 10px;
    color: #4b6a57;
}}
.price-row {{
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid #1e3a2a;
}}
.price-label {{
    font-size: 10px;
    color: #4b6a57;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}
.price-value {{
    font-size: 18px;
    font-weight: 500;
    color: #d1fae5;
}}
.metrics-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 7px 10px;
    margin-bottom: 10px;
}}
.metric-item {{ display: flex; flex-direction: column; gap: 2px; }}
.metric-label {{
    font-size: 9px;
    color: #4b6a57;
    text-transform: uppercase;
    letter-spacing: 0.07em;
}}
.metric-value {{ font-size: 13px; font-weight: 500; }}
.metric-value.gain {{ color: #34d399; }}
.metric-value.loss {{ color: #f87171; }}
.rr-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #0a1f12;
    border-radius: 6px;
    padding: 5px 10px;
    border: 1px solid #1e3a2a;
}}
.rr-label {{
    font-size: 10px;
    color: #4b6a57;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}}
.rr-value {{ font-size: 14px; font-weight: 500; color: #fbbf24; }}
</style>
</head>
<body>
    <div class="cards-wrap">
        {''.join(cards_html)}
    </div>
    <script>
        function selectTicker(ticker) {{
            window.parent.postMessage({{type: 'streamlit:setComponentValue', value: ticker}}, '*');
        }}
        window.addEventListener('load', function() {{
            const defaultTicker = "{default_ticker}";
            if (defaultTicker) {{
                setTimeout(() => selectTicker(defaultTicker), 80);
            }}
        }});
    </script>
</body>
</html>"""
    return html, tickers


# ---------------------------
# DATE PROCESSING
# ---------------------------
df_current_internal = df_current_other.copy()
df_closed_internal = df_closed_other.copy()
df_current_internal['Entry_Date'] = pd.to_datetime(df_current_internal['Entry_Date'], errors='coerce').dt.date
df_current_internal['Target_Hit_Date'] = pd.to_datetime(df_current_internal['Target_Hit_Date'], errors='coerce').dt.date
df_closed_internal['Entry_Date'] = pd.to_datetime(df_closed_internal['Entry_Date'], errors='coerce').dt.date
df_closed_internal['Exit_Date'] = pd.to_datetime(df_closed_internal['Exit_Date'], errors='coerce').dt.date


# ---------------------------
# 5-TAB DASHBOARD
# ---------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⚡ **TODAY'S ACTIONS**",
    "📊 **STOCK DETAIL**",
    "📈 **PORTFOLIO**",
    "📋 **HISTORY**",
    "📊 **Overall Market Sentiment**"
])


# ── TAB 1: TODAY'S ACTIONS ───────────────────────────────────────────────────
with tab1:
    st.markdown("### 🚨 **TODAY'S TRADING DECISIONS**")
    st.caption(f"📅 Refresh Date: {refresh_date_str}")

    new_buys = df_current_other[df_current_internal['Entry_Date'] == refresh_date_obj].copy()
    new_buys_with_strategy = new_buys.merge(df_strategy[['Ticker', 'Best_Strategy']], on='Ticker', how='left')

    # Session state init
    if "fresh_buy_ticker" not in st.session_state:
        st.session_state.fresh_buy_ticker = (
            new_buys_with_strategy['Ticker'].iloc[0]
            if len(new_buys_with_strategy) > 0 else None
        )

    # Section header
    st.markdown(
        "<div style='font-family:Syne,sans-serif;font-size:11px;font-weight:700;"
        "letter-spacing:0.18em;text-transform:uppercase;color:#10b981;"
        "margin:18px 0 10px;display:flex;align-items:center;gap:10px;'>"
        "🆕 &nbsp;Fresh Buys"
        "<span style='flex:1;height:1px;background:linear-gradient(90deg,#10b98140,transparent);"
        "display:inline-block;margin-left:8px'></span></div>",
        unsafe_allow_html=True
    )

    if len(new_buys_with_strategy) > 0:
        cards_col, chart_col = st.columns([5, 4])

        with cards_col:
            cards_html, tickers_list = render_fresh_buys_cards(
                new_buys_with_strategy, st.session_state.fresh_buy_ticker
            )
            card_rows = max(1, -(-len(tickers_list) // 2))  # ceiling div
            component_height = min(card_rows * 200 + 20, 620)

            clicked_ticker = st.components.v1.html(
                cards_html, height=component_height, scrolling=True
            )
            if clicked_ticker and clicked_ticker != st.session_state.fresh_buy_ticker:
                st.session_state.fresh_buy_ticker = clicked_ticker
                st.rerun()

        with chart_col:
            chart_ticker = st.session_state.fresh_buy_ticker
            if chart_ticker:
                st.markdown(
                    f"<div style='font-family:DM Mono,monospace;font-size:12px;"
                    f"color:#10b981;margin-bottom:6px;letter-spacing:0.05em;'>"
                    f"📈 EGX : <strong style='color:#d1fae5;font-size:15px'>"
                    f"{chart_ticker}</strong> — Daily</div>",
                    unsafe_allow_html=True
                )
                st.components.v1.iframe(
                    f"https://s.tradingview.com/widgetembed/?symbol=EGX:{chart_ticker}"
                    f"&interval=D&theme=Dark&style=9&hide_side_toolbar=1"
                    f"&allow_symbol_change=0&save_image=0",
                    height=component_height
                )
    else:
        st.info("No fresh buys today")

    # Take Profit
    take_profit = df_current_other[
        (df_current_internal['Target_Hit_Date'] == refresh_date_obj) &
        (df_current_internal['Bars_To_Target'] != 0)
    ].copy()
    take_profit_with_strategy = take_profit.merge(df_strategy[['Ticker', 'Best_Strategy']], on='Ticker', how='left')

    st.markdown("#### 🎯 **Take Profit**")
    col1, col2, col3 = st.columns(3)
    col2.metric("💰 Best PnL", f"{take_profit['Trade_PnL_%'].max():.1f}%" if len(take_profit) > 0 else "-")
    col3.metric("📊 Avg PnL", f"{take_profit['Trade_PnL_%'].mean():.1f}%" if len(take_profit) > 0 else "-")
    st.dataframe(fix_pyarrow_df(take_profit_with_strategy[[
        'Ticker', 'Entry_Date', 'Entry_Price', 'Current_Price',
        'Stop_Loss', 'Target_Price', 'Risk_%', 'Reward_%', 'RR_Ratio', 'Bars_To_Target', 'Trade_PnL_%'
    ]]), use_container_width=True, height=300)

    # Close Now
    close_now = df_closed_other[df_closed_internal['Exit_Date'] == refresh_date_obj].copy()

    st.markdown("#### ❌ **CLOSE NOW**")
    col1, col2, col3 = st.columns(3)
    col2.metric("💰 Best PnL", f"{close_now['Trade_PnL_%'].max():.1f}%" if len(close_now) > 0 else "-")
    col3.metric("📊 Avg PnL", f"{close_now['Trade_PnL_%'].mean():.1f}%" if len(close_now) > 0 else "-")
    st.dataframe(fix_pyarrow_df(close_now[[
        'Ticker', 'Entry_Date', 'Exit_Price', 'Trade_PnL_%', 'Entry_Price', 'Days_Held'
    ]]), use_container_width=True, height=200)

    # Holds
    holds = df_current_other[df_current_internal['Entry_Date'] != refresh_date_obj].copy()
    holds_with_strategy = holds.merge(df_strategy[['Ticker', 'Best_Strategy']], on='Ticker', how='left')

    st.markdown("#### ✅ **HOLDS**")
    col1, col2, col3 = st.columns(3)
    col2.metric("🚀 Best PnL", f"{holds['Trade_PnL_%'].max():.1f}%" if len(holds) > 0 else "-")
    col3.metric("📊 Avg PnL", f"{holds['Trade_PnL_%'].mean():.1f}%" if len(holds) > 0 else "-")
    st.dataframe(fix_pyarrow_df(
        holds_with_strategy[[
            'Ticker', 'Current_Price', 'Entry_Price', 'Entry_Date',
            'Trade_PnL_%', 'Days_Held', 'Breaks_Trendline', 'Anchor_High', 'Buffer_Gain'
        ]].rename(columns={'Anchor_High': 'Target_Price', 'Buffer_Gain': 'Target_Gain_%'})
    ), use_container_width=True, height=200)


# ── TAB 2: STOCK DETAIL ───────────────────────────────────────────────────────
with tab2:
    selected_symbol = st.selectbox("🔍 Choose Stock:", all_symbols_other)

    current_stock_df = df_current_other[df_current_other["Ticker"] == selected_symbol]
    stock_history = df_closed_other[df_closed_other["Ticker"] == selected_symbol].sort_values("Entry_Date", ascending=False)
    strategy_for_stock = df_strategy[df_strategy["Ticker"] == selected_symbol]

    left_col, right_col = st.columns([3, 1])

    with left_col:
        st.markdown(f"### 📈 **{selected_symbol}**")
        if len(current_stock_df) > 0:
            st.markdown("#### 🟢 **CURRENT TRADES**")
            st.dataframe(fix_pyarrow_df(current_stock_df[[
                'Entry_Date', 'Entry_Price', 'Current_Price', 'Trade_PnL_%', 'Days_Held'
            ]]), use_container_width=True, height=200)
        else:
            st.info("⚠️ No current open trades")

        st.markdown("#### 📊 **CHART**")
        st.components.v1.iframe(
            f"https://s.tradingview.com/widgetembed/?symbol=EGX:{selected_symbol}&interval=D&theme=Light&style=9",
            height=400
        )

        st.markdown("#### 📰 **LATEST NEWS** (Top 3)")
        news_items = fetch_latest_news(selected_symbol, max_items=3)
        if news_items:
            for i, n in enumerate(news_items, 1):
                st.markdown(f"**{i}. {n['title']}**")
                st.caption(f"📅 **{n['date']}** | {n['provider']} | [Read more]({n['url']})")
                st.divider()
        else:
            st.info("📰 No recent news for this stock")

        st.markdown(f"#### 📋 **HISTORY** ({len(stock_history)} closed trades)")
        if len(stock_history) > 0:
            st.dataframe(fix_pyarrow_df(stock_history), use_container_width=True, height=250)

    with right_col:
        st.markdown("#### 🎯 **STRATEGY METRICS**")
        if len(strategy_for_stock) > 0:
            strat = strategy_for_stock.iloc[0]
            st.metric("🏆 Best Strategy", strat['Best_Strategy'])
            st.metric("📊 Score", f"{safe_display(strat['composite_score'])}")
            st.metric("✅ Win Rate", f"{safe_display(strat['win_rate'])}%")
            st.metric("🎯 Median PnL", f"{safe_display(strat['median_pnl'])}%")
            st.metric("📈 Total Trades", safe_display(strat['total_trades']))
        else:
            st.info("No strategy metrics")

        st.markdown("---")
        st.markdown("#### 📊 **TRADE METRICS**")
        if len(current_stock_df) > 0:
            latest = current_stock_df.iloc[0]
            st.metric("💰 PnL", f"{safe_display(latest['Trade_PnL_%'])}%")
            st.metric("⏳ Days", safe_display(latest['Days_Held']))


# ── TAB 3: PORTFOLIO ──────────────────────────────────────────────────────────
with tab3:
    st.markdown("### 📈 **PORTFOLIO OVERVIEW**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 Open", len(df_current_other))
    col2.metric("📋 Closed", len(df_closed_other))
    col3.metric("✅ Win Rate",
        f"{len(df_closed_other[df_closed_other['Trade_PnL_%'] > 0]) / len(df_closed_other) * 100:.1f}%"
        if len(df_closed_other) > 0 else "0%")
    col4.metric("💰 Avg PnL", f"{df_closed_other['Trade_PnL_%'].mean():.1f}%")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🏆 **ALL STRATEGIES**")
        top_strategies = fix_pyarrow_df(
            df_strategy[df_strategy['Ticker'] != 'EGX30']
            [['Ticker', 'Best_Strategy', 'composite_score', 'win_rate', 'median_pnl']]
            .sort_values('win_rate', ascending=False)
        )
        st.dataframe(top_strategies, use_container_width=True)


# ── TAB 4: FULL HISTORY ───────────────────────────────────────────────────────
with tab4:
    st.markdown("### 📋 **COMPLETE HISTORY** - Filtered View")
    full_history_raw = df_closed_other.copy()

    col1, col2, col3 = st.columns(3)
    with col1:
        ticker_filter = st.selectbox(
            "🔍 Ticker",
            options=['ALL'] + sorted(full_history_raw['Ticker'].dropna().unique().tolist()),
            index=0, key="ticker_filter"
        )
    with col2:
        sector_filter = st.multiselect(
            "🏢 Sector",
            options=sorted(full_history_raw['Sector'].dropna().unique().tolist()),
            default=[], key="sector_filter"
        )

    filtered_history = full_history_raw.copy()
    if ticker_filter != 'ALL':
        filtered_history = filtered_history[filtered_history['Ticker'] == ticker_filter]
    if sector_filter:
        filtered_history = filtered_history[filtered_history['Sector'].isin(sector_filter)]

    if 'Trade_PnL_%' in filtered_history.columns and len(filtered_history) > 0:
        filtered_pnl = pd.to_numeric(filtered_history['Trade_PnL_%'], errors='coerce').dropna()
        col1, col2, col3 = st.columns(3)
        with col1:
            wr = len(filtered_pnl[filtered_pnl > 0]) / len(filtered_pnl) * 100 if len(filtered_pnl) > 0 else 0
            st.metric("✅ Win Rate", f"{wr:.1f}%")
        with col2:
            st.metric("🎯 Median PnL", f"{filtered_pnl.median():.1f}%")
        with col3:
            st.metric("📈 Total Trades", f"{len(filtered_pnl):,}")
    else:
        st.info("📊 Select filters to see aggregate metrics")

    st.divider()
    if len(filtered_history) > 0:
        st.dataframe(fix_pyarrow_df(filtered_history.sort_values("Entry_Date", ascending=False)),
                     use_container_width=True, height=500)
        st.caption(f"📋 Showing {len(filtered_history):,} of {len(full_history_raw):,} total trades")
    else:
        st.warning("⚠️ No trades match your filters")


# ── TAB 5: EGX30 SENTIMENT ────────────────────────────────────────────────────
with tab5:
    st.markdown("## 📊 **EGX30 – Market Overview & Sentiment**")
    open_trades = len(df_current_egx30)
    if open_trades > 0:
        sentiment_text = "🟢 Positive"
        sentiment_emoji = "🚀📈"
    else:
        sentiment_text = "🔴 Neutral / Cautious"
        sentiment_emoji = "⚠️📉"
    st.markdown(f"### {sentiment_emoji} Market Sentiment: **{sentiment_text}**")
    st.divider()

    left, right = st.columns([2.2, 1])
    with left:
        st.markdown("### 📈 **EGX30 Technical Chart**")
        st.components.v1.iframe(
            "https://s.tradingview.com/widgetembed/?symbol=EGX:EGX30&interval=D&theme=Light&style=9",
            height=480
        )
        st.divider()
        st.markdown("### 🟢 **Open Positions**")
        if len(df_current_egx30) > 0:
            st.dataframe(fix_pyarrow_df(df_current_egx30[[
                'Entry_Date', 'Entry_Price', 'Trade_PnL_%', 'Days_Held', 'Status'
            ]]), use_container_width=True, height=220)
        else:
            st.info("No open EGX30 trades")
        st.divider()
        st.markdown("### 📋 **Closed History**")
        if len(df_closed_egx30) > 0:
            st.dataframe(fix_pyarrow_df(df_closed_egx30.sort_values("Exit_Date", ascending=False)[[
                'Entry_Date', 'Exit_Date', 'Entry_Price', 'Exit_Price', 'Trade_PnL_%', 'Days_Held', 'Exit_Reason'
            ]]), use_container_width=True, height=260)
        else:
            st.info("No closed EGX30 trades")

    with right:
        st.markdown("### 🎯 **Strategy Health**")
        if len(df_strategy_egx30) > 0:
            strat = df_strategy_egx30.iloc[0]
            st.metric("🏆 Best", strat['Best_Strategy'])
            st.metric("📊 Score", safe_display(strat['composite_score']))
            st.metric("✅ Win", f"{safe_display(strat['win_rate'])}%")
            st.metric("🎯 Median", f"{safe_display(strat['median_pnl'])}%")
            st.metric("📈 Trades", safe_display(strat['total_trades']))
        else:
            st.warning("No strategy metrics")
        st.divider()

        st.markdown("### 🧭 **Support / Resistance**")
        eg30_latest = None
        if len(df_current_egx30) > 0:
            eg30_latest = df_current_egx30.loc[df_current_egx30['Entry_Date'].idxmax()]
        if eg30_latest is not None:
            has_support = 'Exit_Support' in eg30_latest and pd.notna(eg30_latest['Exit_Support'])
            has_resistance = 'Exit_Resistance' in eg30_latest and pd.notna(eg30_latest['Exit_Resistance'])
            if has_support:
                st.metric("🟢 Support", safe_display(eg30_latest['Exit_Support']))
            if has_resistance:
                st.metric("🔴 Resistance", safe_display(eg30_latest['Exit_Resistance']))
            if not has_support and not has_resistance:
                st.info("No support / resistance levels found")
        else:
            st.info("No open EGX30 trades")
        st.divider()

        st.markdown("### 📰 **Market News** (Top 5)")
        news = fetch_latest_news("EGX30", max_items=5)
        if news:
            for i, n in enumerate(news, 1):
                st.markdown(f"**{i}. {n['title']}**")
                st.caption(f"📢 {n['provider']} | [Read more]({n['url']})")
                st.divider()
        else:
            st.info("No recent EGX30 news")


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
new_buys_other = df_current_other[df_current_internal['Entry_Date'] == refresh_date_obj]
close_now_other = df_closed_other[df_closed_internal['Exit_Date'] == refresh_date_obj]
holds_other = df_current_other[df_current_internal['Entry_Date'] != refresh_date_obj]
new_buys_tickers = set(new_buys_other['Ticker'].dropna().str.strip())
close_now_tickers = set(close_now_other['Ticker'].dropna().str.strip())
holds_tickers = set(holds_other['Ticker'].dropna().str.strip())

with st.sidebar:
    st.markdown("### 🎛️ **TRADING STATUS**")
    st.info(f"🆕 New: {len(new_buys_tickers)} | ❌ Closed: {len(close_now_tickers)} | ✅ Holds: {len(holds_tickers)}")
    st.caption(f"📅 Updated: {refresh_date_str}")
    st.markdown(f"### {sentiment_emoji} Market: **{sentiment_text}**")
    st.markdown("---")
    st.markdown("### 💡 Trading Insights & Fun Facts")
    st.markdown(f"- {selected_facts}")

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 12px;
                padding: 20px; margin-top: 40px;'>
    <strong>⚠️ Important Disclaimer</strong><br>
    This EGX Trading Dashboard provides market data for educational purposes only.
    It does <strong>NOT</strong> constitute financial, investment, or trading advice.
    All trading carries significant risk of loss.
    Consult a licensed financial advisor before making any investment decisions.
    </div>
    """,
    unsafe_allow_html=True
)
