# -*- coding: utf-8 -*-
"""从 BP2.3 页面模板生成『流浪计划』页面（与现有策略页同壳）。"""
from __future__ import annotations

import datetime
import shutil

from . import config

TPL = config.CZERO_WEB / "site" / "bp2-3" / "index.html"
OUT_DIR = config.SITE_OUT
OUT = OUT_DIR / "index.html"

CURVE_STYLE = """<style>
.curve-card{padding:18px 18px 14px}
.curve-box{width:100%;min-height:300px;position:relative}
.curve-box svg{display:block;width:100%;height:auto;overflow:visible}
.curve-meta{display:flex;flex-wrap:wrap;gap:18px;margin:6px 0 10px;color:#91a5ca;font-size:13px}
.curve-meta b{color:#e8eefc}
.curve-labels{display:flex;justify-content:space-between;color:#91a5ca;font-size:12px;margin-top:6px}
.curve-dot{fill:#ff4d4f}
.curve-tip{position:absolute;pointer-events:none;background:#101a2c;border:1px solid #2b4165;border-radius:10px;padding:8px 10px;font-size:12px;color:#dbe6fb;display:none;z-index:5;white-space:nowrap}
</style>
"""

CURVE_SECTION = """  <section class="section">
    <div class="section-head"><div><div class="eyebrow">资金曲线</div><h2>三路组合复利曲线（10 万起）</h2></div><div class="muted small" id="curveMeta">-</div></div>
    <div class="card curve-card">
      <div class="curve-box" id="curveBox"></div>
      <div class="curve-labels"><span id="curveStart">-</span><span id="curveEnd">-</span></div>
    </div>
  </section>

"""

CURVE_SCRIPT = """<script>
(function(){
  function parseDate(s){ return new Date(s.replace(/-/g,'/')).getTime(); }
  function draw(pts){
    var box=document.getElementById('curveBox'); if(!box||pts.length<2) return;
    var W=900,H=300,pad=14;
    var eq=pts.map(function(p){return Number(p.equity);});
    var ts=pts.map(function(p){return parseDate(p.date);});
    var logs=eq.map(function(v){return Math.log(v);});
    var xmin=Math.min.apply(null,ts), xmax=Math.max.apply(null,ts);
    var ymin=Math.min.apply(null,logs), ymax=Math.max.apply(null,logs);
    if(xmax===xmin||ymax===ymin) return;
    function X(v){return pad+(v-xmin)/(xmax-xmin)*(W-2*pad);}
    function Y(v){return H-pad-(v-ymin)/(ymax-ymin)*(H-2*pad);}
    var d=pts.map(function(p,i){return (i?'L':'M')+X(ts[i]).toFixed(1)+' '+Y(logs[i]).toFixed(1);}).join(' ');
    var area=d+' L'+X(xmax).toFixed(1)+' '+(H-pad)+' L'+X(xmin).toFixed(1)+' '+(H-pad)+' Z';
    var peak=-Infinity,mdd=0;
    eq.forEach(function(v){ if(v>peak) peak=v; var dd=v/peak-1; if(dd<mdd) mdd=dd; });
    var svg='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none">'
      +'<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#ff4d4f" stop-opacity="0.35"/><stop offset="100%" stop-color="#ff4d4f" stop-opacity="0"/></linearGradient></defs>'
      +'<path d="'+area+'" fill="url(#cg)"/>'
      +'<path d="'+d+'" fill="none" stroke="#ff4d4f" stroke-width="2.2" vector-effect="non-scaling-stroke"/>'
      +'</svg>';
    box.innerHTML=svg;
    var meta=document.getElementById('curveMeta');
    if(meta){ meta.textContent='最终 '+(eq[eq.length-1]/100000).toFixed(1)+' 倍 · 最大回撤 '+(mdd*100).toFixed(1)+'%'; }
    var s=document.getElementById('curveStart'), e=document.getElementById('curveEnd');
    if(s) s.textContent=pts[0].date; if(e) e.textContent=pts[pts.length-1].date;
    var tip=document.createElement('div'); tip.className='curve-tip'; box.appendChild(tip);
    box.onmousemove=function(ev){
      var r=box.getBoundingClientRect();
      var x=(ev.clientX-r.left)/r.width*W;
      var best=0,bd=1e9;
      for(var i=0;i<ts.length;i++){var dd=Math.abs(X(ts[i])-x); if(dd<bd){bd=dd;best=i;}}
      var p=pts[best];
      tip.style.display='block';
      tip.style.left=Math.min(r.width-170,Math.max(0,ev.clientX-r.left+12))+'px';
      tip.style.top=Math.max(0,ev.clientY-r.top-36)+'px';
      tip.textContent=p.date+'  '+(eq[best]/100000).toFixed(2)+' 倍';
    };
    box.onmouseleave=function(){ tip.style.display='none'; };
  }
  fetch('/api/wandering-plan/data',{credentials:'same-origin'})
    .then(function(r){return r.json();})
    .then(function(d){ draw((d&&d.curve)||[]); })
    .catch(function(){});
})();
</script>
"""

REPL = [
    ("</head>", CURVE_STYLE + "</head>"),
    ('<section class="section">\n    <div class="section-head"><div><div class="eyebrow">最新信号</div><h2>最近信号日候选</h2></div></div>',
     CURVE_SECTION + '  <section class="section">\n    <div class="section-head"><div><div class="eyebrow">最新信号</div><h2>最近信号日候选</h2></div></div>'),
    ("</body>", CURVE_SCRIPT + "</body>"),

    ("<title>BP2.3</title>", "<title>流浪计划</title>"),
    ('<div class="eyebrow">BP2.3</div>', '<div class="eyebrow">流浪计划</div>'),
    ("<h1>爆破2.3实时策略页</h1>", "<h1>流浪计划实时策略页</h1>"),
    ('<a class="nav-link" href="/wandering-plan/">流浪计划</a>', '<a class="nav-link" href="/">BP2.3 首页</a>'),
    ('<body data-api="/api/bp2-3/data">', '<body data-api="/api/wandering-plan/data">'),
    ("<div>数据源：本机 BP2.3 回测与每日信号；每年独立按 10 万本金重算，最新候选单独列出。</div>",
     "<div>数据源：已逐笔核验的 610 笔回测（B1 313 / QL2 266 / V12 31）；2 仓 × 50% 复利。</div>"),
    ("<div>冠军参数 m3|1.0/1.0/0.8|low0.1|q40|zskip|k3|h1；已知代价：全期最大回撤 -44.70%（BP2.2 为 -44.55%）。</div>",
     "<div>三路信号：B1 爆破 / QL2 冠军 / 双波 O1+C3（V1.2 离场）；每日 17:45 自动更新。</div>"),
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
