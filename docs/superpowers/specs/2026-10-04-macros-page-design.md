# Macros page: design

- Date: 2026-10-04
- Status: revised after the owner's review on 2026-10-04. Nothing described here has been built or deployed.
- Address: `https://macros.theta-markets.com/`

## 1. Goal

One web page that shows:

1. US Treasury yields, as two linked interactive charts.
2. The odds of a rate cut, hold or hike at the next FOMC meeting, with a countdown.
3. The Fed funds rate with its target range.
4. An "Explain Macros" button that opens an AI-written analysis as a PDF in a new tab.

Constraints:

- The audience is 2–5 people. The page is public for a few days, then private behind Cloudflare Access.
- Data changes only when the owner runs a refresh on the Mac.
- The page is served from the existing Lightsail box (`ssh theta`). That box's real job is the daily options capture and the broker sign-in page. Neither may be put at risk.
- No cookies, trackers, analytics or third-party requests, in line with the site's privacy page.

## 2. Decisions

| Topic | Decision | Reason |
|---|---|---|
| Address | Subdomain `macros.theta-markets.com`, not `/macro` on the apex | The apex Pages site, `/` and `/privacy` stay untouched. Access can be switched on per hostname |
| Division of work | The Mac fetches data, calculates, writes the analysis and builds the page. The box only serves the finished files | The box needs no fetching, no API key, no installed package and no timer. A capture can start at any minute and cannot be disturbed |
| Refresh | Manual, by a command on the Mac | Owner's choice |
| Rate odds | Calculated in our own code from Fed funds futures prices, with the method CME publishes for FedWatch | CME's page blocks automated readers and its data is licensed. Polymarket and Kalshi are ruled out because prediction markets are not allowed in India |
| Analysis | Produced on the Mac before publishing, as a PDF. The button opens it | Nothing new runs on the box, the PDF opens instantly, and the owner reads it before publishing |
| Who writes the analysis | For now, an Opus subagent in a Claude Code session writes the text from the computed facts, and the project turns it into the PDF. Calling a model API from the refresh command comes later | Owner's choice on 2026-10-04. No API key, account or model integration is needed to launch |
| Date range | One range row drives both history charts | Confirmed by the owner on 2026-10-04 |
| Curve axis | Two modes with a toggle: even spacing and true scale | Owner's choice on 2026-10-04 |
| Box down | Visitors see Cloudflare's error page | Accepted by the owner |

## 3. Not in this version

- SOFR and other rates.
- Odds for meetings after the next one.
- Scheduled refresh, or any fetching on the box.
- Generating the analysis on a button press.
- Calling a model API from the refresh command. The analysis file in section 6.5 is the contract a later integration fills.
- FRED as a source.
- Charts inside the PDF.

Each can be added later without changing the parts below.

## 4. How it fits together

```
Mac (on demand)                          Box (always on)                     Cloudflare
---------------                          ---------------                     ----------
python -m macro refresh                  /var/lib/macro/releases/<id>/       macros.theta-markets.com
  fetch Treasury, NY Fed, futures        /var/lib/macro/current -> <id>        | existing tunnel
  calculate odds and facts               macro-web.service                     v
  build dist/                              serves current/ on               visitor's browser draws
Opus subagent writes the analysis text     127.0.0.1:8081                    the charts from data.json
python -m macro analysis  (check the text, write the PDF into dist/)
python -m macro preview   (look at it locally)
python -m macro publish   -- upload over ssh --> new release, then switch `current`
```

A "snapshot" is one complete build: the page, its data file and its PDF. Each has an id made from its UTC build time, for example `20261004T181500Z`.

## 5. The page

### 5.1 Layout

Top to bottom, on one page:

```
[ Explain Macros ]   AI-written analysis of this data            Refreshed <date, time>
Range:  1Y  5Y  10Y  Max   From [date]  To [date]
+-- UST yields -------------------------------------------------------------+
|  Yield history, one tenor            |  Yield curve, one date             |
|  <---------- date slider ---------->  |  <-------- tenor slider -------->  |
+---------------------------------------------------------------------------+
+-- Next FOMC decision ------------------------------------------------------+
|  Countdown; cut, hold, hike          |  Odds by target range              |
|  How the odds have moved (table)                                           |
+---------------------------------------------------------------------------+
+-- Fed funds rate and target range ----------------------------------------+
Sources and notices
```

On screens narrower than about 900 px, the side-by-side pairs stack.

### 5.2 Range row

