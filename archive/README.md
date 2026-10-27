# Preserved source files

This folder retains files that are outside the active deployment path.

- `adf/test.json`: incomplete experimental Copy activity from the ADF repository.
- `notebooks/`: `My_` variants, the older calendar notebook and the exploratory test notebook. Notebook outputs were cleared.
- `unrelated-sql/`: original telesales and Do Not Call queries. No supplied CareSync pipeline references these files, so they are excluded from deployment and the healthcare data flow.
- `original-readmes/`: both original short README files.

`../docs/provenance/source-files.json` records the original paths and SHA-256 digests. These are original-file digests, not checksums of normalized notebooks in this package. No nested Git metadata or original credential-bearing factory JSON is distributed.
