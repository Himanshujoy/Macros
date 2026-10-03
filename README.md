# Macros

A one-page view of US macro data, served at `https://macros.theta-markets.com/`.

- **Treasury yields:** two linked charts, yield history for one tenor and the yield curve on one date.
- **Rate odds:** the chance of a cut, hold or hike at the next FOMC meeting, with a countdown.
- **Fed funds rate:** the effective rate with its target range.
- **Explain Macros:** a button that opens an AI-written analysis as a PDF.

## Status

As of 2026-10-04 the data pipeline and the web server work: `python -m macro refresh` builds `dist/`, and `python -m macro preview` serves it locally. The page is still a placeholder that prints one line of data. The charts, the analysis PDF and publishing are not built yet. Progress follows the plans in [docs/superpowers/plans/](docs/superpowers/plans/).

## How it works

- **The Mac builds.** One command fetches the data, calculates the rate odds and builds the page into `dist/`.
- **The server only serves.** The finished files are uploaded to a small server, which serves them as static files behind a Cloudflare Tunnel. It fetches nothing and holds no secrets.
- **Refresh is manual.** The data changes only when the refresh command is run.

The full design, including the server setup and the rollout steps, is in the [design spec](docs/superpowers/specs/2026-10-04-macros-page-design.md).

## Quick start

Needs Python 3.12 or newer.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

The tests never touch a real service. A guard fails any test that opens a network connection outside localhost.

## Commands

Each command arrives with the plan that builds it. Run them with the project's interpreter, for example `.venv/bin/python -m macro refresh`.

| Command | What it does | Status |
|---|---|---|
| `python -m macro refresh` | Fetches the data, calculates, and builds `dist/`. Add `--debug` to see a full error | Works |
| `python -m macro preview` | Serves `dist/` at `http://127.0.0.1:8081/` with the server the box will run. `--port` picks another port | Works, with a placeholder page |
| `python -m macro analysis` | Turns an analysis file into the PDF | Plan 3 |
| `python -m macro publish` | Uploads `dist/` to the server and switches to it | Plan 4 |
| `python -m macro rollback` | Switches the server back to the previous snapshot | Plan 4 |

The first refresh downloads one Treasury file per year since 1990, so it takes about half a minute. Later runs fetch only the current year.

## Data sources

| Data | Source |
|---|---|
| Treasury yields, from 1990 | US Treasury, Daily Treasury Par Yield Curve Rates |
| Fed funds rate and target range, from July 2000 | New York Fed Markets Data API |
| FOMC meeting dates | Federal Reserve calendar, kept in `data/fomc_meetings.json` |
| Rate odds | Own calculation from Fed funds futures prices, with the method CME publishes for FedWatch |

Terms and required notices for each source are in section 6.1 of the design spec.

## Working rules

- The owner makes every git commit.
- Nothing changes on the server or in Cloudflare without the owner's explicit go.
- The page uses no cookies, trackers or third-party requests.
