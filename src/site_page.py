# -*- coding: utf-8 -*-
"""从 BP2.3 页面模板生成『流浪计划』页面（同壳 + 顶部作战面板 + 红/灰双线曲线）。"""
from __future__ import annotations

import datetime
import re
import shutil

from . import config

TPL = config.CZERO_WEB / "site" / "bp2-3" / "index.html"
OUT_DIR = config.SITE_OUT
OUT = OUT_DIR / "index.html"

CURVE_STYLE = """<style>
.curve-card{padding:18px 18px 14px}
.curve-box{width:100%;min-height:320px;position:relative}
.curve-box svg{display:block;width:100%;height:auto;overflow:visible}
.chart-legend{display:flex;gap:18px;align-items:center;margin:2px 0 10px;font-size:14px;color:#c9d6ef}
.chart-legend .dot{display:inline-block;width:18px;height:4px;border-radius:3px;margin-right:7px;vertical-align:middle}
.dot.red{background:#ff4d4f}.dot.gray{background:#8a94a6}
.chart-axis-note{color:#7f8ba3;font-size:12px;margin-top:6px}
.chart-tip{position:absolute;pointer-events:none;background:#101a2c;border:1px solid #2b4165;border-radius:10px;padding:8px 10px;font-size:12px;color:#dbe6fb;box-shadow:0 8px 24px rgba(0,0,0,.35);display:none;z-index:5;white-space:nowrap}
.curve-meta{display:flex;flex-wrap:wrap;gap:18px;margin:4px 0 10px;color:#91a5ca;font-size:13px}
.curve-meta b{color:#e8eefc;margin-left:6px}
.year-btns{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 12px}
.year-btn{border:1px solid #2b4165;background:#111b2d;color:#c9d6ef;border-radius:999px;padding:6px 14px;font-size:14px;cursor:pointer}
.year-btn.active{background:#ff4d4f;border-color:#ff4d4f;color:#fff}
.pos{color:#ff4d4f!important}.neg{color:#3ddc84!important}
.signal-features{display:none!important}
.live-record{display:none!important}
.dash{margin:2px 0 18px}
.dash-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.dash-item{background:linear-gradient(180deg,rgba(18,24,32,.97),rgba(14,20,27,.97));border:1px solid var(--line);border-radius:16px;padding:16px 18px}
.dash-item.wide{grid-column:1/-1}
.dash-k{color:var(--muted);font-size:13px;letter-spacing:.08em;margin-bottom:8px}
.dash-v{font-size:21px;font-weight:800;line-height:1.55}
.dash-v small{display:block;color:var(--muted);font-size:12px;font-weight:400;margin-top:2px}
.act{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:700;margin-right:5px}
.act.buy{background:rgba(255,77,79,.16);color:#ff4d4f;border:1px solid rgba(255,77,79,.5)}
.act.sell{background:rgba(61,220,132,.14);color:#3ddc84;border:1px solid rgba(61,220,132,.45)}
.plan-date{color:#8192b0;font-size:13px;margin-right:8px}
.summary-strip{display:flex;flex-wrap:wrap;gap:16px;margin:2px 0 12px;color:#91a5ca;font-size:13px}
.summary-strip b{margin-left:5px}
.rules{margin:0 0 18px}
.rules-card{padding:16px 20px}
.rules-title{font-size:16px;font-weight:900;color:#eaf2ff;margin-bottom:8px}
.rules-line{color:#c9d6ef;font-size:13.5px;line-height:1.85}
.rules-line b{margin-right:2px}
.rules-line em{color:#ffe4a0;font-style:normal}
.r-b1{color:#ff4d4f}.r-ql2{color:#5ca9ff}.r-v12{color:#3ddc84}
.dash-card{padding:18px 20px}
.dash-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}
.dash-head span{color:var(--muted);font-size:13px;letter-spacing:.12em}
.dash-head b{font-size:22px}
.dash-line{display:flex;gap:14px;padding:10px 0;border-bottom:1px solid rgba(37,48,59,.75);align-items:flex-start}
.dash-line:last-child{border-bottom:none}
.dash-k{color:var(--muted);font-size:13px;min-width:96px;padding-top:5px}
.dash-v{font-size:19px;font-weight:800;line-height:1.5;flex:1}
.dash-v small{display:block;color:var(--muted);font-size:12px;font-weight:400;margin-top:1px}
.dash3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.dash-panel{padding:16px 18px}
.dash-title{font-size:19px;font-weight:900;letter-spacing:.05em;color:#eaf2ff;margin-bottom:10px;padding-left:10px;border-left:4px solid #2b4165}
.dash-title.hold{color:#ff4d4f;border-left-color:#ff4d4f}
.dash-title.next{color:#3ddc84;border-left-color:#3ddc84}
.d-item{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px solid rgba(37,48,59,.7)}
.d-item:last-child{border-bottom:none}
.d-code{font-weight:900;font-size:17px}
.d-name{color:#dfe9fb;font-size:14px}
.d-sub{color:var(--muted);font-size:12px;margin-top:2px;line-height:1.6}
.d-time{display:inline-block;background:#0d141c;border:1px solid var(--line);border-radius:8px;padding:1px 7px;font-size:12px;color:#c9d6ef;margin-right:8px}
.d-pnl{font-weight:900;font-size:17px;text-align:right;white-space:nowrap}
.d-amount{display:block;font-size:12px;color:var(--muted);font-weight:400}
.dash-signals{margin-top:12px;color:#91a5ca;font-size:13px;line-height:1.7}
.todo-head{margin:16px 0 8px;color:var(--muted);font-size:13px;letter-spacing:.1em}
.todo-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}
.todo-card{padding:14px 16px;border:1px solid var(--line);border-radius:16px;background:linear-gradient(180deg,rgba(18,24,32,.96),rgba(14,20,27,.96))}
.todo-date{font-size:18px;font-weight:900;margin-bottom:8px;color:#eaf2ff}
.todo-item{display:flex;justify-content:space-between;gap:8px;font-size:14px;padding:4px 0}
@media(max-width:900px){.dash3{grid-template-columns:1fr}}
</style>
"""

