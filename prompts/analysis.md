# Writing the macro analysis

You are writing a short analysis of one snapshot of US interest-rate data. It is printed as a PDF next to the numbers it was written from, and read by a few people who follow markets but are not bond specialists.

## What you are given

One file, `work/facts.json`. Every number in it was computed in code and is correct. Read all of it before you write.

| Field | What it holds |
|---|---|
| `snapshot_id` | The snapshot these facts belong to. Copy it into your output unchanged |
| `as_of` | The date of the latest yields |
| `curves` | The Treasury par yield curve, in percent, on five dates: the latest, and one week, one month, three months and one year earlier |
| `spreads_bp` | On each of those dates, in basis points: 10Y minus 2Y, 10Y minus 3M, and 30Y minus 5Y |
| `changes_bp` | The change from each earlier date to the latest, for each tenor, in basis points |
| `fed_funds` | The target range, the effective federal funds rate (EFFR) and its date, and the last change in the range |
| `odds` | The chance, in percent, of each target range after the next FOMC decision, as priced now and one day, one week and one month earlier. `current_range` is the range in force now. `summary` adds the "now" column up into cut, hold and hike, and describes that column only. These are the project's own calculation from fed funds futures prices |
| `next_meeting` | The date of that decision and how many days away it is |

## What to write

Write one JSON object to `work/analysis.json` with exactly these fields and no others:

| Field | Content |
|---|---|
| `snapshot_id` | Copied from `work/facts.json` |
| `model` | Your model's name as it should be printed, for example `Claude Opus 5.5` |
| `written_at` | The time you finish, in UTC, in the form `2026-10-04T01:30:00Z`. In a terminal, `date -u +%Y-%m-%dT%H:%M:%SZ` prints it |
| `curve_now` | What the latest curve says about economic conditions |
| `curve_change` | What the change over the four earlier dates says about the outlook |
| `rate_odds` | What the cut, hold and hike odds say, and how they have moved |
| `outlook.bonds` | The likely effect on bonds |
| `outlook.rates` | The likely effect on short-term interest rates and money markets |
| `outlook.fx` | The likely effect on the dollar |
| `outlook.equities` | The likely effect on shares |
| `outlook.other` | Optional. Anything else worth noting. Leave the field out if there is nothing |

`outlook` is an object holding the `bonds`, `rates`, `fx`, `equities` and optional `other` texts.

## Rules

1. **Use only the numbers in the facts file.** Do not bring in anything from outside it: no news, no data releases, no events, no levels of other markets, no dates of things that happened. You do not know them, and a reader cannot check them.
2. **Keep every number's value and unit**: percent for yields and odds, basis points for spreads and changes. Write yields and rates with two decimals (4.00%), odds with one (27.0%), and dates in words (28 October 2026). You may compare two given numbers ("higher than", "about twice"). Do not work out new figures.
3. **Read the earlier odds against the range in force then.** An earlier column gives the chance of each target range as priced on that column's date, and the range in force may have been different on that date. `fed_funds.last_change` gives the day the present range took effect and the range before it. For an earlier column, name the target range. Call it a cut, a hold or a rise only once you have checked which range was in force on that date.
4. **Say what the data cannot show.** The facts hold no exchange rates and no share prices. In `outlook.fx` and `outlook.equities`, say so, and reason only from the direction of rates.
5. **State uncertainty plainly.** These are readings of market prices, not forecasts. Say "suggests" or "is consistent with" where that is the truth. Never tell the reader to buy or sell anything.
6. **Plain text only.** Each text is one paragraph. No Markdown, no lists, no headings and no line breaks. The characters `*`, `` ` ``, `#`, `<`, `>` and `|` are rejected.
7. **Each text is 40 to 160 words.** Aim for 80 to 120.
8. **Write plainly.** Short sentences and common words. Explain a term the first time you use it if a general reader might not know it. Do not repeat the same point in two sections.

## How it is checked

`python -m macro analysis` reads your file. It stops and names the problem if the file is not valid JSON, a field is missing or unknown, a text is too short, too long or not plain text, or `snapshot_id` does not match the snapshot in `dist/`. Fix the file and run the command again.
