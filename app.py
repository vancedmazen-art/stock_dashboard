import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import os
import numpy as np
import random
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_echarts import st_echarts, JsCode

# ---------------------------
# CHART DATA
# ---------------------------
@st.cache_data(ttl=3600)
def load_chart_data():
    url = "https://raw.githubusercontent.com/vancedmazen-art/stock_dashboard/main/chart_6m.csv"
    df = pd.read_csv(url, parse_dates=['datetime'])
    df.columns = df.columns.str.strip().str.lower()
    return df


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()
 
 
def _vol_color(close, open_):
    return "#10b981" if close >= open_ else "#f87171"
 
 
# ── main function ─────────────────────────────────────────────────────────────
 
def draw_candle_chart(
    ticker: str,
    height: int = 650,
    stop_loss=None,
    target=None,
    entry=None,
    entry_date=None,
    closed_trades_df=None,
):
    # ── load & filter ─────────────────────────────────────────────────────────
    df_all = load_chart_data()
    df = df_all[df_all["symbol"] == ticker].copy().sort_values("datetime")
 
    if df.empty:
        st.warning(f"No chart data for {ticker}")
        return
 
    df["date_str"] = df["datetime"].dt.strftime("%Y-%m-%d")
    df["ema20"]    = _ema(df["close"], 20).round(4)
 
    dates = df["date_str"].tolist()
    n     = len(dates)
 
    # ── initial 3-month window ────────────────────────────────────────────────
    max_date     = df["datetime"].max()
    start_cutoff = (max_date - timedelta(days=90)).strftime("%Y-%m-%d")
    start_idx    = next((i for i, d in enumerate(dates) if d >= start_cutoff), 0)
    start_pct    = round(start_idx / n * 100)
 
    # ── candlestick data: plain [open, close, low, high] lists ───────────────
    # Do NOT pass per-item itemStyle — that overrides the series-level
    # up/down color logic and makes every candle the same color.
    candle_data = [
        [float(r["open"]), float(r["close"]), float(r["low"]), float(r["high"])]
        for _, r in df.iterrows()
    ]
 
    # ── volume data ───────────────────────────────────────────────────────────
    vol_data = [
        {
            "value": float(r["volume"]),
            "itemStyle": {"color": _vol_color(r["close"], r["open"]), "opacity": 0.75},
        }
        for _, r in df.iterrows()
    ]
 
    # ── EMA 20 ────────────────────────────────────────────────────────────────
    ema_data = [round(v, 4) for v in df["ema20"].tolist()]
 
    # ── mark points (entry / exit arrows) ────────────────────────────────────
    mark_points = []
 
    def _add_buy(date_str, price_low):
        if date_str not in dates:
            return
        idx = dates.index(date_str)
        y   = price_low * 0.975
        mark_points.append({
            "name":         "BUY",
            "coord":        [idx, y],
            "value":        "BUY",
            "symbol":       "triangle",
            "symbolSize":   20,
            "symbolRotate": 0,
            "itemStyle":    {"color": "#10b981"},
            "label": {
                "show":       True,
                "formatter":  "BUY",
                "position":   "bottom",
                "color":      "#10b981",
                "fontSize":   9,
                "fontFamily": "DM Mono",
            },
        })
 
    def _add_sell(date_str, price_high, pnl_val):
        if date_str not in dates:
            return
        idx = dates.index(date_str)
        y   = price_high * 1.025
        lbl = f"{pnl_val:+.1f}%" if pd.notna(pnl_val) else ""
        clr = "#34d399" if (pd.notna(pnl_val) and pnl_val >= 0) else "#f87171"
        mark_points.append({
            "name":         "SELL",
            "coord":        [idx, y],
            "value":        lbl,
            "symbol":       "triangle",
            "symbolSize":   20,
            "symbolRotate": 180,
            "itemStyle":    {"color": "#f87171"},
            "label": {
                "show":       True,
                "formatter":  lbl,
                "position":   "top",
                "color":      clr,
                "fontSize":   10,
                "fontFamily": "DM Mono",
            },
        })
 
    # current open trade entry
    if entry_date:
        ed_str = pd.to_datetime(entry_date).strftime("%Y-%m-%d")
        ed_row = df[df["date_str"] == ed_str]
        if not ed_row.empty:
            _add_buy(ed_str, float(ed_row["low"].values[0]))
 
    # closed trades
    if closed_trades_df is not None and len(closed_trades_df) > 0:
        ctdf = closed_trades_df.copy()
        ctdf["Entry_Date"] = pd.to_datetime(ctdf["Entry_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
        ctdf["Exit_Date"]  = pd.to_datetime(ctdf["Exit_Date"],  errors="coerce").dt.strftime("%Y-%m-%d")
 
        for _, tr in ctdf.iterrows():
            tr_ed  = tr.get("Entry_Date", "")
            tr_ep  = tr.get("Entry_Price", None)
            ed_row = df[df["date_str"] == tr_ed]
            if not ed_row.empty and pd.notna(tr_ep):
                _add_buy(tr_ed, float(ed_row["low"].values[0]))
 
            tr_xd  = tr.get("Exit_Date", "")
            tr_xp  = tr.get("Exit_Price", None)
            tr_pnl = tr.get("Trade_PnL_%", None)
            xd_row = df[df["date_str"] == tr_xd]
            if not xd_row.empty and pd.notna(tr_xp):
                _add_sell(tr_xd, float(xd_row["high"].values[0]), tr_pnl)
 
    # ── horizontal level lines ────────────────────────────────────────────────
    # markLine data format: list of two-point pairs.
    # Label goes ONLY on point[0]; point[1] must be a plain {yAxis: value} dict.
    mark_lines = []
    level_cfg = []
    if stop_loss:
        level_cfg.append((stop_loss, "#f87171", f"Stop  {stop_loss:.2f}", "dashed"))
    if entry:
        level_cfg.append((entry,     "#94a3b8", f"Entry  {entry:.2f}",    "dotted"))
    if target:
        level_cfg.append((target,    "#10b981", f"Target  {target:.2f}",  "dashed"))
 
    for price, color, label, dash in level_cfg:
        mark_lines.append([
            {
                "yAxis": price,
                "lineStyle": {"color": color, "width": 1.5, "type": dash},
                "label": {
                    "show":       True,
                    "formatter":  label,
                    "position":   "insideEndTop",
                    "color":      color,
                    "fontSize":   11,
                    "fontFamily": "DM Mono",
                    "fontWeight": "600",
                },
            },
            {
                "yAxis": price,
            },
        ])
 
    # ── tooltip JS formatter ──────────────────────────────────────────────────
    # params is an array (trigger="axis"). We scan for the candlestick series
    # whose value is a 4-element array, then also show EMA if present.
    tooltip_js = JsCode("""
    function(params) {
        if (!params || !params.length) return '';
 
        var candle = null;
        var ema    = null;
        for (var i = 0; i < params.length; i++) {
            var v = params[i].value;
            if (Array.isArray(v) && v.length === 4) { candle = params[i]; }
            else if (typeof v === 'number' && params[i].seriesName === 'EMA 20') { ema = params[i]; }
        }
        if (!candle) return '';
 
        var o   = parseFloat(candle.value[0]);
        var c   = parseFloat(candle.value[1]);
        var low = parseFloat(candle.value[2]);
        var h   = parseFloat(candle.value[3]);
        var pct = ((c - o) / o * 100);
        var arrow = pct >= 0 ? '\u25b2' : '\u25bc';
        var col   = pct >= 0 ? '#10b981' : '#f87171';
        var sign  = pct >= 0 ? '+' : '';
 
        var html = '<div style="font-family:DM Mono,monospace;font-size:12px;line-height:1.8;min-width:160px">'
            + '<b style="color:#d1fae5;font-size:13px">' + candle.name + '</b><br>'
            + '<span style="color:#6b7280">O</span> <b style="color:#e2e8f0">' + o.toFixed(2) + '</b>'
            + '&nbsp;&nbsp;<span style="color:#6b7280">H</span> <b style="color:#e2e8f0">' + h.toFixed(2) + '</b><br>'
            + '<span style="color:#6b7280">L</span> <b style="color:#e2e8f0">' + low.toFixed(2) + '</b>'
            + '&nbsp;&nbsp;<span style="color:#6b7280">C</span> <b style="color:#e2e8f0">' + c.toFixed(2) + '</b><br>'
            + '<span style="color:' + col + ';font-size:13px"><b>' + arrow + ' ' + sign + pct.toFixed(2) + '%</b></span>';
 
        if (ema) {
            html += '<br><span style="color:#facc15">\u25a0 EMA20</span> <b style="color:#e2e8f0">' + parseFloat(ema.value).toFixed(2) + '</b>';
        }
 
        html += '</div>';
        return html;
    }
    """)
 
    # ── ECharts option ────────────────────────────────────────────────────────
    option = {
        "backgroundColor": "#0f172a",
        "animation": False,
        "title": {
            "text": f"EGX: {ticker}",
            "textStyle": {
                "color": "#d1fae5", "fontSize": 15,
                "fontFamily": "DM Mono", "fontWeight": "700",
            },
            "left": "1%",
            "top": 6,
        },
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {
                "type": "cross",
                "crossStyle": {"color": "#4b6a57", "width": 1},
                "lineStyle":  {"color": "#4b6a57", "width": 1, "type": "dashed"},
            },
            "backgroundColor": "#0f172a",
            "borderColor":     "#1e3a2a",
            "borderWidth":     1,
            "padding":         [8, 12],
            "formatter":       tooltip_js,
        },
        "legend": {
            "data": ["EMA 20"],
            "top": 6,
            "right": "2%",
            "textStyle": {"color": "#9ca3af", "fontSize": 11, "fontFamily": "DM Mono"},
        },
        "axisPointer": {"link": [{"xAxisIndex": "all"}]},
        "grid": [
            {"left": "1%", "right": "14%", "top": 50,    "height": "60%"},
            {"left": "1%", "right": "14%", "top": "76%", "height": "14%"},
        ],
        "xAxis": [
            {
                "type":        "category",
                "data":        dates,
                "gridIndex":   0,
                "scale":       True,
                "boundaryGap": True,
                "axisLine":    {"lineStyle": {"color": "#1e3a2a"}},
                "axisTick":    {"show": False},
                "axisLabel":   {"show": False},
                "splitLine":   {"show": False},
            },
            {
                "type":        "category",
                "data":        dates,
                "gridIndex":   1,
                "scale":       True,
                "boundaryGap": True,
                "axisLine":    {"lineStyle": {"color": "#1e3a2a"}},
                "axisTick":    {"show": False},
                "axisLabel": {
                    "color":      "#6b7280",
                    "fontSize":   11,
                    "rotate":     -30,
                    "fontFamily": "DM Mono",
                    "interval":   "auto",
                },
                "splitLine": {"show": False},
            },
        ],
        "yAxis": [
            {
                "scale":     True,
                "gridIndex": 0,
                "position":  "right",
                "splitLine": {"show": False},
                "axisLine":  {"show": False},
                "axisTick":  {"show": False},
                "axisLabel": {
                    "color":      "#9ca3af",
                    "fontSize":   13,
                    "fontFamily": "DM Mono",
                    "margin":     8,
                },
            },
            {
                "scale":     True,
                "gridIndex": 1,
                "position":  "right",
                "splitLine": {"show": False},
                "axisLine":  {"show": False},
                "axisTick":  {"show": False},
                "axisLabel": {
                    "color":      "#4b6a57",
                    "fontSize":   11,
                    "fontFamily": "DM Mono",
                    "formatter":  "{value}",
                },
                "name":          "Vol",
                "nameTextStyle": {"color": "#4b6a57", "fontSize": 10},
            },
        ],
        "dataZoom": [
            {
                "type":             "inside",
                "xAxisIndex":       [0, 1],
                "start":            start_pct,
                "end":              100,
                "zoomOnMouseWheel": True,
                "moveOnMouseMove":  True,
            },
            {
                "type":        "slider",
                "xAxisIndex":  [0, 1],
                "start":       start_pct,
                "end":         100,
                "bottom":      4,
                "height":      18,
                "borderColor": "#1e3a2a",
                "backgroundColor": "#0a1a12",
                "dataBackground": {
                    "lineStyle": {"color": "#1e3a2a"},
                    "areaStyle": {"color": "#0a1f12"},
                },
                "selectedDataBackground": {
                    "lineStyle": {"color": "#10b981"},
                    "areaStyle": {"color": "#0a2a18"},
                },
                "fillerColor": "rgba(16,185,129,0.08)",
                "handleStyle": {"color": "#10b981"},
                "textStyle":   {"color": "#4b6a57", "fontSize": 9},
            },
        ],
        "series": [
            {
                "name":       ticker,
                "type":       "candlestick",
                "xAxisIndex": 0,
                "yAxisIndex": 0,
                "data":       candle_data,
                # Series-level itemStyle is what ECharts uses to decide
                # bullish vs bearish colors. Per-item overrides break this.
                # color / borderColor       = bullish (close >= open)
                # color0 / borderColor0     = bearish (close <  open)
                "itemStyle": {
                    "color":        "transparent",   # bullish body hollow
                    "color0":       "transparent",   # bearish body hollow
                    "borderColor":  "#10b981",       # bullish border/wick green
                    "borderColor0": "#f87171",       # bearish border/wick red
                    "borderWidth":  1,
                },
                "markPoint": {
                    "data":      mark_points,
                    "animation": False,
                    "silent":    False,
                },
                "markLine": {
                    "symbol":    ["none", "none"],
                    "data":      mark_lines,
                    "animation": False,
                    "silent":    True,
                },
            },
            {
                "name":       "EMA 20",
                "type":       "line",
                "xAxisIndex": 0,
                "yAxisIndex": 0,
                "data":       ema_data,
                "smooth":     False,
                "lineStyle":  {"color": "#facc15", "width": 1.5},
                "symbol":     "none",
                "z":          3,
            },
            {
                "name":       "Volume",
                "type":       "bar",
                "xAxisIndex": 1,
                "yAxisIndex": 1,
                "data":       vol_data,
                "barMaxWidth": 8,
            },
        ],
    }
 
    st_echarts(
        options=option,
        height=f"{height}px",
        key=f"echarts_{ticker}_{height}",
    )

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

        closed_trades    = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="Closed_Trades")
        current_trades   = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="Open_Trades")
        strategy_metrics = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="Best_Strategy_Summary")
        refresh_df       = pd.read_excel("Complete_Trades_Metrics.xlsx", sheet_name="refresh_date")
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
        # ── FIX: Clear all radio session state keys so the displayed ticker
        #    resets to match the first item in each tab after reload.
        #    Without this, the radio widget resets visually to item[0]
        #    but the old session_state value lingers, causing the chart
        #    to render the previously selected ticker instead. ─────────────────
        for key in ["buy_ticker", "tp_ticker", "close_ticker"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

# Load data
data, all_symbols, df_strategy, refresh_date_obj, refresh_date_str = load_data()
df_current = data["current"].copy()
df_closed  = data["closed"].copy()
st.caption(f"📅 Data as of: **{refresh_date_str}**")

# ── Moving ticker tape ────────────────────────────────────────────────────────
_all_facts = [
    "🧠 Discipline Wins: Following your rules beats predicting the market.",
    "⏳ Patience Pays: Sometimes the best trade is no trade at all.",
    "📊 Plan Before You Trade: Know your entry and exit before starting.",
    "🎢 Emotions Are the Enemy: Fear and greed cost more than market moves.",
    "💡 Risk Management: Never risk more than you can afford to lose.",
    "🔥 Trend Follower: The trend is your friend until it ends.",
    "⚡ Quick Decisions: Opportunities are fleeting, but rushing is dangerous.",
    "📐 Position Size Matters: Risk small, stay in the game.",
    "🔄 Cut Losses Fast: A small loss today beats a big one tomorrow.",
]
_tape_text = "  ·  ".join(_all_facts) + "  ·  " + "  ·  ".join(_all_facts)
_tape_style = (
    "<style>"
    "@keyframes tape { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }"
    ".ticker-outer { width:100%; overflow:hidden; background:#0a1f12; border:1px solid #1e3a2a;"
    "border-radius:6px; padding:7px 0; margin-bottom:14px; }"
    ".ticker-inner { display:inline-block; white-space:nowrap; animation:tape 60s linear infinite;"
    "font-family:'DM Mono',monospace; font-size:12px; color:#10b981; letter-spacing:0.03em; }"
    "</style>"
)
_tape_div = '<div class="ticker-outer"><div class="ticker-inner">' + _tape_text + '</div></div>'
st.markdown(_tape_style + _tape_div, unsafe_allow_html=True)

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

    st.markdown("---")
    st.markdown("### 📊 Market Pulse")
    st.markdown(f"{sentiment_emoji} **EGX30: {sentiment_text}**")

    if len(holds_df) > 0:
        pnl_col = 'Trade_PnL_%'
        positive_holds  = holds_df[holds_df[pnl_col] > 0] if pnl_col in holds_df.columns else pd.DataFrame()
        avg_pnl         = holds_df[pnl_col].mean() if pnl_col in holds_df.columns else 0

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

        negative_holds = holds_df[holds_df[pnl_col] < 0] if pnl_col in holds_df.columns else pd.DataFrame()
        if len(negative_holds) > 0:
            st.markdown("<div style='font-size:10px;color:#4b6a57;text-transform:uppercase;"
                        "letter-spacing:.1em;margin:10px 0 4px'>📉 Top Losers</div>",
                        unsafe_allow_html=True)
            bot3 = negative_holds.nsmallest(3, pnl_col)[['Ticker', pnl_col]]
            for _, r in bot3.iterrows():
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;"
                    f"background:#1a0a0a;border:1px solid #3a1e1e;border-radius:6px;"
                    f"padding:6px 10px;margin-bottom:4px'>"
                    f"<span style='color:#fecaca;font-weight:600'>{r['Ticker']}</span>"
                    f"<span style='color:#f87171;font-weight:700'>▼ {r[pnl_col]:.1f}%</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

    st.markdown("---")


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

        ticker_closed = df_closed_other[df_closed_other['Ticker'] == selected].copy()
        ticker_closed_arg = ticker_closed if len(ticker_closed) > 0 else None

        draw_candle_chart(selected, height=650,
                          stop_loss=sl, target=tg, entry=en, entry_date=ed,
                          closed_trades_df=ticker_closed_arg)

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
    if len(take_profit_df) > 0:
        _s1, _s2, _s3, _s4 = st.columns(4)
        _s1.metric("🎯 Count",    len(take_profit_df))
        _s2.metric("🚀 Best PnL", f"{take_profit_df['Trade_PnL_%'].max():.1f}%")
        _s3.metric("📊 Avg PnL",  f"{take_profit_df['Trade_PnL_%'].mean():.1f}%")
        _s4.metric("📋 Avg Days", f"{take_profit_df['Days_Held'].mean():.0f}" if 'Days_Held' in take_profit_df.columns else "—")
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
    if len(close_now_df) > 0:
        _c1, _c2, _c3, _c4 = st.columns(4)
        _c1.metric("❌ Count",    len(close_now_df))
        _c2.metric("🚀 Best PnL", f"{close_now_df['Trade_PnL_%'].max():.1f}%")
        _c3.metric("📊 Avg PnL",  f"{close_now_df['Trade_PnL_%'].mean():.1f}%")
        _c4.metric("📋 Avg Days", f"{close_now_df['Days_Held'].mean():.0f}" if 'Days_Held' in close_now_df.columns else "—")
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
        sym_closed = df_closed_other[df_closed_other['Ticker'] == chart_symbol].copy()
        sym_closed_arg = sym_closed if len(sym_closed) > 0 else None

        sym_open = df_current_other[df_current_other['Ticker'] == chart_symbol]
        sl2 = en2 = tg2 = ed2 = None
        if len(sym_open) > 0:
            sl2, en2, tg2, ed2 = get_levels(sym_open.iloc[0])

        draw_candle_chart(chart_symbol, height=700,
                          stop_loss=sl2, target=tg2, entry=en2, entry_date=ed2,
                          closed_trades_df=sym_closed_arg)

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

    egx30_sl = egx30_en = egx30_tg = egx30_ed = None
    if len(df_current_egx30) > 0:
        egx_row  = df_current_egx30.iloc[0]
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
