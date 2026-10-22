"""Daily forecasting models. Each takes a history series and returns `horizon` future days."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from kpi_forecast.config import TRAINING_DAYS


def _future_index(history: pd.Series, horizon: int) -> pd.DatetimeIndex:
    return pd.date_range(history.index[-1] + pd.Timedelta(days=1), periods=horizon, freq="D")


def seasonal_naive(history: pd.Series, horizon: int) -> pd.Series:
    """Baseline: each future day equals the same weekday last week."""
    last_week = history.iloc[-7:].to_numpy()
    values = np.resize(last_week, horizon)
    return pd.Series(values, index=_future_index(history, horizon), name="forecast")


def ets(history: pd.Series, horizon: int) -> pd.Series:
    """Holt-Winters exponential smoothing on the log scale.

    Damped additive trend plus a weekly seasonal pattern. Working on logs makes the
    weekly pattern proportional to the level and keeps forecasts positive.
    """
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    train = np.log(history.iloc[-TRAINING_DAYS:].astype(float))
    train.index = pd.DatetimeIndex(train.index, freq="D")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = ExponentialSmoothing(
            train,
            trend="add",
            damped_trend=True,
            seasonal="add",
            seasonal_periods=7,
            initialization_method="estimated",
        ).fit()
        values = np.exp(fitted.forecast(horizon).to_numpy())
    return pd.Series(values, index=_future_index(history, horizon), name="forecast")


MODELS = {"seasonal_naive": seasonal_naive, "ets": ets}
