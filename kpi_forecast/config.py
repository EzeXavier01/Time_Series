"""Project settings: which publishers we track, where data lives, and the model defaults."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DATA = ROOT / "data" / "raw" / "daily_pageviews.csv"
SQL_DIR = ROOT / "sql"
REPORTS_DIR = ROOT / "reports"

# Each Wikipedia language edition stands in for one "enterprise publisher".
# The KPI is daily user pageviews (bots and spiders excluded by Wikimedia).
PUBLISHERS = {
    "en.wikipedia.org": "English",
    "de.wikipedia.org": "German",
    "ja.wikipedia.org": "Japanese",
    "fr.wikipedia.org": "French",
    "es.wikipedia.org": "Spanish",
    "it.wikipedia.org": "Italian",
    "pt.wikipedia.org": "Portuguese",
    "nl.wikipedia.org": "Dutch",
    "pl.wikipedia.org": "Polish",
    "ar.wikipedia.org": "Arabic",
}

HISTORY_START = "2022-01-01"

# Wikimedia asks API clients to identify themselves.
USER_AGENT = "KPI_Forecast_Alerts/1.0 (https://github.com/EzeXavier01/Time_Series)"

# Monthly target = same month last year x (1 + trailing 3-month YoY trend + TARGET_STRETCH).
# 0.0 means "keep your recent trajectory"; 0.02 would ask for two points better than trend.
TARGET_STRETCH = 0.0

# ETS is fitted on this many most recent days (two years keeps yearly patterns in view
# without letting old regimes dominate).
TRAINING_DAYS = 730

# Days of the month on which the backtest re-runs the month-end projection.
BACKTEST_DAYS = (7, 14, 21)
BACKTEST_MONTHS = 12