DASH_SECTION = """  <section class="dash">
    <div class="dash3">
      <div class="card dash-panel"><div class="dash-title hold">今日持仓</div><div class="dash-body" id="dashHold">-</div></div>
      <div class="card dash-panel"><div class="dash-title">今日操作</div><div class="dash-body" id="dashToday">-</div></div>
      <div class="card dash-panel"><div class="dash-title next" id="dashTmrTitle">明日买卖提醒</div><div class="dash-body" id="dashTmr">-</div></div>
    </div>
    <div class="dash-signals" id="dashSig">-</div>
    <div class="todo-head">交易日待办（不含明日）</div>
    <div class="todo-grid" id="dashTodo"></div>
  </section>
"""

DASH_SCRIPT = """<script>
(function(){
  "use strict";
  var WP=null;
  var _f=window.fetch;
  window.fetch=function(u,o){
    var url=String(u||"");
    if(url.indexOf("/api/wandering-plan/data")<0)return _f.apply(window,arguments);
    function attempt(n){
      return _f.call(window,u,o).then(function(r){
        if(!r.ok)throw new Error("http "+r.status);
        return r.clone().json().then(function(){return r;}).catch(function(){throw new Error("bad json")});
      }).catch(function(e){
        if(n<=2)return new Promise(function(res,rej){setTimeout(function(){attempt(n+1).then(res,rej)},500)});
        throw e;
      });
    }
    return attempt(0);
  };
  function esc(v){var s=String(v===null||v===undefined?"":v);return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
  function fmtPct(v){if(v===null||v===undefined||isNaN(Number(v)))return "-";var n=Number(v)*100;return (n>=0?"+":"")+n.toFixed(2)+"%"}
  function fmtMoney(v){if(v===null||v===undefined||isNaN(Number(v)))return "-";var n=Number(v);return Math.abs(n)>=10000?(n/10000).toFixed(2)+"万":n.toFixed(0)}
  function actBadge(a){return '<span class="act '+(a==="买入"?"buy":"sell")+'">'+esc(a)+"</span>"}
  function block(k,v,wide){return '<div class="dash-item'+(wide?" wide":"")+'"><div class="dash-k">'+esc(k)+'</div><div class="dash-v">'+v+"</div></div>"}
  function renderDash(d){
    if(!d||!d.dashboard)return;var x=d.dashboard;
    function g(id){return document.getElementById(id)}
    function money(v){if(v===null||v===undefined||isNaN(Number(v)))return "";var n=Number(v);return (n>=0?"+":"")+Math.round(n).toLocaleString("zh-CN")}
    function timeBadge(a){return '<span class="d-time">'+esc(a.time)+" "+(a.action==="买入"?"买":"卖")+"</span>"}
    function pnlHtml(pct,amount){if(pct===null||pct===undefined||isNaN(Number(pct)))return "";var cls=Number(pct)>=0?"pos":"neg";var h='<div class="d-pnl '+cls+'">'+(Number(pct)>=0?"+":"")+Number(pct).toFixed(2)+'%';if(amount!==null&&amount!==undefined&&!isNaN(Number(amount)))h+='<span class="d-amount">'+(Number(amount)>=0?"+":"")+Math.round(Number(amount)).toLocaleString("zh-CN")+' 元</span>';return h+'</div>'}
    function item(a){
      var right=a.action==="卖出"?pnlHtml(a.pnl_pct,a.pnl_amount):(a.price?'<div class="d-pnl">'+Number(a.price).toFixed(2)+'</div>':"");
      var sub=timeBadge(a)+esc(a.source);
      if(a.action==="卖出"&&a.exit_reason==="STOP")sub+=' · 止损';
      if(a.note)sub+='<br>'+esc(a.note);
      return '<div class="d-item"><div><span class="d-code">'+esc(a.symbol)+'</span> <span class="d-name">'+esc(a.name)+'</span><div class="d-sub">'+sub+'</div></div>'+right+'</div>'
    }
    var hold=(x.holdings&&x.holdings.length)?x.holdings.map(function(h){
      var sub=(h.entry!==null&&h.entry!==undefined)?('成本 '+Number(h.entry).toFixed(2)+'<br>计划 '+esc(h.sell_date||"-")+' 15:00 卖'):('计划 '+esc(h.buy_date)+' 09:30 买<br>'+esc(h.sell_date||"-")+' 15:00 卖');
      if(h.last)sub+='<br>现价 '+Number(h.last).toFixed(2);
      if(h.stop_px)sub+='<br>止损 '+Number(h.stop_px).toFixed(2);
      return '<div class="d-item"><div><span class="d-code">'+esc(h.symbol)+'</span> <span class="d-name">'+esc(h.name)+'</span><div class="d-sub">'+esc(h.source)+' · '+sub+'</div></div>'+pnlHtml(h.pnl_pct,h.pnl_amount)+'</div>'
    }).join(""):'<div class="d-sub">空仓</div>';
    var today=(x.today_actions&&x.today_actions.length)?x.today_actions.map(item).join(""):'<div class="d-sub">无操作</div>';
    var tmr=(x.tomorrow_actions&&x.tomorrow_actions.length)?x.tomorrow_actions.map(item).join(""):'<div class="d-sub">无操作</div>';
    var sig=(x.latest_signals&&x.latest_signals.length)?x.latest_signals.map(function(s){return esc(s.symbol)+" "+esc(s.name)+"（"+esc(s.source)+"）"}).join("　"):"无";
    var todo=(x.todo_days&&x.todo_days.length)?x.todo_days.map(function(day){
      return '<div class="todo-card"><div class="todo-date">'+esc(day.date)+'</div>'+day.items.map(function(a){
        return '<div class="todo-item"><span>'+timeBadge(a)+'<b>'+esc(a.symbol)+'</b> '+esc(a.name)+'</span></div>'
      }).join("")+'</div>'
    }).join(""):'<div class="d-sub">未来几日无待办</div>';
    if(g("dashHold"))g("dashHold").innerHTML=hold;
    if(g("dashToday"))g("dashToday").innerHTML=today;
    if(g("dashTmr"))g("dashTmr").innerHTML=tmr;
    if(g("dashTmrTitle"))g("dashTmrTitle").textContent="明日买卖提醒（"+(x.next_day||"-")+"）";
    if(g("dashSig"))g("dashSig").innerHTML="今日信号（"+x.data_date+"）："+sig+(x.intraday_at?"　｜　盘中快照 "+esc(String(x.intraday_at).slice(11,16)):"");
    if(g("dashTodo"))g("dashTodo").innerHTML=todo;
  }

  function scaleForYear(y){var arr=(WP&&WP.yearly)||[];for(var i=0;i<arr.length;i++){if(Number(arr[i].year)===Number(y)){var se=Number(arr[i].start_equity);return se?100000/se:1}}return 1}
  function detailTable(rows){
    var trs=rows.map(function(t){
      var sc=scaleForYear(t.year),pv=Number(t.net_profit)*sc,cls=pv>=0?"pos":"neg";
      var startEq=yearStart(t.year),bal=(t.balance_after!==null&&t.balance_after!==undefined&&startEq)?100000*Number(t.balance_after)/startEq:null;
      var gain=(bal!==null)?(bal/100000-1):null;
      var Q=String.fromCharCode(34);
      var gainHtml=(gain===null)?'<td>-</td>':'<td class='+Q+(gain>=0?"pos":"neg")+Q+'>'+(gain>=0?"+":"")+(gain*100).toFixed(2)+'%</td>';
      var balHtml=(bal===null)?'<td>-</td>':'<td>'+fmtMoney(bal)+'</td>';
      return "<tr><td>"+esc(t.buy_date)+(t.buy_time?" "+esc(t.buy_time):"")+"</td><td>"+(t.sell_date?esc(t.sell_date)+(t.sell_time?" "+esc(t.sell_time):"")+(t.exit_reason==="STOP"?" 止损":""):"持仓中")+"</td><td>"+esc(t.symbol)+"</td><td>"+esc(t.name)+"</td><td>"+esc(t.source||"")+"</td><td>"+Number(t.return_pct).toFixed(2)+"%</td><td class="+Q+cls+Q+">"+fmtMoney(pv)+"</td>"+gainHtml+balHtml+"</tr>"
    }).join("");
    return '<div class="table-wrap" style="overflow-x:auto"><table><thead><tr><th>买入</th><th>卖出</th><th>代码</th><th>名称</th><th>策略</th><th>单笔涨跌</th><th>按当年10万折算盈亏</th><th>当年收益</th><th>折算余额</th></tr></thead><tbody>'+trs+"</tbody></table></div>"
  }
  function yearStart(y){var arr=(WP&&WP.yearly)||[];for(var i=0;i<arr.length;i++){if(Number(arr[i].year)===Number(y)){return Number(arr[i].start_equity)||null}}return null}
  function showYear(y){
    if(!WP)return;var yr=(WP.yearly||[]).filter(function(x){return Number(x.year)===Number(y)})[0];
    var rows=(WP.trades||[]).filter(function(t){return Number(t.year)===Number(y)}).sort(function(a,b){return String(b.buy_date||"").localeCompare(String(a.buy_date||""))});
    var sec=document.getElementById("detailSection"),body=document.getElementById("detailBody");
    if(!sec||!body)return;sec.hidden=false;
    document.getElementById("detailEyebrow").textContent="年度详情（每年独立 10 万起算）";
    document.getElementById("detailTitle").textContent=y+" 年";
    var sum="";
    if(yr){sum='<div class="summary-strip"><div>本策略<b class="'+(Number(yr.year_return)>=0?"pos":"neg")+'">'+fmtPct(yr.year_return)+'</b></div><div>沪深300<b class="'+(Number(yr.benchmark_return)>=0?"pos":"neg")+'">'+fmtPct(yr.benchmark_return)+'</b></div><div>最大回撤<b class="neg">'+fmtPct(yr.max_drawdown)+'</b></div><div>成交<b>'+yr.trades+" 笔</b></div><div>胜率<b>"+Number(yr.win_rate).toFixed(1)+"%</b></div></div>"}
    body.innerHTML=sum+detailTable(rows);
  }
  function showStock(sym){
    if(!WP)return;var rows=(WP.trades||[]).filter(function(t){return t.symbol===sym}).sort(function(a,b){return String(b.buy_date||"").localeCompare(String(a.buy_date||""))});if(!rows.length)return;
    var sec=document.getElementById("detailSection"),body=document.getElementById("detailBody");
    if(!sec||!body)return;sec.hidden=false;
    document.getElementById("detailEyebrow").textContent="个股详情（按当年 10 万折算）";
    document.getElementById("detailTitle").textContent=sym+" "+(rows[0].name||"");
    body.innerHTML=detailTable(rows);
  }
  document.addEventListener("click",function(e){
    var t=e.target;if(!t||!t.closest)return;
    var yc=t.closest(".year-card");if(yc){setTimeout(function(){showYear(yc.getAttribute("data-year"))},25);return}
    var tr=t.closest("tr.clickable");if(tr){setTimeout(function(){showStock(tr.getAttribute("data-symbol"))},25)}
  },true);
  document.addEventListener("DOMContentLoaded",function(){
    ["latestCards","pendingTable"].forEach(function(id){
      var el=document.getElementById(id);var sec=el&&el.closest?el.closest("section"):null;
      if(sec)sec.style.display="none";
    });
  });
  fetch("/api/wandering-plan/data",{credentials:"same-origin",cache:"no-store"})
    .then(function(r){return r.json()})
    .then(function(d){WP=d;renderDash(d)})
    .catch(function(){});
})();
</script>"""

