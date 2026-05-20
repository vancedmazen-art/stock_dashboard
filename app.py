import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import os
import textwrap
import json
import streamlit.components.v1 as components
import numpy as np


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
    try:
        url = "https://raw.githubusercontent.com/vancedmazen-art/stock_dashboard/main/EGX_Corporate_Actions.xlsx"
        splits    = pd.read_excel(url, sheet_name="Splits")
        dividends = pd.read_excel(url, sheet_name="Dividends")
        for df in [splits, dividends]:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        splits    = splits.rename(columns={'Split_Ratio':'Ratio','Type':'Event_Type'})
        dividends = dividends.rename(columns={'Dividend_EGP':'Amount'})
        return splits, dividends
    except:
        return pd.DataFrame(), pd.DataFrame()

def _ema(series, span):
    return series.ewm(span=span, adjust=False).mean()
def _wma(series, period):
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(
        lambda x: np.dot(x, weights) / weights.sum(),
        raw=True
    )
def _hma(series, period):
    half = int(period / 2)
    sqrt_period = int(np.sqrt(period))

    wma_half = _wma(series, half)
    wma_full = _wma(series, period)

    raw_hma = 2 * wma_half - wma_full

    return _wma(raw_hma, sqrt_period)

def _vol_color(close, open_):
    return "#10b981" if close >= open_ else "#f87171"

