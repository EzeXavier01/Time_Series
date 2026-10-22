"""Project each publisher's month-end total and flag the ones likely to miss target."""

from __future__ import annotations

import pandas as pd

MISS_LIKELY, AT_RISK, ON_TRACK = "MISS LIKELY", "AT RISK", "ON TRACK"
STATUS_ORDER = [MISS_LIKELY, AT_RISK, ON_TRACK]


def classify(projected: float, low: float, high: float, target: float) -> str:
    """MISS LIKELY: even the optimistic end of the range is below target.
    AT RISK: the central projection is below target, but hitting it is still plausible.
    ON TRACK: the central projection meets or beats target.
    """
    if high < target:
        return MISS_LIKELY
    if projected < target:
        return AT_RISK
    return ON_TRACK


def project_month(mtd: float, forecast_remaining: float, error_low: float, error_high: float) -> tuple[float, float, float]:
    """Month-end projection with a range taken from past forecast errors.

    Errors are measured in the backtest as forecast / actual - 1, so the actual
    remaining total implied by an error e is forecast / (1 + e). A large positive
    error (we over-forecast) gives the low end of the range.
    """
    projected = mtd + forecast_remaining
    low = mtd + forecast_remaining / (1 + error_high)
    high = mtd + forecast_remaining / (1 + error_low)
    return projected, low, high


def month_bounds(as_of: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = as_of.replace(day=1)
    return start, start + pd.offsets.MonthEnd(0)


def snapshot(series: pd.Series, as_of: pd.Timestamp, model) -> tuple[float, pd.Series]:
    """Month-to-date actual through `as_of`, plus the model's forecast for the rest of the month."""
    start, end = month_bounds(as_of)
    mtd = float(series[start:as_of].sum())
    horizon = (end - as_of).days
    forecast = model(series[:as_of], horizon) if horizon > 0 else pd.Series(dtype=float)
    return mtd, forecast


def build_alerts(
    daily: pd.DataFrame,
    targets: pd.DataFrame,
    as_of: pd.Timestamp,
    model,
    error_low: float,
    error_high: float,
) -> pd.DataFrame:
    """One row per publisher for the month containing `as_of`."""
    month_start, month_end = month_bounds(as_of)
    rows = []
    for publisher, group in daily.groupby("publisher"):
        series = group.set_index("date")["views"].sort_index()
        target_row = targets[(targets["publisher"] == publisher) & (targets["month"] == month_start)]
        if target_row.empty:
            continue
        target = float(target_row["target"].iloc[0])

        mtd, forecast = snapshot(series, as_of, model)
        projected, low, high = project_month(mtd, float(forecast.sum()), error_low, error_high)
        days_left = len(forecast)
        required_daily = (target - mtd) / days_left if days_left else float("nan")
        forecast_daily = float(forecast.mean()) if days_left else float("nan")

        rows.append(
            {
                "publisher": publisher,
                "month": month_start.date(),
                "as_of": as_of.date(),
                "target": round(target),
                "mtd_actual": round(mtd),
                "projected": round(projected),
                "projected_low": round(low),
                "projected_high": round(high),
                "attainment": round(projected / target, 4),
                "attainment_low": round(low / target, 4),
                "attainment_high": round(high / target, 4),
                "days_left": days_left,
                "required_daily": round(required_daily),
                "forecast_daily": round(forecast_daily),
                "uplift_needed": round(required_daily / forecast_daily - 1, 4) if days_left else float("nan"),
                "status": classify(projected, low, high, target),
            }
        )
    alerts = pd.DataFrame(rows)
    alerts["status"] = pd.Categorical(alerts["status"], categories=STATUS_ORDER, ordered=True)
    return alerts.sort_values(["status", "attainment"]).reset_index(drop=True)