- Presets `1Y`, `5Y`, `10Y`, `Max`, then custom `From` and `To` dates. The default is `10Y`.
- The range applies to both history charts: yield history and the Fed funds rate. One range keeps the two charts comparable.
- A custom range is kept inside the data and put in order. It must span at least two different dates; otherwise the two inputs go back to the range in force.

### 5.3 UST yields

**Left: yield history.** A line of one tenor's yield over the selected range.

- The title names the tenor, for example "10-year Treasury yield".
- A date slider sits under the chart and spans exactly the dates shown. It selects one date. The default is the latest date. A vertical marker shows the selected date on the chart.
- Each slider has a caption saying what it picks: "Date shown on the yield curve" and "Tenor shown on the yield history".
- A readout shows the selected date and that day's yield.

**Right: yield curve.** Yield against tenor for the selected date.

- A line with a marker per tenor. The title names the date.
- A tenor slider sits under the chart, one step per tenor. It selects the tenor shown on the left. The default is 10Y. The selected tenor's marker is highlighted.
- Clicking a point on the curve selects that tenor too, in either mode.
- A "Show table" toggle lists tenor and yield for the selected date.
- A mode toggle above the chart switches the horizontal axis between two modes:
  - **Even spacing**, the default. Tenors are evenly spaced and labelled (1M, 3M, ... 30Y). The tenor slider is active and its steps line up with the points.
  - **True scale.** Tenors are placed by their years to maturity, so the curve keeps its real, undistorted shape. The tenor slider is disabled and greyed out. Hovering over it, or reaching it with the keyboard, shows the hint "Switch to even spacing to pick a tenor".
- Switching mode keeps the selected date and tenor. The selected tenor stays highlighted in both modes.
- Every tenor has a tick mark. Where the labels would collide (true scale, or a narrow screen), the most watched tenors are labelled first: 10Y, 2Y, 30Y, 5Y, 3M, then the rest.
- The hint is attached to a wrapper around the slider, because a disabled input does not reliably raise hover events.

**Linking rules.**

- Moving the date slider redraws the curve for that date.
- Moving the tenor slider redraws the history for that tenor.
- The date slider steps only through dates that have data.
- Older years have fewer tenors (nine in 1990, fourteen now). The curve shows the tenors published on the selected date. The history line starts where that tenor's data starts and breaks across gaps.
- When the range changes and the selected date falls outside it, the date snaps to the nearest end of the range.

### 5.4 Next FOMC decision

**Countdown.** Days, hours and minutes to the scheduled statement, kept current in the browser. It shows the statement time in US Eastern time and in the visitor's local time. It always counts to the first meeting on the list that is still in the future.

**Odds.**

- A summary beside the countdown: cut, hold and hike percentages, the current range and the pricing date.
- One bar per target range that has a non-zero probability, with the value printed on the bar. The current range is labelled "current". On a narrow screen a range is written on two lines under its bar.
- Below both, a table with one row per range and columns `Now`, `1 day`, `1 week` and `1 month`, each headed by its date. A cell with no price data shows "n/a".
- A note: "Own calculation from 30-Day Federal Funds futures prices, using the method CME Group publishes for its FedWatch tool. These are not CME FedWatch figures."
- If the meeting the odds refer to has already passed when the page is viewed, the block says the odds were calculated before that decision.

### 5.5 Fed funds rate

- The effective federal funds rate (EFFR) as a line, with the target range as a shaded band behind it. Before 16 December 2008 the target was a single rate, drawn as a line.
- A legend names the two series. Data starts on 3 July 2000.
- The selected date's marker also appears on this chart, with a readout of that day's rate and target.
- The published series trails a decision by a day or two. When the odds' current range (section 6.3) differs from the last published target range, a note under the chart says the Fed has moved the range and that the series will catch up.

### 5.6 Explain Macros button

- A link styled as a button, at the top. It opens `analysis.pdf` in a new tab.
- Beside it: "AI-written analysis of this data" and the analysis date.
- If a snapshot has no analysis, the button is disabled and says so.

### 5.7 Header and footer

- The header shows when the data was refreshed. If that is more than three days ago, it also says how many days old the data is.
- The footer carries the source credits and notices from section 6.1, and, when a snapshot has an analysis, the AI notice: "The analysis was written by an AI model (<model name>) from the data on this page. It can be wrong. Not investment advice."

### 5.8 Chart rules

Implementers load the `dataviz` skill before writing any chart code and follow it. In particular:

