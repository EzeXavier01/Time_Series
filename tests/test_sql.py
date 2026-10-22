import pandas as pd
import pytest

from kpi_forecast.sql import monthly_kpis, monthly_targets


def steady(start: str, end: str, views: float, publisher: str = "A") -> pd.DataFrame:
    return pd.DataFrame({"date": pd.date_range(start, end), "publisher": publisher, "views": views})


def make_daily() -> pd.DataFrame:
    # Publisher A runs at 100/day through 2025 and 90/day in 2026: a steady -10% YoY trend.
    # Publisher B is missing the second half of April 2025, so April 2026 has no fair target.
    a = pd.concat([steady("2025-01-01", "2025-12-31", 100), steady("2026-01-01", "2026-04-10", 90)])
    b = pd.concat(
        [
            steady("2025-01-01", "2025-04-15", 100, "B"),
            steady("2025-05-01", "2025-12-31", 100, "B"),
            steady("2026-01-01", "2026-04-10", 90, "B"),
        ]
    )
    return pd.concat([a, b], ignore_index=True)


def test_target_follows_trailing_trend_plus_stretch():
    targets = monthly_targets(make_daily(), stretch=0.02).set_index(["publisher", "month"])
    april = targets.loc[("A", pd.Timestamp("2026-04-01"))]
    assert april["trailing_yoy"] == pytest.approx(-0.10)
    assert april["target"] == pytest.approx(30 * 100 * (1 - 0.10 + 0.02))


def test_no_target_without_three_months_of_trend():
    targets = monthly_targets(make_daily(), stretch=0.0)
    # March 2026 only has Jan and Feb as complete trend months.
    assert targets[(targets["publisher"] == "A") & (targets["month"] == "2026-03-01")].empty


def test_no_target_when_last_years_month_is_incomplete():
    targets = monthly_targets(make_daily(), stretch=0.0)
    assert targets[(targets["publisher"] == "B") & (targets["month"] == "2026-04-01")].empty


def test_monthly_kpis_mark_partial_months_and_yoy():
    kpis = monthly_kpis(make_daily()).set_index(["publisher", "month"])
    april = kpis.loc[("A", pd.Timestamp("2026-04-01"))]
    assert not april["is_complete"]
    assert april["views"] == 900
    jan = kpis.loc[("A", pd.Timestamp("2026-01-01"))]
    assert jan["is_complete"]
    assert jan["yoy_change"] == pytest.approx(-0.10)