CURVE_SECTION = """  <section class="section">
    <div class="section-head"><div><div class="eyebrow">资金曲线</div><h2>三路组合复利曲线（10 万起）</h2></div></div>
    <div class="card curve-card">
      <div class="chart-legend"><span><i class="dot red"></i>本策略</span><span><i class="dot gray"></i>沪深300</span></div>
      <div class="curve-box" id="curveBox"></div>
      <div class="curve-meta"><span>当前<b id="curveNow">-</b></span><span>最高<b id="curveHigh">-</b></span><span>沪深300 同期<b id="benchNow">-</b></span><span>区间<b id="curveStart">-</b> ~ <b id="curveEnd">-</b></span></div>
      <div class="chart-axis-note">横轴：日期　纵轴：累计收益率；红色=本策略，灰色=沪深300（同期 10 万起算）。</div>
    </div>
  </section>

  <section class="section">
    <div class="section-head"><div><div class="eyebrow">年度曲线</div><h2>每年从 10 万重新起算</h2></div><div class="muted small">点年份切换</div></div>
    <div class="year-btns" id="yearBtns"></div>
    <div class="card curve-card"><div id="yearCurveBox" class="curve-box"></div><div class="chart-axis-note">两条线都从当年 10 万起算；策略红色、沪深300 灰色。</div></div>
  </section>

"""

