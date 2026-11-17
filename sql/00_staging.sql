-- Staging: load synthetic CSVs and set the data date used by every KPI.
CREATE OR REPLACE TABLE params AS SELECT DATE '2026-06-30' AS data_date;

CREATE OR REPLACE TABLE control_accounts      AS SELECT * FROM read_csv_auto('data/control_accounts.csv');
CREATE OR REPLACE TABLE ev_monthly            AS SELECT * FROM read_csv_auto('data/ev_monthly.csv');
CREATE OR REPLACE TABLE engineering_documents AS SELECT * FROM read_csv_auto('data/engineering_documents.csv');
CREATE OR REPLACE TABLE rfis                  AS SELECT * FROM read_csv_auto('data/rfis.csv');
CREATE OR REPLACE TABLE purchase_orders       AS SELECT * FROM read_csv_auto('data/purchase_orders.csv');
CREATE OR REPLACE TABLE punch_items           AS SELECT * FROM read_csv_auto('data/punch_items.csv');
CREATE OR REPLACE TABLE ncrs                  AS SELECT * FROM read_csv_auto('data/ncrs.csv');