def draw_candle_chart(ticker, height=650, stop_loss=None, entry=None, entry_date=None, closed_trades_df=None):
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
        if div_date not in dates: continue
        idx = dates.index(div_date)
        amount = float(row['Amount'])
        ca_mark_points.append({"name":"DIV","coord":[idx,float(df.iloc[idx]["low"])*0.96],"value":f"Div {amount:.3f}","symbol":"circle","symbolSize":14,"itemStyle":{"color":"#60a5fa"},"label":{"show":True,"formatter":f"↓{amount:.2f}","position":"bottom","color":"#60a5fa","fontSize":11,"fontFamily":"DM Mono"}})

    for _, row in ticker_splits.iterrows():
        if pd.isna(row.get('Date')): continue
        split_date = row['Date'].strftime("%Y-%m-%d")
        if split_date not in dates: continue
        idx = dates.index(split_date)
        ratio = float(row['Ratio'])
        is_reverse = "Reverse" in str(row.get('Event_Type','')) or ratio < 1.0
        color  = "#f87171" if is_reverse else "#34d399"
        symbol = "diamond"  if is_reverse else "triangle"
        ca_mark_points.append({"name":"SPLIT","coord":[idx,float(df.iloc[idx]["high"])*1.05],"value":f"{ratio:.2f}x","symbol":symbol,"symbolSize":16,"itemStyle":{"color":color},"label":{"show":True,"formatter":"S" if is_reverse else "F","position":"top","color":color,"fontSize":12,"fontWeight":"bold"}})

    mark_points = []

    def _add_buy(date_str, price_low):
        if date_str not in dates: return
        idx = dates.index(date_str)
        mark_points.append({"name":"BUY","coord":[idx,price_low*0.975],"value":"","symbol":"triangle","symbolSize":20,"itemStyle":{"color":"#10b981"},"label":{"show":False}})

    def _add_sell(date_str, price_high, pnl_val):
        if date_str not in dates: return
        idx = dates.index(date_str)
        lbl = f"{pnl_val:+.1f}%" if pd.notna(pnl_val) else ""
        clr = "#34d399" if (pd.notna(pnl_val) and pnl_val >= 0) else "#f87171"
        mark_points.append({"name":"SELL","coord":[idx,price_high*1.025],"value":lbl,"symbol":"triangle","symbolSize":20,"symbolRotate":180,"itemStyle":{"color":"#f87171"},"label":{"show":True,"formatter":lbl,"position":"top","color":clr,"fontSize":13,"fontWeight":"700","fontFamily":"DM Mono"}})

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
            tr_ed = str(tr.get("Entry_Date",""))[:10]
            if tr_ed in dates:
                ed_r = df[df["date_str"]==tr_ed]
                if not ed_r.empty:
                    _add_buy(tr_ed, float(ed_r["low"].values[0]))
            tr_xd = str(tr.get("Exit_Date",""))[:10]
            if tr_xd in dates:
                xd_r = df[df["date_str"]==tr_xd]
                if not xd_r.empty:
                    _add_sell(tr_xd, float(xd_r["high"].values[0]), tr.get("PnL_%"))

    all_mark_points = mark_points + ca_mark_points
    df["ema20"] = _ema(df["close"], 20).round(4)
    df["hma20"] = _hma(df["close"], 20).round(4)
    dates = df["date_str"].tolist()
    n = len(dates)
    max_date     = df["datetime"].max()
    start_cutoff = (max_date - timedelta(days=90)).strftime("%Y-%m-%d")
    start_idx    = next((i for i,d in enumerate(dates) if d >= start_cutoff), 0)
    start_pct    = round(start_idx / n * 100)
    candle_data  = [[float(r["open"]),float(r["close"]),float(r["low"]),float(r["high"])] for _,r in df.iterrows()]
    vol_data     = [{"value":float(r["volume"]),"itemStyle":{"color":_vol_color(r["close"],r["open"]),"opacity":0.75}} for _,r in df.iterrows()]
    ema_data     = [round(v,4) for v in df["ema20"].tolist()]
    hma_data     = [round(v,4) for v in df["hma20"].tolist()]

    for i in range(1, 6):
        pad = (max_date + timedelta(days=i)).strftime("%Y-%m-%d")
        dates.append(pad)
        candle_data.append([None,None,None,None])
        vol_data.append({"value":None,"itemStyle":{"color":"transparent"}})
        ema_data.append(None)
        hma_data.append(None)

    mark_lines_data = []
    if stop_loss is not None:
        mark_lines_data.append({"yAxis":float(stop_loss),"lineStyle":{"color":"#f87171","width":1.5,"type":"dashed"},"label":{"show":True,"formatter":f"SL {float(stop_loss):.3f}","position":"insideEndTop","color":"#f87171","fontSize":11}})
    if entry is not None:
        mark_lines_data.append({"yAxis":float(entry),"lineStyle":{"color":"#94a3b8","width":1.5,"type":"dotted"},"label":{"show":True,"formatter":f"Entry {float(entry):.3f}","position":"insideEndTop","color":"#94a3b8","fontSize":11}})

    dates_json       = json.dumps(dates)
    candle_json      = json.dumps(candle_data)
    vol_json         = json.dumps(vol_data)
    ema_json         = json.dumps(ema_data)
    hma_json         = json.dumps(hma_data)
    mark_points_json = json.dumps(all_mark_points)
    mark_lines_json  = json.dumps(mark_lines_data)

    html = textwrap.dedent(f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"/>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>*{{box-sizing:border-box;margin:0;padding:0}}html,body{{width:100%;height:100%;background:#0f172a;font-family:'DM Mono',monospace;overflow:hidden}}
    #toolbar{{display:flex;align-items:center;gap:5px;padding:5px 8px;background:#0a1f12;border:1px solid #1e3a2a;border-radius:6px;margin-bottom:5px;flex-wrap:wrap}}
    .tb-btn{{background:#0f172a;border:1px solid #1e3a2a;border-radius:5px;color:#9ca3af;font-size:11px;font-family:'DM Mono',monospace;padding:3px 9px;cursor:pointer;transition:all .15s}}
    .tb-btn:hover{{background:#1e3a2a;color:#d1fae5}}.tb-btn.active{{background:#10b981;color:#0f172a;border-color:#10b981;font-weight:700}}
    #trend-hint{{font-size:10px;color:#facc15;display:none;margin-left:4px}}#chart{{width:100%;height:{height}px}}</style></head><body>
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
    const DATES={dates_json},CANDLES={candle_json},VOL={vol_json},EMA={ema_json},HMA={hma_json};
    const MARK_PTS={mark_points_json},MARK_LINES={mark_lines_json};
    const START_PCT={start_pct},TICKER="{ticker}";
    function fmtVol(v){{if(v>=1e9)return(v/1e9).toFixed(1).replace(/\\.0$/,'')+'B';if(v>=1e6)return(v/1e6).toFixed(1).replace(/\\.0$/,'')+'M';if(v>=1e3)return(v/1e3).toFixed(1).replace(/\\.0$/,'')+'K';return v;}}
    function buildOption(s){{return{{backgroundColor:'#0f172a',animation:false,
      title:{{text:'EGX: '+TICKER,textStyle:{{color:'#d1fae5',fontSize:15,fontFamily:'DM Mono',fontWeight:'700'}},left:'1%',top:6}},
      tooltip:{{trigger:'item',axisPointer:{{type:'cross',crossStyle:{{color:'#4b6a57',width:1}},lineStyle:{{color:'#4b6a57',width:1,type:'dashed'}}}},backgroundColor:'#0f172a',borderColor:'#1e3a2a',borderWidth:1,padding:[8,12],
        formatter:function(p){{var v=p.value;if(!Array.isArray(v)||v.length<5){{if(p.seriesName==='EMA 20')return'<div style="font-family:DM Mono,monospace;font-size:12px"><span style="color:#facc15">EMA20</span> <b style="color:#e2e8f0">'+parseFloat(v).toFixed(3)+'</b></div>';if(p.seriesName==='Volume')return'<div style="font-family:DM Mono,monospace;font-size:12px"><span style="color:#6b7280">Vol</span> <b style="color:#e2e8f0">'+fmtVol(p.value)+'</b></div>';return'';}}
          var o=parseFloat(v[1]),c=parseFloat(v[2]),lo=parseFloat(v[3]),h=parseFloat(v[4]),pct=((c-o)/o*100),arrow=pct>=0?'▲':'▼',col=pct>=0?'#10b981':'#f87171',sign=pct>=0?'+':'';
          return'<div style="font-family:DM Mono,monospace;font-size:12px;line-height:1.9;min-width:170px"><b style="color:#d1fae5;font-size:13px">'+p.name+'</b><br><span style="color:#6b7280">O</span> <b style="color:#e2e8f0">'+o.toFixed(3)+'</b>&nbsp;&nbsp;<span style="color:#6b7280">H</span> <b style="color:#e2e8f0">'+h.toFixed(3)+'</b><br><span style="color:#6b7280">L</span> <b style="color:#e2e8f0">'+lo.toFixed(3)+'</b>&nbsp;&nbsp;<span style="color:#6b7280">C</span> <b style="color:#e2e8f0">'+c.toFixed(3)+'</b><br><span style="color:'+col+';font-size:13px"><b>'+arrow+' '+sign+pct.toFixed(2)+'%</b></span></div>';
        }}}},
      legend:{{data:['EMA 20','HMA 20'],top:6,right:'2%',textStyle:{{color:'#9ca3af',fontSize:11,fontFamily:'DM Mono'}}}},
      axisPointer:{{link:[{{xAxisIndex:'all'}}]}},
      grid:[{{left:'1%',right:'6%',top:46,height:'65%'}},{{left:'1%',right:'6%',top:'80%',height:'8%'}}],
      xAxis:[{{type:'category',data:DATES,gridIndex:0,scale:true,boundaryGap:true,axisLine:{{lineStyle:{{color:'#1e3a2a'}}}},axisTick:{{show:false}},axisLabel:{{show:false}},splitLine:{{show:false}}}},{{type:'category',data:DATES,gridIndex:1,scale:true,boundaryGap:true,axisLine:{{lineStyle:{{color:'#1e3a2a'}}}},axisTick:{{show:false}},axisLabel:{{show:false}},splitLine:{{show:false}}}}],
      yAxis:[{{scale:true,gridIndex:0,position:'right',splitLine:{{show:false}},axisLine:{{show:false}},axisTick:{{show:false}},axisLabel:{{color:'#d1fae5',fontSize:13,fontWeight:'bold',fontFamily:'DM Mono',margin:8,formatter:function(v){{return parseFloat(v).toFixed(3);}}}}}},{{scale:true,gridIndex:1,position:'right',splitLine:{{show:false}},axisLine:{{show:false}},axisTick:{{show:false}},axisLabel:{{color:'#4b6a57',fontSize:11,fontFamily:'DM Mono',formatter:function(v){{return fmtVol(v);}}}},name:'Vol',nameTextStyle:{{color:'#4b6a57',fontSize:10}}}}],
      dataZoom:[{{type:'inside',xAxisIndex:[0,1],start:s,end:100,zoomOnMouseWheel:true,moveOnMouseWheel:false,preventDefaultMouseMove:false}},{{type:'slider',xAxisIndex:[0,1],start:s,end:100,bottom:4,height:18,borderColor:'#1e3a2a',backgroundColor:'#0a1a12',dataBackground:{{lineStyle:{{color:'#1e3a2a'}},areaStyle:{{color:'#0a1f12'}}}},selectedDataBackground:{{lineStyle:{{color:'#10b981'}},areaStyle:{{color:'#0a2a18'}}}},fillerColor:'rgba(16,185,129,0.08)',handleStyle:{{color:'#10b981'}},textStyle:{{color:'#4b6a57',fontSize:9}}}}],
      series:[{{name:TICKER,type:'candlestick',xAxisIndex:0,yAxisIndex:0,data:CANDLES,itemStyle:{{color:'transparent',color0:'transparent',borderColor:'#10b981',borderColor0:'#f87171',borderWidth:1}},markPoint:{{data:MARK_PTS,animation:false}},markLine:{{symbol:['none','none'],animation:false,silent:true,data:MARK_LINES}}}},{{name:'EMA 20',type:'line',xAxisIndex:0,yAxisIndex:0,data:EMA,smooth:false,lineStyle:{{color:'#facc15',width:1.5}},symbol:'none',z:3}},{{name:'HMA 20',type:'line',xAxisIndex:0,yAxisIndex:0,data:HMA,smooth:false,lineStyle:{{color:'#60a5fa',width:1.5}},symbol:'none',z:3}},{{name:'Volume',type:'bar',xAxisIndex:1,yAxisIndex:1,data:VOL,barMaxWidth:8}}],
    }};}}
    const chart=echarts.init(document.getElementById('chart'),null,{{renderer:'canvas'}});
    chart.setOption(buildOption(START_PCT));
    window.addEventListener('resize',()=>chart.resize());
    function resetZoom(){{chart.dispatchAction({{type:'dataZoom',dataZoomIndex:0,start:START_PCT,end:100}});chart.dispatchAction({{type:'dataZoom',dataZoomIndex:1,start:START_PCT,end:100}});}}
    document.getElementById('chart').addEventListener('wheel',function(e){{if(!e.ctrlKey)return;e.preventDefault();var opt=chart.getOption(),dz=opt.dataZoom[0],span=dz.end-dz.start,step=span*0.08*(e.deltaY>0?1:-1),ns=Math.max(0,Math.min(100-span,dz.start+step));chart.dispatchAction({{type:'dataZoom',dataZoomIndex:0,start:ns,end:ns+span}});chart.dispatchAction({{type:'dataZoom',dataZoomIndex:1,start:ns,end:ns+span}});}},{{passive:false}});
    var drawMode=null,drawnLines=[],isDragging=false,dragStart=null;const DRAW_COLOR='#facc15';
    function setMode(mode){{drawMode=mode;isDragging=false;dragStart=null;document.getElementById('trend-hint').style.display=mode==='trend'?'inline':'none';['hline','vline','trend','none'].forEach(function(id){{var btn=document.getElementById('btn-'+id);if(btn)btn.classList.toggle('active',(mode===null&&id==='none')||id===mode);}});chart.setOption({{dataZoom:[{{type:'inside',disabled:!!mode}}]}});chart.getZr().setCursorStyle(mode?'crosshair':'default');if(!mode)clearPreview();}}
    function pixelToData(px,py){{var dp;try{{dp=chart.convertFromPixel({{gridIndex:0}},[px,py]);}}catch(e){{return null;}}if(!dp||dp.length<2)return null;var idx=Math.round(dp[0]);if(idx<0||idx>=DATES.length)return null;return{{idx:idx,date:DATES[idx],price:dp[1]}};}}
    function clearPreview(){{chart.setOption({{series:[{{id:'__preview__',type:'scatter',xAxisIndex:0,yAxisIndex:0,data:[],symbol:'none',markLine:{{symbol:['none','none'],silent:true,animation:false,data:[]}}}}]}},{{replaceMerge:[]}});}}
    function drawPreview(x1,y1,x2,y2){{if(x1===x2)return;var sl=(y2-y1)/(x2-x1),x0=0,xe=DATES.length-1;chart.setOption({{series:[{{id:'__preview__',type:'scatter',xAxisIndex:0,yAxisIndex:0,data:[],symbol:'none',markLine:{{symbol:['none','none'],silent:true,animation:false,lineStyle:{{color:'#facc1588',width:1.5,type:'dashed'}},data:[[{{xAxis:DATES[x0],yAxis:y1+sl*(x0-x1)}},{{xAxis:DATES[xe],yAxis:y1+sl*(xe-x1)}}]]}}}}]}},{{replaceMerge:[]}});}}
    var zr=chart.getZr(),canvas=document.querySelector('#chart canvas');
    zr.on('mousedown',function(e){{if(!drawMode)return;var d=pixelToData(e.offsetX,e.offsetY);if(!d)return;if(drawMode==='hline'){{drawnLines.push({{type:'hline',price:d.price,color:DRAW_COLOR}});renderDrawn();setMode(null);}}else if(drawMode==='vline'){{drawnLines.push({{type:'vline',idx:d.idx,date:d.date,color:DRAW_COLOR}});renderDrawn();setMode(null);}}else if(drawMode==='trend'){{isDragging=true;dragStart=d;document.getElementById('trend-hint').style.display='inline';}}}});
    zr.on('mousemove',function(e){{if(!isDragging||!dragStart)return;var d=pixelToData(e.offsetX,e.offsetY);if(!d||d.idx===dragStart.idx)return;drawPreview(dragStart.idx,dragStart.price,d.idx,d.price);}});
    window.addEventListener('mouseup',function(e){{if(!isDragging||!dragStart)return;var rect=canvas?canvas.getBoundingClientRect():null,ox=rect?e.clientX-rect.left:e.offsetX,oy=rect?e.clientY-rect.top:e.offsetY;isDragging=false;document.getElementById('trend-hint').style.display='none';clearPreview();var d=pixelToData(ox,oy);if(!d||d.idx===dragStart.idx){{drawnLines.push({{type:'vline',idx:dragStart.idx,date:dragStart.date,color:DRAW_COLOR}});}}else{{drawnLines.push({{type:'trend',x1:dragStart.idx,y1:dragStart.price,x2:d.idx,y2:d.price,color:DRAW_COLOR}});}}dragStart=null;renderDrawn();setMode(null);}});
    function deleteLast(){{drawnLines.pop();renderDrawn();}}function clearAll(){{drawnLines=[];isDragging=false;dragStart=null;clearPreview();renderDrawn();}}
    function renderDrawn(){{var ml=[];drawnLines.forEach(function(ln){{if(ln.type==='hline'){{ml.push({{yAxis:ln.price,lineStyle:{{color:ln.color,width:1.5,type:'solid'}},label:{{show:true,formatter:ln.price.toFixed(3),position:'insideEndTop',color:ln.color,fontSize:10,fontFamily:'DM Mono'}}}});}}else if(ln.type==='vline'){{ml.push([{{xAxis:ln.date,yAxis:'min',lineStyle:{{color:ln.color,width:1.5,type:'solid'}},label:{{show:true,formatter:ln.date,position:'insideEndTop',color:ln.color,fontSize:10,fontFamily:'DM Mono'}}}},{{xAxis:ln.date,yAxis:'max'}}]);}}else if(ln.type==='trend'){{var sl=(ln.y2-ln.y1)/(ln.x2-ln.x1),x0=0,xe=DATES.length-1;ml.push([{{xAxis:DATES[x0],yAxis:ln.y1+sl*(x0-ln.x1),lineStyle:{{color:ln.color,width:1.5,type:'solid'}},label:{{show:false}}}},{{xAxis:DATES[xe],yAxis:ln.y1+sl*(xe-ln.x1)}}]);}}}});chart.setOption({{series:[{{id:'__drawn__',type:'scatter',xAxisIndex:0,yAxisIndex:0,data:[],symbol:'none',markLine:{{symbol:['none','none'],silent:true,animation:false,data:ml}}}}]}},{{replaceMerge:[]}});}}
    renderDrawn();
    </script></body></html>""")
    components.html(html, height=height+65, scrolling=False)


# ---------------------------
# HELPERS
# ---------------------------
def load_data():
    try:
        fname = "Pattern_Scanner_Results.xlsx"
        if not os.path.exists(fname):
            st.error(f"❌ {fname} missing!")
            st.stop()
        closed_trades  = pd.read_excel(fname, sheet_name="Closed_Trades")
        open_trades    = pd.read_excel(fname, sheet_name="Open_Trades")
        ticker_summary = pd.read_excel(fname, sheet_name="Ticker_Summary")
        for col in ['Entry_Date','Exit_Date','Trigger_Date']:
            if col in closed_trades.columns:
                closed_trades[col] = pd.to_datetime(closed_trades[col], errors='coerce')
        for col in ['Entry_Date','Trigger_Date','Last_Date']:
            if col in open_trades.columns:
                open_trades[col] = pd.to_datetime(open_trades[col], errors='coerce')
        return closed_trades, open_trades, ticker_summary
    except Exception as e:
        st.error(f"❌ Load failed: {e}")
        st.stop()

def fix_df(df):
    df = df.copy()
    for col in df.select_dtypes(include=['datetime64[ns]']).columns:
        df[col] = df[col].dt.strftime('%Y-%m-%d')
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str)
    return df.reset_index(drop=True)

def safe(v, dec=3):
    try: return "—" if pd.isna(v) else f"{float(v):.{dec}f}"
    except: return str(v) if v else "—"

def safepct(v, dec=2):
    try: return "—" if pd.isna(v) else f"{float(v):.{dec}f}"
    except: return str(v) if v else "—"

def fmt_date(v):
    try: return pd.to_datetime(v).strftime('%Y-%m-%d')
    except: return "—"

def pnl_color(v):
    try: return "#34d399" if float(v) >= 0 else "#f87171"
    except: return "#d1fae5"

def metric_card(label, value, color="#d1fae5"):
    st.markdown(f"""
    <div style="background:#0f172a;border:1px solid #1e3a2a;border-radius:9px;
                padding:9px 13px;margin-bottom:7px;">
      <div style="font-size:10px;color:#4b6a57;text-transform:uppercase;
                  letter-spacing:.1em;font-family:'DM Mono',monospace;margin-bottom:3px;">{label}</div>
      <div style="font-size:15px;font-weight:600;color:{color};font-family:'DM Mono',monospace;">{value}</div>
    </div>""", unsafe_allow_html=True)

def stat_row(label, value, pct_str=None, color="#d1fae5"):
    pct_html = f"&nbsp;<span style='color:#4b6a57;font-size:11px'>({pct_str})</span>" if pct_str else ""
    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:8px 14px;border-bottom:1px solid #1e3a2a;">
      <span style="font-size:12px;color:#6b7280;font-family:'DM Mono',monospace;">{label}</span>
      <span style="font-size:14px;font-weight:600;color:{color};font-family:'DM Mono',monospace;">{value}{pct_html}</span>
    </div>""", unsafe_allow_html=True)

def fetch_latest_news(symbol, max_items=3):
    tz = pytz.timezone("Africa/Cairo")
    symbol_upper = symbol.strip().upper()
    egx_symbol   = f"EGX:{symbol_upper}"
    seen_ids, result = set(), []
    def _fmt(ts):
        try: return datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.UTC).astimezone(tz).strftime('%Y-%m-%d %H:%M')
        except: return "Recent"
    def _parse(items):
        found = []
        for n in items:
            nid = n.get("id","")
            if not nid or nid in seen_ids: continue
            title = n.get("title","")
            syms = [s.get("symbol","").replace("EGX:","") for s in n.get("relatedSymbols",[]) if "EGX:" in s.get("symbol","")]
            if not (symbol_upper in [s.upper() for s in syms] or symbol_upper in title.upper()): continue
            seen_ids.add(nid)
            found.append({"title":title,"url":f"https://www.tradingview.com{n.get('storyPath','')}","provider":n.get("provider",{}).get("name",""),"date":_fmt(n.get("published",0))})
        return found
    for url in [
        f"https://news-mediator.tradingview.com/news-flow/v2/news?filter=lang%3Aen&filter=symbol%3A{egx_symbol}&client=screener",
        "https://news-mediator.tradingview.com/news-flow/v2/news?filter=lang%3Aen&filter=market%3Astock&filter=market_country%3AEG&client=screener"
    ]:
        if len(result) >= max_items: break
        try:
            r = requests.get(url, timeout=10); r.raise_for_status()
            result.extend(_parse(r.json().get("items",[])))
        except: pass
    seen_urls, deduped = set(), []
    for item in result:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"]); deduped.append(item)
    return deduped[:max_items]

def trade_panel(source_df, session_key, is_open=True, closed_ref=None):
    """Reusable panel: ticker list | metrics | chart"""
    if source_df.empty:
        st.info("No trades here.")
        return

    tickers = source_df['Ticker'].drop_duplicates().sort_values().tolist()
    col_list, col_metrics, col_chart = st.columns([1, 1, 5])

    with col_list:
        st.markdown("**Stocks**")
        selected = st.radio("Select", options=tickers, key=session_key, label_visibility="collapsed")

    if not selected:
        return

    rows = source_df[source_df['Ticker'] == selected].sort_values('Entry_Date', ascending=False)
    row  = rows.iloc[0]

    with col_metrics:
        st.markdown(f"**{selected}**")
        metric_card("Entry Date",      fmt_date(row.get('Entry_Date')))
        metric_card("Entry Price",     safe(row.get('Entry_Price')))
        metric_card("Stop Loss",       safe(row.get('Stop_Loss_Initial')), "#f87171")
        metric_card("Entry Risk %",    safepct(row.get('Entry_Risk_%')),   "#f87171")
        metric_card("Candles Between", str(row.get('Candles_Between','—')))
        if is_open:
            metric_card("Current Price",   safe(row.get('Last_Price')))
            pv = row.get('PnL_%')
            metric_card("PnL %",           safepct(pv), pnl_color(pv))
            metric_card("Bars Held",       str(row.get('Bars_Held','—')))
            metric_card("High Broken",     str(row.get('Entry_High_Broken','—')))
            metric_card("Range Low",       safe(row.get('Current_Range_Low')))
        else:
            metric_card("Exit Date",    fmt_date(row.get('Exit_Date')))
            metric_card("Exit Price",   safe(row.get('Exit_Price')))
            pv = row.get('PnL_%')
            metric_card("PnL %",        safepct(pv), pnl_color(pv))
            metric_card("Exit Reason",  str(row.get('Exit_Reason','—')))
            metric_card("Max Gain",     safepct(row.get('Max_Gain')),  "#34d399")
            metric_card("Max Loss",     safepct(row.get('Max_Loss')),  "#f87171")
            metric_card("Bars Held",    str(row.get('Bars_Held','—')))

    with col_chart:
        sl = float(row['Stop_Loss_Initial']) if pd.notna(row.get('Stop_Loss_Initial')) else None
        en = float(row['Entry_Price'])        if pd.notna(row.get('Entry_Price'))       else None
        ed = row.get('Entry_Date')

        # always pass closed trades for markers
        if closed_ref is not None:
            ticker_closed = closed_ref[closed_ref['Ticker'] == selected].copy()
        else:
            ticker_closed = pd.DataFrame()

        draw_candle_chart(selected, height=650, stop_loss=sl, entry=en, entry_date=ed,
                          closed_trades_df=ticker_closed if len(ticker_closed) > 0 else None)

        if not ticker_closed.empty:
            with st.expander(f"📋 Trade History — {selected} ({len(ticker_closed)} trades)", expanded=False):
                show_cols = [c for c in ['Entry_Date','Exit_Date','Entry_Price','Exit_Price',
                                         'PnL_%','Bars_Held','Exit_Reason','Max_Gain','Max_Loss']
                             if c in ticker_closed.columns]
                st.dataframe(fix_df(ticker_closed[show_cols].sort_values('Entry_Date', ascending=False)),
                             use_container_width=True, height=250)

        st.markdown("#### 📰 Latest News")
        for n in fetch_latest_news(selected, 3):
            st.markdown(f"**{n['title']}**")
            st.caption(f"📅 {n['date']} | {n['provider']} | [Read]({n['url']})")
            st.divider()


# ---------------------------
# PAGE CONFIG & LOAD
# ---------------------------
st.set_page_config(page_title="EGX Pattern Scanner", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap');
* { font-family: 'DM Mono', monospace; }
div[data-testid="stMetric"] { background:#0f172a; border:1px solid #1e3a2a; border-radius:8px; padding:10px 14px; }
</style>""", unsafe_allow_html=True)

c1, c2 = st.columns([5,1])
with c1: st.markdown("# 📡 EGX Pattern Scanner")
with c2:
    if st.button("⟳ Refresh", type="primary"):
        st.cache_data.clear(); st.cache_resource.clear()
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

df_closed, df_open, df_summary = load_data()

last_date     = df_open['Last_Date'].max() if 'Last_Date' in df_open.columns else None
last_date_str = fmt_date(last_date) if last_date else "—"
st.caption(f"📅 Data as of: **{last_date_str}**")

# Segment open trades
if last_date is not None and 'Entry_Date' in df_open.columns:
    last_date_only = pd.to_datetime(last_date).date()
    fresh_buys_df  = df_open[df_open['Entry_Date'].dt.date == last_date_only].copy()
    holds_df       = df_open[df_open['Entry_Date'].dt.date != last_date_only].copy()
else:
    fresh_buys_df = pd.DataFrame()
    holds_df      = df_open.copy()

# Close now = closed on last date
if last_date is not None and 'Exit_Date' in df_closed.columns:
    last_date_only = pd.to_datetime(last_date).date()
    close_now_df   = df_closed[df_closed['Exit_Date'].dt.date == last_date_only].copy()
else:
    close_now_df = pd.DataFrame()

# Ticker tape
_facts = ["🧠 Discipline Wins","⏳ Patience Pays","📊 Plan Before You Trade","🎢 Emotions Are the Enemy","💡 Risk Management First","🔥 Trend Is Your Friend","⚡ Cut Losses Fast","📐 Position Size Matters"]
_tape  = "  ·  ".join(_facts * 4)
st.markdown(f"""
<style>@keyframes tape{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}
.to{{width:100%;overflow:hidden;background:#0a1f12;border:1px solid #1e3a2a;border-radius:6px;padding:7px 0;margin-bottom:14px}}
.ti{{display:inline-block;white-space:nowrap;animation:tape 50s linear infinite;font-family:'DM Mono',monospace;font-size:12px;color:#10b981}}</style>
<div class="to"><div class="ti">{_tape}</div></div>""", unsafe_allow_html=True)

# ---------------------------
# SIDEBAR — full scan stats
# ---------------------------
with st.sidebar:
    st.markdown("### 📊 Scan Results")
    total   = len(df_closed)
    wins    = int((df_closed['PnL_%'] > 0).sum())    if total > 0 else 0
    sl1     = int((df_closed['Exit_Reason']=='SL').sum())        if total > 0 else 0
    sl_t    = int((df_closed['Exit_Reason']=='SL_TRAIL').sum())  if total > 0 else 0
    timeout = int((df_closed['Exit_Reason']=='TIMEOUT').sum())   if total > 0 else 0
    avg_pnl = df_closed['PnL_%'].mean()   if total > 0 else 0
    med_pnl = df_closed['PnL_%'].median() if total > 0 else 0

    def pct_of(n, total): return f"{n/total*100:.1f}%" if total > 0 else "—"

    st.markdown(f"""
    <div style="background:#0a1f12;border:1px solid #1e3a2a;border-radius:10px;padding:14px;margin-bottom:12px;">
    <div style="font-size:10px;color:#4b6a57;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;">Closed Trades</div>
    <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a2a;">
      <span style="font-size:12px;color:#6b7280;">Total</span>
      <span style="font-size:13px;font-weight:600;color:#d1fae5;">{total}</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a2a;">
      <span style="font-size:12px;color:#6b7280;">Win Rate</span>
      <span style="font-size:13px;font-weight:600;color:#34d399;">{pct_of(wins,total)}</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a2a;">
      <span style="font-size:12px;color:#6b7280;">Avg PnL</span>
      <span style="font-size:13px;font-weight:600;color:{'#34d399' if avg_pnl>=0 else '#f87171'};">{avg_pnl:.2f}%</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a2a;">
      <span style="font-size:12px;color:#6b7280;">Median PnL</span>
      <span style="font-size:13px;font-weight:600;color:{'#34d399' if med_pnl>=0 else '#f87171'};">{med_pnl:.2f}%</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a2a;">
      <span style="font-size:12px;color:#6b7280;">SL Phase 1</span>
      <span style="font-size:13px;font-weight:600;color:#f87171;">{sl1} <span style="font-size:11px;color:#4b6a57;">({pct_of(sl1,total)})</span></span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a2a;">
      <span style="font-size:12px;color:#6b7280;">SL Trail</span>
      <span style="font-size:13px;font-weight:600;color:#f87171;">{sl_t} <span style="font-size:11px;color:#4b6a57;">({pct_of(sl_t,total)})</span></span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:5px 0;">
      <span style="font-size:12px;color:#6b7280;">Timeout</span>
      <span style="font-size:13px;font-weight:600;color:#facc15;">{timeout} <span style="font-size:11px;color:#4b6a57;">({pct_of(timeout,total)})</span></span>
    </div>
    </div>

    <div style="background:#0a1f12;border:1px solid #1e3a2a;border-radius:10px;padding:14px;margin-bottom:12px;">
    <div style="font-size:10px;color:#4b6a57;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;">Open Trades</div>
    <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a2a;">
      <span style="font-size:12px;color:#6b7280;">Total Open</span>
      <span style="font-size:13px;font-weight:600;color:#d1fae5;">{len(df_open)}</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a2a;">
      <span style="font-size:12px;color:#6b7280;">Fresh Buys</span>
      <span style="font-size:13px;font-weight:600;color:#10b981;">{len(fresh_buys_df)}</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a2a;">
      <span style="font-size:12px;color:#6b7280;">Holds</span>
      <span style="font-size:13px;font-weight:600;color:#facc15;">{len(holds_df)}</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:5px 0;">
      <span style="font-size:12px;color:#6b7280;">Close Now</span>
      <span style="font-size:13px;font-weight:600;color:#f87171;">{len(close_now_df)}</span>
    </div>
    </div>
    """, unsafe_allow_html=True)

    # top gainers / losers from holds
    if len(holds_df) > 0:
        pos = holds_df[holds_df['PnL_%'] > 0]
        neg = holds_df[holds_df['PnL_%'] < 0]
        if len(pos) > 0:
            st.markdown("🏆 **Top Gainers**")
            for _, r in pos.nlargest(3,'PnL_%').iterrows():
                st.markdown(f"""<div style='display:flex;justify-content:space-between;background:#0a1f12;
                padding:6px 10px;border-radius:6px;margin-bottom:4px'>
                <span style='color:#d1fae5'>{r['Ticker']}</span>
                <span style='color:#34d399'>▲ {r['PnL_%']:.1f}%</span></div>""", unsafe_allow_html=True)
        if len(neg) > 0:
            st.markdown("📉 **Top Losers**")
            for _, r in neg.nsmallest(3,'PnL_%').iterrows():
                st.markdown(f"""<div style='display:flex;justify-content:space-between;background:#1a0a0a;
                padding:6px 10px;border-radius:6px;margin-bottom:4px'>
                <span style='color:#fecaca'>{r['Ticker']}</span>
                <span style='color:#f87171'>▼ {r['PnL_%']:.1f}%</span></div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""<div style="text-align:center">
    <a href="https://wa.me/201067352509" target="_blank"
    style="display:inline-block;background:#25D366;color:#0f172a;padding:8px 12px;
    border-radius:6px;font-size:13px;text-decoration:none;font-weight:700;">💬 WhatsApp</a>
    <div style="margin-top:6px;font-size:11px;color:#9ca3af">01067352509</div>
    <div style="margin-top:8px;font-size:10px;color:#6b7280">Designed by Mazen Diab</div>
    </div>""", unsafe_allow_html=True)


# ---------------------------
# TABS
# ---------------------------
tab_fresh, tab_holds, tab_close, tab_history, tab_summary, tab_charts, tab_egx30 = st.tabs([
    f"🆕 Fresh Buys ({len(fresh_buys_df)})",
    f"✅ Holds ({len(holds_df)})",
    f"❌ Close Now ({len(close_now_df)})",
    f"📋 History ({len(df_closed)})",
    "📊 Summary",
    "📈 Charts",
    "📊 EGX30",
])

with tab_fresh:
    st.markdown("### 🆕 Fresh Buys — entered today")
    if len(fresh_buys_df) > 0:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Count",    len(fresh_buys_df))
        c2.metric("Avg Risk", f"{fresh_buys_df['Entry_Risk_%'].mean():.2f}%" if 'Entry_Risk_%' in fresh_buys_df.columns else "—")
        c3.metric("Avg Candles Between", f"{fresh_buys_df['Candles_Between'].mean():.1f}" if 'Candles_Between' in fresh_buys_df.columns else "—")
        c4.metric("Avg Entry Vol", f"{fresh_buys_df['Entry_Volume'].mean()/1e6:.1f}M" if 'Entry_Volume' in fresh_buys_df.columns else "—")
    trade_panel(fresh_buys_df, "fresh_ticker", is_open=True, closed_ref=df_closed)

with tab_holds:
    st.markdown("### ✅ Holds — positions entered before today")
    if len(holds_df) > 0:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Count",    len(holds_df))
        c2.metric("Positive", int((holds_df['PnL_%'] > 0).sum()))
        c3.metric("Avg PnL",  f"{holds_df['PnL_%'].mean():.2f}%")
        c4.metric("Best",     f"{holds_df['PnL_%'].max():.2f}%")
    trade_panel(holds_df, "holds_ticker", is_open=True, closed_ref=df_closed)

with tab_close:
    st.markdown("### ❌ Close Now — exited today")
    if len(close_now_df) > 0:
        c1,c2,c3,c4 = st.columns(4)
        wins_cn = int((close_now_df['PnL_%'] > 0).sum())
        c1.metric("Count",    len(close_now_df))
        c2.metric("Winners",  wins_cn)
        c3.metric("Avg PnL",  f"{close_now_df['PnL_%'].mean():.2f}%")
        c4.metric("Best",     f"{close_now_df['PnL_%'].max():.2f}%")

        reasons = close_now_df['Exit_Reason'].value_counts()
        r_cols  = st.columns(len(reasons))
        for col, (reason, cnt) in zip(r_cols, reasons.items()):
            col.metric(reason, cnt)
    trade_panel(close_now_df, "close_ticker", is_open=False, closed_ref=df_closed)

with tab_history:
    st.markdown("### 📋 Full Trade History")
    if len(df_closed) > 0:
        c1,c2,c3,c4,c5 = st.columns(5)
        wins_h = int((df_closed['PnL_%'] > 0).sum())
        c1.metric("Total",      len(df_closed))
        c2.metric("Win Rate",   f"{wins_h/len(df_closed)*100:.1f}%")
        c3.metric("Avg PnL",    f"{df_closed['PnL_%'].mean():.2f}%")
        c4.metric("Median PnL", f"{df_closed['PnL_%'].median():.2f}%")
        c5.metric("Best Trade", f"{df_closed['PnL_%'].max():.2f}%")

        # exit reason breakdown
        reasons = df_closed['Exit_Reason'].value_counts()
        r_cols  = st.columns(len(reasons))
        for col, (reason, cnt) in zip(r_cols, reasons.items()):
            pct = f"{cnt/len(df_closed)*100:.1f}%"
            col.metric(reason, f"{cnt}  ({pct})")

    trade_panel(df_closed, "history_ticker", is_open=False, closed_ref=df_closed)

with tab_summary:
    st.markdown("### 📊 Strategy Summary")

    if total > 0:
        # top-level scan stats block
        st.markdown(f"""
        <div style="background:#0a1f12;border:1px solid #1e3a2a;border-radius:12px;padding:18px;margin-bottom:20px;">
          <div style="font-size:11px;color:#4b6a57;text-transform:uppercase;letter-spacing:.1em;margin-bottom:14px;">
            Scan Complete — {total} closed &nbsp;|&nbsp; {len(df_open)} open
          </div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">
            <div style="background:#0f172a;border:1px solid #1e3a2a;border-radius:8px;padding:12px;">
              <div style="font-size:10px;color:#4b6a57;margin-bottom:4px;">WIN RATE</div>
              <div style="font-size:22px;font-weight:700;color:#34d399;">{pct_of(wins,total)}</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e3a2a;border-radius:8px;padding:12px;">
              <div style="font-size:10px;color:#4b6a57;margin-bottom:4px;">AVG PnL</div>
              <div style="font-size:22px;font-weight:700;color:{'#34d399' if avg_pnl>=0 else '#f87171'};">{avg_pnl:.2f}%</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e3a2a;border-radius:8px;padding:12px;">
              <div style="font-size:10px;color:#4b6a57;margin-bottom:4px;">MEDIAN PnL</div>
              <div style="font-size:22px;font-weight:700;color:{'#34d399' if med_pnl>=0 else '#f87171'};">{med_pnl:.2f}%</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e3a2a;border-radius:8px;padding:12px;">
              <div style="font-size:10px;color:#4b6a57;margin-bottom:4px;">SL PHASE 1</div>
              <div style="font-size:22px;font-weight:700;color:#f87171;">{sl1}</div>
              <div style="font-size:11px;color:#4b6a57;">{pct_of(sl1,total)}</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e3a2a;border-radius:8px;padding:12px;">
              <div style="font-size:10px;color:#4b6a57;margin-bottom:4px;">SL TRAIL</div>
              <div style="font-size:22px;font-weight:700;color:#f87171;">{sl_t}</div>
              <div style="font-size:11px;color:#4b6a57;">{pct_of(sl_t,total)}</div>
            </div>
            <div style="background:#0f172a;border:1px solid #1e3a2a;border-radius:8px;padding:12px;">
              <div style="font-size:10px;color:#4b6a57;margin-bottom:4px;">TIMEOUT</div>
              <div style="font-size:22px;font-weight:700;color:#facc15;">{timeout}</div>
              <div style="font-size:11px;color:#4b6a57;">{pct_of(timeout,total)}</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

    # per-ticker table
    if not df_summary.empty:
        st.markdown("#### Per-Ticker Breakdown")
        df_s = df_summary.sort_values('Median_PnL', ascending=False).copy()

        # highlight top 3
        top3 = df_s.head(3)
        cols = st.columns(3)
        for col, (_, r) in zip(cols, top3.iterrows()):
            wr  = r.get('Win_Rate', 0)
            med = r.get('Median_PnL', 0)
            col.markdown(f"""
            <div style="background:#0a1f12;border:1px solid #1e3a2a;border-radius:10px;padding:14px;text-align:center;">
              <div style="font-size:18px;font-weight:700;color:#d1fae5;">{r['Ticker']}</div>
              <div style="font-size:12px;color:#4b6a57;margin:4px 0;">Win Rate</div>
              <div style="font-size:20px;font-weight:700;color:#34d399;">{wr:.1f}%</div>
              <div style="font-size:12px;color:#4b6a57;margin-top:6px;">Median PnL</div>
              <div style="font-size:18px;font-weight:600;color:{'#34d399' if med>=0 else '#f87171'};">{med:.2f}%</div>
              <div style="font-size:11px;color:#4b6a57;margin-top:4px;">{int(r.get('Total_Trades',0))} trades</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(fix_df(df_s), use_container_width=True, height=500)

with tab_charts:
    st.markdown("### 📈 Chart Lookup")
    chart_df_all = load_chart_data()
    available    = sorted(chart_df_all['symbol'].dropna().unique().tolist())
    chart_symbol = st.selectbox("Symbol", options=available, key="chart_lookup")

    if chart_symbol:
        sym_closed = df_closed[df_closed['Ticker'] == chart_symbol].copy()
        sym_open   = df_open[df_open['Ticker'] == chart_symbol]
        sl2 = en2 = ed2 = None
        if len(sym_open) > 0:
            r   = sym_open.sort_values('Entry_Date', ascending=False).iloc[0]
            sl2 = float(r['Stop_Loss_Initial']) if pd.notna(r.get('Stop_Loss_Initial')) else None
            en2 = float(r['Entry_Price'])        if pd.notna(r.get('Entry_Price'))       else None
            ed2 = r.get('Entry_Date')

        draw_candle_chart(chart_symbol, height=700, stop_loss=sl2, entry=en2, entry_date=ed2,
                          closed_trades_df=sym_closed if len(sym_closed) > 0 else None)

        if len(sym_closed) > 0:
            with st.expander(f"📋 Trade History — {chart_symbol} ({len(sym_closed)} trades)", expanded=False):
                show_cols = [c for c in ['Entry_Date','Exit_Date','Entry_Price','Exit_Price',
                                         'PnL_%','Bars_Held','Exit_Reason','Max_Gain','Max_Loss']
                             if c in sym_closed.columns]
                st.dataframe(fix_df(sym_closed[show_cols].sort_values('Entry_Date', ascending=False)),
                             use_container_width=True, height=300)

        st.markdown("#### 📰 Latest News")
        for n in fetch_latest_news(chart_symbol, 3):
            st.markdown(f"**{n['title']}**")
            st.caption(f"📅 {n['date']} | {n['provider']} | [Read]({n['url']})")
            st.divider()

with tab_egx30:
    st.markdown("### 📊 EGX30")
    egx_closed = df_closed[df_closed['Ticker']=='EGX30']
    draw_candle_chart('EGX30', height=700,
                      closed_trades_df=egx_closed if len(egx_closed) > 0 else None)

st.markdown("---")
st.markdown("<div style='text-align:center;color:#888;font-size:11px;padding:12px'>⚠️ For educational purposes only. Not financial advice.</div>", unsafe_allow_html=True)
