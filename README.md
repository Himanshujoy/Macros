# Macros

A one-page view of US macro data, served at `https://macros.theta-markets.com/`.

- **Treasury yields:** two linked charts, yield history for one tenor and the yield curve on one date.
- **Rate odds:** the chance of a cut, hold or hike at the next FOMC meeting, with a countdown.
- **Fed funds rate:** the effective rate with its target range.
- **Explain Macros:** a button that opens an AI-written analysis as a PDF.

## Status

As of 2026-10-04 the project is being built. Only the project setup exists, and none of the commands below works yet. Progress follows the plans in [docs/superpowers/plans/](docs/superpowers/plans/).

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

Each command arrives with the plan that builds it.

| Command | What it does | Plan |
|---|---|---|
| `python -m macro refresh` | Fetches the data, calculates, and builds `dist/` | 1 |
| `python -m macro preview` | Serves `dist/` locally | 2 |
| `python -m macro analysis` | Turns an analysis file into the PDF | 3 |
| `python -m macro publish` | Uploads `dist/` to the server and switches to it | 4 |
| `python -m macro rollback` | Switches the server back to the previous snapshot | 4 |

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
