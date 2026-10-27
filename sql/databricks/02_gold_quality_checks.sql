-- Gold grain checks: each query must return zero rows.
SELECT patient_id, COUNT(*) AS n
FROM adb_healthy.gold.patient_360
GROUP BY patient_id HAVING COUNT(*) > 1;

SELECT hospital_id, summary_date, COUNT(*) AS n
FROM adb_healthy.gold.hospital_daily_summary
GROUP BY hospital_id, summary_date HAVING COUNT(*) > 1;

SELECT test_name, year, month, COUNT(*) AS n
FROM adb_healthy.gold.lab_test_trends
GROUP BY test_name, year, month HAVING COUNT(*) > 1;

-- Inspect source duplication rather than hiding it behind the Gold deduplication.
SELECT lab_result_id, COUNT(*) AS n
FROM adb_healthy.silver.lab_results
GROUP BY lab_result_id HAVING COUNT(*) > 1;

SELECT 'patient_360' AS table_name, COUNT(*) AS row_count FROM adb_healthy.gold.patient_360
UNION ALL
SELECT 'hospital_daily_summary', COUNT(*) FROM adb_healthy.gold.hospital_daily_summary
UNION ALL
SELECT 'lab_test_trends', COUNT(*) FROM adb_healthy.gold.lab_test_trends;
