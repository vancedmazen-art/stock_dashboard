import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import os
import numpy as np
import random
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------
# CHART
# ---------------------------
@st.cache_data(ttl=3600)
def load_chart_data():
    url = "https://raw.githubusercontent.com/vancedmazen-art/stock_dashboard/main/chart_6m.csv"
    df = pd.read_csv(url, parse_dates=['datetime'])
    df.columns = df.columns.str.strip().str.lower()
    return df


def draw_candle_chart(ticker, height=580, stop_loss=None, target=None, entry=None):
    df_all = load_chart_data()
    df = df_all[df_all['symbol'] == ticker].copy().sort_values('datetime')

    if df.empty:
        st.warning(f"No chart data for {ticker}")
        return

    df['date_str'] = df['datetime'].dt.strftime('%Y-%m-%d')
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    vol_colors = ['#10b981' if c >= o else '#f87171'
                  for c, o in zip(df['close'], df['open'])]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.75, 0.25])

    fig.add_trace(go.Candlestick(
        x=df['date_str'], open=df['open'], high=df['high'],
        low=df['low'], close=df['close'],
        increasing=dict(line=dict(color='#10b981', width=1), fillcolor='rgba(0,0,0,0)'),
        decreasing=dict(line=dict(color='#f87171', width=1), fillcolor='rgba(0,0,0,0)'),
        name=ticker, showlegend=False,
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df['date_str'], y=df['ema20'], mode='lines',
        line=dict(color='#facc15', width=1.5), name='EMA 20',
    ), row=1, col=1)

    if stop_loss:
        fig.add_hline(y=stop_loss, row=1, col=1,
                      line=dict(color='#f87171', width=1.5, dash='dash'),
                      annotation_text=f"Stop  {stop_loss:.2f}",
                      annotation_position="right",
                      annotation_font=dict(color='#f87171', size=11))
    if entry:
        fig.add_hline(y=entry, row=1, col=1,
                      line=dict(color='#94a3b8', width=1.5, dash='dot'),
                      annotation_text=f"Entry  {entry:.2f}",
                      annotation_position="right",
                      annotation_font=dict(color='#94a3b8', size=11))
    if target:
        fig.add_hline(y=target, row=1, col=1,
                      line=dict(color='#10b981', width=1.5, dash='dash'),
                      annotation_text=f"Target  {target:.2f}",
                      annotation_position="right",
                      annotation_font=dict(color='#10b981', size=11))

    fig.add_trace(go.Bar(
        x=df['date_str'], y=df['volume'],
        marker_color=vol_colors, marker_opacity=0.7,
        name='Volume', showlegend=False,
    ), row=2, col=1)

    x_range_end = len(df) + 15
    fig.update_layout(
        title=dict(text=f"EGX: {ticker}", font=dict(size=15, color='#d1fae5'), x=0.01),
        paper_bgcolor='#0f172a', plot_bgcolor='#0a1a12',
        font=dict(color='#9ca3af', family='DM Mono'),
        height=height, margin=dict(l=10, r=100, t=45, b=50),
        dragmode='zoom',
        xaxis=dict(rangeslider=dict(visible=False), showticklabels=False),
        xaxis2=dict(rangeslider=dict(visible=False)),
        legend=dict(bgcolor='#0f172a', bordercolor='#1e3a2a',
                    font=dict(color='#9ca3af', size=11), x=0.01, y=0.99),
        modebar=dict(bgcolor='#0f172a', color='#4b6a57', activecolor='#10b981'),
    )
    axis_style = dict(gridcolor='#1e3a2a', showgrid=True,
                      showline=True, linecolor='#1e3a2a', side='right')
    fig.update_xaxes(gridcolor='#1e3a2a', showgrid=True, type='category',
                     tickangle=-45, nticks=12, range=[0, x_range_end], row=2, col=1)
    fig.update_xaxes(showgrid=False, type='category',
                     range=[0, x_range_end], showticklabels=False, row=1, col=1)
    fig.update_yaxes(**axis_style, row=1, col=1)
    fig.update_yaxes(**axis_style, tickformat='.2s',
                     title=dict(text='Vol', font=dict(size=10, color='#4b6a57')),
                     row=2, col=1)

    st.plotly_chart(fig, use_container_width=True,
                    config={'displayModeBar': True, 'scrollZoom': True,
                            'modeBarButtonsToRemove': ['toImage', 'sendDataToCloud']})


# ---------------------------
# HELPERS
# ---------------------------
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


