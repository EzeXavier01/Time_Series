"""Replay past months to measure forecast accuracy and how often the alerts were right.

For each past month and each check-in day (for example the 7th, 14th and 21st), the
model only sees data up to that day, forecasts the rest of the month, and the
projection is compared with what actually happened.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from kpi_forecast.alerts import AT_RISK, MISS_LIKELY, classify, project_month


def past_months(last_complete_month_end: pd.Timestamp, n_months: int) -> list[pd.Timestamp]:
    first = (last_complete_month_end.replace(day=1) - pd.DateOffset(months=n_months - 1)).normalize()
    return list(pd.date_range(first, periods=n_months, freq="MS"))


def run_backtest(
    daily: pd.DataFrame,
    models: dict,
    months: list[pd.Timestamp],
    check_days: tuple[int, ...],
) -> pd.DataFrame:
    """Forecast the rest of each past month from each check day. Targets are attached separately,
    so changing the target rule never requires refitting the models."""
    rows = []
    for publisher, group in daily.groupby("publisher"):
        series = group.set_index("date")["views"].sort_index()
        for month_start in months:
            month_end = month_start + pd.offsets.MonthEnd(0)
            if month_end > series.index.max():
                continue
            actual_total = float(series[month_start:month_end].sum())
            for day in check_days:
                as_of = month_start + pd.Timedelta(days=day - 1)
                if as_of >= month_end:
                    continue
                horizon = (month_end - as_of).days
                mtd = float(series[month_start:as_of].sum())
                actual_future = series[as_of + pd.Timedelta(days=1) : month_end]
                for name, model in models.items():
                    forecast = model(series[:as_of], horizon)
                    rows.append(
                        {
                            "publisher": publisher,
                            "month": month_start,
                            "check_day": day,
                            "model": name,
                            "mtd": mtd,
                            "actual_remaining": float(actual_future.sum()),
                            "forecast_remaining": float(forecast.sum()),
                            "actual_total": actual_total,
                            "daily_ape": float(np.mean(np.abs(forecast.to_numpy() / actual_future.to_numpy() - 1))),
                        }
                    )
    results = pd.DataFrame(rows)
    results["rel_error"] = results["forecast_remaining"] / results["actual_remaining"] - 1
    return results


def attach_targets(backtest: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """Add each publisher-month's target to the backtest rows."""
    merged = backtest.drop(columns=["target"], errors="ignore").merge(
        targets[["publisher", "month", "target"]], on=["publisher", "month"], how="left"
    )
    return merged


def accuracy_table(backtest: pd.DataFrame) -> pd.DataFrame:
    """Mean absolute % error of the rest-of-month total, and of individual days."""
    table = (
        backtest.assign(abs_error=backtest["rel_error"].abs())
        .groupby(["model", "check_day"])
        .agg(remaining_total_mape=("abs_error", "mean"), daily_mape=("daily_ape", "mean"), n=("abs_error", "size"))
        .reset_index()
    )
    return table


def error_bounds(errors: pd.Series, coverage: float = 0.9) -> tuple[float, float]:
    tail = (1 - coverage) / 2
    return float(errors.quantile(tail)), float(errors.quantile(1 - tail))


def evaluate_alerts(backtest: pd.DataFrame, model: str, coverage: float = 0.9) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score the alerts the system would have raised in each past month.

    The error range for a month is built only from the *other* months
    (leave-one-month-out), so a month never helps calibrate its own alert.

    Returns (row-level alerts with outcomes, summary by check day).
    """
    runs = backtest[(backtest["model"] == model) & backtest["target"].notna()].copy()
    statuses, lows, highs, inside = [], [], [], []
    for _, row in runs.iterrows():
        others = runs[(runs["check_day"] == row["check_day"]) & (runs["month"] != row["month"])]
        err_low, err_high = error_bounds(others["rel_error"], coverage)
        projected, low, high = project_month(row["mtd"], row["forecast_remaining"], err_low, err_high)
        statuses.append(classify(projected, low, high, row["target"]))
        lows.append(low)
        highs.append(high)
        inside.append(low <= row["actual_total"] <= high)
    runs["status"] = statuses
    runs["projected_low"] = lows
    runs["projected_high"] = highs
    runs["actual_in_range"] = inside
    runs["predicted_miss"] = runs["status"].isin([MISS_LIKELY, AT_RISK])
    runs["actual_miss"] = runs["actual_total"] < runs["target"]

    def summarise(group: pd.DataFrame) -> pd.Series:
        tp = (group["predicted_miss"] & group["actual_miss"]).sum()
        fp = (group["predicted_miss"] & ~group["actual_miss"]).sum()
        fn = (~group["predicted_miss"] & group["actual_miss"]).sum()
        strict = group["status"] == MISS_LIKELY
        return pd.Series(
            {
                "publisher_months": len(group),
                "actual_misses": int(group["actual_miss"].sum()),
                "alert_precision": tp / (tp + fp) if tp + fp else np.nan,
                "alert_recall": tp / (tp + fn) if tp + fn else np.nan,
                "status_accuracy": (group["predicted_miss"] == group["actual_miss"]).mean(),
                "miss_likely_precision": (group.loc[strict, "actual_miss"]).mean() if strict.any() else np.nan,
                "range_coverage": group["actual_in_range"].mean(),
            }
        )

    summary = runs.groupby("check_day").apply(summarise, include_groups=False).reset_index()
    return runs, summary
