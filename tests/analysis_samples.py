"""A facts file and an analysis file in the shapes the real ones have, for the analysis and PDF tests."""

SNAPSHOT_ID = "20261003T181500Z"
TEXT = " ".join(["word"] * 60)

LABELS = ["latest", "1 week earlier", "1 month earlier", "3 months earlier", "1 year earlier"]
DATES = ["2026-10-02", "2026-09-25", "2026-09-02", "2026-07-02", "2025-10-02"]
YIELDS = {
    "3M": [4.19, 4.24, 3.92, 3.82, 4.02],
    "2Y": [4.83, 4.81, 4.39, 4.14, 3.55],
    "5Y": [5.06, 4.98, 4.54, 4.23, 3.67],
    "10Y": [5.28, 5.17, 4.79, 4.49, 4.10],
    "30Y": [5.63, 5.49, 5.27, 4.98, 4.69],
}


def facts() -> dict:
    """A fresh copy each time, so a test may change it."""
    curves = [
        {"label": label, "date": day, "yields": {tenor: values[index] for tenor, values in YIELDS.items()}}
        for index, (label, day) in enumerate(zip(LABELS, DATES))
    ]
    spreads = [
        {"label": label, "date": day, "10Y-2Y": 45 - index, "10Y-3M": 109 - index, "30Y-5Y": 57 + index}
        for index, (label, day) in enumerate(zip(LABELS, DATES))
    ]
    return {
        "snapshot_id": SNAPSHOT_ID,
        "as_of": "2026-10-02",
        "curves": curves,
        "spreads_bp": spreads,
        "changes_bp": [],
        "fed_funds": {
            "target_lower": 3.75,
            "target_upper": 4.0,
            "effr": 3.88,
            "effr_date": "2026-10-01",
            "last_change": {"effective": "2026-09-17", "from": [3.5, 3.75], "to": [3.75, 4.0], "change_bp": 25},
        },
        "odds": {
            "meeting": "2026-10-28",
            "priced_on": "2026-10-02",
            "current_range": [3.75, 4.0],
            "columns": [
                {"key": "now", "date": "2026-10-02"},
                {"key": "d1", "date": "2026-10-01"},
                {"key": "w1", "date": "2026-09-25"},
                {"key": "m1", "date": "2026-09-02"},
            ],
            "outcomes": [
                {"range": [3.5, 3.75], "now": 0.0, "d1": 0.0, "w1": 0.0, "m1": 27.0},
                {"range": [3.75, 4.0], "now": 77.9, "d1": 75.6, "w1": 35.8, "m1": 55.2},
                {"range": [4.0, 4.25], "now": 22.1, "d1": 24.4, "w1": 64.2, "m1": 17.9},
            ],
            "summary": {"cut": 0.0, "hold": 77.9, "hike": 22.1},
        },
        "next_meeting": {"date": "2026-10-28", "days_away": 25},
    }


def written(**changes) -> dict:
    """The content of a good analysis file, with any top-level fields replaced."""
    content = {
        "snapshot_id": SNAPSHOT_ID,
        "model": "Claude Opus 5.5",
        "written_at": "2026-10-03T19:00:00Z",
        "curve_now": TEXT,
        "curve_change": TEXT,
        "rate_odds": TEXT,
        "outlook": {"bonds": TEXT, "rates": TEXT, "fx": TEXT, "equities": TEXT},
    }
    content.update(changes)
    return content