CURVE_SCRIPT = """<script>
(function(){
  "use strict";
  var reduced=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function fmtPct(v,d){d=d||2;if(v===null||v===undefined||isNaN(Number(v)))return "-";var n=Number(v)*100;return (n>=0?"+":"")+n.toFixed(d)+"%"}
  function fmtAxis(v){var n=Number(v);return (n>=0?"+":"")+n.toFixed(0)+"%"}
  function fmtMoney(v){if(v===null||v===undefined||isNaN(Number(v)))return "-";var n=Number(v);return Math.abs(n)>=100000000?(n/100000000).toFixed(2)+"亿":(Math.abs(n)>=10000?(n/10000).toFixed(1)+"万":n.toFixed(0))}
  function esc(v){var s=String(v===null||v===undefined?"":v);return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
  function drawChart(boxId,main,bench,small){
    var box=document.getElementById(boxId);if(!box)return;
    if(!main||main.length<2){box.innerHTML='<div class="card empty">暂无曲线</div>';return}
    var w=1000,h=small?300:390,left=64,right=22,top=20,bottom=38;
    var series=[main.filter(function(x){return isFinite(Number(x.return_pct))})];
    if(bench&&bench.length>1)series.push(bench.filter(function(x){return isFinite(Number(x.return_pct))}));
    var all=[];series.forEach(function(a){a.forEach(function(x){all.push(Number(x.return_pct))})});
    var mn=Math.min.apply(null,all),mx=Math.max.apply(null,all);mn=Math.min(mn,0);mx=Math.max(mx,0);
    var span=Math.max(mx-mn,1);mx+=span*0.06;if(mn<0)mn-=Math.min(Math.abs(mn)*0.05,span*0.01);
    var n=main.length,plotW=w-left-right,plotH=h-top-bottom;
    function xAt(i){return left+(n<=1?0:plotW*i/(n-1))}
    function yAt(v){return top+plotH*(mx-v)/(mx-mn)}
    var ygrid="",yg="";
    for(var k=0;k<=4;k++){var v=mn+(mx-mn)*k/4,y=yAt(v);
      ygrid+='<line x1="'+left+'" y1="'+y.toFixed(1)+'" x2="'+(w-right)+'" y2="'+y.toFixed(1)+'" stroke="#22324d" stroke-width="1"/>';
      yg+='<text x="'+(left-10)+'" y="'+(y+4).toFixed(1)+'" fill="#8192b0" font-size="20" text-anchor="end">'+esc(fmtAxis(v))+"</text>";}
    var xticks=[];
    if(small){var step=Math.max(1,Math.floor((n-1)/4));for(var i=0;i<n;i+=step)xticks.push(i);if(xticks[xticks.length-1]!==n-1)xticks.push(n-1)}
    else{var last="";for(var j=0;j<n;j++){var yy=String(main[j].date).slice(0,4);if(yy!==last){xticks.push(j);last=yy}}if(xticks[xticks.length-1]!==n-1)xticks.push(n-1)}
    var xg="";
    xticks.forEach(function(i){var x=xAt(i);var lab=small?String(main[i].date).slice(0,7):String(main[i].date).slice(0,4);
      xg+='<line x1="'+x.toFixed(1)+'" y1="'+top+'" x2="'+x.toFixed(1)+'" y2="'+(h-bottom)+'" stroke="#1b2940" stroke-width="1"/>';
      xg+='<text x="'+x.toFixed(1)+'" y="'+(h-14)+'" fill="#8192b0" font-size="20" text-anchor="middle">'+esc(lab)+"</text>";});
    function pathFor(arr,f){var d="";for(var i=0;i<arr.length;i++){d+=(i===0?"M":"L")+xAt(i).toFixed(1)+" "+yAt(Number(arr[i][f])).toFixed(1)+" "}return d}
    var pm=pathFor(main,"return_pct"),pb=(bench&&bench.length>1)?pathFor(bench,"return_pct"):"";
    var area=pm+"L"+xAt(n-1).toFixed(1)+" "+(h-bottom)+" L"+xAt(0).toFixed(1)+" "+(h-bottom)+" Z";
    var gid="g"+boxId;
    var svg='<svg viewBox="0 0 '+w+" "+h+'" preserveAspectRatio="none" role="img" aria-label="收益曲线">';
    svg+='<defs><linearGradient id="'+gid+'" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff4d4f" stop-opacity="0.22"/><stop offset="1" stop-color="#ff4d4f" stop-opacity="0"/></linearGradient></defs>';
    svg+="<g>"+ygrid+"</g><g>"+xg+"</g><g>"+yg+"</g>";
    svg+='<path class="area-main" d="'+area+'" fill="url(#'+gid+')" stroke="none" opacity="0"></path>';
    if(pb)svg+='<path class="line-bench" d="'+pb+'" fill="none" stroke="#8a94a6" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" opacity="0.9"></path>';
    svg+='<path class="line-main" d="'+pm+'" fill="none" stroke="#ff4d4f" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"></path>';
    svg+='<circle class="last-dot" cx="'+xAt(n-1).toFixed(1)+'" cy="'+yAt(Number(main[n-1].return_pct)).toFixed(1)+'" r="5" fill="#ff4d4f" stroke="#0b0f14" stroke-width="2"></circle>';
    svg+="</svg>";
    box.innerHTML=svg+'<div class="chart-tip"></div>';
    var tip=box.querySelector(".chart-tip"),svgEl=box.querySelector("svg");
    if(!reduced){
      var mainPath=box.querySelector(".line-main"),benchPath=box.querySelector(".line-bench"),areaEl=box.querySelector(".area-main");
      if(mainPath){var len=mainPath.getTotalLength();mainPath.style.strokeDasharray=len;mainPath.style.strokeDashoffset=len;mainPath.getBoundingClientRect();mainPath.style.transition="stroke-dashoffset 1.4s ease";requestAnimationFrame(function(){mainPath.style.strokeDashoffset="0"})}
      if(benchPath){var blen=benchPath.getTotalLength();benchPath.style.strokeDasharray=blen;benchPath.style.strokeDashoffset=blen;benchPath.getBoundingClientRect();benchPath.style.transition="stroke-dashoffset 1.4s ease .25s";requestAnimationFrame(function(){benchPath.style.strokeDashoffset="0"})}
      if(areaEl){areaEl.getBoundingClientRect();areaEl.style.transition="opacity .8s ease .45s";requestAnimationFrame(function(){areaEl.style.opacity="1"})}
      setTimeout(function(){[mainPath,benchPath].forEach(function(el){if(el){el.style.strokeDasharray="none";el.style.strokeDashoffset="0";el.style.transition="none"}});if(areaEl)areaEl.style.opacity="1"},1800);
    }else if(box.querySelector(".area-main")){box.querySelector(".area-main").style.opacity="1"}
    if(svgEl&&tip){
      function nearest(clientX){var r=svgEl.getBoundingClientRect();var px=(clientX-r.left)/r.width*w;var i=Math.round((px-left)/(plotW||1)*(n-1));return Math.max(0,Math.min(n-1,i))}
      function show(e){var i=nearest(e.clientX);var r=svgEl.getBoundingClientRect();var b=(bench&&bench[i])?fmtPct(bench[i].return_pct/100):"—";
        tip.innerHTML="<b>"+esc(main[i].date)+"</b><br>本策略 "+fmtPct(main[i].return_pct/100)+"<br>沪深300 "+b;
        tip.style.display="block";var lx=(e.clientX-r.left)+12;if(lx>r.width-150)lx=r.width-150;tip.style.left=Math.max(4,lx)+"px";tip.style.top=Math.max(4,(e.clientY-r.top)-10)+"px"}
      box.addEventListener("pointermove",show);box.addEventListener("pointerleave",function(){tip.style.display="none"});
    }
  }
  function drawYearCharts(data){
    var yc=data.year_curves||{};var keys=Object.keys(yc).sort();var box=document.getElementById("yearBtns");
    if(!box||!keys.length)return;box.innerHTML=keys.map(function(k){return '<button class="year-btn" data-y="'+k+'">'+k+"</button>"}).join("");
    function render(k){box.querySelectorAll(".year-btn").forEach(function(b){b.classList.toggle("active",b.dataset.y===k)});var o=yc[k];if(o)drawChart("yearCurveBox",o.strategy,o.benchmark,true)}
    box.querySelectorAll(".year-btn").forEach(function(b){b.onclick=function(){render(b.dataset.y)}});
    render(keys[keys.length-1]);
  }
  fetch("/api/wandering-plan/data",{credentials:"same-origin",cache:"no-store"})
    .then(function(r){return r.json()})
    .then(function(d){
      if(!d)return;
      drawChart("curveBox",d.curve||[],d.benchmark_curve||[],false);
      var c=d.curve||[];if(c.length){
        var now=c[c.length-1];var high=c.reduce(function(a,b){return Number(b.equity)>Number(a.equity)?b:a},c[0]);
        var elNow=document.getElementById("curveNow"),elHigh=document.getElementById("curveHigh"),elBench=document.getElementById("benchNow"),elS=document.getElementById("curveStart"),elE=document.getElementById("curveEnd");
        if(elNow)elNow.textContent=(Number(now.equity)/100000).toFixed(1)+" 倍";
        if(elHigh)elHigh.textContent=(Number(high.equity)/100000).toFixed(1)+" 倍";
        var b=d.benchmark_curve||[];if(elBench&&b.length)elBench.textContent=(Number(b[b.length-1].equity)/100000).toFixed(1)+" 倍";
        if(elS)elS.textContent=c[0].date;if(elE)elE.textContent=now.date;
      }
      drawYearCharts(d);
    })
    .catch(function(){});
})();
</script>"""