- One y-axis per chart. No dual axes.
- Line charts get a crosshair that snaps to the nearest date and one tooltip listing every series. Bars and curve markers get their own hover and keyboard-focus tooltip.
- Every value in a tooltip is also reachable without hovering: the readout, the curve table and the odds table.
- A legend appears only where a chart has two or more series.
- Text uses text colours, never a series colour.
- Light and dark themes follow the visitor's system setting. Both palettes are checked with the skill's validator script.
- Labels and values are inserted with `textContent`, never `innerHTML`.
- Dates are written day first ("2 Oct 2026"), on the axes as well.

The two history charts are drawn with uPlot 1.6.32 (MIT licence), copied into `site/vendor/` together with its licence; a test checks the copies against the published checksums. The curve and the odds bars are plain SVG. No other chart library is used, and there is no build step and no npm dependency.

The page's own code is three JavaScript modules: `lib.js` (pure helpers with no page access, tested under Node), `charts.js` (drawing) and `app.js` (the visitor's choices and the events that change them).

### 5.9 Privacy rules

- No cookies, no local storage, no analytics.
- Every file loads from `macros.theta-markets.com`. No CDN, no web fonts; the page uses the system font stack.
- A Content-Security-Policy header enforces this (section 8.2).

## 6. Data

### 6.1 Sources and terms

| Data | Source | Key | Terms | Notice shown on the page |
|---|---|---|---|---|
| Treasury yields, from 1990 | US Treasury, Daily Treasury Par Yield Curve Rates, one CSV per year from `home.treasury.gov` | None | US government work | "Yields: U.S. Department of the Treasury, Daily Treasury Par Yield Curve Rates." |
| EFFR and target range, from 3 July 2000 | New York Fed Markets Data API, `markets.newyorkfed.org/api/rates/unsecured/effr/search.json` | None | Free to copy and distribute with their notice | "The EFFR is subject to the Terms of Use posted at newyorkfed.org. The New York Fed is not responsible for publication of the EFFR by theta-markets.com, does not sanction or endorse any particular republication, and has no liability for your use." |
| FOMC meeting dates | Federal Reserve Board calendar | None | US government work | None needed |
| Fed funds futures prices | Yahoo Finance chart endpoint, symbols such as `ZQV26.CBT` | None | Unofficial endpoint; Yahoo does not allow republishing its data | The page shows only calculated probabilities, never prices. The odds note in 5.4 applies |

Known weakness: the Yahoo endpoint is unofficial and can change or fail. If it does, the refresh stops with a clear message (section 12). The paid CME FedWatch API ($25 a month) is the fallback if this becomes a nuisance.

### 6.2 FOMC calendar

A fixed list in `data/fomc_meetings.json`, taken from the Federal Reserve calendar on 2026-10-03:

- 2026: 27–28 October, 8–9 December.
- 2027: 26–27 January, 16–17 March, 27–28 April, 8–9 June, 27–28 July, 14–15 September, 26–27 October, 7–8 December.
- 2028: 25–26 January.

The statement time is taken as 2:00 p.m. US Eastern on the second day, the Fed's usual release time. The Fed marks future dates as tentative. The refresh command warns when fewer than two future meetings remain on the list.

### 6.3 The data file

The page reads one file, `data.json`, so everything a visitor sees comes from the same snapshot.

| Field | Content |
|---|---|
| `snapshot_id`, `generated_at`, `build_id` | Identity and build time |
| `yields.tenors` | Ordered list of `{label, years}`, short to long |
| `yields.dates` | Every date with data, oldest first |
| `yields.values` | One array per tenor, aligned with `dates`; `null` where that tenor was not published |
| `yields.as_of` | Last date with data |
| `fed_funds.dates`, `.effr`, `.target_lower`, `.target_upper`, `.as_of` | Aligned arrays. Before 16 December 2008, lower and upper are equal |
| `fomc.meetings` | Future meetings as `{end, statement_at}`, with `statement_at` in UTC |
| `odds.meeting`, `.priced_on`, `.current_range` | The meeting the odds refer to, the futures price date used for "now", and the target range in force then, counting any decision the published rate table has not caught up with |
| `odds.columns` | The four comparison dates: now, 1 day, 1 week, 1 month |
| `odds.outcomes` | One entry per target range with a probability for each column, or `null` |
| `odds.summary` | Cut, hold and hike percentages for "now" |
| `analysis` | `{file, model, generated_at}`, or `null` |

Expected size is about 1 MB before compression. Cloudflare compresses it on the way to the visitor.

### 6.4 Rate-odds calculation

Inputs: daily closing prices of the monthly Fed funds futures contracts, the FOMC calendar, the EFFR history and the target range.

Definitions for a calendar month:

