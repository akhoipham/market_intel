"""Build dashboard.html + data.json from the SQLite store.

dashboard.html  — the static shell (never changes after first deploy)
data.json       — the data payload, fetched live every 2 minutes by the browser

This split means the browser never needs a full page reload to see fresh data.
All filter state (range, theme, ticker, search) is preserved across refreshes.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .store import connect, export_window

ROOT     = Path(__file__).resolve().parent.parent
OUT      = ROOT / "dashboard.html"
DATA_OUT = ROOT / "data.json"

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

.statusbar{display:flex;align-items:baseline;gap:1.2rem;padding:.7rem 1.4rem;
  border-bottom:1px solid var(--line);background:var(--panel);flex-wrap:wrap}
.brand{font-family:var(--sans);font-weight:800;font-stretch:80%;letter-spacing:.04em;
  font-size:1.05rem;color:var(--amber)}
.brand span{color:var(--text)}
.statusbar .meta{color:var(--dim);font-size:.72rem}
.statusbar .meta b{color:var(--text);font-weight:500}

.controls{display:flex;align-items:center;gap:1rem;padding:.8rem 1.4rem;flex-wrap:wrap}
.ranges{display:flex;border:1px solid var(--line);border-radius:3px;overflow-x:auto;max-width:100%}
.ranges button{background:transparent;border:0;border-right:1px solid var(--line);
  color:var(--dim);font:600 .78rem var(--mono);padding:.45rem .8rem;cursor:pointer}
.ranges button:last-child{border-right:0}
.ranges button:hover{color:var(--text)}
.ranges button.on{background:var(--amber);color:#0a0c10}
.datectl{display:flex;align-items:center;gap:.4rem;font-size:.7rem;color:var(--dim)}
.datectl input{background:var(--panel);border:1px solid var(--line);border-radius:3px;
  color:var(--text);font:.74rem var(--mono);padding:.38rem .5rem;cursor:pointer;color-scheme:dark}
.datectl input:hover{border-color:var(--amber-dim)}
.age{font-size:.62rem;color:var(--faint)}
.age.warn{color:var(--amber)}
.age.stale{color:var(--bear)}
.search{flex:1;min-width:180px;max-width:340px;background:var(--panel);
  border:1px solid var(--line);border-radius:3px;color:var(--text);
  font:.8rem var(--mono);padding:.45rem .7rem}
.search::placeholder{color:var(--faint)}
.selctl{background:var(--panel);border:1px solid var(--line);border-radius:3px;
  color:var(--text);font:.76rem var(--mono);padding:.42rem .55rem;cursor:pointer}
.selctl:hover{border-color:var(--amber-dim)}
.chkctl{display:flex;align-items:center;gap:.35rem;font-size:.72rem;
  color:var(--dim);cursor:pointer;user-select:none}
.chkctl input{accent-color:var(--amber);cursor:pointer}
.kpis{display:flex;gap:1.4rem;margin-left:auto;font-size:.72rem;color:var(--dim)}
.kpis b{display:block;font-size:1.05rem;color:var(--text);font-weight:600}
.kpi{background:none;border:0;border-bottom:2px solid transparent;color:var(--dim);
  font:inherit;cursor:pointer;padding:0 0 .15rem;text-align:left}
.kpi:hover{color:var(--text)}
.kpi.on{border-bottom-color:var(--amber)}
.feedtabs{display:inline-flex;margin-left:.6rem;border:1px solid var(--line);border-radius:3px;vertical-align:middle}
.feedtabs button{background:transparent;border:0;border-right:1px solid var(--line);
  color:var(--dim);font:600 .6rem var(--mono);letter-spacing:.1em;padding:.25rem .6rem;cursor:pointer;text-transform:uppercase}
.feedtabs button:last-child{border-right:0}
.feedtabs button.on{background:var(--amber);color:#0a0c10}

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

.grid{display:grid;grid-template-columns:minmax(360px,5fr) minmax(320px,7fr);
  gap:1px;background:var(--line);border-top:1px solid var(--line)}
.pane{background:var(--bg);min-height:60vh}
.pane h2{font-family:var(--sans);font-stretch:85%;font-weight:700;font-size:.72rem;
  letter-spacing:.16em;color:var(--dim);padding:.85rem 1.2rem .5rem;text-transform:uppercase}
/* scrollable windows: cap each list so the page doesn't grow unbounded */
.scrollbox{max-height:34rem;overflow-y:auto;overflow-x:hidden}
.scrollbox::-webkit-scrollbar{width:8px}
.scrollbox::-webkit-scrollbar-thumb{background:var(--line);border-radius:4px}
.scrollbox::-webkit-scrollbar-track{background:transparent}
#tk-table thead th{position:sticky;top:0;background:var(--bg);z-index:2}

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
.tier{display:inline-block;margin-left:.35rem;font-size:.58rem;font-weight:600;
  width:1rem;height:1rem;line-height:1rem;text-align:center;border-radius:2px;
  vertical-align:middle}
.tier-mega{background:#2a4d8f;color:#cfe0ff}
.tier-large{background:#1f6b52;color:#bff0dc}
.tier-mid{background:#6b5a1f;color:#f0e3bf}
.tier-small{background:#6b3a1f;color:#f0d2bf}
.tier-micro{background:#6b1f3a;color:#f0bfd2}
.tk-name{color:var(--dim);font-size:.7rem;max-width:13rem;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.num{text-align:right;font-variant-numeric:tabular-nums}
.bull{color:var(--bull)} .bear{color:var(--bear)} .flat{color:var(--flat)}
.bar{display:inline-block;height:.55rem;border-radius:1px;vertical-align:middle}
.themes-mini{color:var(--faint);font-size:.64rem;max-width:11rem}

.hl{display:flex;gap:.7rem;padding:.55rem 1.2rem;border-bottom:1px solid #151a23}
.hl-favicon{width:16px;height:16px;border-radius:3px;flex:0 0 auto;margin-top:.2rem;
  background:var(--panel);object-fit:contain}
.hl:hover{background:var(--panel)}
.dot{flex:0 0 auto;width:.55rem;height:.55rem;border-radius:50%;margin-top:.32rem}
.hl-body{min-width:0}
.hl-title{font-size:.8rem;line-height:1.45}
.hl-meta{display:flex;gap:.7rem;flex-wrap:wrap;font-size:.64rem;color:var(--faint);margin-top:.15rem}
.hl-meta .src{color:var(--dim)}
.hl-meta .tag{color:var(--amber-dim)}
.hl-meta .tkx{color:var(--amber)}
.hl.filing .hl-title::before{content:"⊞ ";color:var(--amber-dim)}
.hl.opinion{opacity:.72}
.op-tag{font-size:.56rem;font-weight:600;letter-spacing:.08em;color:var(--faint);
  border:1px solid var(--faint);border-radius:2px;padding:0 .25rem}
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
  <div class="meta" style="margin-left:auto">
    data as of <b id="asof">loading…</b> <span class="age" id="age"></span> · <b id="total-n">–</b> headlines in window
  </div>
</div>

<div class="controls">
  <div class="ranges" id="ranges" role="tablist" aria-label="Time range"></div>
  <label class="datectl">from <input type="date" id="from" aria-label="From date">
    to <input type="date" id="to" aria-label="To date"></label>
  <select class="selctl" id="lens" aria-label="Lens">
    <option value="">all lenses</option>
    <option value="Markets">Markets</option>
    <option value="Macro & Rates">Macro &amp; Rates</option>
    <option value="Geopolitics">Geopolitics</option>
  </select>
  <select class="selctl" id="cap" aria-label="Market cap">
    <option value="">all caps</option>
    <option value="mega">Mega ≥$200B</option>
    <option value="large">Large $10–200B</option>
    <option value="mid">Mid $2–10B</option>
    <option value="small">Small $300M–2B</option>
    <option value="micro">Micro &lt;$300M</option>
  </select>
  <input class="search" id="q" type="search" placeholder="filter: ticker, company, keyword…" aria-label="Filter">
  <div class="kpis">
    <div><b id="k-tickers">–</b>tickers mentioned</div>
    <button class="kpi" id="f-bull" data-sent="bull"><b class="bull">–</b>bullish</button>
    <button class="kpi" id="f-bear" data-sent="bear"><b class="bear">–</b>bearish</button>
    <button class="kpi" id="f-flat" data-sent="flat"><b class="flat">–</b>neutral</button>
    <button class="kpi" id="f-op" data-sent="opinion"><b>–</b>opinion</button>
  </div>
</div>

<div class="tape-label">THEME TAPE — MENTIONS / NET SENTIMENT IN WINDOW <span id="active-filters"></span></div>
<div class="tape" id="tape"></div>

<div class="grid">
  <section class="pane">
    <h2>Ticker Leaderboard</h2>
    <div class="scrollbox" id="tk-scroll">
    <table id="tk-table">
      <thead><tr>
        <th data-k="ticker">SYM</th><th>COMPANY</th>
        <th class="num" data-k="n">MENT</th>
        <th class="num" data-k="sent">SENT</th>
        <th>PULSE</th><th>THEMES</th>
      </tr></thead>
      <tbody id="tk-body"></tbody>
    </table>
    </div>
    <div class="empty" id="tk-empty" hidden>No ticker mentions in this window. Widen the range or clear filters.</div>
  </section>
  <section class="pane">
    <h2>Headline Tape <span id="hl-count" style="color:var(--faint)"></span>
      <span class="feedtabs" id="feedtabs" role="tablist">
        <button data-feed="news" class="on" role="tab">News</button>
        <button data-feed="insider" role="tab">Insider</button>
      </span>
    </h2>
    <div class="scrollbox" id="hl-scroll"><div id="hl-list"></div></div>
    <div class="empty" id="hl-empty" hidden>No headlines match. Widen the range or clear filters.</div>
  </section>
</div>

<footer>
  live · sources: public RSS wires + SEC EDGAR · sentiment: lexicon (headline-level) ·
  matching: cashtag → exchange tag → curated name/alias with ambiguity guard ·
  browser re-checks for new data every 2 min; the feed itself regenerates server-side on a schedule
</footer>

<script>
// ── state ──────────────────────────────────────────────────────────────────
let DATA = [], BUILT = 0;
const REFRESH_S = 120; // seconds between data fetches
let secsLeft = REFRESH_S;
let firstLoad = true;

const $ = id => document.getElementById(id);
const esc = s => s.replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const sentClass = v => v>=.25?"bull":v<=-.25?"bear":"flat";
const fmtSent = v => (v>0?"+":"")+v.toFixed(2);
const ago = p => {
  const d = BUILT-p;
  if(d<3600) return Math.max(1,Math.round(d/60))+"m";
  if(d<86400) return Math.round(d/3600)+"h";
  if(d<5184000) return Math.round(d/86400)+"d";
  return Math.round(d/2592000)+"mo";
};

// Permanently hide specific tickers everywhere (leaderboard, headline chips,
// counts) regardless of how they matched. Add a symbol here any time one turns
// out to be noise — no other code change needed.
const EXCLUDED_TICKERS = new Set(["NWS", "NWSA", "TISI"]);

const S = {range:86400, fromDate:null, toDate:null, theme:null, ticker:null, q:"",
           sortK:"n", sortDir:-1, lens:"", cap:"", sent:null, feed:"news"};

const isInsider = a => a.k==="filing" && /^Form 4/.test(a.t);
const domain = a => { try { return new URL(a.u).hostname.replace(/^www\./,""); }
                      catch { return ""; } };

// ── data loading ────────────────────────────────────────────────────────────
const DATA_URL = "./data.json";
const IS_LOCAL = location.protocol === "file:";

async function loadData() {
  if (IS_LOCAL) { refreshAge(); return; }
  try {
    const resp = await fetch(DATA_URL + "?_=" + Date.now());
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const json = await resp.json();
    DATA  = (json.articles || []).map(a => ({
      ...a, tk: (a.tk || []).filter(m => !EXCLUDED_TICKERS.has(m.ticker))
    }));
    BUILT = json.built   || Math.floor(Date.now()/1000);
    secsLeft = REFRESH_S;
    render();
  } catch(e) {
    console.warn("data.json fetch failed:", e);
  }
}

// How old is the underlying data? The browser re-checks periodically, but the
// feed only regenerates server-side on the cron, so surface the real age + warn.
function refreshAge() {
  if (!BUILT) return;
  const sec = Math.max(0, Math.floor(Date.now()/1000) - BUILT);
  let txt;
  if (sec < 90)        txt = "just now";
  else if (sec < 3600) txt = Math.round(sec/60) + " min old";
  else                 txt = (sec/3600).toFixed(1) + " h old";
  const el = $("age");
  el.textContent = "· " + txt;
  el.className = "age" + (sec > 5400 ? " stale" : sec > 1500 ? " warn" : "");
}

// silent background refresh; no on-page countdown
setInterval(() => {
  secsLeft = Math.max(0, secsLeft - 1);
  refreshAge();
  if (secsLeft === 0) { loadData(); secsLeft = REFRESH_S; }
}, 1000);

// ── render ──────────────────────────────────────────────────────────────────
function inWindow(a){
  if (S.fromDate || S.toDate){                 // explicit date range filter
    if (S.fromDate && a.p < S.fromDate) return false;
    if (S.toDate   && a.p > S.toDate)   return false;
    return true;
  }
  return BUILT - a.p <= S.range;               // quick toggle
}
function passText(a){
  if(!S.q) return true; const q = S.q.toLowerCase();
  return a.t.toLowerCase().includes(q) ||
    a.tk.some(m=>m.ticker.toLowerCase().includes(q)||m.company.toLowerCase().includes(q));
}
function passLens(a){ return !S.lens || (a.ln||[]).includes(S.lens); }
function passCap(a){ return !S.cap || a.tk.some(m=>m.tier===S.cap); }
function passSent(a){
  if(!S.sent) return true;
  if(S.sent==="opinion") return a.k==="opinion";
  if(a.k==="opinion") return false;            // opinion pieces excluded from bull/bear/flat
  if(S.sent==="bull") return a.sn>=.25;
  if(S.sent==="bear") return a.sn<=-.25;
  return a.sn>-.25 && a.sn<.25;                // flat / neutral
}
function passFeed(a){ return S.feed==="insider" ? isInsider(a) : !isInsider(a); }
function visible(){ return DATA.filter(a=>inWindow(a)&&passText(a)&&passLens(a)
  &&passCap(a)&&passSent(a)&&passFeed(a)
  &&(!S.theme||a.th.includes(S.theme))
  &&(!S.ticker||a.tk.some(m=>m.ticker===S.ticker))); }

function render(){
  const RANGES=[["1H",3600],["4H",14400],["8H",28800],["1D",86400],
    ["1W",604800],["1M",2592000]];

  // rebuild range buttons only on first render or BUILT change
  const dateActive = !!(S.fromDate||S.toDate);
  if (!$("ranges").dataset.built || $("ranges").dataset.built !== String(BUILT)) {
    $("ranges").dataset.built = BUILT;
    $("ranges").innerHTML = RANGES.map(([l,s])=>
      `<button data-s="${s}" class="${(!dateActive&&s===S.range)?"on":""}" role="tab">${l}</button>`).join("");
    const dmax = new Date(BUILT*1000).toISOString().slice(0,10);  // no future dates
    $("from").max = dmax; $("to").max = dmax;
  }

  $("asof").textContent = BUILT ? new Date(BUILT*1000).toLocaleString() : "–";
  refreshAge();
  $("total-n").textContent = DATA.filter(a=>inWindow(a)&&passFeed(a)).length;

  const win = visible();
  const winNoTk = DATA.filter(a=>inWindow(a)&&passText(a)&&passLens(a)&&passCap(a)
    &&passSent(a)&&passFeed(a)&&(!S.theme||a.th.includes(S.theme)));
  // KPI counts are over the window (ignoring the active sentiment filter so the
  // tallies stay stable as you toggle them)
  const kbase = DATA.filter(a=>inWindow(a)&&passText(a)&&passLens(a)&&passCap(a)&&passFeed(a)
    &&(!S.theme||a.th.includes(S.theme))&&(!S.ticker||a.tk.some(m=>m.ticker===S.ticker)));
  $("f-bull").firstElementChild.textContent = kbase.filter(a=>a.k!=="opinion"&&a.sn>=.25).length;
  $("f-bear").firstElementChild.textContent = kbase.filter(a=>a.k!=="opinion"&&a.sn<=-.25).length;
  $("f-flat").firstElementChild.textContent = kbase.filter(a=>a.k!=="opinion"&&a.sn>-.25&&a.sn<.25).length;
  $("f-op").firstElementChild.textContent   = kbase.filter(a=>a.k==="opinion").length;
  ["bull","bear","flat","opinion"].forEach(k=>{
    const id={bull:"f-bull",bear:"f-bear",flat:"f-flat",opinion:"f-op"}[k];
    $(id).classList.toggle("on",S.sent===k); });

  // theme tape
  const base = DATA.filter(a=>inWindow(a)&&passText(a)&&passLens(a)&&passCap(a)
    &&passSent(a)&&passFeed(a)&&(!S.ticker||a.tk.some(m=>m.ticker===S.ticker)));
  const tstat={};
  for(const a of base) for(const th of a.th){
    (tstat[th]||={n:0,s:0}); tstat[th].n++; tstat[th].s+=a.sn; }
  $("tape").innerHTML = Object.entries(tstat).sort((x,y)=>y[1].n-x[1].n)
    .map(([name,v])=>{
      const avg=v.s/v.n, cls=sentClass(avg);
      return `<div class="chip ${S.theme===name?"on":""}" data-th="${esc(name)}" tabindex="0" role="button"
        style="border-bottom-color:var(--${cls==="bull"?"bull":cls==="bear"?"bear":"line"})">
        <span class="name">${esc(name)}</span>
        <span class="stats"><span class="n">${v.n}</span><span class="${cls}">${fmtSent(avg)}</span></span></div>`;
    }).join("") || `<div class="empty">No themes in this window.</div>`;

  // ticker leaderboard
  const ts={};
  for(const a of winNoTk) for(const m of a.tk){
    const r=(ts[m.ticker]||={ticker:m.ticker,company:m.company,x:m.exchange,
      tier:m.tier||"unknown",n:0,s:0,th:{}});
    r.n++; r.s+=a.sn; for(const th of a.th) r.th[th]=(r.th[th]||0)+1; }
  let rows=Object.values(ts).map(r=>({...r,sent:r.s/r.n}));
  rows.sort((a,b)=>{const k=S.sortK,va=k==="ticker"?a.ticker:a[k],vb=k==="ticker"?b.ticker:b[k];
    return (va<vb?-1:va>vb?1:0)*S.sortDir;});
  const maxN=Math.max(1,...rows.map(r=>r.n));
  $("tk-body").innerHTML = rows.slice(0,80).map(r=>{
    const cls=sentClass(r.sent);
    const topTh=Object.entries(r.th).sort((x,y)=>y[1]-x[1]).slice(0,2).map(e=>e[0]).join(" · ");
    return `<tr class="tk ${S.ticker===r.ticker?"on":""}" data-tk="${esc(r.ticker)}" tabindex="0">
      <td class="tk-sym">${esc(r.ticker)} <span class="tk-x">${esc(r.x)}</span>${r.tier&&r.tier!=="unknown"?`<span class="tier tier-${r.tier}">${r.tier[0].toUpperCase()}</span>`:""}</td>
      <td class="tk-name" title="${esc(r.company)}">${esc(r.company)}</td>
      <td class="num">${r.n}</td>
      <td class="num ${cls}">${fmtSent(r.sent)}</td>
      <td><span class="bar ${cls}" style="width:${(4+56*r.n/maxN).toFixed(0)}px;background:currentColor"></span></td>
      <td class="themes-mini">${esc(topTh)}</td></tr>`;
  }).join("");
  $("tk-empty").hidden = rows.length>0;
  $("k-tickers").textContent = rows.length;
  document.querySelectorAll("#tk-table th").forEach(th=>
    th.classList.toggle("sorted",th.dataset.k===S.sortK));

  // headline tape
  const hls=win.slice(0,250);
  $("hl-count").textContent = `· ${win.length}`;
  $("hl-list").innerHTML = hls.map(a=>{
    const cls=sentClass(a.sn);
    const tks=a.tk.slice(0,4).map(m=>esc(m.ticker)).join(" ");
    const ths=a.th.slice(0,2).map(esc).join(" · ");
    const fav=`https://www.google.com/s2/favicons?domain=${esc(domain(a))}&sz=32`;
    return `<a href="${esc(a.u)}" target="_blank" rel="noopener">
      <div class="hl ${a.k==="filing"?"filing":""} ${a.k==="opinion"?"opinion":""}">
      <img class="hl-favicon" src="${fav}" alt="" loading="lazy" width="16" height="16">
      <span class="dot ${cls}" style="background:currentColor"></span>
      <div class="hl-body"><div class="hl-title">${esc(a.t)}</div>
      <div class="hl-meta">${a.k==="opinion"?`<span class="op-tag">OPINION</span>`:""}<span>${ago(a.p)}</span><span class="src">${esc(a.s)}</span>
      ${tks?`<span class="tkx">${tks}</span>`:""}${ths?`<span class="tag">${ths}</span>`:""}</div>
      </div></div></a>`;
  }).join("");
  $("hl-empty").hidden = hls.length>0;

  const f=[];
  if(S.theme) f.push(`theme=${S.theme}`);
  if(S.ticker) f.push(`ticker=${S.ticker}`);
  $("active-filters").innerHTML = f.length
    ? ` <span style="color:var(--amber)">· ${f.map(esc).join("  ")}</span><button class="clear" id="clear-f">clear</button>` : "";
  const cf=$("clear-f"); if(cf) cf.onclick=()=>{ S.theme=S.ticker=null; render(); };
}

// ── event wiring ────────────────────────────────────────────────────────────
function clearDates(){ S.fromDate=S.toDate=null; $("from").value=""; $("to").value=""; }
$("ranges").addEventListener("click", e=>{
  const b=e.target.closest("button"); if(!b) return;
  S.range=+b.dataset.s; clearDates();                 // quick toggle overrides the date range
  document.querySelectorAll("#ranges button").forEach(x=>x.classList.toggle("on",x===b));
  render(); });
function onDate(){
  const fv=$("from").value, tv=$("to").value;
  S.fromDate = fv ? Math.floor(new Date(fv+"T00:00:00").getTime()/1000) : null;
  S.toDate   = tv ? Math.floor(new Date(tv+"T23:59:59").getTime()/1000) : null;  // inclusive end of day
  if(S.fromDate||S.toDate) document.querySelectorAll("#ranges button").forEach(x=>x.classList.remove("on"));
  else document.querySelectorAll("#ranges button").forEach(x=>x.classList.toggle("on",+x.dataset.s===S.range));
  render(); }
$("from").addEventListener("change", onDate);
$("to").addEventListener("change", onDate);
$("q").addEventListener("input", e=>{ S.q=e.target.value.trim(); render(); });
$("lens").addEventListener("change", e=>{ S.lens=e.target.value; render(); });
$("cap").addEventListener("change", e=>{ S.cap=e.target.value; render(); });
// sentiment filters (clickable KPIs)
document.querySelector(".kpis").addEventListener("click", e=>{
  const b=e.target.closest(".kpi"); if(!b) return;
  S.sent = S.sent===b.dataset.sent ? null : b.dataset.sent; render(); });
$("feedtabs").addEventListener("click", e=>{
  const b=e.target.closest("button"); if(!b) return;
  S.feed=b.dataset.feed;
  document.querySelectorAll("#feedtabs button").forEach(x=>x.classList.toggle("on",x===b));
  render(); });
$("tape").addEventListener("click", e=>{
  const c=e.target.closest(".chip"); if(!c) return;
  S.theme=S.theme===c.dataset.th?null:c.dataset.th; render(); });
$("tk-body").addEventListener("click", e=>{
  const r=e.target.closest("tr.tk"); if(!r) return;
  S.ticker=S.ticker===r.dataset.tk?null:r.dataset.tk; render(); });
document.querySelector("#tk-table thead").addEventListener("click", e=>{
  const th=e.target.closest("th[data-k]"); if(!th) return;
  if(S.sortK===th.dataset.k) S.sortDir*=-1;
  else { S.sortK=th.dataset.k; S.sortDir=th.dataset.k==="ticker"?1:-1; }
  render(); });
[["tape",".chip"],["tk-body","tr.tk"]].forEach(([id,sel])=>
  $(id).addEventListener("keydown", e=>{
    if(e.key==="Enter"||e.key===" "){
      const t=e.target.closest(sel); if(t){e.preventDefault();t.click();} } }));

// ── boot ─────────────────────────────────────────────────────────────────────
loadData();
</script>
</body>
</html>
"""


def build(out: Path = OUT, data_out: Path = DATA_OUT) -> Path:
    conn = connect()
    data = export_window(conn)
    conn.close()
    built = int(time.time())

    # Write data.json — the payload the browser fetches every 2 minutes
    payload = {"built": built, "articles": data}
    data_out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    # Write dashboard.html — static shell, only needs to be deployed once
    out.write_text(TEMPLATE, encoding="utf-8")
    print(f"Built {out.name} + {data_out.name} ({len(data)} articles).")
    return out
