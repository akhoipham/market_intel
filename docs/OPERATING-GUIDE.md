# SIGNAL/DESK — Operating Guide

This guide covers everything from first run on your own computer to fully
automated, free hosting in the cloud. No prior DevOps experience assumed.

---

## 1. How the system works (30-second mental model)

```
                 ┌──────────────────────────────────────────────┐
  RSS wires ───▶ │                                              │
  (11 feeds)     │  run.py fetch                                │
                 │   ├─ match headlines → tickers (matcher.py)  │──▶ data/intel.db
  SEC EDGAR ───▶ │   ├─ score sentiment (sentiment.py)          │    (SQLite, grows
  (8-K, Form 4)  │   └─ tag themes (themes.py)                  │     over time)
                 └──────────────────────────────────────────────┘
                                                                       │
                 ┌──────────────────────────────────────────────┐      │
                 │  run.py build  →  dashboard.html             │◀─────┘
                 └──────────────────────────────────────────────┘
```

Two commands, run on a schedule. The dashboard is a single static HTML file —
it needs no server, no database connection, nothing. You open it in a browser
(or host it on any static file host) and all filtering happens client-side.

**Key consequence:** history accumulates in `data/intel.db`. On day one,
only 1H–1D windows will have data. After a month of scheduled runs, 1M fills
in; after a year, 1Y. Don't delete the `.db` file unless you want to reset.

---

## 2. First run (any computer)

