#!/usr/bin/env python3
"""Populate ADF authoring JSON from a local, non-secret environment description.

Usage: python tools/configure_environment.py --config config/environment.local.json
Run from any directory. This script does not call Azure or deploy anything.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    required = json.loads((ROOT / 'config/environment.example.json').read_text())
    missing = [k for k in required if not isinstance(config.get(k), str) or not config[k].strip() or '__' in config[k]]
    if missing:
        parser.error('Fill all environment values before applying: ' + ', '.join(missing))
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{1,61}[A-Za-z0-9])?', config['factory_name']):
        parser.error('factory_name must be a valid ADF resource name')
    if not config['databricks_notebook_root'].startswith('/'):
        parser.error('databricks_notebook_root must be an absolute workspace path')
    for key in ['adls_url', 'key_vault_url', 'databricks_host']:
        if not config[key].startswith('https://'):
            parser.error(f'{key} must start with https://')
    if '?' in config['key_vault_url']:
        parser.error('key_vault_url must be a vault base URL, without query parameters')
    services = {
        'LS_ADLS': {'url': config['adls_url'].rstrip('/') + '/'},
        'LS_AzureKeyVault1': {'baseUrl': config['key_vault_url'].rstrip('/') + '/'},
        'LS_AzureSqlDatabase1': {'server': config['azure_sql_server'], 'database': config['azure_sql_database'], 'userName': config['azure_sql_username']},
        'LS_PostgreSql1': {'server': config['postgres_server'], 'database': config['postgres_database'], 'username': config['postgres_username']},
        'AzureDatabricks1': {'domain': config['databricks_host'].rstrip('/'), 'existingClusterId': config['databricks_cluster_id']},
    }
    # Read and validate every target before the first write.
    updates = []
    for name, values in services.items():
        path = ROOT / 'adf/linkedService' / f'{name}.json'
        data = json.loads(path.read_text())
        data['properties']['typeProperties'].update(values)
        updates.append((path, data))
    factory_files = list((ROOT / 'adf/factory').glob('*.json'))
    if len(factory_files) != 1:
        parser.error('Expected exactly one authoring factory JSON')
    factory = json.loads(factory_files[0].read_text())
    factory['name'] = config['factory_name']
    factory['location'] = config['factory_location']
    params = factory['properties']['globalParameters']
    for key, value in {
        'env': config['environment'], 'email_receipent': config['email_recipient'],
        'databricks_notebook_root': config['databricks_notebook_root'].rstrip('/'),
        'key_vault_url': config['key_vault_url'].rstrip('/') + '/',
        'logic_app_secret_name': config['logic_app_secret_name'],
    }.items():
        params[key]['value'] = value
    new_factory = ROOT / 'adf/factory' / f"{config['factory_name']}.json"
    updates.append((new_factory, factory))
    for path, data in updates:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if factory_files[0] != new_factory:
        factory_files[0].unlink()
    print('Updated five linked services and factory parameters. No cloud resources were changed.')
    print('Keep the Logic Apps callback URL in Key Vault. It is not an environment JSON field.')


if __name__ == '__main__':
    main()
