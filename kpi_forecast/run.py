"""End-to-end run: load data, set targets in SQL, backtest, raise this month's alerts, write the report.

    python -m kpi_forecast.run --as-of 2026-10-21
    python -m kpi_forecast.run --as-of 2026-10-21 --reuse-backtest   # skip refitting past months
"""

from __future__ import annotations

import argparse
from functools import partial

import pandas as pd

from kpi_forecast import report
from kpi_forecast.alerts import build_alerts, month_bounds, snapshot
from kpi_forecast.backtest import (
    accuracy_table,
    attach_targets,
    error_bounds,
    evaluate_alerts,
    past_months,
    run_backtest,
)
from kpi_forecast.config import BACKTEST_DAYS, BACKTEST_MONTHS, REPORTS_DIR, TARGET_STRETCH
from kpi_forecast.data import clean_daily, load_daily
from kpi_forecast.models import MODELS
from kpi_forecast.sql import monthly_kpis, monthly_targets

say = partial(print, flush=True)
BACKTEST_CACHE = REPORTS_DIR / "backtest_runs.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as-of", default=str((pd.Timestamp.today() - pd.Timedelta(days=1)).date()))
    parser.add_argument("--stretch", type=float, default=TARGET_STRETCH, help="target stretch on top of trend")
    parser.add_argument("--refresh", action="store_true", help="re-download data even if cached")
    parser.add_argument("--reuse-backtest", action="store_true", help=f"load past-month forecasts from {BACKTEST_CACHE.name}")
    args = parser.parse_args()

    raw = load_daily(args.as_of, refresh=args.refresh)
    as_of = min(pd.Timestamp(args.as_of), raw["date"].max())
    daily, quality_log = clean_daily(raw)
    say(f"Loaded {len(raw):,} rows for {raw['publisher'].nunique()} publishers up to {as_of.date()}")
    say(f"Data quality: {len(quality_log)} days corrected")

    targets = monthly_targets(daily, args.stretch)
    kpis = monthly_kpis(daily)

    month_start, month_end = month_bounds(as_of)
    if as_of >= month_end:
        raise SystemExit("--as-of is the last day of a month; there is nothing left to forecast.")
    last_complete = month_start - pd.Timedelta(days=1)
    months = past_months(last_complete, BACKTEST_MONTHS)
    check_days = tuple(sorted(set(BACKTEST_DAYS) | {as_of.day}))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if args.reuse_backtest and BACKTEST_CACHE.exists():
        backtest = pd.read_csv(BACKTEST_CACHE, parse_dates=["month"])
        say(f"Reusing {len(backtest):,} backtest forecasts from {BACKTEST_CACHE.name}")
    else:
        say(f"Backtesting {len(MODELS)} models over {len(months)} months at days {check_days} ...")
        backtest = run_backtest(daily[daily["date"] <= last_complete], MODELS, months, check_days)
        backtest.to_csv(BACKTEST_CACHE, index=False)
    backtest = attach_targets(backtest, targets)
    accuracy = accuracy_table(backtest)

    today_accuracy = accuracy[accuracy["check_day"] == as_of.day].set_index("model")["remaining_total_mape"]
    model_name = today_accuracy.idxmin()
    say(f"Selected model: {model_name} (rest-of-month MAPE {today_accuracy[model_name]:.2%} at day {as_of.day})")

    errors = backtest[(backtest["model"] == model_name) & (backtest["check_day"] == as_of.day)]["rel_error"]
    err_low, err_high = error_bounds(errors)
    scored_alerts, alert_summary = evaluate_alerts(backtest, model_name)

    model = MODELS[model_name]
    alerts = build_alerts(daily, targets, as_of, model, err_low, err_high)

    alerts.to_csv(REPORTS_DIR / "alerts.csv", index=False)
    quality_log.to_csv(REPORTS_DIR / "data_quality_log.csv", index=False)
    kpis.to_csv(REPORTS_DIR / "monthly_kpis.csv", index=False)
    targets.to_csv(REPORTS_DIR / "monthly_targets.csv", index=False)
    accuracy.to_csv(REPORTS_DIR / "backtest_accuracy.csv", index=False)
    alert_summary.to_csv(REPORTS_DIR / "backtest_alert_summary.csv", index=False)
    scored_alerts.to_csv(REPORTS_DIR / "backtest_alerts_by_month.csv", index=False)

    say("Forecasting the rest of this month ...")
    forecasts = {}
    for publisher, group in daily.groupby("publisher"):
        series = group.set_index("date")["views"].sort_index()
        _, forecasts[publisher] = snapshot(series, as_of, model)
    report.dashboard_extract(daily, forecasts, alerts, as_of).to_csv(REPORTS_DIR / "dashboard_extract.csv", index=False)

    report.plot_attainment(alerts, REPORTS_DIR / "attainment.png")
    report.plot_alert_accuracy(alert_summary, REPORTS_DIR / "alert_accuracy.png")
    worst = alerts.iloc[0]
    series = daily[daily["publisher"] == worst["publisher"]].set_index("date")["views"].sort_index()
    report.plot_publisher(
        series, forecasts[worst["publisher"]], float(worst["target"]), as_of, worst["publisher"],
        REPORTS_DIR / "publisher_most_at_risk.png",
    )
    report.write_markdown(
        REPORTS_DIR / "REPORT.md", as_of, model_name, alerts, accuracy, alert_summary, quality_log, args.stretch
    )

    columns = ["publisher", "status", "attainment", "attainment_low", "attainment_high", "uplift_needed"]
    say(alerts[columns].to_string(index=False))
    say(alert_summary.round(3).to_string(index=False))
    say(f"Report written to {REPORTS_DIR / 'REPORT.md'}")


if __name__ == "__main__":
    main()