RULES_SECTION = """  <section class="section rules">
    <div class="card rules-card">
      <div class="rules-title">买卖规则（三路合并 · 2 仓 × 50% · V1.1）</div>
      <div class="rules-line"><b class="r-b1">B1 爆破</b>：T 日 6 个因子同时满足（ret_1 ≤ -4.77%、range_60 ≥ 62.8%、range_compression ≥ 0.714、price_vs_ma60 ≥ +1.21%、w_amp_first10 ≥ 13.2%、w_std_ret ≥ 8.75%）→ <em>T+3 开盘买，次日收盘卖</em>。</div>
      <div class="rules-line"><b class="r-ql2">QL2 冠军</b>：L2 五因子（t_count / O3 / C2 / C4 / N05）同时达标，按 candidate_score 只取第 1 名 → <em>T+2 开盘买</em>；<em>卖出日盘中最低价 ≤ 买入价 × 0.91 时止损卖出（成交价取 min(开盘, 0.91×买入价)），否则 15:00 收盘卖</em>。</div>
      <div class="rules-line"><b class="r-v12">V12 双波</b>：O1 + C3 同时命中 → <em>T+4 开盘买，持有 22 个交易日</em>；或 V1.2 提前离场（前一日涨停 + 当日不涨停 + 浮盈 ≥ 20% 收盘卖，跌停顺延）。</div>
      <div class="rules-line muted">优先级 B1 &gt; QL2 &gt; V12；单路上限 B1 2 个 / QL2 1 个 / V12 2 个；总共 2 个仓位，每仓 5 万、复利。</div>
    </div>
  </section>

"""

