"""Write the alert table, charts, a dashboard extract and a plain-English summary."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from kpi_forecast.alerts import AT_RISK, MISS_LIKELY, ON_TRACK, month_bounds  # noqa: E402

COLOURS = {MISS_LIKELY: "#c0392b", AT_RISK: "#e67e22", ON_TRACK: "#27ae60"}


def plot_attainment(alerts: pd.DataFrame, path: Path) -> None:
    data = alerts.sort_values("attainment")
    fig, ax = plt.subplots(figsize=(8, 5))
    y = range(len(data))
    ax.barh(y, data["attainment"] * 100, color=[COLOURS[s] for s in data["status"]], alpha=0.85)
    ax.errorbar(
        data["attainment"] * 100,
        y,
        xerr=[(data["attainment"] - data["attainment_low"]) * 100, (data["attainment_high"] - data["attainment"]) * 100],
        fmt="none",
        ecolor="#333333",
        capsize=3,
    )
    ax.axvline(100, color="#333333", linestyle="--", linewidth=1)
    ax.set_yticks(list(y), data["publisher"])
    ax.set_xlabel("Projected month-end attainment vs target (%) with 90% range")
    month = pd.Timestamp(alerts["month"].iloc[0]).strftime("%B %Y")
    ax.set_title(f"Projected target attainment, {month} (as of {alerts['as_of'].iloc[0]})")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in COLOURS.values()]
    ax.legend(handles, COLOURS.keys(), loc="lower right", frameon=False)
    ax.set_xlim(left=max(0, data["attainment_low"].min() * 100 - 10))
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_publisher(series: pd.Series, forecast: pd.Series, target: float, as_of: pd.Timestamp, publisher: str, path: Path) -> None:
    start, end = month_bounds(as_of)
    mtd = series[start:as_of].sum()
    required = (target - mtd) / len(forecast)
    window = series[as_of - pd.Timedelta(days=60) : as_of]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(window.index, window / 1e6, color="#2c3e50", label="Actual daily views")
    ax.plot(forecast.index, forecast / 1e6, color="#2980b9", linestyle="--", label="Forecast, rest of month")
    ax.hlines(required / 1e6, forecast.index[0], forecast.index[-1], color="#c0392b", label="Daily run-rate needed to hit target")
    ax.axvline(start, color="#999999", linewidth=0.8)
    ax.set_ylabel("Views (millions)")
    ax.set_title(f"{publisher}: actual vs forecast and the run-rate needed this month")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_alert_accuracy(summary: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for column, label in [
        ("alert_precision", "Precision (alerts that were real misses)"),
        ("alert_recall", "Recall (misses that were flagged)"),
        ("status_accuracy", "Overall accuracy"),
    ]:
        ax.plot(summary["check_day"], summary[column] * 100, marker="o", label=label)
    ax.set_xlabel("Day of month the projection was made")
    ax.set_ylabel("%")
    ax.set_ylim(0, 105)
    ax.set_title("How early are the target-miss alerts reliable? (12-month backtest)")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def dashboard_extract(daily: pd.DataFrame, forecasts: dict, alerts: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Long table for Tableau: last 120 days of actuals, the forecast, and each publisher's target."""
    actual = daily[daily["date"] > as_of - pd.Timedelta(days=120)].assign(series="actual")
    fc = pd.concat(
        [f.rename("views").to_frame().assign(publisher=p, series="forecast") for p, f in forecasts.items()]
    ).rename_axis("date").reset_index()
    extract = pd.concat([actual, fc], ignore_index=True)
    return extract.merge(alerts[["publisher", "target", "status"]], on="publisher", how="left")


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def write_markdown(
    path: Path,
    as_of: pd.Timestamp,
    model: str,
    alerts: pd.DataFrame,
    accuracy: pd.DataFrame,
    alert_summary: pd.DataFrame,
    quality_log: pd.DataFrame,
    stretch: float,
) -> None:
    month = pd.Timestamp(alerts["month"].iloc[0]).strftime("%B %Y")
    counts = alerts["status"].value_counts()
    lines = [
        f"# Publisher KPI report: {month}, as of {as_of.date()}",
        "",
        f"**{counts.get(MISS_LIKELY, 0)} publishers are likely to miss target, "
        f"{counts.get(AT_RISK, 0)} are at risk and {counts.get(ON_TRACK, 0)} are on track.**",
        "",
        f"Target = same month last year x (1 + trailing 3-month YoY trend + {stretch:.0%} stretch). "
        f"Forecast model: `{model}`.",
        "",
        "| Publisher | Status | Projected attainment | 90% range | Uplift needed per day |",
        "|---|---|---|---|---|",
    ]
    for _, row in alerts.iterrows():
        uplift = "none" if row["uplift_needed"] <= 0 else pct(row["uplift_needed"])
        lines.append(
            f"| {row['publisher']} | {row['status']} | {pct(row['attainment'])} | "
            f"{pct(row['attainment_low'])} to {pct(row['attainment_high'])} | {uplift} |"
        )
    lines += [
        "",
        "*Uplift needed per day* = how far the remaining days must beat the forecast to reach target.",
        "",
    ]
    flagged = alerts["status"].isin([MISS_LIKELY, AT_RISK]).mean()
    if flagged >= 0.7:
        lines += [
            f"> **Portfolio-wide shift:** {flagged:.0%} of publishers are flagged at once. When most accounts move "
            "together the cause is usually shared (a tracking or measurement change, a platform-level traffic "
            "change, a calendar effect) rather than ten separate partner problems. Check for a common cause "
            "before contacting individual publishers.",
            "",
        ]
    lines += [
        "## How reliable is this?",
        "",
        "Backtest over the last 12 complete months, replaying each month as if it were live:",
        "",
        "| Check day | Alert precision | Alert recall | Overall accuracy | Actual inside 90% range |",
        "|---|---|---|---|---|",
    ]
    for _, row in alert_summary.iterrows():
        lines.append(
            f"| Day {int(row['check_day'])} | {pct(row['alert_precision'])} | {pct(row['alert_recall'])} | "
            f"{pct(row['status_accuracy'])} | {pct(row['range_coverage'])} |"
        )
    lines += ["", "Forecast error on the rest-of-month total (mean absolute % error):", ""]
    pivot = accuracy.pivot(index="check_day", columns="model", values="remaining_total_mape")
    lines.append("| Check day | " + " | ".join(pivot.columns) + " |")
    lines.append("|---|" + "---|" * len(pivot.columns))
    for day, row in pivot.iterrows():
        lines.append(f"| Day {day} | " + " | ".join(pct(v) for v in row) + " |")
    lines += [
        "",
        "## Data quality",
        "",
        f"{len(quality_log)} days were corrected before modelling "
        f"({(quality_log['action'] == 'interpolated').sum()} missing, "
        f"{quality_log['issue'].str.startswith('spike').sum()} spikes capped). See `data_quality_log.csv`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
