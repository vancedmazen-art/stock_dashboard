import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import os
import numpy as np
import random
import textwrap
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_echarts import st_echarts, JsCode
import streamlit.components.v1 as components


# ---------------------------
# CHART DATA
# ---------------------------
@st.cache_data(ttl=60)
def load_chart_data():
    url = "https://raw.githubusercontent.com/vancedmazen-art/stock_dashboard/main/chart_6m.csv"
    df = pd.read_csv(url, parse_dates=['datetime'])
    df.columns = df.columns.str.strip().str.lower()
    return df

def load_corporate_actions():
    """Load corporate actions from GitHub - robust date handling"""
    try:
        url = "https://raw.githubusercontent.com/vancedmazen-art/stock_dashboard/main/EGX_Corporate_Actions.xlsx"
        
        splits = pd.read_excel(url, sheet_name="Splits")
        dividends = pd.read_excel(url, sheet_name="Dividends")
        
        # Convert Date column safely
        for df in [splits, dividends]:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        
        splits = splits.rename(columns={'Split_Ratio': 'Ratio', 'Type': 'Event_Type'})
        dividends = dividends.rename(columns={'Dividend_EGP': 'Amount'})
        
        return splits, dividends
        
    except Exception as e:
        st.warning(f"⚠️ Corporate actions load failed: {e}")
        return pd.DataFrame(), pd.DataFrame()
        
def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _vol_color(close, open_):
    return "#10b981" if close >= open_ else "#f87171"


def get_levels(row):
    sl = float(row["Stop_Loss"])    if pd.notna(row.get("Stop_Loss"))    else None
    en = float(row["Entry_Price"])  if pd.notna(row.get("Entry_Price"))  else None
    tg = float(row["Target_Price"]) if pd.notna(row.get("Target_Price")) else None
    ed_raw = row.get("Entry_Date", None)
    ed = pd.to_datetime(ed_raw).strftime("%Y-%m-%d") if pd.notna(ed_raw) else None
    return sl, en, tg, ed


