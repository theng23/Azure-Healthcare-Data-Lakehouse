# Logic Apps notification contract

The original source supplied an ADF HTTP caller, but no Logic Apps workflow export. Configure the receiving workflow separately.

1. Create a workflow with the HTTP trigger **When an HTTP request is received**.
2. Use [the request schema](logic-app-request.schema.json) as the trigger body schema.
3. Create an HTML table from `status_table` and combine it with `body_header` and `body_footer`.
4. Configure the email action with `email_receipients` as the destination and `subject` as the email subject. Authorize the connector using the intended sender account.
5. Save the workflow and put its complete HTTP callback URL into Key Vault as `logic-app-callback-url`.
6. Grant the ADF managed identity secret read access. Set the factory globals `key_vault_url` and `logic_app_secret_name` to the matching vault and secret name.
7. Execute a development master run and verify the Logic Apps trigger, email action and resulting delivery.

The contract intentionally preserves the original field spelling `email_receipients`. The ADF global parameter is named `email_receipent`; `tools/configure_environment.py` maps it from `email_recipient` in the local config file.

`PL_SEND_EMAIL` now reads the secret using an MSI-authenticated Web activity and sends the HTTP request with secure input/output. The previous signed URL is absent from the merged factory JSON. Rotate its old signature, because removing a value from a new commit does not revoke existing credentials.

The master currently calls this pipeline only when Gold succeeds. For broader alert coverage, add terminal-path handling that preserves the master failure status, then test source failure, Gold failure, metadata failure and notification failure independently. This extension is not represented as already implemented.
