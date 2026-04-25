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
# CHART DATA
# ---------------------------
@st.cache_data(ttl=3600)
def load_chart_data():
    url = "https://raw.githubusercontent.com/vancedmazen-art/stock_dashboard/main/chart_6m.csv"
    df = pd.read_csv(url, parse_dates=['datetime'])
    df.columns = df.columns.str.strip().str.lower()
    return df


def draw_candle_chart(ticker, height=620, stop_loss=None, target=None, entry=None):
    df_all = load_chart_data()
    df = df_all[df_all['symbol'] == ticker].copy().sort_values('datetime')

    if df.empty:
        st.warning(f"No chart data for {ticker}")
        return

    df['date_str'] = df['datetime'].dt.strftime('%Y-%m-%d')
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    vol_colors = ['#10b981' if c >= o else '#f87171'
                  for c, o in zip(df['close'], df['open'])]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25]
    )

    fig.add_trace(go.Candlestick(
        x=df['date_str'],
        open=df['open'], high=df['high'],
        low=df['low'], close=df['close'],
        increasing=dict(line=dict(color='#10b981', width=1), fillcolor='rgba(0,0,0,0)'),
        decreasing=dict(line=dict(color='#f87171', width=1), fillcolor='rgba(0,0,0,0)'),
        name=ticker, showlegend=False,
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df['date_str'], y=df['ema20'],
        mode='lines', line=dict(color='#facc15', width=1.5),
        name='EMA 20',
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
        height=height,
        margin=dict(l=10, r=100, t=45, b=50),
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
# STOCK ROW CARD COMPONENT
# ---------------------------
def render_stock_cards(df, session_key, cols_to_show, card_color='#10b981'):
    """Renders clickable stock cards. Returns selected ticker."""
    if df.empty:
        st.info("Nothing here today.")
        return None

    tickers = df['Ticker'].tolist()

    if session_key not in st.session_state:
        st.session_state[session_key] = tickers[0] if tickers else None

    def fmt(v, decimals=2):
        try: return f"{float(v):.{decimals}f}"
        except: return str(v) if pd.notna(v) else '—'

    def fmt1(v): return fmt(v, 1)

    cards_html = []
    for _, row in df.iterrows():
        ticker = row.get('Ticker', '')
        is_selected = (ticker == st.session_state[session_key])
        selected_class = "selected" if is_selected else ""

        # Build stat pills from cols_to_show: list of (label, col, color_hint)
        pills = ""
        for label, col, hint in cols_to_show:
            val = row.get(col, '')
            color = '#34d399' if hint == 'gain' else '#f87171' if hint == 'loss' else '#94a3b8'
            pills += f"""
            <div class="pill">
                <span class="pill-label">{label}</span>
                <span class="pill-val" style="color:{color}">{fmt1(val) if hint in ('gain','loss','neutral') else str(val)[:12] if pd.notna(val) else '—'}</span>
            </div>"""

        cards_html.append(f"""
        <div class="scard {selected_class}" onclick="sel('{ticker}')">
            <div class="scard-ticker">{ticker}</div>
            <div class="pills">{pills}</div>
        </div>""")

    html = f"""<!DOCTYPE html><html><head>
    <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap" rel="stylesheet">
    <style>
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{background:transparent;font-family:'DM Mono',monospace;padding:4px 0 8px;}}
    .wrap{{display:flex;flex-direction:column;gap:7px;}}
    .scard{{
        background:linear-gradient(135deg,#0f172a,#0a1a12);
        border:1px solid #1e3a2a;border-radius:11px;
        padding:12px 14px;cursor:pointer;
        transition:all 0.14s ease;position:relative;overflow:hidden;
    }}
    .scard::before{{content:'';position:absolute;left:0;top:0;bottom:0;
        width:3px;background:{card_color};opacity:0;transition:opacity 0.14s;}}
    .scard:hover{{border-color:{card_color};box-shadow:0 4px 20px {card_color}22;transform:translateX(3px);}}
    .scard:hover::before,.scard.selected::before{{opacity:1;}}
    .scard.selected{{border-color:{card_color};background:linear-gradient(135deg,#0f2318,#091a10);
        box-shadow:0 0 0 1px {card_color}44,0 4px 20px {card_color}22;transform:translateX(3px);}}
    .scard-ticker{{font-family:'Syne',sans-serif;font-size:15px;font-weight:800;
        color:#f0fdf4;letter-spacing:0.04em;margin-bottom:8px;}}
    .pills{{display:flex;flex-wrap:wrap;gap:6px;}}
    .pill{{display:flex;flex-direction:column;background:#0a1f12;
        border:1px solid #1e3a2a;border-radius:6px;padding:4px 8px;min-width:60px;}}
    .pill-label{{font-size:8px;color:#4b6a57;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:2px;}}
    .pill-val{{font-size:12px;font-weight:500;}}
    </style></head><body>
    <div class="wrap">{''.join(cards_html)}</div>
    <script>
    function sel(t){{window.parent.postMessage({{type:'streamlit:setComponentValue',value:t}},'*');}}
    window.addEventListener('load',function(){{
        setTimeout(()=>sel("{st.session_state[session_key] or ''}"),80);
    }});
    </script></body></html>"""

    card_h = min(len(tickers) * 110 + 10, 700)
    clicked = st.components.v1.html(html, height=card_h, scrolling=True)
    if clicked and clicked != st.session_state[session_key]:
        st.session_state[session_key] = clicked
        st.rerun()

    return st.session_state[session_key]


# ---------------------------
# LOAD DATA
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

        st.success("✅ Data loaded")
        return {"closed": closed_trades, "current": current_trades}, all_tickers, strategy_metrics, refresh_date_obj, refresh_date_str

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


def safe_display(value):
    if pd.isna(value) or value is None or value == "":
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.1f}"
    return str(value)


def fetch_latest_news(symbol: str, max_items=3):
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
        symbols = [s.get("symbol", "").replace("EGX:", "")
                   for s in news.get("relatedSymbols", [])
                   if s.get("symbol", "").startswith("EGX:")]
        if symbol.upper() not in [s.upper() for s in symbols]:
            continue
        try:
            CAIRO_TZ = pytz.timezone("Africa/Cairo")
            published_dt = datetime.utcfromtimestamp(news["published"]).replace(tzinfo=pytz.UTC).astimezone(CAIRO_TZ)
            news_date = published_dt.strftime('%Y-%m-%d %H:%M')
        except:
            news_date = "Recent"
        result.append({
            "title": news.get("title", ""),
            "url": f"https://www.tradingview.com{news.get('storyPath', '')}",
            "provider": news.get("provider", {}).get("name", ""),
            "date": news_date,
        })
    return result[:max_items]


# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(page_title="🚀 EGX Trading Dashboard", layout="wide")

# Global style
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');
.section-head {
    font-family: 'Syne', sans-serif;
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.2em; text-transform: uppercase;
    color: #10b981; margin: 16px 0 8px;
    display: flex; align-items: center; gap: 8px;
}
.section-head::after {
    content: ''; flex: 1; height: 1px;
    background: linear-gradient(90deg, #10b98140, transparent);
}
</style>
""", unsafe_allow_html=True)

# Header row
h1, h2, h3 = st.columns([4, 2, 1])
with h1:
    st.markdown(
        "<div style='font-family:Syne,sans-serif;font-size:22px;font-weight:800;"
        "color:#d1fae5;letter-spacing:0.04em;padding:6px 0'>🚀 EGX Trading Dashboard</div>",
        unsafe_allow_html=True)
with h3:
    if st.button("🔄 Reload", type="primary"):
        st.rerun()

# Load
data, all_symbols, df_strategy, refresh_date_obj, refresh_date_str = load_data()
df_current = data["current"].copy()
df_closed = data["closed"].copy()

st.caption(f"📅 Data as of: **{refresh_date_str}**")

# Separate EGX30
df_current_egx30 = df_current[df_current['Ticker'] == 'EGX30'].copy()
df_closed_egx30 = df_closed[df_closed['Ticker'] == 'EGX30'].copy()
df_current_other = df_current[df_current['Ticker'] != 'EGX30'].copy()
df_closed_other = df_closed[df_closed['Ticker'] != 'EGX30'].copy()

# Date processing
df_ci = df_current_other.copy()
df_xi = df_closed_other.copy()
df_ci['Entry_Date'] = pd.to_datetime(df_ci['Entry_Date'], errors='coerce').dt.date
df_ci['Target_Hit_Date'] = pd.to_datetime(df_ci['Target_Hit_Date'], errors='coerce').dt.date
df_xi['Entry_Date'] = pd.to_datetime(df_xi['Entry_Date'], errors='coerce').dt.date
df_xi['Exit_Date'] = pd.to_datetime(df_xi['Exit_Date'], errors='coerce').dt.date

# Slice each group
fresh_buys_df = df_current_other[df_ci['Entry_Date'] == refresh_date_obj].copy()
take_profit_df = df_current_other[
    (df_ci['Target_Hit_Date'] == refresh_date_obj) &
    (df_ci['Bars_To_Target'] != 0)
].copy()
close_now_df = df_closed_other[df_xi['Exit_Date'] == refresh_date_obj].copy()
holds_df = df_current_other[df_ci['Entry_Date'] != refresh_date_obj].copy()

# Sidebar counts
with st.sidebar:
    st.markdown("### 🎛️ **Status**")
    st.metric("🆕 Fresh Buys", len(fresh_buys_df))
    st.metric("🎯 Take Profit", len(take_profit_df))
    st.metric("❌ Close Now", len(close_now_df))
    st.metric("✅ Holds", len(holds_df))
    st.caption(f"📅 {refresh_date_str}")

    # EGX30 sentiment
    if len(df_current_egx30) > 0:
        sentiment_text, sentiment_emoji = "Positive", "🚀📈"
    else:
        sentiment_text, sentiment_emoji = "Neutral / Cautious", "⚠️📉"
    st.markdown(f"### {sentiment_emoji} **{sentiment_text}**")
    st.markdown("---")
    st.markdown("### 💡 Insight")
    st.markdown(f"*{selected_facts}*")


# ---------------------------
# HELPER: chart + info panel for a selected ticker
# ---------------------------
def chart_panel(ticker, source_df, extra_cols, show_news=True):
    """Right panel: chart with trade levels + optional news."""
    row = source_df[source_df['Ticker'] == ticker]
    if row.empty:
        st.info("Select a stock on the left.")
        return

    row = row.iloc[0]
    stop_loss = float(row['Stop_Loss']) if pd.notna(row.get('Stop_Loss')) else None
    entry = float(row['Entry_Price']) if pd.notna(row.get('Entry_Price')) else None
    target = float(row['Target_Price']) if pd.notna(row.get('Target_Price')) else None

    # Key metrics strip
    mc = st.columns(len(extra_cols))
    for i, (label, col) in enumerate(extra_cols):
        mc[i].metric(label, safe_display(row.get(col, '—')))

    draw_candle_chart(ticker, height=580,
                      stop_loss=stop_loss, target=target, entry=entry)

    if show_news:
        st.markdown('<div class="section-head">📰 Latest News</div>', unsafe_allow_html=True)
        news_items = fetch_latest_news(ticker, max_items=3)
        if news_items:
            for n in news_items:
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
        left, right = st.columns([2, 5])
        with left:
            st.markdown('<div class="section-head">🆕 Fresh Buys</div>', unsafe_allow_html=True)
            selected = render_stock_cards(
                fresh_buys_df,
                session_key="buy_ticker",
                cols_to_show=[
                    ("Entry", "Entry_Price", "neutral"),
                    ("Stop",  "Stop_Loss",   "loss"),
                    ("Target","Target_Price","gain"),
                    ("Risk%", "Risk_%",      "loss"),
                    ("Rwd%",  "Reward_%",    "gain"),
                    ("R:R",   "RR_Ratio",    "neutral"),
                ],
                card_color='#10b981'
            )
        with right:
            if selected:
                chart_panel(
                    selected, fresh_buys_df,
                    extra_cols=[
                        ("Entry Price", "Entry_Price"),
                        ("Stop Loss",   "Stop_Loss"),
                        ("Target",      "Target_Price"),
                        ("Risk %",      "Risk_%"),
                        ("Reward %",    "Reward_%"),
                        ("R:R",         "RR_Ratio"),
                    ]
                )


# ── TAB 2: TAKE PROFIT ───────────────────────────────────────────────────────
with tab_tp:
    if take_profit_df.empty:
        st.info("No take profit signals today.")
    else:
        left, right = st.columns([2, 5])
        with left:
            st.markdown('<div class="section-head">🎯 Take Profit</div>', unsafe_allow_html=True)
            selected = render_stock_cards(
                take_profit_df,
                session_key="tp_ticker",
                cols_to_show=[
                    ("Entry",   "Entry_Price",  "neutral"),
                    ("Current", "Current_Price","neutral"),
                    ("PnL %",   "Trade_PnL_%",  "gain"),
                    ("Days",    "Days_Held",     "neutral"),
                    ("R:R",     "RR_Ratio",      "neutral"),
                ],
                card_color='#facc15'
            )
        with right:
            if selected:
                chart_panel(
                    selected, take_profit_df,
                    extra_cols=[
                        ("Entry",   "Entry_Price"),
                        ("Current", "Current_Price"),
                        ("PnL %",   "Trade_PnL_%"),
                        ("Target",  "Target_Price"),
                        ("Days",    "Days_Held"),
                    ]
                )


# ── TAB 3: CLOSE NOW ─────────────────────────────────────────────────────────
with tab_close:
    if close_now_df.empty:
        st.info("Nothing to close today.")
    else:
        left, right = st.columns([2, 5])
        with left:
            st.markdown('<div class="section-head">❌ Close Now</div>', unsafe_allow_html=True)
            selected = render_stock_cards(
                close_now_df,
                session_key="close_ticker",
                cols_to_show=[
                    ("Entry",  "Entry_Price", "neutral"),
                    ("Exit",   "Exit_Price",  "neutral"),
                    ("PnL %",  "Trade_PnL_%", "gain"),
                    ("Days",   "Days_Held",   "neutral"),
                ],
                card_color='#f87171'
            )
        with right:
            if selected:
                # closed trades don't have open levels
                row = close_now_df[close_now_df['Ticker'] == selected]
                if not row.empty:
                    row = row.iloc[0]
                    mc = st.columns(4)
                    mc[0].metric("Entry Price", safe_display(row.get('Entry_Price')))
                    mc[1].metric("Exit Price",  safe_display(row.get('Exit_Price')))
                    mc[2].metric("PnL %",       safe_display(row.get('Trade_PnL_%')))
                    mc[3].metric("Days Held",   safe_display(row.get('Days_Held')))
                    # chart with no levels (already closed)
                    draw_candle_chart(selected, height=580)

                    st.markdown('<div class="section-head">📰 Latest News</div>', unsafe_allow_html=True)
                    news_items = fetch_latest_news(selected, max_items=3)
                    if news_items:
                        for n in news_items:
                            st.markdown(f"**{n['title']}**")
                            st.caption(f"📅 {n['date']} | {n['provider']} | [Read]({n['url']})")
                            st.divider()
                    else:
                        st.caption("No recent news.")


# ── TAB 4: HOLDS ─────────────────────────────────────────────────────────────
with tab_holds:
    st.markdown('<div class="section-head">✅ Current Holdings</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    if len(holds_df) > 0:
        col1.metric("🚀 Best PnL",  f"{holds_df['Trade_PnL_%'].max():.1f}%")
        col2.metric("📊 Avg PnL",   f"{holds_df['Trade_PnL_%'].mean():.1f}%")
        col3.metric("📋 Positions", len(holds_df))

    display_cols = [
        'Ticker', 'Entry_Date', 'Entry_Price', 'Current_Price',
        'Trade_PnL_%', 'Days_Held', 'Breaks_Trendline',
        'Target_Price', 'Reward_%', 'Target_Hit',
        'Current_Clears_Anchor', 'Trendline_Hit', 'RR_Ratio'
    ]
    available = [c for c in display_cols if c in holds_df.columns]
    st.dataframe(
        fix_pyarrow_df(holds_df[available].sort_values('Trade_PnL_%', ascending=False)),
        use_container_width=True,
        height=600
    )


# ── TAB 5: EGX30 ─────────────────────────────────────────────────────────────
with tab_egx30:
    st.markdown("## 📊 EGX30 – Market Overview")
    st.markdown(f"### {sentiment_emoji} Sentiment: **{sentiment_text}**")
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
            st.dataframe(fix_pyarrow_df(df_current_egx30[
                ['Entry_Date', 'Entry_Price', 'Trade_PnL_%', 'Days_Held', 'Status']
            ]), use_container_width=True, height=220)
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
            st.metric("📊 Score",  safe_display(strat['composite_score']))
            st.metric("✅ Win",    f"{safe_display(strat['win_rate'])}%")
            st.metric("🎯 Median", f"{safe_display(strat['median_pnl'])}%")
            st.metric("📈 Trades", safe_display(strat['total_trades']))
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
    "<div style='text-align:center;color:#666;font-size:11px;padding:16px'>"
    "<strong>⚠️ Disclaimer:</strong> For educational purposes only. "
    "Not financial advice. All trading carries risk."
    "</div>", unsafe_allow_html=True)