def load_data():
    try:
        if not os.path.exists("Complete_Trades_Metrics.xlsx"):
            st.error("❌ Complete_Trades_Metrics.xlsx missing!")
            st.stop()
            return {}, [], pd.DataFrame(), None, None

        closed_trades  = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="Closed_Trades")
        current_trades = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="Open_Trades")
        strategy_metrics = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="Best_Strategy_Summary")
        refresh_df     = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="refresh_date")
        refresh_date_scalar = refresh_df['refresh_date'].iloc[0]
        refresh_date_obj = pd.to_datetime(refresh_date_scalar).date()
        refresh_date_str = refresh_date_scalar.strftime('%Y-%m-%d')

        if os.path.exists("egx_company_map.csv"):
            company_map = pd.read_csv("egx_company_map.csv")
            if "Symbol" in company_map.columns:
                company_map["Ticker"] = company_map["Symbol"].str.replace("EGX:", "", regex=False)
                closed_trades  = closed_trades.merge(company_map,  on="Ticker", how="left")
                current_trades = current_trades.merge(company_map, on="Ticker", how="left")

        all_tickers = pd.concat([
            closed_trades['Ticker'].dropna(),
            current_trades['Ticker'].dropna()
        ]).drop_duplicates().sort_values().str.strip().tolist()

        st.success("✅ Data loaded")
        return ({"closed": closed_trades, "current": current_trades},
                all_tickers, strategy_metrics, refresh_date_obj, refresh_date_str)
    except Exception as e:
        st.error(f"❌ Load failed: {e}")
        st.stop()
        return {}, [], pd.DataFrame(), None, None


def fix_pyarrow_df(df):
    df_display = df.copy()
    for col in ['Entry_Date', 'Exit_Date']:
        if col in df_display.columns:
            df_display[col] = pd.to_datetime(df_display[col], errors='coerce').dt.strftime('%Y-%m-%d')
    for col in df_display.select_dtypes(include=['object']).columns:
        df_display[col] = df_display[col].astype(str)
    df_display.reset_index(drop=True, inplace=True)
    return df_display


def safe(v, dec=1):
    try:
        if pd.isna(v): return "—"
        return f"{float(v):.{dec}f}"
    except:
        return str(v) if v else "—"


def fetch_latest_news(symbol, max_items=3):
    try:
        r = requests.get(
            "https://news-mediator.tradingview.com/news-flow/v2/news?"
            "filter=lang%3Aen&filter=market%3Astock&filter=market_country%3AEG&client=screener",
            timeout=10)
        r.raise_for_status()
        payload = r.json()
    except:
        return []
    result = []
    for news in payload.get("items", []):
        news_id = news.get("id")
        if not news_id:
            continue
        syms = [s.get("symbol", "").replace("EGX:", "")
                for s in news.get("relatedSymbols", [])
                if s.get("symbol", "").startswith("EGX:")]
        if symbol.upper() not in [s.upper() for s in syms]:
            continue
        try:
            tz = pytz.timezone("Africa/Cairo")
            dt = datetime.utcfromtimestamp(news["published"]).replace(tzinfo=pytz.UTC).astimezone(tz)
            nd = dt.strftime('%Y-%m-%d %H:%M')
        except:
            nd = "Recent"
        result.append({"title": news.get("title",""),
                        "url": f"https://www.tradingview.com{news.get('storyPath','')}",
                        "provider": news.get("provider",{}).get("name",""),
                        "date": nd})
    return result[:max_items]


def get_levels(row):
    sl = float(row['Stop_Loss'])    if pd.notna(row.get('Stop_Loss'))    else None
    en = float(row['Entry_Price'])  if pd.notna(row.get('Entry_Price'))  else None
    tg = float(row['Target_Price']) if pd.notna(row.get('Target_Price')) else None
    return sl, en, tg


# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(page_title="🚀 EGX Dashboard", layout="wide")