REPL = [
    ("<title>BP2.3</title>", "<title>流浪计划 V1.1</title>"),
    ('<div class="eyebrow">BP2.3</div>', '<div class="eyebrow">流浪计划 · V1.1</div>'),
    ("<h1>爆破2.3实时策略页</h1>", "<h1>流浪计划实时策略页 V1.1</h1>"),
    ('<body data-api="/api/bp2-3/data">', '<body data-api="/api/wandering-plan/data">'),
    ("<div>数据源：本机 BP2.3 回测与每日信号；每年独立按 10 万本金重算，最新候选单独列出。</div>",
     "<div>数据源：610 笔回测 + 实盘（B1 / QL2 / V12）；QL2 卖出日 -9% 止损；2 仓 × 50% 复利；每日 08:30、12:00、17:45 自动更新；红色=本策略，灰色=沪深300。</div>"),
    ("<div>冠军参数 m3|1.0/1.0/0.8|low0.1|q40|zskip|k3|h1；已知代价：全期最大回撤 -44.70%（BP2.2 为 -44.55%）。</div>",
     "<div>三路信号：B1 爆破 / QL2 冠军（卖出日 -9% 止损）/ 双波 O1+C3（V1.2 离场）；每个交易日 08:30、12:00、17:45 自动更新。</div>"),
    ("</header>", "</header>\n" + DASH_SECTION),
    ('<section class="metric-grid">', RULES_SECTION + '<section class="metric-grid">'),
    ("</head>", CURVE_STYLE + "</head>"),
    ('<section class="section">\n    <div class="section-head"><div><div class="eyebrow">最新信号</div><h2>最近信号日候选</h2></div></div>',
     CURVE_SECTION + '  <section class="section">\n    <div class="section-head"><div><div class="eyebrow">最新信号</div><h2>最近信号日候选</h2></div></div>'),
    ("</body>", DASH_SCRIPT + CURVE_SCRIPT + "\n</body>"),
]


def build_page(backup: bool = True) -> tuple[str, list[str]]:
    if not TPL.exists():
        raise FileNotFoundError(f"template missing: {TPL}")
    html = TPL.read_text(encoding="utf-8")
    html = re.sub(r'<a class="nav-link" href="/(bp2-0|ql2|double-wave|wandering-plan)/">[^<]*</a>', "", html)
    missing = []
    for a, b in REPL:
        if a not in html:
            missing.append(a[:50])
            continue
        html = html.replace(a, b)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if backup and OUT.exists():
        shutil.copy2(OUT, OUT_DIR / ("index.html.bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
    OUT.write_text(html, encoding="utf-8")
    return str(OUT), missing