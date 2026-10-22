import pandas as pd
import pytest

from kpi_forecast.alerts import AT_RISK, MISS_LIKELY, ON_TRACK, build_alerts, classify, project_month
from kpi_forecast.models import seasonal_naive


@pytest.mark.parametrize(
    ("projected", "low", "high", "target", "expected"),
    [
        (90, 85, 95, 100, MISS_LIKELY),  # even the optimistic end misses
        (95, 90, 105, 100, AT_RISK),  # central view misses, target still reachable
        (100, 95, 105, 100, ON_TRACK),  # exactly on target counts as on track
        (120, 110, 130, 100, ON_TRACK),
    ],
)
def test_classify(projected, low, high, target, expected):
    assert classify(projected, low, high, target) == expected


def test_project_month_range_orientation():
    # Past forecasts ran between 10% under and 25% over the actual.
    projected, low, high = project_month(mtd=500, forecast_remaining=500, error_low=-0.10, error_high=0.25)
    assert projected == 1000
    assert low == pytest.approx(500 + 500 / 1.25)  # we over-forecast -> actual lower
    assert high == pytest.approx(500 + 500 / 0.90)  # we under-forecast -> actual higher
    assert low < projected < high


def _daily(level: float, publisher: str = "A") -> pd.DataFrame:
    dates = pd.date_range("2026-08-01", "2026-09-30", freq="D")
    return pd.DataFrame({"date": dates, "publisher": publisher, "views": level})


def test_build_alerts_flags_publisher_below_target():
    daily = pd.concat([_daily(100.0, "A"), _daily(100.0, "B")])
    targets = pd.DataFrame(
        {
            "publisher": ["A", "B"],
            "month": pd.to_datetime(["2026-09-01", "2026-09-01"]),
            "target": [3000.0 * 1.5, 3000.0 * 0.8],  # A needs 50% more than its run-rate, B is comfortably ahead
        }
    )
    alerts = build_alerts(daily, targets, pd.Timestamp("2026-09-15"), seasonal_naive, -0.05, 0.05)
    status = dict(zip(alerts["publisher"], alerts["status"], strict=True))
    assert status == {"A": MISS_LIKELY, "B": ON_TRACK}
    row_a = alerts.set_index("publisher").loc["A"]
    assert row_a["mtd_actual"] == 1500  # 15 days x 100
    assert row_a["projected"] == 3000
    assert row_a["days_left"] == 15
    assert row_a["uplift_needed"] == pytest.approx(1.0)  # needs 200/day vs 100 forecast
