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


def draw_candle_chart(ticker, height=650, stop_loss=None, target=None,
                      entry=None, entry_date=None,
                      closed_trades_df=None):
    """
    Full-featured candlestick chart:
    - Hollow candles with % gain/loss on hover
    - EMA 20
    - Green triangle-up on entry date, red triangle-down on exit date
    - PnL% annotation on exit candle
    - Horizontal level lines (stop/entry/target)
    - No grid lines
    - Drawing tools: horizontal line, trendline, extended line, tilted line, eraser
    - Volume panel
    """
    df_all = load_chart_data()
    df = df_all[df_all['symbol'] == ticker].copy().sort_values('datetime')

    if df.empty:
        st.warning(f"No chart data for {ticker}")
        return

    # Date only (no time)
    df['date_str'] = df['datetime'].dt.strftime('%Y-%m-%d')
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()

    # Candle % change for hover
    df['pct_change'] = ((df['close'] - df['open']) / df['open'] * 100).round(2)
    df['hover'] = df.apply(
        lambda r: (f"<b>{r['date_str']}</b><br>"
                   f"O: {r['open']:.2f}  H: {r['high']:.2f}<br>"
                   f"L: {r['low']:.2f}  C: {r['close']:.2f}<br>"
                   f"<b>{'▲' if r['pct_change']>=0 else '▼'} {r['pct_change']:+.2f}%</b>"),
        axis=1
    )

    vol_colors = ['#10b981' if c >= o else '#f87171'
                  for c, o in zip(df['close'], df['open'])]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.75, 0.25])

    # ── Hollow candlesticks with custom hover ─────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df['date_str'],
        open=df['open'], high=df['high'],
        low=df['low'],   close=df['close'],
        increasing=dict(line=dict(color='#10b981', width=1), fillcolor='rgba(0,0,0,0)'),
        decreasing=dict(line=dict(color='#f87171', width=1), fillcolor='rgba(0,0,0,0)'),
        text=df['hover'],
        hoverinfo='text',
        name=ticker, showlegend=False,
    ), row=1, col=1)

    # ── EMA 20 ────────────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df['date_str'], y=df['ema20'], mode='lines',
        line=dict(color='#facc15', width=1.5), name='EMA 20',
    ), row=1, col=1)

    # ── Entry arrow (green triangle-up below candle) ──────────────────────────
    if entry_date:
        ed_str = pd.to_datetime(entry_date).strftime('%Y-%m-%d')
        ed_row = df[df['date_str'] == ed_str]
        if not ed_row.empty:
            arrow_y = ed_row['low'].values[0] * 0.992
            fig.add_trace(go.Scatter(
                x=[ed_str], y=[arrow_y],
                mode='markers',
                marker=dict(symbol='triangle-up', size=16,
                            color='#10b981', line=dict(color='#d1fae5', width=1)),
                name='Entry',
                hovertemplate=f"<b>Entry</b><br>Date: {ed_str}<br>Price: {entry:.2f}<extra></extra>" if entry else f"Entry: {ed_str}<extra></extra>",
            ), row=1, col=1)

    # ── Closed trade arrows from history ─────────────────────────────────────
    if closed_trades_df is not None and len(closed_trades_df) > 0:
        ctdf = closed_trades_df.copy()
        ctdf['Entry_Date'] = pd.to_datetime(ctdf['Entry_Date'], errors='coerce').dt.strftime('%Y-%m-%d')
        ctdf['Exit_Date']  = pd.to_datetime(ctdf['Exit_Date'],  errors='coerce').dt.strftime('%Y-%m-%d')

        for _, tr in ctdf.iterrows():
            # Entry arrow
            tr_ed = tr.get('Entry_Date', '')
            tr_ep = tr.get('Entry_Price', None)
            ed_row = df[df['date_str'] == tr_ed]
            if not ed_row.empty and pd.notna(tr_ep):
                arr_y = ed_row['low'].values[0] * 0.992
                fig.add_trace(go.Scatter(
                    x=[tr_ed], y=[arr_y],
                    mode='markers',
                    marker=dict(symbol='triangle-up', size=14,
                                color='#10b981', line=dict(color='#d1fae5', width=1)),
                    name='Entry', showlegend=False,
                    hovertemplate=f"<b>Entry</b><br>{tr_ed}<br>{tr_ep:.2f}<extra></extra>",
                ), row=1, col=1)

            # Exit arrow with PnL%
            tr_xd  = tr.get('Exit_Date', '')
            tr_xp  = tr.get('Exit_Price', None)
            tr_pnl = tr.get('Trade_PnL_%', None)
            xd_row = df[df['date_str'] == tr_xd]
            if not xd_row.empty and pd.notna(tr_xp):
                arr_y2 = xd_row['high'].values[0] * 1.008
                pnl_str = f"{tr_pnl:+.1f}%" if pd.notna(tr_pnl) else ""
                pnl_color = '#34d399' if (pd.notna(tr_pnl) and tr_pnl >= 0) else '#f87171'
                fig.add_trace(go.Scatter(
                    x=[tr_xd], y=[arr_y2],
                    mode='markers+text',
                    marker=dict(symbol='triangle-down', size=14,
                                color='#f87171', line=dict(color='#fecaca', width=1)),
                    text=[pnl_str],
                    textposition='top center',
                    textfont=dict(color=pnl_color, size=10),
                    name='Exit', showlegend=False,
                    hovertemplate=f"<b>Exit</b><br>{tr_xd}<br>{tr_xp:.2f}<br><b>{pnl_str}</b><extra></extra>",
                ), row=1, col=1)

    # ── Level lines ───────────────────────────────────────────────────────────
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

    # ── Volume ────────────────────────────────────────────────────────────────
    fig.add_trace(go.Bar(
        x=df['date_str'], y=df['volume'],
        marker_color=vol_colors, marker_opacity=0.7,
        name='Volume', showlegend=False,
    ), row=2, col=1)

    x_range_end = len(df) + 15
    no_grid = dict(showgrid=False, showline=False, zeroline=False)

    fig.update_layout(
        title=dict(text=f"EGX: {ticker}", font=dict(size=15, color='#d1fae5'), x=0.01),
        paper_bgcolor='#0f172a', plot_bgcolor='#0a1a12',
        font=dict(color='#9ca3af', family='DM Mono'),
        height=height, margin=dict(l=10, r=110, t=45, b=50),
        dragmode='zoom',
        xaxis=dict(rangeslider=dict(visible=False), showticklabels=False, **no_grid),
        xaxis2=dict(rangeslider=dict(visible=False), **no_grid),
        legend=dict(bgcolor='#0f172a', bordercolor='#1e3a2a',
                    font=dict(color='#9ca3af', size=11), x=0.01, y=0.99),
        modebar=dict(bgcolor='#0f172a', color='#4b6a57', activecolor='#10b981'),
        newshape=dict(line=dict(color='#facc15', width=1.5), fillcolor='rgba(0,0,0,0)'),
    )

    price_ax = dict(side='right', showgrid=False, showline=False, zeroline=False)
    vol_ax   = dict(side='right', showgrid=False, showline=False, zeroline=False,
                    tickformat='.2s',
                    title=dict(text='Vol', font=dict(size=10, color='#4b6a57')))

    # Show ALL candles by default, leave room on the right
    # Using autorange — do NOT set explicit range with category axis or only a window shows
    fig.update_xaxes(type='category', tickangle=-45, nticks=20,
                     showgrid=False, showline=False, zeroline=False,
                     autorange=True, row=2, col=1)
    fig.update_xaxes(type='category', showticklabels=False,
                     showgrid=False, showline=False, zeroline=False,
                     autorange=True, row=1, col=1)
    fig.update_yaxes(**price_ax, row=1, col=1)
    fig.update_yaxes(**vol_ax,   row=2, col=1)

    st.plotly_chart(fig, use_container_width=True,
                    config={
                        'displayModeBar': True,
                        'scrollZoom': True,
                        'modeBarButtonsToRemove': ['toImage', 'sendDataToCloud'],
                        'modeBarButtonsToAdd': [
                            'drawline',       # tilted / trendline
                            'drawopenpath',   # free draw
                            'drawclosedpath', # closed shape
                            'drawcircle',     # circle
                            'drawrect',       # horizontal band / rectangle
                            'eraseshape',     # eraser
                        ],
                    })


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
        result.append({"title": news.get("title", ""),
                        "url": f"https://www.tradingview.com{news.get('storyPath', '')}",
                        "provider": news.get("provider", {}).get("name", ""),
                        "date": nd})
    return result[:max_items]


