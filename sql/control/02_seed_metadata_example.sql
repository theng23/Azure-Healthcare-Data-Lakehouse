-- EXAMPLE ONLY: this is not an export of the original Azure SQL configuration.
-- All rows start disabled. Verify source locations and column names, then activate.
-- The current Landing notebook requires source_table_name = bronze_table_name
-- = silver_table_name. Keep Gold table IDs distinct from source table IDs.
INSERT INTO ctrl.table_config
    (table_id, stage, source_system, source_table_name, source_path,
     source_file_format, bronze_table_name, silver_table_name,
     gold_table_name, load_type, merge_keys, watermark_column, is_active)
SELECT v.* FROM (VALUES
    (1, 'SOURCE_TO_SILVER', 'neon_postgres', 'patients', NULL, 'parquet', 'patients', 'patients', NULL, 'FULL', NULL, NULL, 0),
    (2, 'SOURCE_TO_SILVER', 'neon_postgres', 'hospitals', NULL, 'parquet', 'hospitals', 'hospitals', NULL, 'FULL', NULL, NULL, 0),
    (3, 'SOURCE_TO_SILVER', 'neon_postgres', 'insurance_providers', NULL, 'parquet', 'insurance_providers', 'insurance_providers', NULL, 'FULL', NULL, NULL, 0),
    (4, 'SOURCE_TO_SILVER', 'adls_csv', 'lab_results', 'lab_results', 'csv', 'lab_results', 'lab_results', NULL, 'MERGE', 'lab_result_id', NULL, 0),
    (101, 'SILVER_TO_GOLD', NULL, NULL, NULL, NULL, NULL, NULL, 'patient_360', 'FULL', NULL, NULL, 0),
    (102, 'SILVER_TO_GOLD', NULL, NULL, NULL, NULL, NULL, NULL, 'hospital_daily_summary', 'FULL', NULL, NULL, 0),
    (103, 'SILVER_TO_GOLD', NULL, NULL, NULL, NULL, NULL, NULL, 'lab_test_trends', 'FULL', NULL, NULL, 0)
) v(table_id, stage, source_system, source_table_name, source_path, source_file_format,
    bronze_table_name, silver_table_name, gold_table_name, load_type, merge_keys,
    watermark_column, is_active)
WHERE NOT EXISTS (SELECT 1 FROM ctrl.table_config t WHERE t.table_id = v.table_id);
GO
INSERT INTO ctrl.watermark(table_id, watermark_value)
SELECT table_id, CAST('1900-01-01T00:00:00' AS DATETIME2)
FROM ctrl.table_config t
WHERE stage = 'SOURCE_TO_SILVER' AND load_type <> 'FULL'
  AND NOT EXISTS (SELECT 1 FROM ctrl.watermark w WHERE w.table_id = t.table_id);
GO
-- After verifying the sample mapping, enable only the rows you intend to run.
-- UPDATE ctrl.table_config SET is_active = 1 WHERE table_id IN (1,2,3,4,101,102,103);
