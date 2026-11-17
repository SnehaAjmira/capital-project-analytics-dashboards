-- Engineering deliverables: planned vs actual first submittals (cumulative, monthly).
CREATE OR REPLACE TABLE eng_progress AS
WITH m AS (
    SELECT UNNEST(generate_series(DATE '2024-01-31', (SELECT data_date FROM params), INTERVAL 1 MONTH))::DATE AS month
)
SELECT
    LAST_DAY(m.month) AS month,
    (SELECT COUNT(*) FROM engineering_documents d WHERE d.planned_issue_date <= LAST_DAY(m.month)) AS planned_cum,
    (SELECT COUNT(*) FROM engineering_documents d WHERE d.first_submittal_date <= LAST_DAY(m.month)) AS actual_cum,
    (SELECT COUNT(*) FROM engineering_documents d WHERE d.approved_date <= LAST_DAY(m.month)) AS approved_cum
FROM m
ORDER BY 1;

-- Quality of submittals by discipline: first-time approval and review turnaround.
CREATE OR REPLACE TABLE eng_by_discipline AS
SELECT
    discipline,
    COUNT(*) AS documents,
    COUNT(first_submittal_date) AS submitted,
    ROUND(100.0 * COUNT(*) FILTER (WHERE first_return_code = 'Code 1') / COUNT(first_return_code), 1) AS first_time_approval_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE first_return_code = 'Code 3') / COUNT(first_return_code), 1) AS revise_resubmit_pct,
    MEDIAN(first_review_days) AS median_review_days,
    ROUND(AVG(first_submittal_date - planned_issue_date), 1) AS avg_days_late
FROM engineering_documents
GROUP BY discipline
ORDER BY first_time_approval_pct;

-- Overdue: planned to be issued but not yet submitted, by days overdue.
CREATE OR REPLACE TABLE eng_overdue AS
SELECT
    discipline,
    CASE
        WHEN p.data_date - planned_issue_date <= 30 THEN '1-30 days'
        WHEN p.data_date - planned_issue_date <= 60 THEN '31-60 days'
        WHEN p.data_date - planned_issue_date <= 90 THEN '61-90 days'
        ELSE '90+ days'
    END AS overdue_bucket,
    COUNT(*) AS documents
FROM engineering_documents, params p
WHERE first_submittal_date IS NULL AND planned_issue_date < p.data_date
GROUP BY ALL
ORDER BY discipline, overdue_bucket;