- `I` is the month's implied average rate: `100 - price`. For a month that has already ended on the pricing date, `I` is the calendar-day average of EFFR for that month, with days that have no published rate carrying the previous published rate. That is how the contract settles.
- `N` is the number of days in the month. `M` is the day of the month on which the meeting ends. The new rate applies from day `M + 1`.
- A month with no meeting is an **anchor**: its rate is `I` all month.

For each meeting month, find its start and end rate:

1. If the next month is an anchor: `end = I(next)` and `start = (I * N - end * (N - M)) / M`.
2. Otherwise, if the previous month is an anchor: `start = I(previous)` and `end = (I * N - start * M) / (N - M)`.

With the 2026–2027 calendar every meeting month has exactly one anchor neighbour, so one of the two rules always applies. If a future calendar breaks that, the refresh stops and says so.

Then:

- The expected number of 25 bp moves at that meeting is `x = (end - start) / 0.25`.
- With `k = floor(x)` and `f = x - k`, the meeting has probability `1 - f` of `k` moves and `f` of `k + 1` moves. This works for cuts as well, where `x` is negative.
- The move distributions of several meetings are combined by convolution.

Which meeting, and which meetings are counted:

- **Target.** The odds are for the next meeting whose statement is still ahead, the same rule the countdown uses.
- **Base range.** It comes from the latest New York Fed row on or before the pricing date. A row carries the range in force that day, and a decision takes effect the day after the meeting ends. So the row dated on a meeting day still shows the old range, and the table can be a day behind prices.
- **Counted meetings.** Every meeting ending on or after that row's date, up to the target, is counted. Each total number of moves maps to a target range above or below the base range.
- **Decided meetings.** A counted meeting whose outcome the prices already reflect counts as its nearest whole number of moves, with certainty. For a comparison date that is a meeting ending on or before that date. For "now" it is a meeting whose statement time has passed. If the latest prices are older than such a decision, the refresh stops and says to try later. Quotes need time to show an outcome, so the refresh also stops for the first 30 minutes after a statement, and prices that are not within a quarter of a move of a whole number count as "no price yet".
- **Current range.** The base range plus the decided moves. "Hold" is the probability of ending in the current range, "cut" is the sum below it and "hike" is the sum above.
- **Stale table.** If the rate table is more than five days behind the pricing date, the refresh stops.

The method splits each meeting between two neighbouring outcomes. So when a hike is priced, a cut shows 0%, as it does on CME's page.

The four comparison columns use these pricing dates: `Now` is the latest date on which every contract the calculation needs has a price, looking back at most three price days; `1 day` is the price date before it, and `1 week` and `1 month` are the latest price dates on or before 7 days and one calendar month earlier.

**Check values.** These prices were fetched on 2026-10-03 and become test fixtures. CME's figures are from the owner's screenshot of the same day, for the 28 October 2026 meeting.

| Pricing date | Prices used | Our result | CME |
|---|---|---|---|
| 2 Oct 2026 | Oct 96.12, Nov 96.07 | 375–400: 77.9, 400–425: 22.1 | 77.9, 22.1 |
| 25 Sep 2026 | Oct 96.11, Nov 95.965 | 375–400: 35.8, 400–425: 64.2 | 35.8, 64.2 |
| 3 Sep 2026 | August average EFFR 3.63, Sep 96.315, Oct 96.24, Nov 96.18 | 350–375: 38.8, 375–400: 48.7, 400–425: 12.5 | 37.1, 49.7, 13.1 |
| 3 Sep 2026, with Sep at 96.3125 | As above, Sep changed by a quarter tick | 37.2, 49.7, 13.1 | 37.1, 49.7, 13.1 |

The third row shows the expected size of differences: we use the day's closing price, and a quarter tick in one contract moves the result by more than a point. One further fixture covers rule 2, though no CME figure is available to compare: on 2 Oct 2026 with Nov 96.07 and Dec 95.925, the December meeting has `x = 0.8173`.

### 6.5 Analysis

**Facts, computed in code.** Whoever writes the analysis explains the numbers and does not calculate them.

- The full yield curve on five dates: latest, and 1 week, 1 month, 3 months and 1 year earlier. Each resolves to the latest date with data on or before the target date.
- Spreads on each date, in basis points: 10Y minus 2Y, 10Y minus 3M, 30Y minus 5Y.
- Changes from each earlier date to the latest, in basis points, per tenor.
- The current target range, the latest EFFR, and the date and size of the last target change.
- The odds table and summary from section 6.4, the meeting date and the days remaining.

**The analysis file.** The refresh command writes the facts to `work/facts.json`. The analysis arrives as a second file, `work/analysis.json`:

| Field | Content |
|---|---|
| `snapshot_id` | The snapshot the text was written for |
| `model` | The name printed in the AI notice, for example "Claude Opus 5.5" |
| `written_at` | UTC time |
| `curve_now` | What the latest curve says about economic conditions |
| `curve_change` | What the change over the four earlier dates says about the outlook |
| `rate_odds` | What the cut, hold and hike odds say |
| `outlook.bonds`, `outlook.rates`, `outlook.fx`, `outlook.equities` | The likely effect on each |
| `outlook.other` | Optional, for anything else worth noting |

Each text field is plain text of 40 to 160 words.

**Who writes it, for now.** In a Claude Code session, an Opus subagent is given `prompts/analysis.md` and `work/facts.json`, and writes `work/analysis.json`. The prompt file tells the writer to use only the numbers given, to state uncertainty plainly and to write plain text. Keeping the prompt in the project means every analysis follows the same instructions.

**Checks.** `python -m macro analysis` reads the file and stops with the reason if:

- it is not valid JSON;
- a required field is missing;
- a text is outside its length bounds;
- `snapshot_id` differs from the snapshot in `dist/`. This stops an old analysis being published with new data.

When the checks pass, the command writes `dist/analysis.pdf` and records the analysis in `data.json` and the manifest.

**Later.** A model API call can replace the subagent by producing the same file from the same prompt. Nothing else changes.

**PDF.** Built with fpdf2 (on the Mac only), A4 portrait, using a built-in font:

1. Title and snapshot date.
2. "Data used": yields for 3M, 2Y, 5Y, 10Y and 30Y on the five dates, the three spreads, the target range and EFFR, and the odds table.
3. The four analysis sections, the fourth with a sub-heading per asset class.
4. Sources, the odds note, the model name and generation time, and the AI notice from section 5.7.

## 7. The Mac side

### 7.1 Commands

| Command | What it does |
|---|---|
| `python -m macro refresh` | Fetches, calculates, builds `dist/` without an analysis and writes `work/facts.json`. Prints a summary |
| `python -m macro analysis` | Checks `work/analysis.json`, writes the PDF into `dist/` and records it. Details in 6.5 |
| `python -m macro preview` | Serves `dist/` at `http://127.0.0.1:8081/` with the same server code the box runs |
| `python -m macro publish` | Uploads `dist/` as a new release, switches the box to it and verifies. Details in 7.4 |
| `python -m macro rollback` | Switches the box back to the previous release and verifies |
| `scripts/deploy_box.sh` | Installs or updates the server file and unit on the box. Uses sudo. Run only with the owner's go |
| `scripts/box_status.sh` | Read-only: unit state and memory, current release, recent `macro-web` log lines, and the sign-in health check |

### 7.2 Project layout

```
macro/                  Python package, runs on the Mac
  sources/              treasury.py, nyfed.py, futures.py, fomc.py
  fedwatch.py           the odds calculation, pure functions
  odds.py               the odds block of data.json
  facts.py              the numbers given to the analysis writer and printed in the PDF
  snapshot.py           assembles the content of data.json
  analysis.py           checks an analysis file and records it in dist/
  pdf.py                the analysis PDF
  build.py              writes dist/ with its manifest and checksums
  publish.py            upload, switch, verify, prune, rollback
  cli.py
server/serve.py         the web server; standard library only; runs on the box and in preview
site/                   index.html, style.css, app.js, charts.js, lib.js, vendor/ (uPlot)
data/fomc_meetings.json
prompts/analysis.md     instructions for whoever writes the analysis
work/                   facts.json and analysis.json; git-ignored
deploy/                 macro-web.service, macro.env.example
scripts/                deploy_box.sh, box_status.sh
tests/
```

Each module has one job and can be tested alone. The source modules return plain data; `fedwatch.py` and `facts.py` do no input or output.

### 7.3 Python, dependencies and settings

- The Mac side runs in a project `.venv` built from the Mac's python.org Python 3.14 (`/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`). The Homebrew Python 3.12 installed on 2026-10-03 cannot load its XML module on this macOS version, which breaks pip, so it is not used.
- All code is written to run on Python 3.12 as well. Only `server/serve.py` runs on the box, under 3.12.3. Its `--self-test` mode (section 8.2) is run on the box before the service starts, so compatibility is checked on the real interpreter.
- Dependencies, pinned in `requirements.txt`: `httpx` and `fpdf2`. For tests, in `requirements-dev.txt`: `pytest`.
- Settings live in `.env`, which is git-ignored. `.env.example` is committed.

| Setting | Example |
|---|---|
| `BOX_SSH_HOST` | `theta` |
| `PUBLIC_URL` | `https://macros.theta-markets.com` |

