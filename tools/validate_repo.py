#!/usr/bin/env python3
"""Check local ADF references, activity graphs and notebook contracts.

Uses only the Python standard library. This does not execute ADF, Spark or SQL.
"""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERRORS = []


def check(condition, message):
    if not condition:
        ERRORS.append(message)


def read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError) as exc:
        ERRORS.append(f'{path.relative_to(ROOT)}: {exc}')
        return {}


def all_objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from all_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_objects(child)


def validate_activity_scope(items, label):
    names = [a['name'] for a in items]
    check(len(names) == len(set(names)), f'{label}: duplicate activity names')
    graph = {a['name']: [d['activity'] for d in a.get('dependsOn', [])] for a in items}
    visited, active = set(), set()

    def visit(name):
        if name in active:
            ERRORS.append(f'{label}: activity dependency cycle at {name}')
            return
        if name in visited:
            return
        active.add(name)
        for dependency in graph.get(name, []):
            check(dependency in graph, f'{label}/{name}: missing dependency {dependency}')
            if dependency in graph:
                visit(dependency)
        active.remove(name)
        visited.add(name)

    for name in names:
        visit(name)
    for activity in items:
        props = activity.get('typeProperties', {})
        for key in ['activities', 'ifTrueActivities', 'ifFalseActivities', 'defaultActivities']:
            if key in props:
                validate_activity_scope(props[key], label + '/' + activity['name'] + '/' + key)
        for case in props.get('cases', []):
            validate_activity_scope(case.get('activities', []), label + '/' + activity['name'] + '/' + case['value'])


def main():
    resources = {}
    for folder in ['pipeline', 'dataset', 'linkedService', 'factory', 'trigger']:
        resources[folder] = {}
        for path in sorted((ROOT / 'adf' / folder).glob('*.json')):
            data = read(path)
            check(data.get('name') == path.stem, f'{path}: filename and resource name differ')
            resources[folder][path.stem] = data
    expected = {'PL_MASTER', 'PL_SOURCE_TO_SILVER_MAIN', 'PL_SOURCE_TO_SILVER_INNER', 'PL_SILVER_TO_GOLD', 'PL_SEND_EMAIL'}
    check(set(resources['pipeline']) == expected, 'Expected exactly the five CareSync pipelines')
    check(len(resources['factory']) == 1, 'Expected one ADF authoring factory')
    globals_found = set()
    for data in resources['factory'].values():
        globals_found.update(data.get('properties', {}).get('globalParameters', {}))
    ref_types = {'PipelineReference': 'pipeline', 'DatasetReference': 'dataset', 'LinkedServiceReference': 'linkedService'}
    nb_activities = []
    for folder, entries in resources.items():
        for name, data in entries.items():
            for obj in all_objects(data):
                if obj.get('type') in ref_types:
                    target = ref_types[obj['type']]
                    check(obj.get('referenceName') in resources[target], f'{name}: unresolved {target} {obj.get("referenceName")}')
                if obj.get('type') == 'DatabricksNotebook':
                    nb_activities.append(obj)
                for value in obj.values():
                    if isinstance(value, str):
                        for gp in re.findall(r'globalParameters\.([A-Za-z_][A-Za-z0-9_]*)', value):
                            check(gp in globals_found, f'{name}: undefined global parameter {gp}')
            if folder == 'pipeline':
                validate_activity_scope(data.get('properties', {}).get('activities', []), name)
    for activity in nb_activities:
        value = activity['typeProperties']['notebookPath']
        check(isinstance(value, dict) and 'databricks_notebook_root' in value.get('value', ''), f'{activity["name"]}: notebook path must use shared root')
    for name in ['Landing_to_Bronze', 'Bronze_to_Silver']:
        path = ROOT / 'databricks/notebooks' / f'{name}.ipynb'
        check(path.is_file(), f'Missing notebook {name}')
        notebook = read(path)
        text = '\n'.join(''.join(c.get('source', [])) for c in notebook.get('cells', []))
        widgets = set(re.findall(r'dbutils\.widgets\.text\("(\w+)"', text))
        activity = next(a for a in nb_activities if a['name'] == name.replace('_', ' '))
        required = set(activity['typeProperties'].get('baseParameters', {}))
        check(required <= widgets, f'{name}: missing notebook widget(s) {required - widgets}')
    for gold in ['patient_360', 'hospital_daily_summary', 'lab_test_trends']:
        check((ROOT / f'databricks/notebooks/Gold/NB_{gold}.ipynb').is_file(), f'Missing Gold notebook {gold}')
    notebooks = list((ROOT / 'databricks/notebooks').rglob('*.ipynb'))
    for path in notebooks:
        data = read(path)
        language = data.get('metadata', {}).get('language_info', {}).get('name', 'python')
        for i, cell in enumerate(data.get('cells', [])):
            if cell.get('cell_type') != 'code':
                continue
            check(not cell.get('outputs'), f'{path.name}: committed notebook outputs')
            code = ''.join(cell.get('source', []))
            if language == 'python' and not code.lstrip().startswith(('%', '!')):
                try:
                    ast.parse(code)
                except SyntaxError as exc:
                    ERRORS.append(f'{path.name} cell {i}: {exc}')
    for folder in ['adf', 'databricks/notebooks', 'config']:
        for path in (ROOT / folder).rglob('*'):
            if path.suffix not in {'.json', '.ipynb'} or path.name == 'environment.local.json':
                continue
            text = path.read_text()
            check(not re.search(r'[?&]sig=[A-Za-z0-9_%+/=-]+', text), f'{path}: Logic Apps signature found')
            check(not re.search(r'\bdapi[a-zA-Z0-9]{20,}\b', text), f'{path}: Databricks token found')
    if ERRORS:
        for error in ERRORS:
            print('ERROR:', error, file=sys.stderr)
        return 1
    print(f'PASS: {len(resources["pipeline"])} pipelines; {len(resources["dataset"])} datasets; {len(resources["linkedService"])} linked services; {len(notebooks)} deployable notebooks.')
    print('Checked local references, dependency graphs, global parameters, widget mappings, Python syntax and secret patterns.')
    print('Cloud execution, SQL semantics and source data correctness require the Azure smoke run.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
