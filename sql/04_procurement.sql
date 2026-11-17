-- Supplier RFMT segmentation.
-- Recency: days since last PO. Frequency: PO count. Monetary: total PO value.
-- Tenure: days since first PO. Each scored 1 (low) to 5 (high) by quintile;
-- recency is reversed so a recent PO scores 5.
CREATE OR REPLACE TABLE supplier_rfmt AS
WITH base AS (
    SELECT
        supplier_id,
        ANY_VALUE(category) AS category,
        p.data_date - MAX(po_date) AS recency_days,
        COUNT(*) AS frequency,
        SUM(po_value) AS monetary,
        p.data_date - MIN(po_date) AS tenure_days,
        ROUND(100.0 * COUNT(*) FILTER (WHERE delivered_date <= promised_date)
              / NULLIF(COUNT(delivered_date), 0), 1) AS otd_pct
    FROM purchase_orders, params p
    GROUP BY supplier_id, p.data_date
),
scored AS (
    SELECT *,
        6 - NTILE(5) OVER (ORDER BY recency_days) AS r,
        NTILE(5) OVER (ORDER BY frequency, monetary) AS f,
        NTILE(5) OVER (ORDER BY monetary) AS m,
        NTILE(5) OVER (ORDER BY tenure_days) AS t
    FROM base
)
SELECT *,
    r::VARCHAR || f::VARCHAR || m::VARCHAR || t::VARCHAR AS rfmt_code,
    CASE
        WHEN m >= 4 AND f >= 4 AND r >= 3            THEN 'Strategic'
        WHEN m >= 4 AND r <= 2                       THEN 'High value, going quiet'
        WHEN t <= 2 AND r >= 4                       THEN 'New and active'
        WHEN r <= 2 AND f <= 2                       THEN 'Dormant'
        ELSE 'Core tactical'
    END AS segment
FROM scored;

CREATE OR REPLACE TABLE supplier_segments AS
SELECT
    segment,
    COUNT(*) AS suppliers,
    ROUND(SUM(monetary) / 1e6, 1) AS spend_musd,
    ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 1) AS spend_share_pct,
    ROUND(AVG(otd_pct), 1) AS avg_otd_pct
FROM supplier_rfmt
GROUP BY segment
ORDER BY spend_musd DESC;

-- Spend Pareto (ABC classification): A = top 80% of spend, B = next 15%, C = last 5%.
CREATE OR REPLACE TABLE supplier_pareto AS
SELECT
    supplier_id,
    category,
    monetary,
    ROW_NUMBER() OVER (ORDER BY monetary DESC) AS rank,
    100.0 * SUM(monetary) OVER (ORDER BY monetary DESC ROWS UNBOUNDED PRECEDING) / SUM(monetary) OVER () AS cum_spend_pct,
    CASE
        WHEN 100.0 * SUM(monetary) OVER (ORDER BY monetary DESC ROWS UNBOUNDED PRECEDING) / SUM(monetary) OVER () <= 80 THEN 'A'
        WHEN 100.0 * SUM(monetary) OVER (ORDER BY monetary DESC ROWS UNBOUNDED PRECEDING) / SUM(monetary) OVER () <= 95 THEN 'B'
        ELSE 'C'
    END AS abc_class
FROM supplier_rfmt
ORDER BY rank;

-- On-time delivery and lead time by category.
CREATE OR REPLACE TABLE procurement_by_category AS
SELECT
    category,
    COUNT(*) AS pos,
    ROUND(SUM(po_value) / 1e6, 1) AS spend_musd,
    ROUND(100.0 * COUNT(*) FILTER (WHERE delivered_date <= promised_date) / COUNT(delivered_date), 1) AS otd_pct,
    MEDIAN(promised_date - po_date) AS median_lead_days,
    ROUND(AVG(delivered_date - promised_date) FILTER (WHERE delivered_date > promised_date), 1) AS avg_days_late_when_late
FROM purchase_orders
GROUP BY category
ORDER BY otd_pct;