There are no secrets in this version. `.gitignore` covers `.env`, `.venv/`, `dist/`, `work/`, `.cache/` and `__pycache__/`.

Treasury data is cached under `.cache/`, one file per year, with an index of the day each file was fetched. A past year comes from the cache only if its file was fetched on or after 8 January of the following year and still parses with rows; the Treasury can post a year's last rows a few days late. The current year is always fetched, and so is a past year last fetched before then. A file with no rows is never cached. It is accepted only for the current year, in the first seven days of January.

### 7.4 Publish

In order, stopping at the first failure:

1. Check `dist/`: the manifest is valid, every checksum matches, and an analysis is present. `--without-analysis` overrides the last check.
2. Ask the box whether the capture is running. If `theta-capture.service` is `active` or `activating`, stop and say to retry in five minutes. This only reads the unit's state.
3. Remove any `<id>.tmp` folder left by an earlier failed upload. Upload `dist/` with `scp` to `/var/lib/macro/releases/<id>.tmp`, verify it there with `sha256sum -c`, then rename it to `<id>`.
4. Switch: create a new symlink beside `current` and rename it over `current`. The rename is atomic.
5. Verify on the box: `http://127.0.0.1:8081/data.json` reports the new snapshot id.
6. Verify from outside: `PUBLIC_URL/data.json` reports the new snapshot id. Before the hostname exists, this step is skipped with a note.
7. Prune: keep the newest five releases.

Steps 3 and 7 only ever remove folders inside `/var/lib/macro/releases/` whose names are a snapshot id, with or without the `.tmp` suffix.

Publishing needs no sudo and no restart. Every remote command is a fixed string; the only variable part is the snapshot id, which is checked against its pattern first.

## 8. The box side

### 8.1 What gets installed

| Path | Owner and mode | Content |
|---|---|---|
| `/opt/macro/serve.py` | root, 644 | The server |
| `/etc/macro/macro.env` | root, 600 | `MACRO_PORT=8081`, `MACRO_SITE_DIR=/var/lib/macro/current`. No secrets |
| `/var/lib/macro/` | ubuntu, 755 | `releases/<id>/` folders and the `current` symlink |
| `/etc/systemd/system/macro-web.service` | root, 644 | The unit below |

Nothing is named `theta-*`. No package is installed and no venv is created: the server uses the system Python and its standard library only.

### 8.2 The server

- Listens on `127.0.0.1:8081` only.
- Serves only the files listed in the current release's manifest. `/` means `index.html`. Anything else is a plain 404. The manifest and checksum files themselves are not served.
- Accepts `GET` and `HEAD` only. Anything else is a 405.
- `/healthz` returns `ok`.
- If there is no current release, every page returns a plain 503.
- Sends `ETag` and answers `If-None-Match` with 304.
- `Cache-Control`: a URL with a `?v=` version gets `public, max-age=31536000, immutable`. Everything else gets `public, max-age=60`. The page requests its scripts, styles and the PDF with `?v=`. The build writes the build id into `index.html` and into the page's own scripts, which import each other the same way, so a new build is never mixed with files cached from an old one.
- Every response carries `X-Robots-Tag: noindex, nofollow`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. `robots.txt` disallows everything.
- HTML responses carry `Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`.
- The PDF is served inline.
- Logs one line per request to the journal: method, path and status. No addresses, no headers, and nothing for a connection that was only closed for being silent.
- Never sends a stack trace or a version string. Connections time out after 15 seconds of silence.
- Picks up a new release on the next request after `current` changes. No restart.
- `serve.py --self-test` starts the server on a free localhost port against a small built-in sample, requests its own pages, checks the rules above and exits 0 or 1. It writes nothing.

### 8.3 The unit

```ini
[Unit]
Description=macro-web - static file server for macros.theta-markets.com
After=network.target

[Service]
Type=simple
DynamicUser=yes
EnvironmentFile=/etc/macro/macro.env
ExecStart=/usr/bin/python3 -I -B -u /opt/macro/serve.py
Restart=on-failure
RestartSec=5

# Caps: never compete with the capture job
MemoryMax=64M
MemoryHigh=48M
MemorySwapMax=0
CPUQuota=10%
TasksMax=32
OOMScoreAdjust=900
Nice=10

# Sandbox
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
ProtectHostname=yes
RestrictNamespaces=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
LockPersonality=yes
MemoryDenyWriteExecute=yes
CapabilityBoundingSet=
SystemCallArchitectures=native
SystemCallFilter=@system-service
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
IPAddressDeny=any
IPAddressAllow=localhost
InaccessiblePaths=-/var/lib/theta -/etc/theta -/opt/theta

[Install]
WantedBy=multi-user.target
```

