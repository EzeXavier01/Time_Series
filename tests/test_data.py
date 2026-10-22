import numpy as np
import pandas as pd

from kpi_forecast.data import clean_daily


def test_clean_fills_missing_days_and_caps_spikes():
    dates = pd.date_range("2026-01-01", periods=60, freq="D")
    rng = np.random.default_rng(0)
    views = 1_000_000 * (1 + rng.normal(0, 0.02, len(dates)))
    daily = pd.DataFrame({"date": dates, "publisher": "A", "views": views})
    daily.loc[30, "views"] = 20_000_000  # a one-day bot spike
    daily = daily.drop(index=[10, 11])  # two days never arrived

    cleaned, log = clean_daily(daily)

    assert len(cleaned) == 60
    assert cleaned["views"].max() < 1_200_000
    assert (log["action"] == "interpolated").sum() == 2
    spike_rows = log[log["issue"].str.startswith("spike")]
    assert list(spike_rows["date"]) == [pd.Timestamp("2026-01-31")]


def test_clean_leaves_normal_weekly_pattern_alone():
    dates = pd.date_range("2026-01-01", periods=84, freq="D")
    weekly = np.tile([1.0, 1.1, 1.2, 1.1, 1.0, 0.7, 0.6], 12)
    daily = pd.DataFrame({"date": dates, "publisher": "A", "views": 1_000_000 * weekly})
    cleaned, log = clean_daily(daily)
    assert log.empty
    np.testing.assert_allclose(cleaned["views"].to_numpy(), daily["views"].round().to_numpy())
