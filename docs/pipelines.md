# Pipeline reference

These are the five operational pipelines in `adf/pipeline`. The incomplete original `test` pipeline is retained under `archive/adf`.

## PL_MASTER

No parameters. Starts two `ExecutePipeline` activities in parallel, supplying `source_system` as `neon_postgres` and `adls_csv` and passing `@pipeline().RunId` as `adf_run_id`. Both calls wait for completion.

`Silver to Gold` waits for both source branches to succeed. `Send_Email` waits for Gold to succeed. Consequently, a source failure can skip Gold and email. Reconstruct the complete failure path before adding any claim of guaranteed error notification.

## PL_SOURCE_TO_SILVER_MAIN

| Parameter | Type | Meaning |
| --- | --- | --- |
| `source_system` | String | `neon_postgres` or `adls_csv` |
| `adf_run_id` | String | Master Run ID, reused in audit queries |

Reads active `SOURCE_TO_SILVER` entries for the source system. A parallel `ForEach` creates an `IN_PROGRESS` audit row, then invokes the inner pipeline with `table_id` and `adf_run_id`. If that invocation fails, the loop has separate failure logging and Fail activities. Successful status is written inside the inner pipeline.

The merge adds an explicit stage predicate to the metadata lookup. This prevents Gold metadata from being treated as a source ingestion entry when source-system values overlap.

## PL_SOURCE_TO_SILVER_INNER

| Parameter | Type | Meaning |
| --- | --- | --- |
| `table_id` | String | Numeric control-table ID serialized by ADF |
| `adf_run_id` | String | Master Run ID |

1. `Read Table Details` queries one metadata row. `Set Start Time` independently creates the exact batch-folder timestamp in `yyyy-MM-dd_HH:mm:ss` format.
2. `Check Load Type` reads the stored watermark when `load_type` is not `FULL`.
3. `Check Source System` chooses one of two supported Copy activities. PostgreSQL is read from `PUBLIC.<source_table_name>` and written to Parquet. CSV files are copied as binary objects from the `source` container into `landing`.
4. `Landing to Bronze` receives the batch timestamp, source system, Bronze table name and source file format.
5. `Bronze to Silver` receives the same timestamp, Silver table name, merge keys and load type.
6. `Update Success Status` writes the returned Silver row count. A separate conditional activity updates the watermark for non-FULL loads. These two operations both depend on Silver, rather than on each other.

| Notebook | Parameters |
| --- | --- |
| `Landing_to_Bronze` | `source_system`, `table_name`, `landing_timestamp`, `source_file_format` |
| `Bronze_to_Silver` | `table_name`, `landing_timestamp`, `merge_keys`, `load_type` |

`FULL` overwrites Silver; `APPEND` appends; `MERGE` upserts by comma-separated keys and preserves an existing `insert_timestamp` on updates. MERGE validates the keys but does not deterministically resolve duplicate source keys.

For PostgreSQL incremental extraction, the query uses `watermark_column > stored watermark` without a fixed upper bound. CSV incrementality uses `modifiedDatetimeStart`. The merged version supplies a null modification-time boundary for a FULL CSV load. After successful Silver processing, the watermark still uses SQL processing time. See the replay and watermark limitations in the main README.

## PL_SILVER_TO_GOLD

Takes `adf_run_id`. Reads active rows with `stage = 'SILVER_TO_GOLD'`, then processes them in a parallel `ForEach`. Each iteration writes an `IN_PROGRESS` audit row, calls the dynamically selected notebook and writes either `SUCCESS` with its row count or `FAILED`. A Fail activity propagates a failed notebook execution.

The dynamic path is `databricks_notebook_root + '/Gold/NB_' + gold_table_name`. The three supplied values are `patient_360`, `hospital_daily_summary` and `lab_test_trends`. Gold notebooks do not take widgets in this implementation; they read fixed Silver table names.

## PL_SEND_EMAIL

Takes `adf_run_id`. It performs independent audit status queries and prepares body fragments. The subject is `<env> | <FAIL or SUCCESS> | CARESYNC MASTER RUN`, using the count of audit rows whose status is not `SUCCESS`.

After preparing the body, `Get Logic App URL` retrieves the configured secret with the ADF managed identity. `Send Email` posts the body to that URL. Secret lookup output and HTTP activity inputs/outputs are secured in the merged pipeline definition.

The request contract keeps `email_receipients` for compatibility. See `logic-app-request.schema.json`. There is no recipient verification, email provider connection or delivery receipt implemented in the ADF pipeline itself.

## Schedule

`TGR_CARESYNC_DAILY` is configured as `Hour` with interval `8`, start time `2026-10-27T16:30:00`, and time zone `SE Asia Standard Time`. Its display name does not mean once per day. The packaged `runtimeState` is `Stopped`; review and enable it after the environment smoke run.