def draw_candle_chart(
    ticker: str,
    height: int = 650,
    stop_loss=None,
    target=None,
    entry=None,
    entry_date=None,
    closed_trades_df=None,
):
    df_all = load_chart_data()
    splits_df, dividends_df = load_corporate_actions()
    df = df_all[df_all["symbol"] == ticker].copy().sort_values("datetime")

    if df.empty:
        st.warning(f"No chart data for {ticker}")
        return

    ticker_splits = splits_df[splits_df['Symbol'] == ticker].copy() if not splits_df.empty else pd.DataFrame()
    ticker_divs   = dividends_df[dividends_df['Symbol'] == ticker].copy() if not dividends_df.empty else pd.DataFrame()

    df["date_str"] = df["datetime"].dt.strftime("%Y-%m-%d")
    dates = df["date_str"].tolist()

    ca_mark_points = []
    for _, row in ticker_divs.iterrows():
        if pd.isna(row.get('Date')): continue
        div_date = row['Date'].strftime("%Y-%m-%d")
        if div_date in dates:
            idx = dates.index(div_date)
            amount = float(row['Amount'])
            ca_mark_points.append({
                "name": "DIV",
                "coord": [idx, float(df.iloc[idx]["low"]) * 0.96],
                "value": f"Div {amount:.3f}",
                "symbol": "circle", "symbolSize": 14,
                "itemStyle": {"color": "#60a5fa"},
                "label": {"show": True, "formatter": f"↓{amount:.2f}", "position": "bottom",
                          "color": "#60a5fa", "fontSize": 11, "fontFamily": "DM Mono"}
            })

    for _, row in ticker_splits.iterrows():
        if pd.isna(row.get('Date')): continue
        split_date = row['Date'].strftime("%Y-%m-%d")
        if split_date not in dates: continue
        idx = dates.index(split_date)
        ratio = float(row['Ratio'])
        is_reverse = "Reverse" in str(row.get('Event_Type', '')) or ratio < 1.0
        color  = "#f87171" if is_reverse else "#34d399"
        symbol = "diamond"  if is_reverse else "triangle"
        ca_mark_points.append({
            "name": "SPLIT",
            "coord": [idx, float(df.iloc[idx]["high"]) * 1.05],
            "value": f"{ratio:.2f}x", "symbol": symbol, "symbolSize": 16,
            "itemStyle": {"color": color},
            "label": {"show": True, "formatter": "S" if is_reverse else "F",
                      "position": "top", "color": color, "fontSize": 12, "fontWeight": "bold"}
        })

    mark_points = []

    def _add_buy(date_str, price_low):
        if date_str not in dates: return
        idx = dates.index(date_str)
        mark_points.append({
            "name": "BUY", "coord": [idx, price_low * 0.975],
            "value": "", "symbol": "triangle", "symbolSize": 20,
            "itemStyle": {"color": "#10b981"}, "label": {"show": False}
        })

    def _add_sell(date_str, price_high, pnl_val):
        if date_str not in dates: return
        idx = dates.index(date_str)
        lbl = f"{pnl_val:+.1f}%" if pd.notna(pnl_val) else ""
        clr = "#34d399" if (pd.notna(pnl_val) and pnl_val >= 0) else "#f87171"
        mark_points.append({
            "name": "SELL", "coord": [idx, price_high * 1.025],
            "value": lbl, "symbol": "triangle", "symbolSize": 20, "symbolRotate": 180,
            "itemStyle": {"color": "#f87171"},
            "label": {"show": True, "formatter": lbl, "position": "top",
                      "color": clr, "fontSize": 13, "fontWeight": "700", "fontFamily": "DM Mono"}
        })

    if entry_date:
        ed_str = pd.to_datetime(entry_date).strftime("%Y-%m-%d")
        if ed_str in dates:
            ed_row = df[df["date_str"] == ed_str]
            if not ed_row.empty:
                _add_buy(ed_str, float(ed_row["low"].values[0]))

    if closed_trades_df is not None and len(closed_trades_df) > 0:
        ctdf = closed_trades_df.copy()
        ctdf["Entry_Date"] = pd.to_datetime(ctdf["Entry_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
        ctdf["Exit_Date"]  = pd.to_datetime(ctdf["Exit_Date"],  errors="coerce").dt.strftime("%Y-%m-%d")
        for _, tr in ctdf.iterrows():
            tr_ed = str(tr.get("Entry_Date", ""))[:10]
            if tr_ed in dates:
                ed_r = df[df["date_str"] == tr_ed]
                if not ed_r.empty and pd.notna(tr.get("Entry_Price")):
                    _add_buy(tr_ed, float(ed_r["low"].values[0]))
            tr_xd = str(tr.get("Exit_Date", ""))[:10]
            if tr_xd in dates:
                xd_r = df[df["date_str"] == tr_xd]
                if not xd_r.empty and pd.notna(tr.get("Exit_Price")):
                    _add_sell(tr_xd, float(xd_r["high"].values[0]), tr.get("Trade_PnL_%"))

    all_mark_points = mark_points + ca_mark_points

    df["ema20"] = _ema(df["close"], 20).round(4)
    dates = df["date_str"].tolist()
    n = len(dates)

    max_date     = df["datetime"].max()
    start_cutoff = (max_date - timedelta(days=90)).strftime("%Y-%m-%d")
    start_idx    = next((i for i, d in enumerate(dates) if d >= start_cutoff), 0)
    start_pct    = round(start_idx / n * 100)

    candle_data = [[float(r["open"]), float(r["close"]), float(r["low"]), float(r["high"])] for _, r in df.iterrows()]
    vol_data    = [{"value": float(r["volume"]), "itemStyle": {"color": _vol_color(r["close"], r["open"]), "opacity": 0.75}} for _, r in df.iterrows()]
    ema_data    = [round(v, 4) for v in df["ema20"].tolist()]

    mark_lines_data = []
    if stop_loss is not None:
        mark_lines_data.append({"yAxis": float(stop_loss), "lineStyle": {"color": "#f87171", "width": 1.5, "type": "dashed"},
                                 "label": {"show": True, "formatter": f"Stop {float(stop_loss):.3f}", "position": "insideEndTop", "color": "#f87171", "fontSize": 11}})
    if entry is not None:
        mark_lines_data.append({"yAxis": float(entry), "lineStyle": {"color": "#94a3b8", "width": 1.5, "type": "dotted"},
                                 "label": {"show": True, "formatter": f"Entry {float(entry):.3f}", "position": "insideEndTop", "color": "#94a3b8", "fontSize": 11}})
    if target is not None:
        mark_lines_data.append({"yAxis": float(target), "lineStyle": {"color": "#10b981", "width": 1.5, "type": "dashed"},
                                 "label": {"show": True, "formatter": f"Target {float(target):.3f}", "position": "insideEndTop", "color": "#10b981", "fontSize": 11}})

    dates_json       = json.dumps(dates)
    candle_json      = json.dumps(candle_data)
    vol_json         = json.dumps(vol_data)
    ema_json         = json.dumps(ema_data)
    mark_points_json = json.dumps(all_mark_points)
    mark_lines_json  = json.dumps(mark_lines_data)

    html = textwrap.dedent(f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8"/>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      html, body {{ width:100%; height:100%; background:#0f172a; font-family:'DM Mono',monospace; overflow:hidden; }}
      #toolbar {{ display:flex; align-items:center; gap:5px; padding:5px 8px; background:#0a1f12;
        border:1px solid #1e3a2a; border-radius:6px; margin-bottom:5px; flex-wrap:wrap; }}
      .tb-btn {{ background:#0f172a; border:1px solid #1e3a2a; border-radius:5px; color:#9ca3af;
        font-size:11px; font-family:'DM Mono',monospace; padding:3px 9px; cursor:pointer; transition:all .15s; }}
      .tb-btn:hover  {{ background:#1e3a2a; color:#d1fae5; }}
      .tb-btn.active {{ background:#10b981; color:#0f172a; border-color:#10b981; font-weight:700; }}
      #trend-hint {{ font-size:10px; color:#facc15; display:none; margin-left:4px; }}
      #chart {{ width:100%; height:{height}px; }}
    </style>
    </head>
    <body>

    <div id="toolbar">
      <span style="color:#4b6a57;font-size:11px;">Draw</span>
      <button class="tb-btn" id="btn-hline" onclick="setMode('hline')">── H-Line</button>
      <button class="tb-btn" id="btn-vline" onclick="setMode('vline')">│ V-Line</button>
      <button class="tb-btn" id="btn-trend" onclick="setMode('trend')">↗ Trendline</button>
      <span id="trend-hint">▶ drag then release</span>
      <button class="tb-btn" onclick="deleteLast()">✕ Last</button>
      <button class="tb-btn" onclick="clearAll()">✕ All</button>
      <button class="tb-btn" onclick="resetZoom()">⟳ Reset</button>
      <button class="tb-btn active" id="btn-none" onclick="setMode(null)">✋ Pointer</button>
      <button class="tb-btn" id="btn-fullscreen"
        style="margin-left:auto; border-color:#facc15; color:#facc15;"
        onclick="openFullscreen()">⛶ Full Screen</button>
    </div>

    <div id="chart"></div>

    <script>
    const DATES      = {dates_json};
    const CANDLES    = {candle_json};
    const VOL        = {vol_json};
    const EMA        = {ema_json};
    const MARK_PTS   = {mark_points_json};
    const MARK_LINES = {mark_lines_json};
    const START_PCT  = {start_pct};
    const TICKER     = "{ticker}";

    // ── Full screen: serialize everything into a self-contained page ──────────
    function openFullscreen() {{
      var w = window.open('', '_blank');
      w.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"/>
        <title>EGX: ${{TICKER}}</title>
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"><\/script>
        <style>
          *{{box-sizing:border-box;margin:0;padding:0}}
          html,body{{width:100%;height:100%;background:#0f172a;font-family:'DM Mono',monospace;overflow:hidden}}
          #toolbar{{display:flex;align-items:center;gap:5px;padding:6px 10px;background:#0a1f12;
            border-bottom:1px solid #1e3a2a;flex-wrap:wrap}}
          .tb-btn{{background:#0f172a;border:1px solid #1e3a2a;border-radius:5px;color:#9ca3af;
            font-size:12px;padding:4px 10px;cursor:pointer}}
          .tb-btn:hover{{background:#1e3a2a;color:#d1fae5}}
          .tb-btn.active{{background:#10b981;color:#0f172a;border-color:#10b981;font-weight:700}}
          #trend-hint{{font-size:10px;color:#facc15;display:none;margin-left:4px}}
          #chart{{width:100%;height:calc(100vh - 44px)}}
        </style></head><body>
        <div id="toolbar">
          <span style="color:#4b6a57;font-size:11px;">Draw</span>
          <button class="tb-btn" id="btn-hline" onclick="setMode('hline')">── H-Line</button>
          <button class="tb-btn" id="btn-vline" onclick="setMode('vline')">│ V-Line</button>
          <button class="tb-btn" id="btn-trend" onclick="setMode('trend')">↗ Trendline</button>
          <span id="trend-hint">▶ drag then release</span>
          <button class="tb-btn" onclick="deleteLast()">✕ Last</button>
          <button class="tb-btn" onclick="clearAll()">✕ All</button>
          <button class="tb-btn" onclick="resetZoom()">⟳ Reset</button>
          <button class="tb-btn active" id="btn-none" onclick="setMode(null)">✋ Pointer</button>
        </div>
        <div id="chart"></div>
        <script>
          const DATES=${{JSON.stringify(DATES)}};
          const CANDLES=${{JSON.stringify(CANDLES)}};
          const VOL=${{JSON.stringify(VOL)}};
          const EMA=${{JSON.stringify(EMA)}};
          const MARK_PTS=${{JSON.stringify(MARK_PTS)}};
          const MARK_LINES=${{JSON.stringify(MARK_LINES)}};
          const START_PCT=${{START_PCT}};
          const TICKER="${{TICKER}}";
        <\/script>
        <script src="https://cdn.jsdelivr.net/gh/YOUR_PLACEHOLDER/chart_logic.js"><\/script>
      </body></html>`);
      // Instead of external JS, inject the full chart logic inline
      var script = w.document.createElement('script');
      script.textContent = getChartLogic();
      w.document.body.appendChild(script);
      w.document.close();
    }}

    function fmtVol(v) {{
      if (v >= 1e9) return (v/1e9).toFixed(1).replace(/\\.0$/,'') + 'B';
      if (v >= 1e6) return (v/1e6).toFixed(1).replace(/\\.0$/,'') + 'M';
      if (v >= 1e3) return (v/1e3).toFixed(1).replace(/\\.0$/,'') + 'K';
      return v;
    }}

    function buildOption(startPct) {{
      return {{
        backgroundColor: '#0f172a',
        animation: false,
        title: {{
          text: 'EGX: ' + TICKER,
          textStyle: {{ color:'#d1fae5', fontSize:15, fontFamily:'DM Mono', fontWeight:'700' }},
          left:'1%', top:6,
        }},
        tooltip: {{
          trigger: 'item',
          axisPointer: {{
            type:'cross',
            crossStyle: {{ color:'#4b6a57', width:1 }},
            lineStyle:  {{ color:'#4b6a57', width:1, type:'dashed' }},
          }},
          backgroundColor:'#0f172a', borderColor:'#1e3a2a', borderWidth:1, padding:[8,12],
          formatter: function(p) {{
            var v = p.value;
            if (!Array.isArray(v) || v.length < 5) {{
              if (p.seriesName === 'EMA 20')
                return '<div style="font-family:DM Mono,monospace;font-size:12px"><span style="color:#facc15">EMA20</span> <b style="color:#e2e8f0">' + parseFloat(v).toFixed(3) + '</b></div>';
              if (p.seriesName === 'Volume')
                return '<div style="font-family:DM Mono,monospace;font-size:12px"><span style="color:#6b7280">Vol</span> <b style="color:#e2e8f0">' + fmtVol(p.value) + '</b></div>';
              return '';
            }}
            var o=parseFloat(v[1]),c=parseFloat(v[2]),lo=parseFloat(v[3]),h=parseFloat(v[4]);
            var pct=((c-o)/o*100),arrow=pct>=0?'▲':'▼',col=pct>=0?'#10b981':'#f87171',sign=pct>=0?'+':'';
            return '<div style="font-family:DM Mono,monospace;font-size:12px;line-height:1.9;min-width:170px">'
              +'<b style="color:#d1fae5;font-size:13px">'+p.name+'</b><br>'
              +'<span style="color:#6b7280">O</span> <b style="color:#e2e8f0">'+o.toFixed(3)+'</b>'
              +'&nbsp;&nbsp;<span style="color:#6b7280">H</span> <b style="color:#e2e8f0">'+h.toFixed(3)+'</b><br>'
              +'<span style="color:#6b7280">L</span> <b style="color:#e2e8f0">'+lo.toFixed(3)+'</b>'
              +'&nbsp;&nbsp;<span style="color:#6b7280">C</span> <b style="color:#e2e8f0">'+c.toFixed(3)+'</b><br>'
              +'<span style="color:'+col+';font-size:13px"><b>'+arrow+' '+sign+pct.toFixed(2)+'%</b></span>'
              +'</div>';
          }},
        }},
        legend: {{ data:['EMA 20'], top:6, right:'2%', textStyle:{{ color:'#9ca3af', fontSize:11, fontFamily:'DM Mono' }} }},
        axisPointer: {{ link:[{{ xAxisIndex:'all' }}] }},
        grid: [
          {{ left:'1%', right:'6%', top:46, height:'65%' }},
          {{ left:'1%', right:'6%', top:'80%', height:'8%' }},
        ],
        xAxis: [
          {{ type:'category', data:DATES, gridIndex:0, scale:true, boundaryGap:true,
             axisLine:{{ lineStyle:{{ color:'#1e3a2a' }} }}, axisTick:{{ show:false }},
             axisLabel:{{ show:false }}, splitLine:{{ show:false }} }},
          {{ type:'category', data:DATES, gridIndex:1, scale:true, boundaryGap:true,
             axisLine:{{ lineStyle:{{ color:'#1e3a2a' }} }}, axisTick:{{ show:false }},
             axisLabel:{{ show:false }}, splitLine:{{ show:false }} }},
        ],
        yAxis: [
          {{ scale:true, gridIndex:0, position:'right', splitLine:{{ show:false }},
             axisLine:{{ show:false }}, axisTick:{{ show:false }},
             axisLabel:{{ color:'#d1fae5', fontSize:13, fontWeight:'bold', fontFamily:'DM Mono', margin:8,
                          formatter:function(v){{ return parseFloat(v).toFixed(3); }} }} }},
          {{ scale:true, gridIndex:1, position:'right', splitLine:{{ show:false }},
             axisLine:{{ show:false }}, axisTick:{{ show:false }},
             axisLabel:{{ color:'#4b6a57', fontSize:11, fontFamily:'DM Mono',
                          formatter:function(v){{ return fmtVol(v); }} }},
             name:'Vol', nameTextStyle:{{ color:'#4b6a57', fontSize:10 }} }},
        ],
        dataZoom: [
          {{ type:'inside', xAxisIndex:[0,1], start:startPct, end:100,
             zoomOnMouseWheel:true, moveOnMouseWheel:false, preventDefaultMouseMove:false }},
          {{ type:'slider', xAxisIndex:[0,1], start:startPct, end:100,
             bottom:4, height:18, borderColor:'#1e3a2a', backgroundColor:'#0a1a12',
             dataBackground:{{ lineStyle:{{ color:'#1e3a2a' }}, areaStyle:{{ color:'#0a1f12' }} }},
             selectedDataBackground:{{ lineStyle:{{ color:'#10b981' }}, areaStyle:{{ color:'#0a2a18' }} }},
             fillerColor:'rgba(16,185,129,0.08)', handleStyle:{{ color:'#10b981' }},
             textStyle:{{ color:'#4b6a57', fontSize:9 }} }},
        ],
        series: [
          {{ name:TICKER, type:'candlestick', xAxisIndex:0, yAxisIndex:0, data:CANDLES,
             itemStyle:{{ color:'transparent', color0:'transparent',
               borderColor:'#10b981', borderColor0:'#f87171', borderWidth:1 }},
             markPoint:{{ data:MARK_PTS, animation:false }},
             markLine:{{ symbol:['none','none'], animation:false, silent:true, data:MARK_LINES }} }},
          {{ name:'EMA 20', type:'line', xAxisIndex:0, yAxisIndex:0, data:EMA, smooth:false,
             lineStyle:{{ color:'#facc15', width:1.5 }}, symbol:'none', z:3 }},
          {{ name:'Volume', type:'bar', xAxisIndex:1, yAxisIndex:1, data:VOL, barMaxWidth:8 }},
        ],
      }};
    }}

    const chart = echarts.init(document.getElementById('chart'), null, {{renderer:'canvas'}});
    chart.setOption(buildOption(START_PCT));
    window.addEventListener('resize', () => chart.resize());

    function resetZoom() {{
      chart.dispatchAction({{ type:'dataZoom', dataZoomIndex:0, start:START_PCT, end:100 }});
      chart.dispatchAction({{ type:'dataZoom', dataZoomIndex:1, start:START_PCT, end:100 }});
    }}

    document.getElementById('chart').addEventListener('wheel', function(e) {{
      if (!e.ctrlKey) return;
      e.preventDefault();
      var opt  = chart.getOption();
      var dz   = opt.dataZoom[0];
      var span = dz.end - dz.start;
      var step = span * 0.08 * (e.deltaY > 0 ? 1 : -1);
      var ns   = Math.max(0, Math.min(100 - span, dz.start + step));
      chart.dispatchAction({{ type:'dataZoom', dataZoomIndex:0, start:ns, end:ns+span }});
      chart.dispatchAction({{ type:'dataZoom', dataZoomIndex:1, start:ns, end:ns+span }});
    }}, {{ passive:false }});

    // ══════════════════════════════════════════════════════════════════════════
    // DRAWING TOOLS
    // ══════════════════════════════════════════════════════════════════════════
    var drawMode     = null;
    var drawnLines   = [];
    var isDragging   = false;
    var dragStart    = null;
    var previewActive = false;
    const DRAW_COLOR  = '#facc15';

    function setMode(mode) {{
      drawMode      = mode;
      isDragging    = false;
      dragStart     = null;
      previewActive = false;
      document.getElementById('trend-hint').style.display = mode === 'trend' ? 'inline' : 'none';

      ['hline','vline','trend','none'].forEach(function(id) {{
        var btn = document.getElementById('btn-' + id);
        if (btn) btn.classList.toggle('active', (mode === null && id === 'none') || id === mode);
      }});

      chart.setOption({{ dataZoom: [{{ type:'inside', disabled: !!mode }}] }});
      chart.getZr().setCursorStyle(mode ? 'crosshair' : 'default');
      if (!mode) clearPreview();
    }}

    function pixelToData(pixelX, pixelY) {{
      var dp;
      try {{ dp = chart.convertFromPixel({{ gridIndex:0 }}, [pixelX, pixelY]); }}
      catch(e) {{ return null; }}
      if (!dp || dp.length < 2) return null;
      var idx = Math.round(dp[0]);
      if (idx < 0 || idx >= DATES.length) return null;
      return {{ idx:idx, date:DATES[idx], price:dp[1] }};
    }}

    function clearPreview() {{
      previewActive = false;
      chart.setOption({{
        series: [{{ id:'__preview__', type:'scatter', xAxisIndex:0, yAxisIndex:0,
          data:[], symbol:'none',
          markLine:{{ symbol:['none','none'], silent:true, animation:false, data:[] }} }}],
      }}, {{ replaceMerge:[] }});
    }}

    function drawPreview(x1idx, y1, x2idx, y2) {{
      if (x1idx === x2idx) return;
      var slope = (y2 - y1) / (x2idx - x1idx);
      var x0 = 0, xEnd = DATES.length - 1;
      previewActive = true;
      chart.setOption({{
        series: [{{ id:'__preview__', type:'scatter', xAxisIndex:0, yAxisIndex:0,
          data:[], symbol:'none',
          markLine:{{
            symbol:['none','none'], silent:true, animation:false,
            lineStyle:{{ color:'#facc1588', width:1.5, type:'dashed' }},
            data:[[
              {{ xAxis:DATES[x0],   yAxis:y1 + slope*(x0-x1idx)   }},
              {{ xAxis:DATES[xEnd], yAxis:y1 + slope*(xEnd-x1idx) }},
            ]],
          }} }}],
      }}, {{ replaceMerge:[] }});
    }}

    // ── Use native DOM events on the canvas for reliable drag detection ───────
    var zr      = chart.getZr();
    var canvas  = document.querySelector('#chart canvas');

    // mousedown via zrender (works fine)
    zr.on('mousedown', function(e) {{
      if (!drawMode) return;
      var d = pixelToData(e.offsetX, e.offsetY);
      if (!d) return;

      if (drawMode === 'hline') {{
        drawnLines.push({{ type:'hline', price:d.price, color:DRAW_COLOR }});
        renderDrawn();
        setMode(null);   // ← auto-revert to pointer

      }} else if (drawMode === 'vline') {{
        drawnLines.push({{ type:'vline', idx:d.idx, date:d.date, color:DRAW_COLOR }});
        renderDrawn();
        setMode(null);   // ← auto-revert to pointer

      }} else if (drawMode === 'trend') {{
        isDragging = true;
        dragStart  = d;
        document.getElementById('trend-hint').style.display = 'inline';
      }}
    }});

    zr.on('mousemove', function(e) {{
      if (!isDragging || !dragStart) return;
      var d = pixelToData(e.offsetX, e.offsetY);
      if (!d || d.idx === dragStart.idx) return;
      drawPreview(dragStart.idx, dragStart.price, d.idx, d.price);
    }});

    // ── mouseup: listen on the WINDOW so it fires even if mouse leaves canvas ─
    window.addEventListener('mouseup', function(e) {{
      if (!isDragging || !dragStart) return;

      // convert window coords → canvas-relative coords
      var rect = canvas ? canvas.getBoundingClientRect() : null;
      var ox   = rect ? e.clientX - rect.left : e.offsetX;
      var oy   = rect ? e.clientY - rect.top  : e.offsetY;

      isDragging = false;
      document.getElementById('trend-hint').style.display = 'none';
      clearPreview();

      var d = pixelToData(ox, oy);

      if (!d || d.idx === dragStart.idx) {{
        // Zero-length drag → treat as vline
        drawnLines.push({{ type:'vline', idx:dragStart.idx, date:dragStart.date, color:DRAW_COLOR }});
      }} else {{
        drawnLines.push({{
          type:'trend',
          x1:dragStart.idx, y1:dragStart.price,
          x2:d.idx,         y2:d.price,
          color:DRAW_COLOR,
        }});
      }}
      dragStart = null;
      renderDrawn();
      setMode(null);   // ← auto-revert to pointer after trendline
    }});

    function deleteLast() {{ drawnLines.pop(); renderDrawn(); }}
    function clearAll()   {{
      drawnLines = []; isDragging = false; dragStart = null;
      clearPreview();
      renderDrawn();
    }}

    function renderDrawn() {{
      var ml = [];
      drawnLines.forEach(function(ln) {{
        if (ln.type === 'hline') {{
          ml.push({{
            yAxis: ln.price,
            lineStyle: {{ color:ln.color, width:1.5, type:'solid' }},
            label: {{ show:true, formatter:ln.price.toFixed(3), position:'insideEndTop',
                      color:ln.color, fontSize:10, fontFamily:'DM Mono' }},
          }});
        }} else if (ln.type === 'vline') {{
          ml.push([
            {{ xAxis:ln.date, yAxis:'min',
               lineStyle:{{ color:ln.color, width:1.5, type:'solid' }},
               label:{{ show:true, formatter:ln.date, position:'insideEndTop',
                        color:ln.color, fontSize:10, fontFamily:'DM Mono' }} }},
            {{ xAxis:ln.date, yAxis:'max' }},
          ]);
        }} else if (ln.type === 'trend') {{
          var slope = (ln.y2-ln.y1)/(ln.x2-ln.x1);
          var x0=0, xEnd=DATES.length-1;
          ml.push([
            {{ xAxis:DATES[x0],   yAxis:ln.y1+slope*(x0-ln.x1),
               lineStyle:{{ color:ln.color, width:1.5, type:'solid' }},
               label:{{ show:false }} }},
            {{ xAxis:DATES[xEnd], yAxis:ln.y1+slope*(xEnd-ln.x1) }},
          ]);
        }}
      }});
      chart.setOption({{
        series: [{{ id:'__drawn__', type:'scatter', xAxisIndex:0, yAxisIndex:0,
          data:[], symbol:'none',
          markLine:{{ symbol:['none','none'], silent:true, animation:false, data:ml }} }}],
      }}, {{ replaceMerge:[] }});
    }}

    // ── Full screen logic: inject chart logic into new window ─────────────────
    function getChartLogic() {{
      return `
        ${{fmtVol.toString()}}
        ${{buildOption.toString()}}
        var chart = echarts.init(document.getElementById('chart'), null, {{renderer:'canvas'}});
        chart.setOption(buildOption(START_PCT));
        window.addEventListener('resize', () => chart.resize());
        ${{resetZoom.toString()}}
        var drawMode=null,drawnLines=[],isDragging=false,dragStart=null,previewActive=false;
        var DRAW_COLOR='#facc15';
        ${{setMode.toString()}}
        ${{pixelToData.toString()}}
        ${{clearPreview.toString()}}
        ${{drawPreview.toString()}}
        var zr=chart.getZr();
        var canvas=document.querySelector('#chart canvas');
        zr.on('mousedown',function(e){{
          if(!drawMode)return;
          var d=pixelToData(e.offsetX,e.offsetY);if(!d)return;
          if(drawMode==='hline'){{drawnLines.push({{type:'hline',price:d.price,color:DRAW_COLOR}});renderDrawn();setMode(null);}}
          else if(drawMode==='vline'){{drawnLines.push({{type:'vline',idx:d.idx,date:d.date,color:DRAW_COLOR}});renderDrawn();setMode(null);}}
          else if(drawMode==='trend'){{isDragging=true;dragStart=d;document.getElementById('trend-hint').style.display='inline';}}
        }});
        zr.on('mousemove',function(e){{if(!isDragging||!dragStart)return;var d=pixelToData(e.offsetX,e.offsetY);if(!d||d.idx===dragStart.idx)return;drawPreview(dragStart.idx,dragStart.price,d.idx,d.price);}});
        window.addEventListener('mouseup',function(e){{
          if(!isDragging||!dragStart)return;
          var rect=canvas?canvas.getBoundingClientRect():null;
          var ox=rect?e.clientX-rect.left:e.offsetX,oy=rect?e.clientY-rect.top:e.offsetY;
          isDragging=false;document.getElementById('trend-hint').style.display='none';clearPreview();
          var d=pixelToData(ox,oy);
          if(!d||d.idx===dragStart.idx){{drawnLines.push({{type:'vline',idx:dragStart.idx,date:dragStart.date,color:DRAW_COLOR}});}}
          else{{drawnLines.push({{type:'trend',x1:dragStart.idx,y1:dragStart.price,x2:d.idx,y2:d.price,color:DRAW_COLOR}});}}
          dragStart=null;renderDrawn();setMode(null);
        }});
        ${{deleteLast.toString()}}
        ${{clearAll.toString()}}
        ${{renderDrawn.toString()}}
        renderDrawn();
      `;
    }}

    renderDrawn();
    </script>
    </body>
    </html>
    """)

    components.html(html, height=height + 65, scrolling=False)


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


# ── Formatting helpers ────────────────────────────────────────────────────────
# safe()    → 3 decimal places for prices / ratios
# safepct() → 2 decimal places for percentages

def safe(v, dec=3):
    """Format a numeric value to `dec` decimal places (default 3 for prices)."""
    try:
        if pd.isna(v):
            return "—"
        return f"{float(v):.{dec}f}"
    except Exception:
        return str(v) if v else "—"


def safepct(v, dec=2):
    """Format a percentage value to `dec` decimal places (default 2)."""
    try:
        if pd.isna(v):
            return "—"
        return f"{float(v):.{dec}f}"
    except Exception:
        return str(v) if v else "—"


# ─────────────────────────────────────────────────────────────────────────────
# Column sets that contain percentages so render_metrics_list knows which
# columns to display with safepct() instead of safe().
# ─────────────────────────────────────────────────────────────────────────────
PCT_COLS = {
    "Trade_PnL_%", "Risk_%", "Reward_%", "win_rate", "median_pnl",
}

# Columns that need exactly 1 decimal place
ONE_DEC_COLS = {"RR_Ratio"}


def fetch_latest_news(symbol: str, max_items: int = 3) -> list:
    """
    Two-attempt strategy:
    1. Symbol-specific endpoint (most accurate)
    2. Egypt market feed with title fallback (catches untagged articles)
    """
    tz = pytz.timezone("Africa/Cairo")
    symbol_upper = symbol.strip().upper()
    egx_symbol   = f"EGX:{symbol_upper}"
    seen_ids     = set()
    result       = []

    def _fmt_date(ts):
        try:
            return (datetime.utcfromtimestamp(ts)
                    .replace(tzinfo=pytz.UTC)
                    .astimezone(tz)
                    .strftime('%Y-%m-%d %H:%M'))
        except Exception:
            return "Recent"

    def _parse_items(items):
        found = []
        for news in items:
            news_id = news.get("id", "")
            if not news_id or news_id in seen_ids:
                continue

            title = news.get("title", "")

            syms = [
                s.get("symbol", "").replace("EGX:", "")
                for s in news.get("relatedSymbols", [])
                if "EGX:" in s.get("symbol", "")
            ]
            symbol_match = symbol_upper in [s.upper() for s in syms]
            title_match  = symbol_upper in title.upper()

            if not (symbol_match or title_match):
                continue

            seen_ids.add(news_id)
            found.append({
                "title":    title,
                "url":      f"https://www.tradingview.com{news.get('storyPath', '')}",
                "provider": news.get("provider", {}).get("name", ""),
                "date":     _fmt_date(news.get("published", 0)),
            })
        return found

    # ── Attempt 1: symbol-specific URL ───────────────────────────────────────
    try:
        r1 = requests.get(
            "https://news-mediator.tradingview.com/news-flow/v2/news"
            f"?filter=lang%3Aen&filter=symbol%3A{egx_symbol}&client=screener",
            timeout=10,
        )
        r1.raise_for_status()
        result.extend(_parse_items(r1.json().get("items", [])))
    except Exception:
        pass

    # ── Attempt 2: broad Egypt feed ───────────────────────────────────────────
    if len(result) < max_items:
        try:
            r2 = requests.get(
                "https://news-mediator.tradingview.com/news-flow/v2/news"
                "?filter=lang%3Aen&filter=market%3Astock"
                "&filter=market_country%3AEG&client=screener",
                timeout=10,
            )
            r2.raise_for_status()
            result.extend(_parse_items(r2.json().get("items", [])))
        except Exception:
            pass

    seen_urls, deduped = set(), []
    for item in result:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            deduped.append(item)

    return deduped[:max_items]


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

        # ── date columns ──────────────────────────────────────────────────────
        if 'date' in col.lower() or 'Date' in col:
            try:
                display = pd.to_datetime(val).strftime('%Y-%m-%d')
            except Exception:
                display = str(val) if pd.notna(val) else "—"

        # ── R:R ratio → 1 decimal place ───────────────────────────────────────
        elif col in ONE_DEC_COLS:
            if isinstance(val, (int, float)):
                display = safepct(val, dec=1)
            elif isinstance(val, str) and val.replace('.', '', 1).lstrip('-').isdigit():
                display = safepct(float(val), dec=1)
            else:
                display = str(val) if pd.notna(val) else "—"

        # ── percentage columns → 2 decimal places ─────────────────────────────
        elif col in PCT_COLS:
            if isinstance(val, (int, float)):
                display = safepct(val)
            elif isinstance(val, str) and val.replace('.', '', 1).lstrip('-').isdigit():
                display = safepct(float(val))
            else:
                display = str(val) if pd.notna(val) else "—"

        # ── all other numeric columns → 3 decimal places ──────────────────────
        elif isinstance(val, (int, float)):
            display = safe(val)
        elif isinstance(val, str) and val.replace('.', '', 1).lstrip('-').isdigit():
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
    if st.button("Refresh", type="primary"):
        # Clear all cached data (load_chart_data, any other cached functions)
        st.cache_data.clear()
        st.cache_resource.clear()
        # Clear relevant session state keys
        for key in list(st.session_state.keys()):
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
def compute_gappers(chart_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each symbol find the two most-recent sessions.
    A gap-up occurs when: today_open > max(prev_open, prev_close)
    Returns a DataFrame with columns: symbol, today_open, prev_open, prev_close, gap_pct
    """
    results = []
    for symbol, grp in chart_df.groupby("symbol"):
        grp = grp.sort_values("datetime")
        if len(grp) < 2:
            continue
        today = grp.iloc[-1]
        prev  = grp.iloc[-2]
        today_open = float(today["open"])
        today_close = float(today["close"])
        prev_open  = float(prev["open"])
        prev_close = float(prev["close"])
        prev_max   = max(prev_open, prev_close)
        if today_open > prev_max and today_close > prev_max:
            gap_pct = (today_open - prev_max) / prev_max * 100
            results.append({
                "Ticker":      symbol,
                "Today_Open":  today_open,
                "Prev_Open":   prev_open,
                "Prev_Close":  prev_close,
                "Gap_%":       round(gap_pct, 2),
            })
    return pd.DataFrame(results)


chart_df_all  = load_chart_data()
gappers_raw   = compute_gappers(chart_df_all)

# Keep only gappers that also have an open trade
if not gappers_raw.empty and not df_current_other.empty:
    gappers_df = df_current_other.merge(
        gappers_raw[["Ticker", "Today_Open", "Prev_Open", "Prev_Close", "Gap_%"]],
        on="Ticker",
        how="inner",
    ).sort_values("Entry_Date", ascending=False)
else:
    gappers_df = pd.DataFrame()
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
        positive_holds = holds_df[holds_df[pnl_col] > 0] if pnl_col in holds_df.columns else pd.DataFrame()
        negative_holds = holds_df[holds_df[pnl_col] < 0] if pnl_col in holds_df.columns else pd.DataFrame()
        avg_pnl = holds_df[pnl_col].mean() if pnl_col in holds_df.columns else 0

        avg_color = "#34d399" if avg_pnl >= 0 else "#f87171"
        avg_sign  = "▲" if avg_pnl >= 0 else "▼"

        st.markdown(f"""
        <div style='background:#0f172a;border:1px solid #1e3a2a;border-radius:8px;
        padding:10px;margin:6px 0'>
            <div style='font-size:10px;color:#4b6a57;text-transform:uppercase'>
                Portfolio Avg PnL
            </div>
            <div style='font-size:18px;font-weight:700;color:{avg_color}'>
                {avg_sign} {avg_pnl:.1f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Top performers
        if len(positive_holds) > 0:
            st.markdown("🏆 **Top Performers**")
            for _, r in positive_holds.nlargest(3, pnl_col).iterrows():
                st.markdown(f"""
                <div style='display:flex;justify-content:space-between;
                background:#0a1f12;padding:6px 10px;border-radius:6px;margin-bottom:4px'>
                    <span style='color:#d1fae5'>{r['Ticker']}</span>
                    <span style='color:#34d399'>▲ {r[pnl_col]:.1f}%</span>
                </div>
                """, unsafe_allow_html=True)

        # Top losers
        if len(negative_holds) > 0:
            st.markdown("📉 **Top Losers**")
            for _, r in negative_holds.nsmallest(3, pnl_col).iterrows():
                st.markdown(f"""
                <div style='display:flex;justify-content:space-between;
                background:#1a0a0a;padding:6px 10px;border-radius:6px;margin-bottom:4px'>
                    <span style='color:#fecaca'>{r['Ticker']}</span>
                    <span style='color:#f87171'>▼ {r[pnl_col]:.1f}%</span>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("""
    <div style="text-align:center">
    
    <div style="font-size:10px;color:#4b6a57;text-transform:uppercase;margin-bottom:6px">
        Contact
    </div>
    
    <div style="font-size:15px;font-weight:700;color:#25D366;margin-bottom:6px">
        WhatsApp Support
    </div>
    
    <a href="https://wa.me/201067352509" target="_blank"
    style="display:inline-block;background:#25D366;color:#0f172a;
    padding:8px 12px;border-radius:6px;font-size:13px;
    text-decoration:none;font-weight:700;">
        💬 Chat Now
    </a>
    
    <div style="margin-top:6px;font-size:11px;color:#9ca3af">
        01067352509
    </div>
    
    <div style="margin-top:10px;font-size:10px;color:#6b7280">
        Designed by Mazen Diab
    </div>
    
    </div>
    """, unsafe_allow_html=True)


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
tab_buys, tab_tp, tab_close, tab_holds, tab_charts, tab_egx30, tab_gappers = st.tabs([
    f"🆕 Fresh Buys ({len(fresh_buys_df)})",
    f"🎯 Take Profit ({len(take_profit_df)})",
    f"❌ Close Now ({len(close_now_df)})",
    f"✅ Holds ({len(holds_df)})",
    "📈 Charts",
    "📊 EGX30",
    f"⚡ Gappers ({len(gappers_df)})",
])


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
        show_levels=False, show_news=True,
    )

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

with tab_charts:
    st.markdown("### 📈 Chart")
    chart_df_all = load_chart_data()
    available_symbols = sorted(chart_df_all['symbol'].dropna().unique().tolist())
    ch_col1, ch_col2 = st.columns([2, 5])
    with ch_col1:
        chart_symbol = st.selectbox("Symbol", options=available_symbols,
                                    key="chart_lookup_symbol", help="Type to search")
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
                hist_cols = [c for c in ['Entry_Date','Exit_Date','Entry_Price','Exit_Price',
                                         'Trade_PnL_%','Days_Held','Exit_Reason'] if c in sym_closed.columns]
                st.dataframe(fix_pyarrow_df(sym_closed[hist_cols].sort_values('Entry_Date', ascending=False)),
                             use_container_width=True, height=300)
        else:
            st.caption("No trade history for this symbol.")
        st.markdown("#### 📰 Latest News")
        chart_news = fetch_latest_news(chart_symbol, max_items=3)
        if chart_news:
            for n in chart_news:
                st.markdown(f"**{n['title']}**")
                st.caption(f"📅 {n['date']} | {n['provider']} | [Read]({n['url']})")
                st.divider()
        else:
            st.caption("No recent news found.")

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
                ("Score",         safe(strat.get('composite_score'))),           # 3 dec
                ("Win Rate",      f"{safepct(strat.get('win_rate'))}%"),          # 2 dec
                ("Median PnL",    f"{safepct(strat.get('median_pnl'))}%"),        # 2 dec
                ("Total Trades",  safe(strat.get('total_trades'), 0)),
            ]
            if len(df_current_egx30) > 0:
                egx_row = df_current_egx30.iloc[0]
                egx_metric_rows += [
                    ("Entry Date",  pd.to_datetime(egx_row.get('Entry_Date')).strftime('%Y-%m-%d') if pd.notna(egx_row.get('Entry_Date')) else '—'),
                    ("Entry Price", safe(egx_row.get('Entry_Price'))),            # 3 dec
                    ("Stop Loss",   safe(egx_row.get('Stop_Loss'))),              # 3 dec
                    ("Target",      safe(egx_row.get('Target_Price'))),           # 3 dec
                    ("PnL %",       f"{safepct(egx_row.get('Trade_PnL_%'))}%"),  # 2 dec
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
                hist_cols = [c for c in ['Entry_Date','Exit_Date','Entry_Price','Exit_Price',
                                         'Trade_PnL_%','Days_Held','Exit_Reason'] if c in df_closed_egx30.columns]
                st.dataframe(fix_pyarrow_df(df_closed_egx30[hist_cols].sort_values('Entry_Date', ascending=False)),
                             use_container_width=True, height=260)
        st.markdown("### 📰 Market News")
        news = fetch_latest_news("EGX30", max_items=5)
        if news:
            for n in news:
                st.markdown(f"**{n['title']}**")
                st.caption(f"📢 {n['provider']} | [Read]({n['url']})")
                st.divider()
        else:
            st.info("No recent EGX30 news")
with tab_gappers:
    st.markdown("### ⚡ Gapping Up — Open Trades Only")
    if not gappers_df.empty:
        g1, g2, g3 = st.columns(3)
        g1.metric("⚡ Count",    len(gappers_df))
        g2.metric("🚀 Best Gap", f"{gappers_df['Gap_%'].max():.2f}%")
        g3.metric("📊 Avg Gap",  f"{gappers_df['Gap_%'].mean():.2f}%")

    stock_panel(
        gappers_df, "gap_ticker",
        metric_cols=[
            ("Entry Date",  "Entry_Date",  "neutral"),
            ("Entry Price", "Entry_Price", "neutral"),
            ("Today Open",  "Today_Open",  "gain"),
            ("Prev Close",  "Prev_Close",  "neutral"),
            ("Prev Open",   "Prev_Open",   "neutral"),
            ("Gap %",       "Gap_%",       "gain"),
            ("Stop Loss",   "Stop_Loss",   "loss"),
            ("Target",      "Target_Price","gain"),
            ("R:R",         "RR_Ratio",    "warn"),
        ],
        show_levels=True, show_news=True,
    )
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#888;font-size:11px;padding:12px'>"
    "⚠️ For educational purposes only. Not financial advice. All trading carries risk."
    "</div>", unsafe_allow_html=True)
