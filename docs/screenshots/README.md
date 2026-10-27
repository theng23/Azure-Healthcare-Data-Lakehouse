# Add the five ADF screenshots

The package includes generated logical diagrams under `../images/`. Add actual ADF canvas captures here when you want to show the interface you built. No actual pipeline screenshots were present in the uploaded source archives.

| Pipeline | Screenshot filename |
| --- | --- |
| `PL_MASTER` | `01-pl-master-adf.png` |
| `PL_SOURCE_TO_SILVER_MAIN` | `02-pl-source-to-silver-main-adf.png` |
| `PL_SOURCE_TO_SILVER_INNER` | `03-pl-source-to-silver-inner-adf.png` |
| `PL_SILVER_TO_GOLD` | `04-pl-silver-to-gold-adf.png` |
| `PL_SEND_EMAIL` | `05-pl-send-email-adf.png` |

Open each pipeline in ADF Author, choose a zoom that makes activity labels readable and capture the whole canvas. For loops and switches, also capture the expanded inner activities if you want to show their implementation. Use PNG and keep the pipeline name visible. Exclude signed URLs, tokens, recipient information and unrelated account details from the capture.

After adding the actual files, insert the corresponding snippets into the root README, next to each generated diagram:

```markdown
![PL_MASTER in Azure Data Factory](docs/screenshots/01-pl-master-adf.png)
![PL_SOURCE_TO_SILVER_MAIN in Azure Data Factory](docs/screenshots/02-pl-source-to-silver-main-adf.png)
![PL_SOURCE_TO_SILVER_INNER in Azure Data Factory](docs/screenshots/03-pl-source-to-silver-inner-adf.png)
![PL_SILVER_TO_GOLD in Azure Data Factory](docs/screenshots/04-pl-silver-to-gold-adf.png)
![PL_SEND_EMAIL in Azure Data Factory](docs/screenshots/05-pl-send-email-adf.png)
```

Do not add these image references until the files exist. A design canvas shows the configuration. To demonstrate execution, capture the actual ADF Monitor run with its date, state and activity results separately and describe the observed result accurately.
