"""Run the SQL files in sql/ against a daily KPI frame with DuckDB."""

from __future__ import annotations

import duckdb
import pandas as pd

from kpi_forecast.config import SQL_DIR


def run_sql(name: str, daily: pd.DataFrame, params: list | None = None) -> pd.DataFrame:
    """Execute sql/<name>.sql with the frame available as the table `daily`."""
    query = (SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")
    con = duckdb.connect()
    try:
        con.register("daily", daily[["date", "publisher", "views"]])
        result = con.execute(query, params or []).df()
    finally:
        con.close()
    if "month" in result:
        result["month"] = pd.to_datetime(result["month"])
    return result


def monthly_kpis(daily: pd.DataFrame) -> pd.DataFrame:
    return run_sql("monthly_kpis", daily)


def monthly_targets(daily: pd.DataFrame, stretch: float) -> pd.DataFrame:
    return run_sql("targets", daily, [stretch])
