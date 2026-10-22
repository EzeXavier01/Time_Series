-- Monthly KPI totals per publisher, with year-on-year change.
-- Only complete months are marked complete, so partial months are never compared like for like.
WITH monthly AS (
    SELECT
        publisher,
        CAST(date_trunc('month', date) AS DATE) AS month,
        SUM(views)                              AS views,
        COUNT(*)                                AS days_reported
    FROM daily
    GROUP BY ALL
)
SELECT
    cur.publisher,
    cur.month,
    cur.views,
    cur.days_reported = day(last_day(cur.month))          AS is_complete,
    prev.views                                            AS views_last_year,
    ROUND(cur.views / prev.views - 1, 4)                  AS yoy_change
FROM monthly AS cur
LEFT JOIN monthly AS prev
    ON  prev.publisher = cur.publisher
    AND prev.month = CAST(cur.month - INTERVAL 1 YEAR AS DATE)
ORDER BY cur.publisher, cur.month;
