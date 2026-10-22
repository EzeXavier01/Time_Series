import numpy as np
import pandas as pd

from kpi_forecast.models import ets, seasonal_naive


def weekly_series(days: int = 400, trend: float = 0.0) -> pd.Series:
    index = pd.date_range("2025-01-01", periods=days, freq="D")
    weekly = np.tile([1.0, 1.1, 1.2, 1.1, 1.0, 0.7, 0.6], days // 7 + 1)[:days]
    level = 1_000_000 * (1 + trend) ** np.arange(days)
    return pd.Series(level * weekly, index=index)


def test_seasonal_naive_repeats_last_week():
    history = weekly_series(28)
    forecast = seasonal_naive(history, 10)
    assert len(forecast) == 10
    assert forecast.index[0] == history.index[-1] + pd.Timedelta(days=1)
    np.testing.assert_allclose(forecast.to_numpy()[:7], history.to_numpy()[-7:])
    np.testing.assert_allclose(forecast.to_numpy()[7:], history.to_numpy()[-7:-4])


def test_ets_learns_weekly_pattern():
    history = weekly_series(400)
    forecast = ets(history, 14)
    expected = seasonal_naive(history, 14)  # a clean weekly series should be continued as-is
    assert (forecast > 0).all()
    np.testing.assert_allclose(forecast.to_numpy(), expected.to_numpy(), rtol=0.02)