What this gives:

- **Not `ubuntu`.** `DynamicUser` makes systemd create a throwaway user with no login, no sudo and no files. This departs from the box's convention of running services as `ubuntu`, on purpose: `ubuntu` has passwordless sudo and can read the broker session, the Drive login and copies of the tunnel credentials.
- **Read-only.** The whole filesystem is read-only to the service. `/home`, `/root` and the theta folders are hidden from it.
- **No outbound network.** It can only talk to localhost, which is where `cloudflared` connects from.
- **First to be killed.** Under memory pressure the kernel kills this service before anything else, and its own cap is 64 MB with no swap.

### 8.4 Budget

| Resource | Expected | Cap |
|---|---|---|
| Memory | 15–20 MB | 64 MB, no swap |
| CPU | Near zero | 10% of one core. The box's sustainable total is 20% of one core |
| Disk | About 1.5 MB per release, five kept | 32 GB free |
| Processes | 1, with a thread per connection | 32 tasks |

Measured on 2026-10-03: the box had 501 MB of memory available, averaged 0.2% CPU since boot, and showed about 7 seconds of memory stalls in 32 days.

## 9. Cloudflare

### 9.1 Tunnel

One rule is added to `/etc/cloudflared/config.yml`, above the catch-all:

```yaml
ingress:
  - hostname: auth.theta-markets.com
    service: http://localhost:8080
  - hostname: macros.theta-markets.com
    service: http://localhost:8081
  - service: http_status:404
```

The change follows the owner's procedure, only after an explicit go:

1. Back the file up.
2. Edit it, keeping the catch-all last.
3. Run `cloudflared tunnel ingress validate`, and `cloudflared tunnel ingress rule https://macros.theta-markets.com/` to confirm the new rule matches.
4. Restart `cloudflared` at a quiet time: a weekend, or a weekday after 22:30 or before 09:00 IST, and never while a capture is running.
5. Wait for four "Registered tunnel connection" lines.
6. Confirm sign-in: `curl -s http://127.0.0.1:8080/healthz` returns `{"ok":true}` on the box, and `https://auth.theta-markets.com/healthz` returns a 302 to Access from outside.

### 9.2 DNS

One proxied CNAME for `macros`, pointing at the tunnel. Either the owner adds it in the dashboard, or one command runs on the box: `sudo cloudflared tunnel route dns theta-auth macros.theta-markets.com`. Never with `--overwrite-dns`. The name does not resolve today, so nothing is replaced.

The record is created after the tunnel rule is live. Until it exists, nothing public can reach the page.

### 9.3 Optional, while the page is public

Both rules are scoped to the hostname so they cannot touch `auth` or `app`. The owner creates them in the dashboard.

- **Cache rule.** When hostname equals `macros.theta-markets.com`: eligible for cache, edge TTL from the origin's `Cache-Control`. Repeat requests then stop at Cloudflare's edge for 60 seconds. The page is correct with or without this rule.
- **Rate-limiting rule**, if the one free rule is unused. When hostname equals `macros.theta-markets.com`: more than 40 requests in 10 seconds from one IP is blocked for 10 seconds. A page view makes about 8 requests.

### 9.4 Going private

The owner does this in the Zero Trust dashboard:

1. Delete the cache rule from 9.3.
2. Add a self-hosted Access application for `macros.theta-markets.com`.
3. Add an Allow policy listing each person's email. Only listed emails receive a login code.
4. To admit someone later, add their email to the policy.

Private mode sets a Cloudflare login cookie and records visitors' emails in the Access logs. The privacy page says the site uses no cookies and collects nothing, so it needs a line about this subdomain before the switch.

## 10. Rollout and approval gates

Nothing changes on the box or in Cloudflare without the owner's explicit go for that phase. Every command is shown first.

| Phase | Where | What | Gate |
|---|---|---|---|
| 1 | Mac only | Build, tests, local preview. The owner reviews the page and the PDF locally | This spec and the implementation plan |
| 2 | Box | Create the folders, install the server, run its self-test on the box's own Python, install and start the unit, check it on `127.0.0.1`, publish the first snapshot. Nothing is public yet | Explicit go |
| 3 | Box and Cloudflare | Tunnel rule and restart, then the DNS record, then a check from outside | Explicit go, in a quiet window |
| 4 | Cloudflare | Optional rules from 9.3 | Owner's choice |
| 5 | Cloudflare | Going private, from 9.4 | Owner's choice, later |

