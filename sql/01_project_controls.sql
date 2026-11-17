-- Earned value: monthly cumulative PV, EV, AC with CPI and SPI.
CREATE OR REPLACE TABLE pc_monthly AS
SELECT
    month,
    SUM(pv) AS pv,
    SUM(ev) AS ev,
    SUM(ac) AS ac,
    SUM(ev) / NULLIF(SUM(ac), 0) AS cpi,
    SUM(ev) / NULLIF(SUM(pv), 0) AS spi
FROM ev_monthly
GROUP BY month
ORDER BY month;

-- Status at data date by area. EAC uses the CPI method: EAC = BAC / CPI.
CREATE OR REPLACE TABLE pc_by_area AS
SELECT
    ca.area,
    SUM(ca.bac) AS bac,
    SUM(e.pv) AS pv,
    SUM(e.ev) AS ev,
    SUM(e.ac) AS ac,
    SUM(e.ev) - SUM(e.ac) AS cv,
    SUM(e.ev) - SUM(e.pv) AS sv,
    SUM(e.ev) / SUM(e.ac) AS cpi,
    SUM(e.ev) / SUM(e.pv) AS spi,
    SUM(ca.bac) / (SUM(e.ev) / SUM(e.ac)) AS eac,
    SUM(ca.bac) - SUM(ca.bac) / (SUM(e.ev) / SUM(e.ac)) AS vac
FROM control_accounts ca
JOIN ev_monthly e ON e.control_account = ca.control_account
WHERE e.month = (SELECT data_date FROM params)
GROUP BY ca.area
ORDER BY bac DESC;
