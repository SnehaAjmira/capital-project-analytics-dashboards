-- Punch list Pareto by cause.
CREATE OR REPLACE TABLE punch_pareto AS
SELECT
    cause,
    COUNT(*) AS items,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct,
    ROUND(100.0 * SUM(COUNT(*)) OVER (ORDER BY COUNT(*) DESC ROWS UNBOUNDED PRECEDING) / SUM(COUNT(*)) OVER (), 1) AS cum_pct
FROM punch_items
GROUP BY cause
ORDER BY items DESC;

-- Weekly open punch items (burndown).
CREATE OR REPLACE TABLE punch_weekly AS
WITH w AS (
    SELECT UNNEST(generate_series(DATE '2025-07-06', (SELECT data_date FROM params), INTERVAL 7 DAY))::DATE AS week_end
)
SELECT
    week_end,
    (SELECT COUNT(*) FROM punch_items p WHERE p.raised_date <= w.week_end) AS raised_cum,
    (SELECT COUNT(*) FROM punch_items p WHERE p.closed_date <= w.week_end) AS closed_cum,
    (SELECT COUNT(*) FROM punch_items p WHERE p.raised_date <= w.week_end
        AND (p.closed_date IS NULL OR p.closed_date > w.week_end)) AS open_items,
    (SELECT COUNT(*) FROM punch_items p WHERE p.category = 'A' AND p.raised_date <= w.week_end
        AND (p.closed_date IS NULL OR p.closed_date > w.week_end)) AS open_cat_a
FROM w
ORDER BY week_end;

-- Open Category A items by system (A items must close before turnover).
CREATE OR REPLACE TABLE punch_open_by_system AS
SELECT
    system,
    COUNT(*) FILTER (WHERE category = 'A' AND closed_date IS NULL) AS open_cat_a,
    COUNT(*) FILTER (WHERE category = 'B' AND closed_date IS NULL) AS open_cat_b,
    ROUND(100.0 * COUNT(closed_date) / COUNT(*), 1) AS closed_pct
FROM punch_items
GROUP BY system
ORDER BY open_cat_a DESC;

-- NCR Pareto by cause with rework cost.
CREATE OR REPLACE TABLE ncr_pareto AS
SELECT
    cause,
    COUNT(*) AS ncrs,
    ROUND(SUM(rework_cost) / 1e3) AS rework_cost_kusd,
    ROUND(100.0 * SUM(SUM(rework_cost)) OVER (ORDER BY SUM(rework_cost) DESC ROWS UNBOUNDED PRECEDING)
          / SUM(SUM(rework_cost)) OVER (), 1) AS cum_cost_pct,
    COUNT(*) FILTER (WHERE closed_date IS NULL) AS open_ncrs
FROM ncrs
GROUP BY cause
ORDER BY rework_cost_kusd DESC;
