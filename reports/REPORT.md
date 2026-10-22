# Publisher KPI report: October 2026, as of 2026-10-21

**10 publishers are likely to miss target, 0 are at risk and 0 are on track.**

Target = same month last year x (1 + trailing 3-month YoY trend + 0% stretch). Forecast model: `ets`.

| Publisher | Status | Projected attainment | 90% range | Uplift needed per day |
|---|---|---|---|---|
| Arabic | MISS LIKELY | 85.1% | 82.7% to 87.3% | 55.3% |
| Dutch | MISS LIKELY | 88.8% | 86.3% to 91.1% | 40.1% |
| Spanish | MISS LIKELY | 88.8% | 86.2% to 91.2% | 39.2% |
| Portuguese | MISS LIKELY | 89.2% | 86.7% to 91.5% | 38.9% |
| Polish | MISS LIKELY | 89.8% | 87.2% to 92.1% | 35.9% |
| German | MISS LIKELY | 90.3% | 87.7% to 92.7% | 33.5% |
| English | MISS LIKELY | 92.0% | 89.4% to 94.4% | 27.7% |
| French | MISS LIKELY | 92.7% | 90.1% to 95.1% | 25.2% |
| Japanese | MISS LIKELY | 93.2% | 90.4% to 95.6% | 23.0% |
| Italian | MISS LIKELY | 95.7% | 93.0% to 98.1% | 14.6% |

*Uplift needed per day* = how far the remaining days must beat the forecast to reach target.

> **Portfolio-wide shift:** 100% of publishers are flagged at once. When most accounts move together the cause is usually shared (a tracking or measurement change, a platform-level traffic change, a calendar effect) rather than ten separate partner problems. Check for a common cause before contacting individual publishers.

## How reliable is this?

Backtest over the last 12 complete months, replaying each month as if it were live:

| Check day | Alert precision | Alert recall | Overall accuracy | Actual inside 90% range |
|---|---|---|---|---|
| Day 7 | 89.5% | 83.6% | 86.7% | 88.3% |
| Day 14 | 93.1% | 88.5% | 90.8% | 89.2% |
| Day 21 | 95.0% | 93.4% | 94.2% | 87.5% |

Forecast error on the rest-of-month total (mean absolute % error):

| Check day | ets | seasonal_naive |
|---|---|---|
| Day 7 | 3.5% | 3.6% |
| Day 14 | 3.5% | 3.4% |
| Day 21 | 3.7% | 3.9% |

## Data quality

76 days were corrected before modelling (0 missing, 76 spikes capped). See `data_quality_log.csv`.
