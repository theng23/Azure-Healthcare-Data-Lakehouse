# Operations and validation

## Local checks

Run `python tools/validate_repo.py` from the repository. It checks the five-pipeline inventory, JSON references, activity dependency graphs, global parameter references, notebook widget mappings, Python cell syntax, cleared notebook outputs and selected secret patterns. It does not execute Spark, SQL, ADF or email actions and is not an Azure semantic validator.

After configuring the environment, also run ADF Validate All and Test connection for linked services. Follow these with a controlled end to end smoke run.

## Smoke run acceptance

| Check | Expected observation |
| --- | --- |
| Configuration | Both source systems have the expected active table entries and all required Gold entries are active. |
| Master graph | Both source branches succeed before Gold starts; Gold succeeds before notification starts. |
| Run ID | Audit records use the `PL_MASTER` Run ID throughout the child pipelines. |
| Landing | New batch folders match the exact timestamp passed to the notebooks. |
| Bronze and Silver | Intended tables exist; batch data and returned counts reconcile with the known test input. |
| Gold grain | The first three queries in `sql/databricks/02_gold_quality_checks.sql` return zero duplicate-key rows. |
| Audit | Every expected source and Gold entry has the appropriate terminal status; verify the row count, not only the absence of failures. |
| Watermark | Only intended incremental entries advance; investigate processing failures before continuing. |
| Logic Apps | The HTTP trigger and email action succeed and the intended message is received. |

Use `sql/control/03_check_execution.sql` with the actual master Run ID. Do not treat an empty audit result or an empty Gold table as proof of a successful useful run.

## Troubleshooting

| Symptom | Check first |
| --- | --- |
| Notebook not found | Factory `databricks_notebook_root` and GitHub `DATABRICKS_WORKSPACE_ROOT`; imported notebook names omit `.ipynb`. |
| Volume path missing | Exact catalog/schema/volume spelling, external location, UC permissions and the ADF Landing container. |
| No CSV files copied | Source folder, file modification times, watermark and `source_file_format = 'csv'`. |
| MERGE fails | Merge key names, source duplicate keys and target schema. |
| Gold notebook fails | Required Silver tables/fields, calendar setup and date/numeric types. |
| Audit says SUCCESS but master fails | Watermark update or status operations may fail independently after a notebook write. Inspect all failed activities. |
| No failure email | The master has only a success dependency for the email pipeline. |
| Key Vault or HTTP failure | ADF managed identity, vault network access, secret name, callback signature and Logic Apps run details. |

## Reruns and recovery

Record the master Run ID, table ID, batch path and current watermark before recovery. Inspect the last successful Delta write and the audit rows before restarting. A failed pipeline can have already written data.

Bronze appends every batch, so replays can duplicate data. `APPEND` also permits duplicate Silver rows. `MERGE` can be used when the batch has unique keys, but it is not an exactly-once guarantee. A FULL retry can overwrite a target. Reconcile batch input, target contents, watermark and audit status together; do not simply reset one control value and rerun blindly.

The original watermark algorithm needs improvement for unattended ingestion: capture a fixed upper boundary before extraction, read only that window, and advance to the captured boundary after successful processing. Choose timestamp precision and late-arrival handling against the real source. This is a future correctness change, separate from the repository consolidation.

## Deployment rollback

To restore notebook code, revert to a known Git commit and rerun the deployment workflow into the same workspace folder. Importing with overwrite restores files but does not remove notebooks that were subsequently added. Code rollback does not revert Delta table contents or control-table state.

For ADF, restore the intended authoring version, validate it and publish it. Restore data and watermarks through a separate, explicit recovery process. Keep the old schedule stopped during migration to avoid concurrent writes.
