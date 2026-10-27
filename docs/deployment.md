# Deployment guide

This guide configures an existing Azure environment or a new manual installation. The repository contains authoring resources and notebooks; it does not provision Azure resources. Validate in a development environment first.

## 1 Prepare resources and access

| Resource | Required preparation |
| --- | --- |
| ADLS Gen2 | Enable hierarchical namespace; create `source` and `landing` containers; place source CSV files under the configured source folder. |
| PostgreSQL | Make the intended `public` tables reachable from the ADF integration runtime; verify TLS, firewall and credentials. |
| Azure SQL | Create or reuse the metadata database. Allow the ADF integration runtime to connect and grant its SQL account permissions on the control tables. |
| ADF | Enable its system-assigned managed identity. Configure storage access and network reachability for all linked services. |
| Key Vault | Grant the ADF managed identity secret read access through the vault's configured permission model. Network restrictions must also permit the request. |
| Databricks | Use a cluster and runtime that support the supplied Spark SQL, Delta and Unity Catalog volume operations. The ADF token identity needs permission to run notebooks and use the cluster; the CI identity needs permission to import notebooks into the target folder. |
| Unity Catalog | Grant the notebook execution identity access to `adb_healthy`, its schemas, the external Landing volume and the underlying storage location. |
| Logic Apps | Create an HTTP-triggered workflow and an authenticated email connection. No deployed workflow definition was supplied with the original source. |

Use the Azure portal and Databricks permissions screens to grant the exact access needed by the identities in your own environment. Managed identity use for ADF storage and secrets does not replace Databricks' Unity Catalog storage authorization.

## 2 Create secrets

The existing linked-service reference names are preserved:

| Secret name | Used by | Value |
| --- | --- | --- |
| `postgres-passwords` | `LS_PostgreSql1` | PostgreSQL password |
| `medata-db-passworld` | `LS_AzureSqlDatabase1` | Azure SQL password; spelling retained from the original code |
| `azure-databrick-token` | `AzureDatabricks1` | Token authorized to run Databricks notebooks |
| `logic-app-callback-url` | `PL_SEND_EMAIL` | Complete callback URL for the HTTP-triggered Logic App, including its signature |

If you use different secret names, update the corresponding JSON references. The callback secret name can also be set in `config/environment.local.json`.

The original factory configuration included a signed callback URL. Rotate that callback signature before reusing the endpoint. Removing it from the new working tree does not revoke the old URL or remove it from the old repositories' histories.

## 3 Configure the authoring resources

Copy the example JSON and replace every `__PLACEHOLDER__` with the environment value:

```bash
python tools/configure_environment.py --config config/environment.local.json
python tools/validate_repo.py
```

The script reads the local file, updates the five linked services and updates/renames the single factory JSON. It does not connect to Azure. The local configuration is ignored by Git. Generated ADF JSON contains environment identifiers and the recipient address but does not contain the password, token or callback URL values.

Keep these values aligned:

| Setting | Example |
| --- | --- |
| ADF Git root | `/adf` |
| Git collaboration branch | `main` |
| ADF publish branch | `adf_publish` |
| Factory global `databricks_notebook_root` | `/Shared/caresync/databricks` |
| GitHub environment variable `DATABRICKS_WORKSPACE_ROOT` | `/Shared/caresync/databricks` |
| Notebook catalog | `adb_healthy` |
| Notebook Landing volume | `/Volumes/adb_healthy/landing/landing_volumne` |

The script preserves `email_receipent` in ADF because the pipeline references that spelling. The local configuration uses the correctly spelled `email_recipient`. The HTTP request uses the existing contract field `email_receipients`. Coordinate both sides before renaming either field.

## 4 Prepare control metadata and source schemas

For an existing deployment, retain the actual contents of `ctrl.table_config`, `ctrl.watermark` and `ctrl.audit_log`; compare their schemas with the query contracts. Do not replace a working metadata database with the example seed.

For a new deployment:

1. Review and run `sql/control/01_create_control_tables.sql` in Azure SQL.
2. Review `02_seed_metadata_example.sql`, change source assignments and paths to match your sources, and run it. The example assigns patient/hospital/insurer tables to PostgreSQL and lab results to CSV; these assignments are examples rather than recovered original metadata.
3. Keep `source_table_name`, `bronze_table_name` and `silver_table_name` equal with the current notebooks. PostgreSQL source tables must be addressable as unquoted `PUBLIC.<name>`.
4. For PostgreSQL incremental loads, set a real source `watermark_column`, use `APPEND` or `MERGE`, and create an initial watermark row. The field must have a comparable timestamp representation.
5. For CSV incremental loads, configure the source folder and initial watermark. Incrementality is based on file modification time, not a row timestamp inside each CSV.
6. Keep every Gold `table_id` distinct and set `gold_table_name` to `patient_360`, `hospital_daily_summary` or `lab_test_trends`.
7. Activate only verified rows. Confirm both source branches and all intended Gold rows have the expected active configuration before the first master run.

The Gold SQL expects at least the following fields:

| Silver table | Required business fields |
| --- | --- |
| `patients` | `patient_id`, `first_name`, `last_name`, `date_of_birth`, `gender`, `city`, `state`, `registered_hospital_id`, `insurance_provider_id` |
| `hospitals` | `hospital_id`, `hospital_name` |
| `insurance_providers` | `insurance_provider_id`, `provider_name` |
| `lab_results` | `lab_result_id`, `patient_id`, `hospital_id`, `doctor_id`, `test_name`, `test_date`, `result_status`; plus the load metadata `update_timestamp` added by Silver |
| `calendar` | `date_key`, `date`, `day_name`, `is_weekend`, `year`, `month`, `month_name`, `quarter` |

Provide compatible numeric, date and string types. The supplied ingestion notebook infers CSV schema; establish stable schemas before using it for repeated production loads.

## 5 Prepare Unity Catalog and notebooks

Review `sql/databricks/01_unity_catalog_setup.sql.template`. Create a storage credential and external location for the Landing container, then create the catalog, schemas and external volume. Replace `<storage-account>` before running the SQL. If the catalog already exists, retain its intended managed storage and access policy.

Import notebooks manually for the initial setup or run the provided GitHub workflow:

```bash
databricks workspace import-dir databricks/notebooks /Shared/caresync/databricks --overwrite
```

Run `setup/Calendar_Dimension_Build` once. It creates the calendar from 1940-01-01 through 2030-12-31. It is a setup notebook and is not called by the five operational pipelines.

## 6 Configure CI and Databricks CD

Create GitHub environment `dev`, then add:

| Kind | Name | Value |
| --- | --- | --- |
| Variable | `DATABRICKS_HOST` | Workspace URL beginning with `https://` |
| Variable | `DATABRICKS_WORKSPACE_ROOT` | Same path as ADF `databricks_notebook_root` |
| Secret | `DATABRICKS_TOKEN` | Token with workspace import permissions |

The CI workflow runs on pushes and pull requests targeting `main`. The deployment workflow runs on matching notebook-related pushes to `main` and can also be dispatched manually. It validates first, then imports notebooks. It does not execute transformations or change Delta tables.

For `prod`, create a separate GitHub environment, configure its own values, add environment protection rules and select it through manual dispatch. Review the chosen Git ref before running the manual workflow. ADF environment deployment is still a separate process.

## 7 Connect and publish ADF

Configure the shared GitHub repository with collaboration branch `main`, publish branch `adf_publish`, and root folder `/adf`. Keep the active `publish_config.json` at `adf/publish_config.json`. When changing an existing connection, avoid importing old live resources into the new folder unintentionally; use the migration sequence.

Open ADF, confirm linked services and global parameters, and test each connection. Run Validate All, resolve any environment-specific validation errors, then Publish All from the collaboration branch. A Git commit alone does not update the live ADF service. The publish branch contains generated ARM templates and is not the authoring branch.

## 8 Run and verify

Run `PL_MASTER` manually and record its Run ID. Verify expected audit rows, non-empty intended outputs, Gold grain checks, the Logic Apps run and delivery through the configured email connector. Stop and diagnose if source inputs or required metadata are missing. Leave the schedule stopped until these checks succeed.

The packaged trigger retains the original start time and UTC+7 time zone but is stopped. Review the start time and eight-hour recurrence before enabling it. Do not run the old and new schedules simultaneously against the same tables and watermarks.
