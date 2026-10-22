"""Load daily pageviews from the Wikimedia API, cache them, and clean them for modelling."""

from __future__ import annotations

import numpy as np
import pandas as pd

from kpi_forecast.config import HISTORY_START, PUBLISHERS, RAW_DATA, USER_AGENT

API = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/"
    "{project}/all-access/user/daily/{start}/{end}"
)


def fetch_publisher(project: str, start: str, end: str) -> pd.DataFrame:
    """Fetch daily user pageviews for one project between two dates (inclusive)."""
    import requests

    url = API.format(
        project=project,
        start=pd.Timestamp(start).strftime("%Y%m%d"),
        end=pd.Timestamp(end).strftime("%Y%m%d"),
    )
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    response.raise_for_status()
    items = response.json()["items"]
    return pd.DataFrame(
        {
            "date": pd.to_datetime([item["timestamp"][:8] for item in items], format="%Y%m%d"),
            "publisher": PUBLISHERS[project],
            "views": [item["views"] for item in items],
        }
    )


def load_daily(end: str, refresh: bool = False) -> pd.DataFrame:
    """Return raw daily pageviews up to `end`, using the cached CSV when it already covers it."""
    end_ts = pd.Timestamp(end)
    if RAW_DATA.exists() and not refresh:
        cached = pd.read_csv(RAW_DATA, parse_dates=["date"])
        if cached["date"].max() >= end_ts:
            return cached[cached["date"] <= end_ts].reset_index(drop=True)

    frames = [fetch_publisher(project, HISTORY_START, end) for project in PUBLISHERS]
    daily = pd.concat(frames, ignore_index=True).sort_values(["publisher", "date"])
    RAW_DATA.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(RAW_DATA, index=False)
    return daily.reset_index(drop=True)


def clean_daily(daily: pd.DataFrame, spike_z: float = 6.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fill missing days and cap one-day spikes before modelling.

    Spikes are found with a robust z-score: how far a day sits from the median of the
    surrounding fortnight, measured in units of that window's median absolute deviation
    (on the log scale, so the rule works the same for large and small publishers).
    Flagged days are replaced by the rolling median and written to a quality log, so
    nothing is changed silently.

    Returns (clean daily frame, quality log).
    """
    cleaned, log_rows = [], []
    for publisher, group in daily.groupby("publisher"):
        series = group.set_index("date")["views"].astype(float).sort_index()
        full_index = pd.date_range(series.index.min(), series.index.max(), freq="D")
        missing = full_index.difference(series.index)
        series = series.reindex(full_index)

        log_values = np.log(series)
        log_values = log_values.interpolate(limit_direction="both")
        for day in missing:
            log_rows.append({"publisher": publisher, "date": day, "issue": "missing day", "action": "interpolated"})

        median = log_values.rolling(15, center=True, min_periods=7).median()
        mad = (log_values - median).abs().rolling(15, center=True, min_periods=7).median()
        robust_z = (log_values - median) / (1.4826 * mad.replace(0, np.nan))
        spikes = robust_z.abs() > spike_z
        for day in robust_z.index[spikes.fillna(False)]:
            log_rows.append(
                {
                    "publisher": publisher,
                    "date": day,
                    "issue": f"spike (robust z = {robust_z[day]:.1f})",
                    "action": "capped to rolling median",
                }
            )
        log_values = log_values.where(~spikes.fillna(False), median)

        cleaned.append(
            pd.DataFrame({"date": full_index, "publisher": publisher, "views": np.exp(log_values).round()})
        )

    quality_log = pd.DataFrame(log_rows, columns=["publisher", "date", "issue", "action"])
    return pd.concat(cleaned, ignore_index=True), quality_log
