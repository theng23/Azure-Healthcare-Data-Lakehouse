-- Replace the value with the PL_MASTER Run ID from ADF Monitor.
DECLARE @adf_run_id VARCHAR(100) = 'REPLACE_WITH_MASTER_RUN_ID';
SELECT table_id, stage, status, start_time, end_time, records_written
FROM ctrl.audit_log WHERE adf_run_id = @adf_run_id
ORDER BY table_id, start_time;

SELECT stage, status, COUNT(*) AS table_runs
FROM ctrl.audit_log WHERE adf_run_id = @adf_run_id
GROUP BY stage, status;

SELECT t.table_id, t.source_system, t.source_table_name, w.watermark_value
FROM ctrl.table_config t LEFT JOIN ctrl.watermark w ON t.table_id = w.table_id
WHERE t.stage = 'SOURCE_TO_SILVER' AND t.is_active = 1;