def get_levels(row):
    sl = float(row['Stop_Loss'])    if pd.notna(row.get('Stop_Loss'))    else None
    en = float(row['Entry_Price'])  if pd.notna(row.get('Entry_Price'))  else None
    tg = float(row['Target_Price']) if pd.notna(row.get('Target_Price')) else None
    # Entry date — date only, strip time
    ed_raw = row.get('Entry_Date', None)
    ed = pd.to_datetime(ed_raw).strftime('%Y-%m-%d') if pd.notna(ed_raw) else None
    return sl, en, tg, ed


def render_metrics_list(row, metric_cols):
    st.markdown("""
    <style>
    .mli { background:#0f172a; border:1px solid #1e3a2a; border-radius:9px;
           padding:9px 13px; margin-bottom:7px; }
    .mll { font-size:10px; color:#4b6a57; text-transform:uppercase;
           letter-spacing:0.1em; font-family:'DM Mono',monospace; margin-bottom:3px; }
    .mlv { font-size:15px; font-weight:600; color:#d1fae5; font-family:'DM Mono',monospace; }
    .mlv.loss { color:#f87171; }
    .mlv.gain { color:#34d399; }
    .mlv.warn { color:#facc15; }
    </style>""", unsafe_allow_html=True)

    for lbl, col, hint in metric_cols:
        if col not in row.index:
            continue
        val = row.get(col)
        # Format dates as date-only strings
        if 'date' in col.lower() or 'Date' in col:
            try:
                display = pd.to_datetime(val).strftime('%Y-%m-%d')
            except:
                display = str(val) if pd.notna(val) else "—"
        elif isinstance(val, (int, float)):
            display = safe(val)
        elif isinstance(val, str) and val.replace('.','',1).lstrip('-').isdigit():
            display = safe(float(val))
        else:
            display = str(val) if pd.notna(val) else "—"

        cc = {"loss": "loss", "gain": "gain", "warn": "warn"}.get(hint, "")
        st.markdown(f"""
        <div class="mli">
            <div class="mll">{lbl}</div>
            <div class="mlv {cc}">{display}</div>
        </div>""", unsafe_allow_html=True)


# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(page_title="🚀 EGX Dashboard", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');
div[data-testid="stRadio"] label {
    font-family: 'DM Mono', monospace !important;
    font-size: 13px !important;
    padding: 4px 0 !important;
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

    # ── Market sentiment ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 Market Pulse")
    st.markdown(f"{sentiment_emoji} **EGX30: {sentiment_text}**")

    # Positive signals from holds
    if len(holds_df) > 0:
        pnl_col = 'Trade_PnL_%'
        positive_holds = holds_df[holds_df[pnl_col] > 0] if pnl_col in holds_df.columns else pd.DataFrame()
        avg_pnl = holds_df[pnl_col].mean() if pnl_col in holds_df.columns else 0
        above_market = holds_df[holds_df[pnl_col] > 0] if pnl_col in holds_df.columns else pd.DataFrame()

        # Color avg PnL
        avg_color = "#34d399" if avg_pnl >= 0 else "#f87171"
        avg_sign  = "▲" if avg_pnl >= 0 else "▼"
        st.markdown(
            f"<div style='background:#0f172a;border:1px solid #1e3a2a;border-radius:8px;"
            f"padding:10px 12px;margin:6px 0'>"
            f"<div style='font-size:10px;color:#4b6a57;text-transform:uppercase;letter-spacing:.1em'>Portfolio Avg PnL</div>"
            f"<div style='font-size:18px;font-weight:700;color:{avg_color}'>{avg_sign} {avg_pnl:.1f}%</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<div style='background:#0f172a;border:1px solid #1e3a2a;border-radius:8px;"
            f"padding:10px 12px;margin:6px 0'>"
            f"<div style='font-size:10px;color:#4b6a57;text-transform:uppercase;letter-spacing:.1em'>Outperforming (PnL &gt; 0)</div>"
            f"<div style='font-size:18px;font-weight:700;color:#34d399'>{len(positive_holds)} / {len(holds_df)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

        # Top 3 performers
        if len(positive_holds) > 0:
            st.markdown("<div style='font-size:10px;color:#4b6a57;text-transform:uppercase;"
                        "letter-spacing:.1em;margin:10px 0 4px'>🏆 Top Performers</div>",
                        unsafe_allow_html=True)
            top3 = positive_holds.nlargest(3, pnl_col)[['Ticker', pnl_col]]
            for _, r in top3.iterrows():
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;"
                    f"background:#0a1f12;border:1px solid #1e3a2a;border-radius:6px;"
                    f"padding:6px 10px;margin-bottom:4px'>"
                    f"<span style='color:#d1fae5;font-weight:600'>{r['Ticker']}</span>"
                    f"<span style='color:#34d399;font-weight:700'>▲ {r[pnl_col]:.1f}%</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

        # Clears/Tests Anchor signals
        if 'Current_Clears_Anchor' in holds_df.columns:
            clears = holds_df[holds_df['Current_Clears_Anchor'] == True]
            if len(clears) > 0:
                st.markdown(
                    f"<div style='background:#0f172a;border:1px solid #facc1540;border-radius:8px;"
                    f"padding:10px 12px;margin:6px 0'>"
                    f"<div style='font-size:10px;color:#facc15;text-transform:uppercase;letter-spacing:.1em'>⚡ Clears Anchor</div>"
                    f"<div style='font-size:13px;color:#d1fae5'>{', '.join(clears['Ticker'].tolist())}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

    st.markdown("---")
    st.markdown(f"*{selected_facts}*")


# ---------------------------
# REUSABLE PANEL
# ---------------------------
def stock_panel(source_df, session_key, metric_cols, show_levels=True, show_news=True):
    if source_df.empty:
        st.info("Nothing here today.")
        return

    tickers = source_df['Ticker'].tolist()
    col_tickers, col_metrics, col_chart = st.columns([1, 1, 5])

    with col_tickers:
        st.markdown("**Stocks**")
        selected = st.radio("Select stock", options=tickers,
                            key=session_key, label_visibility="collapsed")

    if not selected:
        return

    row = source_df[source_df['Ticker'] == selected].iloc[0]

    with col_metrics:
        st.markdown(f"**{selected}**")
        render_metrics_list(row, metric_cols)

    with col_chart:
        sl = en = tg = ed = None
        if show_levels:
            sl, en, tg, ed = get_levels(row)

        # Pull closed trades for this ticker to overlay entry/exit arrows
        ticker_closed = df_closed_other[df_closed_other['Ticker'] == selected].copy()
        ticker_closed_arg = ticker_closed if len(ticker_closed) > 0 else None

        draw_candle_chart(selected, height=650,
                          stop_loss=sl, target=tg, entry=en, entry_date=ed,
                          closed_trades_df=ticker_closed_arg)

        # History table
        if len(ticker_closed) > 0:
            with st.expander(f"📋 Trade History — {selected} ({len(ticker_closed)} trades)", expanded=False):
                hist_cols = [c for c in [
                    'Entry_Date', 'Exit_Date', 'Entry_Price', 'Exit_Price',
                    'Trade_PnL_%', 'Days_Held', 'Exit_Reason'
                ] if c in ticker_closed.columns]
                st.dataframe(fix_pyarrow_df(
                    ticker_closed[hist_cols].sort_values('Entry_Date', ascending=False)
                ), use_container_width=True, height=250)

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
tab_buys, tab_tp, tab_close, tab_holds, tab_charts, tab_egx30 = st.tabs([
    f"🆕 Fresh Buys ({len(fresh_buys_df)})",
    f"🎯 Take Profit ({len(take_profit_df)})",
    f"❌ Close Now ({len(close_now_df)})",
    f"✅ Holds ({len(holds_df)})",
    "📈 Charts",
    "📊 EGX30",
])


# ── TAB 1: FRESH BUYS ────────────────────────────────────────────────────────
with tab_buys:
    stock_panel(
        fresh_buys_df, "buy_ticker",
        metric_cols=[
            ("Entry Date",  "Entry_Date",       "neutral"),
            ("Entry Price", "Entry_Price",       "neutral"),
            ("Stop Loss",   "Stop_Loss",         "loss"),
            ("Target",      "Target_Price",      "gain"),
            ("Risk %",      "Risk_%",            "loss"),
            ("Reward %",    "Reward_%",          "gain"),
            ("R:R",         "RR_Ratio",          "warn"),
            ("TL Break",    "Breaks_Trendline",  "neutral"),
        ],
        show_levels=True, show_news=True,
    )


# ── TAB 2: TAKE PROFIT ───────────────────────────────────────────────────────
with tab_tp:
    stock_panel(
        take_profit_df, "tp_ticker",
        metric_cols=[
            ("Entry Date",  "Entry_Date",    "neutral"),
            ("Entry Price", "Entry_Price",   "neutral"),
            ("Current",     "Current_Price", "neutral"),
            ("PnL %",       "Trade_PnL_%",   "gain"),
            ("Target",      "Target_Price",  "gain"),
            ("Days Held",   "Days_Held",     "neutral"),
            ("R:R",         "RR_Ratio",      "warn"),
        ],
        show_levels=True, show_news=True,
    )


# ── TAB 3: CLOSE NOW ─────────────────────────────────────────────────────────
with tab_close:
    stock_panel(
        close_now_df, "close_ticker",
        metric_cols=[
            ("Entry Date",  "Entry_Date",  "neutral"),
            ("Entry Price", "Entry_Price", "neutral"),
            ("Exit Price",  "Exit_Price",  "neutral"),
            ("PnL %",       "Trade_PnL_%", "gain"),
            ("Days Held",   "Days_Held",   "neutral"),
        ],
        show_levels=False,
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
        'Clears_Anchor', 'Testing_Anchor',
        'Current_Clears_Anchor', 'Trendline_Hit', 'RR_Ratio'
    ]
    available = [c for c in display_cols if c in holds_df.columns]
    st.dataframe(
        fix_pyarrow_df(holds_df[available].sort_values('Trade_PnL_%', ascending=False)),
        use_container_width=True, height=600
    )


# ── TAB 5: CHARTS (free lookup) ──────────────────────────────────────────────
with tab_charts:
    st.markdown("### 📈 Chart Lookup")

    # All known symbols from chart CSV (cached)
    chart_df_all = load_chart_data()
    available_symbols = sorted(chart_df_all['symbol'].dropna().unique().tolist())

    ch_col1, ch_col2 = st.columns([2, 5])
    with ch_col1:
        chart_symbol = st.selectbox(
            "Symbol", options=available_symbols,
            key="chart_lookup_symbol",
            help="Type to search"
        )

    if chart_symbol:
        # Closed trades for this symbol (for entry/exit arrows)
        sym_closed = df_closed_other[df_closed_other['Ticker'] == chart_symbol].copy()
        sym_closed_arg = sym_closed if len(sym_closed) > 0 else None

        # Open trade levels if exists
        sym_open = df_current_other[df_current_other['Ticker'] == chart_symbol]
        sl2 = en2 = tg2 = ed2 = None
        if len(sym_open) > 0:
            sl2, en2, tg2, ed2 = get_levels(sym_open.iloc[0])

        draw_candle_chart(chart_symbol, height=700,
                          stop_loss=sl2, target=tg2, entry=en2, entry_date=ed2,
                          closed_trades_df=sym_closed_arg)

        # History table
        if sym_closed_arg is not None and len(sym_closed) > 0:
            with st.expander(f"📋 Trade History — {chart_symbol} ({len(sym_closed)} trades)", expanded=False):
                hist_cols = [c for c in [
                    'Entry_Date', 'Exit_Date', 'Entry_Price', 'Exit_Price',
                    'Trade_PnL_%', 'Days_Held', 'Exit_Reason'
                ] if c in sym_closed.columns]
                st.dataframe(fix_pyarrow_df(
                    sym_closed[hist_cols].sort_values('Entry_Date', ascending=False)
                ), use_container_width=True, height=300)
        else:
            st.caption("No trade history for this symbol.")


# ── TAB 6: EGX30 ─────────────────────────────────────────────────────────────
with tab_egx30:
    st.markdown(f"## 📊 EGX30  {sentiment_emoji} {sentiment_text}")

    col_egx_tickers, col_egx_metrics, col_egx_chart = st.columns([1, 1, 5])

    # EGX30 open trade levels
    egx30_sl = egx30_en = egx30_tg = egx30_ed = None
    if len(df_current_egx30) > 0:
        egx_row = df_current_egx30.iloc[0]
        egx30_sl = float(egx_row['Stop_Loss'])    if pd.notna(egx_row.get('Stop_Loss'))    else None
        egx30_en = float(egx_row['Entry_Price'])  if pd.notna(egx_row.get('Entry_Price'))  else None
        egx30_tg = float(egx_row['Target_Price']) if pd.notna(egx_row.get('Target_Price')) else None
        ed_raw   = egx_row.get('Entry_Date', None)
        egx30_ed = pd.to_datetime(ed_raw).strftime('%Y-%m-%d') if pd.notna(ed_raw) else None

    egx30_closed_arg = df_closed_egx30 if len(df_closed_egx30) > 0 else None

    with col_egx_tickers:
        st.markdown("**EGX30**")
        st.markdown(f"{sentiment_emoji}")
        st.markdown(f"**{sentiment_text}**")
        if len(df_current_egx30) > 0:
            st.success("📈 Active Trade")
        else:
            st.info("No open trade")

    with col_egx_metrics:
        df_strategy_egx30 = df_strategy[df_strategy['Ticker'] == 'EGX30'].copy()
        st.markdown("**Strategy**")
        if len(df_strategy_egx30) > 0:
            strat = df_strategy_egx30.iloc[0]
            egx_metric_rows = [
                ("Best Strategy", strat.get('Best_Strategy', '—')),
                ("Score",         safe(strat.get('composite_score'))),
                ("Win Rate",      f"{safe(strat.get('win_rate'))}%"),
                ("Median PnL",    f"{safe(strat.get('median_pnl'))}%"),
                ("Total Trades",  safe(strat.get('total_trades'), 0)),
            ]
            if len(df_current_egx30) > 0:
                egx_row = df_current_egx30.iloc[0]
                egx_metric_rows += [
                    ("Entry Date",  pd.to_datetime(egx_row.get('Entry_Date')).strftime('%Y-%m-%d') if pd.notna(egx_row.get('Entry_Date')) else '—'),
                    ("Entry Price", safe(egx_row.get('Entry_Price'))),
                    ("Stop Loss",   safe(egx_row.get('Stop_Loss'))),
                    ("Target",      safe(egx_row.get('Target_Price'))),
                    ("PnL %",       safe(egx_row.get('Trade_PnL_%'))),
                    ("Days Held",   safe(egx_row.get('Days_Held'), 0)),
                ]
            for lbl, val in egx_metric_rows:
                st.markdown(
                    f"<div class='mli'><div class='mll'>{lbl}</div>"
                    f"<div class='mlv'>{val}</div></div>",
                    unsafe_allow_html=True
                )

    with col_egx_chart:
        draw_candle_chart('EGX30', height=650,
                          stop_loss=egx30_sl, target=egx30_tg,
                          entry=egx30_en, entry_date=egx30_ed,
                          closed_trades_df=egx30_closed_arg)

        if len(df_closed_egx30) > 0:
            with st.expander(f"📋 EGX30 Trade History ({len(df_closed_egx30)} trades)", expanded=False):
                hist_cols = [c for c in [
                    'Entry_Date', 'Exit_Date', 'Entry_Price', 'Exit_Price',
                    'Trade_PnL_%', 'Days_Held', 'Exit_Reason'
                ] if c in df_closed_egx30.columns]
                st.dataframe(fix_pyarrow_df(
                    df_closed_egx30[hist_cols].sort_values('Entry_Date', ascending=False)
                ), use_container_width=True, height=260)

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
