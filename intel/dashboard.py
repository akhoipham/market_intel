"""Build a self-contained dashboard.html from the SQLite store.

Everything is embedded (data as JSON, no external JS), so the file works
offline and can be regenerated on a cron after each pipeline run.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .store import connect, export_window

OUT = Path(__file__).resolve().parent.parent / "dashboard.html"

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SIGNAL/DESK — Market Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Archivo:wdth,wght@75..100,400..800&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0a0c10; --panel:#11151d; --panel2:#161b25; --line:#222a37;
  --text:#c9d1dd; --dim:#69748a; --faint:#3d4659;
  --amber:#f3a83b; --amber-dim:#8a5f22;
  --bull:#3ec995; --bear:#ef5b6e; --flat:#8c96a8;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  --sans:"Archivo",system-ui,-apple-system,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html{font-size:15px}
body{background:var(--bg);color:var(--text);font-family:var(--mono);min-height:100vh}
a{color:inherit;text-decoration:none}
a:hover .hl-title{color:var(--amber)}
:focus-visible{outline:2px solid var(--amber);outline-offset:2px}

/* status bar */
.statusbar{display:flex;align-items:baseline;gap:1.2rem;padding:.7rem 1.4rem;
  border-bottom:1px solid var(--line);background:var(--panel);flex-wrap:wrap}
.brand{font-family:var(--sans);font-weight:800;font-stretch:80%;letter-spacing:.04em;
  font-size:1.05rem;color:var(--amber)}
.brand span{color:var(--text)}
.statusbar .meta{color:var(--dim);font-size:.72rem}
.statusbar .meta b{color:var(--text);font-weight:500}

/* controls row */
.controls{display:flex;align-items:center;gap:1rem;padding:.8rem 1.4rem;flex-wrap:wrap}
.ranges{display:flex;border:1px solid var(--line);border-radius:3px;overflow-x:auto;max-width:100%}
.ranges button{background:transparent;border:0;border-right:1px solid var(--line);
  color:var(--dim);font:600 .78rem var(--mono);padding:.45rem .8rem;cursor:pointer}
.ranges button:last-child{border-right:0}
.ranges button:hover{color:var(--text)}
.ranges button.on{background:var(--amber);color:#0a0c10}
.search{flex:1;min-width:180px;max-width:340px;background:var(--panel);
  border:1px solid var(--line);border-radius:3px;color:var(--text);
  font:.8rem var(--mono);padding:.45rem .7rem}
.search::placeholder{color:var(--faint)}
.kpis{display:flex;gap:1.4rem;margin-left:auto;font-size:.72rem;color:var(--dim)}
.kpis b{display:block;font-size:1.05rem;color:var(--text);font-weight:600}

/* theme tape — the signature element */
.tape-label{padding:.2rem 1.4rem 0;font-size:.62rem;letter-spacing:.18em;color:var(--faint)}
.tape{display:flex;gap:.45rem;overflow-x:auto;padding:.55rem 1.4rem .9rem;
  scrollbar-width:thin;scrollbar-color:var(--faint) transparent}
.chip{flex:0 0 auto;display:flex;flex-direction:column;gap:.18rem;cursor:pointer;
  border:1px solid var(--line);border-radius:3px;padding:.45rem .65rem;
  background:var(--panel);min-width:7.2rem;border-bottom-width:3px}
.chip:hover{border-color:var(--amber-dim)}
.chip.on{border-color:var(--amber);background:var(--panel2)}
.chip .name{font-family:var(--sans);font-weight:600;font-size:.74rem;
  font-stretch:85%;white-space:nowrap}
.chip .stats{display:flex;gap:.5rem;font-size:.66rem;color:var(--dim)}
.chip .stats .n{color:var(--text)}

/* main grid */
.grid{display:grid;grid-template-columns:minmax(360px,5fr) minmax(320px,7fr);
  gap:1px;background:var(--line);border-top:1px solid var(--line)}
.pane{background:var(--bg);min-height:60vh}
.pane h2{font-family:var(--sans);font-stretch:85%;font-weight:700;font-size:.72rem;
  letter-spacing:.16em;color:var(--dim);padding:.85rem 1.2rem .5rem;text-transform:uppercase}

/* ticker table */
table{width:100%;border-collapse:collapse;font-size:.78rem}
th{font-size:.62rem;letter-spacing:.12em;color:var(--faint);text-align:left;
  font-weight:500;padding:.3rem .6rem;border-bottom:1px solid var(--line);
  cursor:pointer;user-select:none;white-space:nowrap}
th:hover{color:var(--dim)}
th.sorted{color:var(--amber)}
td{padding:.42rem .6rem;border-bottom:1px solid #151a23;vertical-align:top}
tr.tk{cursor:pointer}
tr.tk:hover td{background:var(--panel)}
tr.tk.on td{background:var(--panel2)}
.tk-sym{color:var(--amber);font-weight:600;white-space:nowrap}
.tk-x{color:var(--faint);font-size:.64rem}
.tk-name{color:var(--dim);font-size:.7rem;max-width:13rem;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.num{text-align:right;font-variant-numeric:tabular-nums}
.bull{color:var(--bull)} .bear{color:var(--bear)} .flat{color:var(--flat)}
.bar{display:inline-block;height:.55rem;border-radius:1px;vertical-align:middle}
.themes-mini{color:var(--faint);font-size:.64rem;max-width:11rem}

/* headline tape */
.hl{display:flex;gap:.7rem;padding:.55rem 1.2rem;border-bottom:1px solid #151a23}
.hl:hover{background:var(--panel)}
.dot{flex:0 0 auto;width:.55rem;height:.55rem;border-radius:50%;margin-top:.32rem}
.hl-body{min-width:0}
.hl-title{font-size:.8rem;line-height:1.45}
.hl-meta{display:flex;gap:.7rem;flex-wrap:wrap;font-size:.64rem;color:var(--faint);margin-top:.15rem}
.hl-meta .src{color:var(--dim)}
.hl-meta .tag{color:var(--amber-dim)}
.hl-meta .tkx{color:var(--amber)}
.hl.filing .hl-title::before{content:"⊞ ";color:var(--amber-dim)}
.empty{padding:2.5rem 1.2rem;color:var(--faint);font-size:.78rem;line-height:1.7}
.clear{background:none;border:1px solid var(--line);color:var(--dim);
  font:.66rem var(--mono);border-radius:3px;padding:.2rem .55rem;cursor:pointer;margin-left:.6rem}
.clear:hover{color:var(--amber);border-color:var(--amber-dim)}
footer{padding:1rem 1.4rem 2rem;color:var(--faint);font-size:.66rem;line-height:1.7}
@media (max-width:900px){.grid{grid-template-columns:1fr}.kpis{margin-left:0}}
@media (prefers-reduced-motion:no-preference){
  .chip,.ranges button{transition:border-color .12s,background .12s,color .12s}
}
</style>
</head>
<body>
<div class="statusbar">
  <div class="brand">SIGNAL<span>/DESK</span></div>
  <div class="meta">north american equities · thematic news intelligence</div>
  <div class="meta" style="margin-left:auto">data as of <b id="asof"></b> · <b id="total-n"></b> headlines in window</div>
</div>

<div class="controls">
  <div class="ranges" id="ranges" role="tablist" aria-label="Time range"></div>
  <input class="search" id="q" type="search" placeholder="filter: ticker, company, keyword…" aria-label="Filter">
  <div class="kpis">
    <div><b id="k-tickers">–</b>tickers mentioned</div>
    <div><b id="k-bull" class="bull">–</b>bullish</div>
    <div><b id="k-bear" class="bear">–</b>bearish</div>
  </div>
</div>

<div class="tape-label">THEME TAPE — MENTIONS / NET SENTIMENT IN WINDOW <span id="active-filters"></span></div>
<div class="tape" id="tape"></div>

<div class="grid">
  <section class="pane">
    <h2>Ticker Leaderboard</h2>
    <table id="tk-table">
      <thead><tr>
        <th data-k="ticker">SYM</th><th>COMPANY</th>
        <th class="num" data-k="n">MENT</th>
        <th class="num" data-k="sent">SENT</th>
        <th>PULSE</th><th>THEMES</th>
      </tr></thead>
      <tbody id="tk-body"></tbody>
    </table>
    <div class="empty" id="tk-empty" hidden>No ticker mentions in this window. Widen the range or clear filters.</div>
  </section>
  <section class="pane">
    <h2>Headline Tape <span id="hl-count" style="color:var(--faint)"></span></h2>
    <div id="hl-list"></div>
    <div class="empty" id="hl-empty" hidden>No headlines match. Widen the range or clear filters.</div>
  </section>
</div>

<footer>
  prototype · sources: public RSS wires + SEC EDGAR · sentiment: lexicon (headline-level) ·
  matching tiers: cashtag → exchange tag → curated name/alias with ambiguity guard ·
  regenerate with <span style="color:var(--dim)">python run.py fetch && python run.py build</span>
</footer>

<script>
const DATA = __DATA__;
const BUILT = __BUILT__;

const YTD_S = (() => { const d = new Date(BUILT*1000);
  return Math.max(86400, Math.round(BUILT - new Date(d.getFullYear(),0,1).getTime()/1000)); })();
const RANGES = [["1H",3600],["8H",28800],["1D",86400],["3D",259200],["1W",604800],
  ["1M",2592000],["3M",7776000],["6M",15552000],["YTD",YTD_S],["1Y",31536000]];
const S = { range: 86400, theme: null, ticker: null, q: "", sortK: "n", sortDir: -1 };

const $ = id => document.getElementById(id);
const esc = s => s.replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const sentClass = v => v >= .25 ? "bull" : v <= -.25 ? "bear" : "flat";
const fmtSent = v => (v>0?"+":"") + v.toFixed(2);
const ago = p => { const d = BUILT - p;
  if (d < 3600) return Math.max(1, Math.round(d/60)) + "m";
  if (d < 86400) return Math.round(d/3600) + "h";
  if (d < 5184000) return Math.round(d/86400) + "d";
  return Math.round(d/2592000) + "mo"; };

function inWindow(a){ return BUILT - a.p <= S.range; }
function passText(a){
  if(!S.q) return true; const q = S.q.toLowerCase();
  return a.t.toLowerCase().includes(q) ||
    a.tk.some(m => m.ticker.toLowerCase().includes(q) || m.company.toLowerCase().includes(q));
}
function visible(){ return DATA.filter(a => inWindow(a) && passText(a)
  && (!S.theme || a.th.includes(S.theme))
  && (!S.ticker || a.tk.some(m => m.ticker === S.ticker))); }

function render(){
  const win = visible();
  // KPIs
  const winNoTk = DATA.filter(a => inWindow(a) && passText(a) && (!S.theme || a.th.includes(S.theme)));
  $("total-n").textContent = DATA.filter(inWindow).length;
  $("k-bull").textContent = win.filter(a => a.sn >= .25).length;
  $("k-bear").textContent = win.filter(a => a.sn <= -.25).length;

  // theme tape (ignores theme filter itself so chips stay comparable)
  const base = DATA.filter(a => inWindow(a) && passText(a) && (!S.ticker || a.tk.some(m=>m.ticker===S.ticker)));
  const tstat = {};
  for(const a of base) for(const th of a.th){
    (tstat[th] ||= {n:0, s:0}); tstat[th].n++; tstat[th].s += a.sn; }
  const tape = Object.entries(tstat).sort((x,y) => y[1].n - x[1].n);
  $("tape").innerHTML = tape.map(([name,v]) => {
    const avg = v.s / v.n, cls = sentClass(avg);
    return `<div class="chip ${S.theme===name?"on":""}" data-th="${esc(name)}" tabindex="0" role="button"
      style="border-bottom-color:var(--${cls==="bull"?"bull":cls==="bear"?"bear":"line"})">
      <span class="name">${esc(name)}</span>
      <span class="stats"><span class="n">${v.n}</span><span class="${cls}">${fmtSent(avg)}</span></span></div>`;
  }).join("") || `<div class="empty">No themes detected in this window.</div>`;

  // ticker leaderboard
  const ts = {};
  for(const a of winNoTk) for(const m of a.tk){
    const r = (ts[m.ticker] ||= {ticker:m.ticker, company:m.company, x:m.exchange, n:0, s:0, th:{}});
    r.n++; r.s += a.sn; for(const th of a.th) r.th[th] = (r.th[th]||0)+1; }
  let rows = Object.values(ts).map(r => ({...r, sent: r.s/r.n}));
  rows.sort((a,b) => { const k = S.sortK;
    const va = k==="ticker" ? a.ticker : a[k], vb = k==="ticker" ? b.ticker : b[k];
    return (va<vb?-1:va>vb?1:0) * S.sortDir; });
  const maxN = Math.max(1, ...rows.map(r=>r.n));
  $("tk-body").innerHTML = rows.slice(0,80).map(r => {
    const cls = sentClass(r.sent);
    const topTh = Object.entries(r.th).sort((x,y)=>y[1]-x[1]).slice(0,2).map(e=>e[0]).join(" · ");
    return `<tr class="tk ${S.ticker===r.ticker?"on":""}" data-tk="${esc(r.ticker)}" tabindex="0">
      <td class="tk-sym">${esc(r.ticker)} <span class="tk-x">${esc(r.x)}</span></td>
      <td class="tk-name" title="${esc(r.company)}">${esc(r.company)}</td>
      <td class="num">${r.n}</td>
      <td class="num ${cls}">${fmtSent(r.sent)}</td>
      <td><span class="bar ${cls}" style="width:${(4+56*r.n/maxN).toFixed(0)}px;background:currentColor"></span></td>
      <td class="themes-mini">${esc(topTh)}</td></tr>`;
  }).join("");
  $("tk-empty").hidden = rows.length > 0;
  $("k-tickers").textContent = rows.length;
  document.querySelectorAll("#tk-table th").forEach(th =>
    th.classList.toggle("sorted", th.dataset.k === S.sortK));

  // headline tape
  const hls = win.slice(0, 250);
  $("hl-count").textContent = `· ${win.length}`;
  $("hl-list").innerHTML = hls.map(a => {
    const cls = sentClass(a.sn);
    const tks = a.tk.slice(0,4).map(m=>esc(m.ticker)).join(" ");
    const ths = a.th.slice(0,2).map(esc).join(" · ");
    return `<a href="${esc(a.u)}" target="_blank" rel="noopener">
      <div class="hl ${a.k==="filing"?"filing":""}">
      <span class="dot ${cls}" style="background:currentColor"></span>
      <div class="hl-body"><div class="hl-title">${esc(a.t)}</div>
      <div class="hl-meta"><span>${ago(a.p)}</span><span class="src">${esc(a.s)}</span>
      ${tks?`<span class="tkx">${tks}</span>`:""}${ths?`<span class="tag">${ths}</span>`:""}</div>
      </div></div></a>`;
  }).join("");
  $("hl-empty").hidden = hls.length > 0;

  // active filter pills
  const f = [];
  if (S.theme) f.push(`theme=${S.theme}`);
  if (S.ticker) f.push(`ticker=${S.ticker}`);
  $("active-filters").innerHTML = f.length ?
    ` <span style="color:var(--amber)">· ${f.map(esc).join("  ")}</span><button class="clear" id="clear-f">clear</button>` : "";
  const cf = $("clear-f"); if (cf) cf.onclick = () => { S.theme = S.ticker = null; render(); };
}

// wire up controls
$("ranges").innerHTML = RANGES.map(([l,s]) =>
  `<button data-s="${s}" class="${s===S.range?"on":""}" role="tab">${l}</button>`).join("");
$("ranges").addEventListener("click", e => {
  const b = e.target.closest("button"); if(!b) return;
  S.range = +b.dataset.s;
  document.querySelectorAll("#ranges button").forEach(x=>x.classList.toggle("on", x===b));
  render(); });
$("q").addEventListener("input", e => { S.q = e.target.value.trim(); render(); });
$("tape").addEventListener("click", e => {
  const c = e.target.closest(".chip"); if(!c) return;
  S.theme = S.theme === c.dataset.th ? null : c.dataset.th; render(); });
$("tk-body").addEventListener("click", e => {
  const r = e.target.closest("tr.tk"); if(!r) return;
  S.ticker = S.ticker === r.dataset.tk ? null : r.dataset.tk; render(); });
document.querySelector("#tk-table thead").addEventListener("click", e => {
  const th = e.target.closest("th[data-k]"); if(!th) return;
  if (S.sortK === th.dataset.k) S.sortDir *= -1;
  else { S.sortK = th.dataset.k; S.sortDir = th.dataset.k === "ticker" ? 1 : -1; }
  render(); });
[["tape",".chip","click"],["tk-body","tr.tk","click"]].forEach(([id,sel]) =>
  $(id).addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") {
      const t = e.target.closest(sel); if (t){ e.preventDefault(); t.click(); } } }));

$("asof").textContent = new Date(BUILT*1000).toLocaleString();
render();
</script>
</body>
</html>
"""


def build(out: Path = OUT) -> Path:
    conn = connect()
    data = export_window(conn)
    conn.close()
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__BUILT__", str(int(time.time()))))
    out.write_text(html, encoding="utf-8")
    print(f"Built {out} with {len(data)} articles.")
    return out
