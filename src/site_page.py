# -*- coding: utf-8 -*-
"""从 BP2.3 页面模板生成『流浪计划』页面（同壳 + 顶部作战面板 + 红/灰双线曲线）。"""
from __future__ import annotations

import datetime
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
@media(max-width:620px){.dash-grid{grid-template-columns:1fr}}
</style>
"""

DASH_SECTION = """  <section class="dash">
    <div class="dash-grid" id="dashGrid"></div>
  </section>

"""

DASH_SCRIPT = """<script>
(function(){
  "use strict";
  var WP=null;
  function esc(v){var s=String(v===null||v===undefined?"":v);return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
  function fmtPct(v){if(v===null||v===undefined||isNaN(Number(v)))return "-";var n=Number(v)*100;return (n>=0?"+":"")+n.toFixed(2)+"%"}
  function fmtMoney(v){if(v===null||v===undefined||isNaN(Number(v)))return "-";var n=Number(v);return Math.abs(n)>=10000?(n/10000).toFixed(2)+"万":n.toFixed(0)}
  function actBadge(a){return '<span class="act '+(a==="买入"?"buy":"sell")+'">'+esc(a)+"</span>"}
  function block(k,v,wide){return '<div class="dash-item'+(wide?" wide":"")+'"><div class="dash-k">'+esc(k)+'</div><div class="dash-v">'+v+"</div></div>"}
  function renderDash(d){
    var g=document.getElementById("dashGrid");if(!g||!d||!d.dashboard)return;var x=d.dashboard;
    var hold=(x.holdings&&x.holdings.length)?x.holdings.map(function(h){return esc(h.symbol)+" "+esc(h.name)+"<small>"+esc(h.source)+" · 计划 "+esc(h.sell_date||"-")+" 卖出</small>"}).join("<br>"):"空仓";
    var today=(x.today_actions&&x.today_actions.length)?x.today_actions.map(function(a){return actBadge(a.action)+" "+esc(a.symbol)+" "+esc(a.name)}).join("<br>"):"无操作";
    var tmr=(x.tomorrow_actions&&x.tomorrow_actions.length)?x.tomorrow_actions.map(function(a){return actBadge(a.action)+" "+esc(a.symbol)+" "+esc(a.name)}).join("<br>"):"无操作";
    var sig=(x.latest_signals&&x.latest_signals.length)?x.latest_signals.map(function(s){return esc(s.symbol)+" "+esc(s.name)+"<small>"+esc(s.source)+" · 信号 "+esc(s.signal_date)+" · 买 "+esc(s.buy_date)+" / 卖 "+esc(s.sell_date||"-")+"</small>"}).join("<br>"):"最新信号日无候选";
    var plan=(x.plan&&x.plan.length)?x.plan.map(function(p){return '<span class="plan-date">'+esc(p.date)+"</span>"+actBadge(p.action)+" "+esc(p.symbol)+" "+esc(p.name)}).join("<br>"):"未来几日无操作";
    g.innerHTML=block("持仓",hold)+block("今日操作（"+x.today+"）",today)+block("明天买卖提醒（"+(x.next_day||"-")+"）",tmr)+block("今日信号（"+x.data_date+"）",sig)+block("未来几日计划操作",plan,true);
  }
  function scaleForYear(y){var arr=(WP&&WP.yearly)||[];for(var i=0;i<arr.length;i++){if(Number(arr[i].year)===Number(y)){var se=Number(arr[i].start_equity);return se?100000/se:1}}return 1}
  function detailTable(rows){
    var trs=rows.map(function(t){var sc=scaleForYear(t.year),pv=Number(t.net_profit)*sc;var cls=pv>=0?"pos":"neg";var Q=String.fromCharCode(34);return "<tr><td>"+esc(t.buy_date)+(t.buy_time?" "+esc(t.buy_time):"")+"</td><td>"+esc(t.sell_date)+(t.sell_time?" "+esc(t.sell_time):"")+"</td><td>"+esc(t.symbol)+"</td><td>"+esc(t.name)+"</td><td>"+esc(t.source||"")+"</td><td>"+Number(t.return_pct).toFixed(2)+"%</td><td class="+Q+cls+Q+">"+fmtMoney(pv)+"</td></tr>"}).join("");
    return '<div class="table-wrap" style="overflow-x:auto"><table><thead><tr><th>买入</th><th>卖出</th><th>代码</th><th>名称</th><th>策略</th><th>收益</th><th>按当年10万折算盈亏</th></tr></thead><tbody>'+trs+"</tbody></table></div>"
  }
  function showYear(y){
    if(!WP)return;var yr=(WP.yearly||[]).filter(function(x){return Number(x.year)===Number(y)})[0];
    var rows=(WP.trades||[]).filter(function(t){return Number(t.year)===Number(y)});
    var sec=document.getElementById("detailSection"),body=document.getElementById("detailBody");
    if(!sec||!body)return;sec.hidden=false;
    document.getElementById("detailEyebrow").textContent="年度详情（每年独立 10 万起算）";
    document.getElementById("detailTitle").textContent=y+" 年";
    var sum="";
    if(yr){sum='<div class="summary-strip"><div>本策略<b class="'+(Number(yr.year_return)>=0?"pos":"neg")+'">'+fmtPct(yr.year_return)+'</b></div><div>沪深300<b class="'+(Number(yr.benchmark_return)>=0?"pos":"neg")+'">'+fmtPct(yr.benchmark_return)+'</b></div><div>最大回撤<b class="neg">'+fmtPct(yr.max_drawdown)+'</b></div><div>成交<b>'+yr.trades+" 笔</b></div><div>胜率<b>"+Number(yr.win_rate).toFixed(1)+"%</b></div></div>"}
    body.innerHTML=sum+detailTable(rows);
  }
  function showStock(sym){
    if(!WP)return;var rows=(WP.trades||[]).filter(function(t){return t.symbol===sym});if(!rows.length)return;
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
      yg+='<text x="'+(left-10)+'" y="'+(y+4).toFixed(1)+'" fill="#8192b0" font-size="12" text-anchor="end">'+esc(fmtAxis(v))+"</text>";}
    var xticks=[];
    if(small){var step=Math.max(1,Math.floor((n-1)/4));for(var i=0;i<n;i+=step)xticks.push(i);if(xticks[xticks.length-1]!==n-1)xticks.push(n-1)}
    else{var last="";for(var j=0;j<n;j++){var yy=String(main[j].date).slice(0,4);if(yy!==last){xticks.push(j);last=yy}}if(xticks[xticks.length-1]!==n-1)xticks.push(n-1)}
    var xg="";
    xticks.forEach(function(i){var x=xAt(i);var lab=small?String(main[i].date).slice(0,7):String(main[i].date).slice(0,4);
      xg+='<line x1="'+x.toFixed(1)+'" y1="'+top+'" x2="'+x.toFixed(1)+'" y2="'+(h-bottom)+'" stroke="#1b2940" stroke-width="1"/>';
      xg+='<text x="'+x.toFixed(1)+'" y="'+(h-14)+'" fill="#8192b0" font-size="12" text-anchor="middle">'+esc(lab)+"</text>";});
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

REPL = [
    ("<title>BP2.3</title>", "<title>流浪计划</title>"),
    ('<div class="eyebrow">BP2.3</div>', '<div class="eyebrow">流浪计划</div>'),
    ("<h1>爆破2.3实时策略页</h1>", "<h1>流浪计划实时策略页</h1>"),
    ('<body data-api="/api/bp2-3/data">', '<body data-api="/api/wandering-plan/data">'),
    ('<a class="nav-link" href="/wandering-plan/">流浪计划</a>', '<a class="nav-link" href="/">BP2.3 首页</a>'),
    ("<div>数据源：本机 BP2.3 回测与每日信号；每年独立按 10 万本金重算，最新候选单独列出。</div>",
     "<div>数据源：已逐笔核验的 610 笔回测（B1 313 / QL2 266 / V12 31）；2 仓 × 50% 复利；红色=本策略，灰色=沪深300。</div>"),
    ("<div>冠军参数 m3|1.0/1.0/0.8|low0.1|q40|zskip|k3|h1；已知代价：全期最大回撤 -44.70%（BP2.2 为 -44.55%）。</div>",
     "<div>三路信号：B1 爆破 / QL2 冠军 / 双波 O1+C3（V1.2 离场）；每日 17:45 自动更新。</div>"),
    ("</header>", "</header>\n" + DASH_SECTION),
    ("</head>", CURVE_STYLE + "</head>"),
    ('<section class="section">\n    <div class="section-head"><div><div class="eyebrow">最新信号</div><h2>最近信号日候选</h2></div></div>',
     CURVE_SECTION + '  <section class="section">\n    <div class="section-head"><div><div class="eyebrow">最新信号</div><h2>最近信号日候选</h2></div></div>'),
    ("</body>", DASH_SCRIPT + CURVE_SCRIPT + "\n</body>"),
]


def build_page(backup: bool = True) -> tuple[str, list[str]]:
    if not TPL.exists():
        raise FileNotFoundError(f"template missing: {TPL}")
    html = TPL.read_text(encoding="utf-8")
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