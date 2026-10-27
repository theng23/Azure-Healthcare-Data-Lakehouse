# Move from two repositories to one

Use `caresync-e2e` as the suggested new repository name. This package is a combined working tree prepared from the two uploaded archives. It does not contain Git history and has not modified either original GitHub repository.

## File mapping

| Original location | Monorepo location |
| --- | --- |
| `health_project_repo/pipeline/PL_*.json` | `adf/pipeline/` |
| `health_project_repo/dataset/`, `linkedService/`, `factory/`, `trigger/` | Corresponding folders under `adf/` |
| `health_project_repo/publish_config.json` | `adf/publish_config.json` |
| `caresync-adb-repo/Landing_to_Bronze.ipynb` | `databricks/notebooks/Landing_to_Bronze.ipynb` |
| `caresync-adb-repo/Bronze_to_Silver.ipynb` | `databricks/notebooks/Bronze_to_Silver.ipynb` |
| `caresync-adb-repo/Gold/NB_*.ipynb` | `databricks/notebooks/Gold/` |
| `caresync-adb-repo/Calendar Dimension Build.ipynb` | `databricks/notebooks/setup/Calendar_Dimension_Build.ipynb` |
| `caresync-adb-repo/Gold/sttm_silver_to_gold.xlsx` | `docs/data-model/sttm_silver_to_gold.xlsx` |
| Alternate and experimental notebooks | `archive/notebooks/` |
| ADF `test.json` | `archive/adf/test.json` |
| Telesales and Do Not Call SQL | `archive/unrelated-sql/` |

The two uploaded archives contained the same non-Git source files, arranged differently. Only one copy of each source file is used. Original file digests are recorded in `docs/provenance/source-files.json`.

## Changes required for the merged layout

1. Notebook paths now use the factory global `databricks_notebook_root` instead of the old `/caresync-repo/caresync-adb-repo` path. The new default deployment root is `/Shared/caresync/databricks`.
2. Source metadata lookup now filters `stage = 'SOURCE_TO_SILVER'` as well as the source system and active flag.
3. `PL_SEND_EMAIL` now retrieves the Logic Apps callback URL from Key Vault with the ADF managed identity. The original signed URL and personal recipient values are not distributed. Rotate the original callback signature.
4. The CSV Copy activity uses a null file-time boundary for `FULL` loads instead of an unset watermark variable.
5. The eight-hour trigger is packaged as stopped. The original recurrence and start time are retained for review.
6. Environment resource identifiers are placeholders populated by `tools/configure_environment.py`. Existing linked-service and secret-reference names are retained.
7. Notebook execution outputs are cleared. One inaccurate calendar comment in the Gold notebook is corrected; Gold transformation SQL is retained.
8. Local validation, Databricks deployment workflows, setup examples, operational queries, diagrams and documentation are added. These did not exist as GitHub Actions workflows in the supplied snapshots.

The data-processing and watermark algorithms otherwise remain the original implementation. Limitations are documented rather than represented as already solved.

## Create the unified GitHub repository

1. Extract the package. Open the **`caresync-e2e` folder itself** in VS Code; it must contain `README.md`, `adf/`, `databricks/` and `.github/` at its root.
2. Follow `docs/deployment.md` to configure non-secret values and run local validation.
3. Create an empty GitHub repository named `caresync-e2e` in the intended account. Do not initialize it with a separate README if you use the following new-repository commands.
4. In the extracted folder, run these commands in PowerShell or a terminal:

```bash
git init -b main
git add .
git commit -m "Combine CareSync ADF and Databricks project"
git remote add origin https://github.com/theng23/caresync-e2e.git
git push -u origin main
```

The URL is a suggested destination based on the existing owner; create that repository first or replace the URL. These commands apply to a new extracted directory and an empty remote. They do not merge the old commit histories. If history preservation is a requirement, perform a separate Git subtree/history migration before the final layout commit.

## Reconnect the platforms

1. Keep the old schedule stopped while testing the new configuration. Retain the previous setup for recovery.
2. Configure GitHub environment `dev` and its Databricks values. Run the Databricks deployment workflow and verify the new notebook paths.
3. Point ADF Git configuration to the unified repository, `main`, root folder `/adf`, publish branch `adf_publish`.
4. When reconnecting, do not import the old live factory into the new Git root over the packaged files. Review the ADF import option and the selected resources before committing any imported contents.
5. Check the factory name, linked services, global parameters and secret permissions. Validate and publish ADF.
6. Run the manual smoke test and reconcile results against the expected data. Review the modified CSV FULL expression and runtime Key Vault lookup in ADF.
7. Enable one schedule only after verification. Keep the original repositories available until the new path has been accepted.

ADF reads only `/adf`; GitHub Actions deploys only `databricks/notebooks`. If you also use Databricks Git folders for interactive development, point them to the same unified repository. Keep the ADF runtime path aligned with the chosen deployment method instead of mixing a personal Git-folder path and the shared imported notebook path.