**Prerequisites:** Python 3.10+ ([python.org](https://python.org), check
"Add to PATH" on Windows). Verify with `python --version`
(or `python3 --version` on Mac/Linux).

```bash
cd market-intel
pip install -r requirements.txt        # just feedparser + requests

# Option A — see it working instantly with bundled sample data:
python run.py demo

# Option B — real data:
python run.py refresh-tickers          # one time: SEC's ~10k ticker list
python run.py fetch build              # ~30-60 seconds
```

Then open `dashboard.html` — double-click it, or:
- macOS: `open dashboard.html`
- Windows: `start dashboard.html`
- Linux: `xdg-open dashboard.html`

On Windows, use `python` instead of `python3` throughout.

> `demo` wipes the database and loads fixtures. Don't run it after you've
> started collecting real data, or you'll lose your history.

---

## 3. Keeping it fresh: scheduling

Run `python run.py fetch build` every 15–30 minutes during market hours.
More frequent gains little (RSS feeds don't update faster) and is impolite
to the free sources.

### macOS / Linux — cron
```bash
crontab -e
```
Add (adjust the path; this runs every 20 min, 7am–7pm Eastern, weekdays):
```
*/20 11-23 * * 1-5  cd /path/to/market-intel && /usr/bin/python3 run.py fetch build >> fetch.log 2>&1
0 6 * * 0           cd /path/to/market-intel && /usr/bin/python3 run.py refresh-tickers >> fetch.log 2>&1
```
(Cron uses your machine's local time — adjust the hour range to your timezone.)

### Windows — Task Scheduler
1. Open **Task Scheduler** → **Create Basic Task**.
2. Trigger: Daily → repeat every 20 minutes for 12 hours.
3. Action: Start a program → Program: `python` →
   Arguments: `run.py fetch build` →
   Start in: `C:\path\to\market-intel`.

### The catch with local scheduling
Your computer must be on and awake. If it sleeps, you get gaps in history
(harmless — the dashboard just shows what it has). If that bothers you,
use the cloud option below.

---

## 4. Recommended free deployment: GitHub Actions + GitHub Pages

This is the best fit for this project: GitHub gives you a free scheduler
(Actions) and free static hosting (Pages), and the repo itself stores your
database history. Total cost: $0. No server to manage.

**One-time setup (~15 minutes):**

1. Create a free account at github.com, then create a new **private or
   public repository** (public required for free Pages on free accounts;
   the data is all public-source anyway).

2. Upload this project to it. Easiest path if you don't know git: on the
   repo page, **Add file → Upload files**, drag the whole folder contents in.
   With git:
   ```bash
   cd market-intel
   git init && git add -A && git commit -m "initial"
   git remote add origin https://github.com/YOURNAME/market-intel.git
   git push -u origin main
   ```

3. The workflow file is already included at
   `.github/workflows/update-dashboard.yml`. It runs the pipeline every
   20 minutes on weekdays, commits the updated database and dashboard back
   to the repo, and publishes to Pages.

4. In the repo: **Settings → Actions → General → Workflow permissions →**
   select **"Read and write permissions"** → Save.

5. **Settings → Pages → Source: "Deploy from a branch"** → Branch: `main`,
   folder: `/ (root)` → Save.

6. **Actions tab → "Update dashboard" → Run workflow** to trigger the first
   run manually.

Your dashboard is then live at
`https://YOURNAME.github.io/market-intel/dashboard.html`
and updates itself forever. Bookmark it on your phone.

**Notes:**
- Free Actions minutes (2,000/month) are plenty: each run takes ~1 minute,
  and the schedule above uses ~1,200/month. Widen the cron interval to
  30 min if you add heavier modules later.
- GitHub's cron is best-effort; runs can start a few minutes late. Fine
  for this use case.
- If your repo is public, your dashboard URL is public too. It contains
  only headlines from public sources, but be aware of it.

---

## 5. Other platform options, compared

| Option | Cost | Always-on | Effort | Verdict |
|---|---|---|---|---|
| **Your own computer + cron** | $0 | only while awake | lowest | Fine to start; gaps when asleep |
| **GitHub Actions + Pages** | $0 | yes | low (one-time) | **Recommended** |
| Raspberry Pi / old laptop at home | ~$0 | yes | medium | Great if you already own one; same cron setup as Linux |
| PythonAnywhere (free tier) | $0 | yes | low | Free tier allows scheduled daily tasks only — too infrequent |
| Small VPS (Hetzner/DigitalOcean) | ~$4–6/mo | yes | medium | Overkill now; right answer later when you add a real backend/API |
| Vercel/Netlify | $0 | hosting only | — | They host static files well but their schedulers don't suit a Python+SQLite pipeline; you'd still need Actions |

**Decision rule:** start with `demo` + local runs today; set up GitHub
Actions this weekend; consider a VPS only when you outgrow static HTML
(e.g., when you add per-user features or a live API).

---

## 6. Routine maintenance

| Task | How often | Command / action |
|---|---|---|
| Refresh SEC ticker list | weekly | `python run.py refresh-tickers` (the Actions workflow does this automatically on Sundays) |
| Check feeds are alive | monthly | look at fetch output — a feed returning 0 items repeatedly is dead; replace its URL in `data/feeds.json` |
| Grow the ticker universe | as you notice misses | add rows to `data/tickers_seed.csv` (set `ambiguous=1` if the name is a common word) |
| Add/refine themes | whenever | edit the dictionary in `intel/themes.py` |
| Back up history | monthly | copy `data/intel.db` somewhere (on GitHub it's versioned automatically) |
| Trim the database | ~yearly | optional; even a year of headlines is only tens of MB |

After editing the universe, themes, or sentiment lexicon, run
`python -m tests.test_core` — and add a test case for whatever you changed.

---

## 7. Troubleshooting

**`ModuleNotFoundError: feedparser`** — `pip install -r requirements.txt`
(use `pip3` if `pip` isn't found; on some Linux systems add
`--break-system-packages`).

**A feed prints `[warn] ... 403/404`** — that endpoint changed or blocks
your network. Remove or replace it in `data/feeds.json`; everything else
keeps working.

**EDGAR returns nothing** — SEC requires a descriptive User-Agent and
rate-limits aggressively. The default UA in `intel/ingest.py` works, but
put your real contact email in it (SEC asks for this), and don't run more
than every few minutes.

**Dashboard shows "No headlines"** in long windows — expected on a fresh
install; history hasn't accumulated yet. Check the `data as of` timestamp
in the header to confirm the last successful build.

**Counts look wrong after laptop sleep** — the time windows are computed
against the build time. Just rerun `python run.py fetch build`.

**Duplicate-looking headlines** — dedup is by normalized title; genuinely
reworded syndications get through. Harmless; tighten `_norm_title()` in
`intel/store.py` if it bothers you.

---

## 8. Where the bodies are buried (file map)

```
market-intel/
├─ run.py                     CLI: fetch | build | demo | refresh-tickers
├─ dashboard.html             generated output — never edit by hand
├─ requirements.txt           feedparser, requests
├─ data/
│  ├─ tickers_seed.csv        ★ curated universe — matching quality lives here
│  ├─ feeds.json              ★ feed list — edit freely
│  ├─ tickers_sec.json        auto-generated by refresh-tickers
│  └─ intel.db                your accumulated history — back this up
├─ intel/
│  ├─ matcher.py              ticker matching (3 evidence tiers + ambiguity guard)
│  ├─ sentiment.py            finance lexicon scorer
│  ├─ themes.py               ★ theme dictionaries — add your themes
│  ├─ ingest.py               RSS + EDGAR fetchers
│  ├─ store.py                SQLite + pipeline
│  └─ dashboard.py            HTML generator (template + ranges live here)
├─ fixtures/headlines.json    demo data
├─ tests/test_core.py         run after any change: python -m tests.test_core
└─ .github/workflows/
   └─ update-dashboard.yml    the free cloud automation (section 4)
```
★ = files you're expected to edit.
