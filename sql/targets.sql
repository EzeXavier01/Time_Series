-- Monthly commitment per publisher.
--
--   target = same month last year x (1 + trailing 3-month YoY trend + stretch)
--
-- The trailing trend is the average year-on-year change of the three complete months
-- before the target month, so a commitment reflects where the publisher was heading
-- when it was set, not a flat repeat of last year. A target is only produced when
-- last year's month and all three trend months are complete.
-- Parameter ? = stretch on top of trend (0.0 = "keep your recent trajectory").
WITH monthly_raw AS (
    SELECT
        publisher,
        CAST(date_trunc('month', date) AS DATE) AS month,
        SUM(views)                              AS views,
        COUNT(*)                                AS days_reported
    FROM daily
    GROUP BY ALL
),
monthly AS (
    SELECT *, days_reported = day(last_day(month)) AS is_complete
    FROM monthly_raw
),
yoy AS (
    SELECT
        cur.publisher,
        cur.month,
        cur.views / prev.views - 1 AS yoy_change
    FROM monthly AS cur
    JOIN monthly AS prev
        ON  prev.publisher = cur.publisher
        AND prev.month = CAST(cur.month - INTERVAL 1 YEAR AS DATE)
    WHERE cur.is_complete AND prev.is_complete
),
months_to_target AS (
    SELECT DISTINCT
        publisher,
        CAST(date_trunc('month', date + INTERVAL 1 YEAR) AS DATE) AS month
    FROM daily
),
trend AS (
    SELECT
        t.publisher,
        t.month,
        last_year.views     AS views_last_year,
        AVG(y.yoy_change)   AS trailing_yoy,
        COUNT(y.yoy_change) AS trend_months
    FROM months_to_target AS t
    JOIN monthly AS last_year
        ON  last_year.publisher = t.publisher
        AND last_year.month = CAST(t.month - INTERVAL 1 YEAR AS DATE)
        AND last_year.is_complete
    LEFT JOIN yoy AS y
        ON  y.publisher = t.publisher
        AND y.month BETWEEN CAST(t.month - INTERVAL 3 MONTH AS DATE) AND CAST(t.month - INTERVAL 1 MONTH AS DATE)
    GROUP BY t.publisher, t.month, last_year.views
)
SELECT
    publisher,
    month,
    ROUND(views_last_year * (1 + trailing_yoy + ?)) AS target,
    ROUND(trailing_yoy, 4)                           AS trailing_yoy
FROM trend
WHERE trend_months = 3
ORDER BY publisher, month;