Rules for every box step:

- Not at 15:45, 18:00, 20:00 or 22:00 IST, and not on a Tuesday.
- First confirm the capture is not running.
- Afterwards confirm the sign-in health check still passes.

## 11. Rollback

| Layer | How | Effect |
|---|---|---|
| Data | `python -m macro rollback` | The previous snapshot is live within seconds. No sudo, no restart |
| Service | `sudo systemctl disable --now macro-web`, then remove the four paths in 8.1 | The box is as it was before Phase 2 |
| Tunnel | Restore the backup config, validate, restart in a quiet window, then repeat the checks in 9.1 | The tunnel serves only `auth` again |
| DNS | Delete the `macros` record | The hostname stops resolving |
| Cloudflare rules | Delete them | No effect on other hostnames |

## 12. When things fail

| Failure | Behaviour |
|---|---|
| Any data source fails or returns something unexpected during refresh | Refresh stops with a clear message. `dist/` is not replaced. The live page keeps its last snapshot |
| A value is outside sane bounds: a yield, a rate or a futures price | Treated as a source failure, as above |
| Anything else goes wrong during refresh | One line naming the error. `refresh --debug` shows the full error |
| The analysis file is missing or fails its checks | The analysis command stops and says why. The snapshot has no analysis, so publish refuses unless `--without-analysis` is given. The page then shows the button disabled |
| The upload fails partway | `current` has not switched, so the old release stays live. The leftover `.tmp` folder is removed on the next publish |
| `macro-web` crashes | systemd restarts it after 5 seconds. After five crashes in 10 seconds it stays stopped and visitors see a Cloudflare error page |
| The box or tunnel is down | Visitors see a Cloudflare error page |
| The data is old | The header says how many days old it is |

## 13. Testing

Tests never touch a real service: no real network, no SSH, no box, no Cloudflare, no model.

- **Sources.** Each parser runs on saved sample files in `tests/fixtures/`. HTTP goes through `httpx.MockTransport`.
- **Network guard.** A test fixture refuses any connection that is not to localhost, so a forgotten mock fails loudly.
- **Odds.** The check values in section 6.4, plus cuts, moves larger than 25 bp and a missing contract.
- **Facts.** Date resolution across weekends and holidays, spreads, and changes.
- **Analysis.** Sample files: a good one, invalid JSON, a missing field, an over-long text and a wrong snapshot id.
- **PDF.** The output starts with `%PDF`, has at least one page and contains the section headings.
- **Build.** The manifest lists every file with the right checksum. The build id is written into the page and its own scripts, and into nothing under `vendor/`.
- **Server.** Started on a free localhost port: the allowlist, 404 and 405, headers, `ETag`, and picking up a switched release.
- **Publish and rollback.** A fake command runner records the commands; the tests check their order and that a failure stops the sequence before the switch.
- **Page logic.** The pure JavaScript helpers (nearest date, range clipping, tenor lookup, and point positions in both curve modes) run under Node's built-in test runner, with no npm packages. The Python suite runs them too, and skips them with a message where Node is not installed.
- **Page files.** Static checks: every element the script looks up is on the page, nothing in the page would be blocked by the content security policy, every address the page asks for is local and carries the build id, every colour role exists in both themes, and the vendored library matches its published checksums.

Before Phase 2, the page is also checked by eye in the local preview, in light and dark themes and at phone width.

## 14. Risks

| Risk | Mitigation |
|---|---|
| The tunnel restart disturbs sign-in | Validated config, a backup, a quiet window, and the checks in 9.1. Rollback is one restore and one restart |
| Public traffic shares the tunnel with sign-in | The server is capped and cheap to serve from. The optional rules in 9.3 keep repeat traffic at the edge. Going private ends anonymous traffic |
| The Yahoo price feed changes | Refresh fails loudly; the live page is unaffected. The CME API is the paid fallback |
| Odds differ from CME by a point or so | Stated on the page as our own calculation. The check values document the expected gap |
| The analysis is wrong or misleading | Numbers are computed in code, the owner reads the PDF in preview before publishing, and the page and PDF carry the AI notice |
| A box command goes wrong | Every command is shown first, phases are gated, and the capture's state is checked before each step |

## 15. What needs the owner

- Approve this spec.
- Ask for an analysis in a Claude Code session whenever a refresh should carry one, and read the PDF in the preview before publishing.
- Give the go for Phases 2 and 3.
- Create the DNS record or approve the one command (9.2), and the optional rules (9.3).
- Add the privacy-page line and the Access application when going private (9.4).
- Make every git commit.
