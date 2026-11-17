-- RFI log: monthly raised vs answered and open backlog.
CREATE OR REPLACE TABLE rfi_monthly AS
WITH m AS (
    SELECT LAST_DAY(UNNEST(generate_series(DATE '2024-06-01', (SELECT data_date FROM params), INTERVAL 1 MONTH))::DATE) AS month
)
SELECT
    m.month,
    (SELECT COUNT(*) FROM rfis r WHERE LAST_DAY(r.raised_date) = m.month) AS raised,
    (SELECT COUNT(*) FROM rfis r WHERE LAST_DAY(r.answered_date) = m.month) AS answered,
    (SELECT COUNT(*) FROM rfis r WHERE r.raised_date <= m.month
        AND (r.answered_date IS NULL OR r.answered_date > m.month)) AS open_end_of_month
FROM m
ORDER BY 1;

-- Response performance by discipline against the required-by date.
CREATE OR REPLACE TABLE rfi_by_discipline AS
SELECT
    discipline,
    COUNT(*) AS rfis,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct,
    MEDIAN(answered_date - raised_date) AS median_response_days,
    ROUND(100.0 * COUNT(*) FILTER (WHERE answered_date <= required_date) / COUNT(answered_date), 1) AS on_time_pct,
    COUNT(*) FILTER (WHERE answered_date IS NULL) AS open_rfis,
    COUNT(*) FILTER (WHERE cost_impact = 'Y') AS cost_impact_rfis
FROM rfis
GROUP BY discipline
ORDER BY rfis DESC;

-- Aging of open RFIs by priority.
CREATE OR REPLACE TABLE rfi_aging AS
SELECT
    priority,
    CASE
        WHEN p.data_date - raised_date <= 7  THEN '0-7 days'
        WHEN p.data_date - raised_date <= 14 THEN '8-14 days'
        WHEN p.data_date - raised_date <= 30 THEN '15-30 days'
        ELSE '30+ days'
    END AS age_bucket,
    COUNT(*) AS open_rfis
FROM rfis, params p
WHERE answered_date IS NULL
GROUP BY ALL
ORDER BY priority, age_bucket;