# Inject minimal CSS — only typography & radio styling, no HTML components
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');
div[data-testid="stRadio"] label {
    font-family: 'DM Mono', monospace !important;
    font-size: 13px !important;
    padding: 4px 0 !important;
}
div[data-testid="metric-container"] {
    background: #0f172a;
    border: 1px solid #1e3a2a;
    border-radius: 10px;
    padding: 10px 14px;
}
</style>
""", unsafe_allow_html=True)

# Header
c1, c2 = st.columns([5, 1])
with c1:
    st.markdown("# 🚀 EGX Trading Dashboard")
with c2:
    if st.button("🔄 Reload", type="primary"):
        st.rerun()

# Load data
data, all_symbols, df_strategy, refresh_date_obj, refresh_date_str = load_data()
df_current = data["current"].copy()
df_closed  = data["closed"].copy()
st.caption(f"📅 Data as of: **{refresh_date_str}**")

# Split EGX30
df_current_egx30 = df_current[df_current['Ticker'] == 'EGX30'].copy()
df_closed_egx30  = df_closed[df_closed['Ticker']   == 'EGX30'].copy()
df_current_other = df_current[df_current['Ticker'] != 'EGX30'].copy()
df_closed_other  = df_closed[df_closed['Ticker']   != 'EGX30'].copy()

# Date masks
df_ci = df_current_other.copy()
df_xi = df_closed_other.copy()
df_ci['Entry_Date']      = pd.to_datetime(df_ci['Entry_Date'],      errors='coerce').dt.date
df_ci['Target_Hit_Date'] = pd.to_datetime(df_ci['Target_Hit_Date'], errors='coerce').dt.date
df_xi['Entry_Date']      = pd.to_datetime(df_xi['Entry_Date'],      errors='coerce').dt.date
df_xi['Exit_Date']       = pd.to_datetime(df_xi['Exit_Date'],       errors='coerce').dt.date

fresh_buys_df  = df_current_other[df_ci['Entry_Date'] == refresh_date_obj].copy()
take_profit_df = df_current_other[
    (df_ci['Target_Hit_Date'] == refresh_date_obj) &
    (df_ci['Bars_To_Target'] != 0)
].copy()
close_now_df = df_closed_other[df_xi['Exit_Date'] == refresh_date_obj].copy()
holds_df     = df_current_other[df_ci['Entry_Date'] != refresh_date_obj].copy()

# EGX30 sentiment
if len(df_current_egx30) > 0:
    sentiment_text, sentiment_emoji = "Positive", "🚀📈"
else:
    sentiment_text, sentiment_emoji = "Neutral / Cautious", "⚠️📉"

# Sidebar
with st.sidebar:
    st.markdown("### 🎛️ Status")
    st.metric("🆕 Fresh Buys",  len(fresh_buys_df))
    st.metric("🎯 Take Profit", len(take_profit_df))
    st.metric("❌ Close Now",   len(close_now_df))
    st.metric("✅ Holds",       len(holds_df))
    st.caption(f"📅 {refresh_date_str}")
    st.markdown(f"### {sentiment_emoji} {sentiment_text}")
    st.markdown("---")
    st.markdown(f"*{selected_facts}*")


# ---------------------------
# REUSABLE PANEL: radio list + chart
# ---------------------------
def stock_panel(source_df, session_key, metric_cols, show_levels=True, show_news=True):
    """
    Left: radio button list of tickers.
    Right: metrics strip + candlestick chart + optional news.
    metric_cols: list of (label, col_name)
    """
    if source_df.empty:
        st.info("Nothing here today.")
        return

    tickers = source_df['Ticker'].tolist()

    # Radio — native Streamlit, no HTML
    selected = st.radio(
        "Select stock",
        options=tickers,
        key=session_key,
        label_visibility="collapsed",
        horizontal=False,
    )

    st.divider()

    if selected:
        row = source_df[source_df['Ticker'] == selected].iloc[0]

        # Metrics strip
        valid_cols = [(lbl, col) for lbl, col in metric_cols if col in source_df.columns]
        if valid_cols:
            cols = st.columns(len(valid_cols))
            for i, (lbl, col) in enumerate(valid_cols):
                cols[i].metric(lbl, safe(row.get(col)))

        # Levels
        sl = en = tg = None
        if show_levels:
            sl, en, tg = get_levels(row)

        draw_candle_chart(selected, height=560, stop_loss=sl, target=tg, entry=en)

        # News
        if show_news:
            st.markdown("#### 📰 Latest News")
            items = fetch_latest_news(selected, max_items=3)
            if items:
                for n in items:
                    st.markdown(f"**{n['title']}**")
                    st.caption(f"📅 {n['date']} | {n['provider']} | [Read]({n['url']})")
                    st.divider()
            else:
                st.caption("No recent news.")


# ---------------------------
# TABS
# ---------------------------
tab_buys, tab_tp, tab_close, tab_holds, tab_egx30 = st.tabs([
    f"🆕 Fresh Buys ({len(fresh_buys_df)})",
    f"🎯 Take Profit ({len(take_profit_df)})",
    f"❌ Close Now ({len(close_now_df)})",
    f"✅ Holds ({len(holds_df)})",
    "📊 EGX30",
])


# ── TAB 1: FRESH BUYS ────────────────────────────────────────────────────────
with tab_buys:
    if fresh_buys_df.empty:
        st.info("No fresh buys today.")
    else:
        left, right = st.columns([1, 3])
        with left:
            stock_panel(
                fresh_buys_df, "buy_ticker",
                metric_cols=[
                    ("Entry",   "Entry_Price"),
                    ("Stop",    "Stop_Loss"),
                    ("Target",  "Target_Price"),
                    ("Risk %",  "Risk_%"),
                    ("Reward%", "Reward_%"),
                    ("R:R",     "RR_Ratio"),
                ],
                show_levels=True, show_news=True,
            )
        with right:
            pass  # chart is drawn inside stock_panel via st.columns context


# ── TAB 2: TAKE PROFIT ───────────────────────────────────────────────────────
with tab_tp:
    if take_profit_df.empty:
        st.info("No take profit signals today.")
    else:
        stock_panel(
            take_profit_df, "tp_ticker",
            metric_cols=[
                ("Entry",   "Entry_Price"),
                ("Current", "Current_Price"),
                ("PnL %",   "Trade_PnL_%"),
                ("Target",  "Target_Price"),
                ("Days",    "Days_Held"),
                ("R:R",     "RR_Ratio"),
            ],
            show_levels=True, show_news=True,
        )


# ── TAB 3: CLOSE NOW ─────────────────────────────────────────────────────────
with tab_close:
    if close_now_df.empty:
        st.info("Nothing to close today.")
    else:
        stock_panel(
            close_now_df, "close_ticker",
            metric_cols=[
                ("Entry",  "Entry_Price"),
                ("Exit",   "Exit_Price"),
                ("PnL %",  "Trade_PnL_%"),
                ("Days",   "Days_Held"),
            ],
            show_levels=False,  # already closed
            show_news=True,
        )


# ── TAB 4: HOLDS ─────────────────────────────────────────────────────────────
with tab_holds:
    st.markdown("### ✅ Current Holdings")
    if len(holds_df) > 0:
        c1, c2, c3 = st.columns(3)
        c1.metric("🚀 Best PnL",  f"{holds_df['Trade_PnL_%'].max():.1f}%")
        c2.metric("📊 Avg PnL",   f"{holds_df['Trade_PnL_%'].mean():.1f}%")
        c3.metric("📋 Positions", len(holds_df))

    display_cols = [
        'Ticker', 'Entry_Date', 'Entry_Price', 'Current_Price',
        'Trade_PnL_%', 'Days_Held', 'Breaks_Trendline',
        'Target_Price', 'Reward_%', 'Target_Hit',
        'Current_Clears_Anchor', 'Trendline_Hit', 'RR_Ratio'
    ]
    available = [c for c in display_cols if c in holds_df.columns]
    st.dataframe(
        fix_pyarrow_df(holds_df[available].sort_values('Trade_PnL_%', ascending=False)),
        use_container_width=True, height=600
    )


# ── TAB 5: EGX30 ─────────────────────────────────────────────────────────────
with tab_egx30:
    st.markdown(f"## 📊 EGX30  {sentiment_emoji} {sentiment_text}")
    st.divider()

    left, right = st.columns([2.2, 1])
    with left:
        st.markdown("### 📈 EGX30 Chart")
        st.components.v1.iframe(
            "https://s.tradingview.com/widgetembed/?symbol=EGX:EGX30&interval=D&theme=Light&style=9",
            height=480)
        st.divider()
        st.markdown("### 🟢 Open Positions")
        if len(df_current_egx30) > 0:
            st.dataframe(fix_pyarrow_df(df_current_egx30[[
                'Entry_Date', 'Entry_Price', 'Trade_PnL_%', 'Days_Held', 'Status'
            ]]), use_container_width=True, height=220)
        else:
            st.info("No open EGX30 trades")
        st.divider()
        st.markdown("### 📋 Closed History")
        if len(df_closed_egx30) > 0:
            st.dataframe(fix_pyarrow_df(df_closed_egx30.sort_values("Exit_Date", ascending=False)[[
                'Entry_Date', 'Exit_Date', 'Entry_Price', 'Exit_Price',
                'Trade_PnL_%', 'Days_Held', 'Exit_Reason'
            ]]), use_container_width=True, height=260)
        else:
            st.info("No closed EGX30 trades")

    with right:
        df_strategy_egx30 = df_strategy[df_strategy['Ticker'] == 'EGX30'].copy()
        st.markdown("### 🎯 Strategy Health")
        if len(df_strategy_egx30) > 0:
            strat = df_strategy_egx30.iloc[0]
            st.metric("🏆 Best",   strat['Best_Strategy'])
            st.metric("📊 Score",  safe(strat['composite_score']))
            st.metric("✅ Win",    f"{safe(strat['win_rate'])}%")
            st.metric("🎯 Median", f"{safe(strat['median_pnl'])}%")
            st.metric("📈 Trades", safe(strat['total_trades'], 0))
        else:
            st.warning("No strategy metrics")
        st.divider()
        st.markdown("### 📰 Market News")
        news = fetch_latest_news("EGX30", max_items=5)
        if news:
            for n in news:
                st.markdown(f"**{n['title']}**")
                st.caption(f"📢 {n['provider']} | [Read]({n['url']})")
                st.divider()
        else:
            st.info("No recent EGX30 news")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#888;font-size:11px;padding:12px'>"
    "⚠️ For educational purposes only. Not financial advice. All trading carries risk."
    "</div>", unsafe_allow_html=True)
