"""Conservative document cleanup; saved evidence and report versions stay intact."""
import copy
import json
import re


def fingerprint(value):
    if isinstance(value, str):
        return re.sub(r'\s+', ' ', value).strip()
    if isinstance(value, list):
        return tuple(fingerprint(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((key, fingerprint(item)) for key, item in value.items()))
    return json.dumps(value, sort_keys=True)


def unique(values):
    seen = set()
    result = []
    for value in values:
        key = fingerprint(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def prepare_report(report):
    """Remove exact repetition, never summarize or discard distinct requirements."""
    result = copy.deepcopy(report)
    seen_artifacts = set()
    for section in result['sections']:
        paragraphs = unique(re.split(r'\n\s*\n', section['narrative']))
        section['narrative'] = '\n\n'.join(paragraphs)
        narrative_keys = {fingerprint(p) for p in paragraphs}
        section['items'] = [item for item in unique(section['items'])
                            if fingerprint(item) not in narrative_keys]
        section['basis'] = '\n'.join(unique(section['basis'].splitlines()))
        tables = []
        for table in section['tables']:
            table['rows'] = unique(table['rows'])
            if not table['columns'] or not table['rows']:
                continue
            existing = next((t for t in tables if fingerprint([t['title'], t['columns']]) ==
                             fingerprint([table['title'], table['columns']])), None)
            if existing is not None:
                existing['rows'] = unique([*existing['rows'], *table['rows']])
            else:
                tables.append(table)
        section['tables'] = tables
        for kind in ('diagrams', 'screens', 'code_assets'):
            artifacts = []
            for artifact in section[kind]:
                if kind == 'diagrams':
                    artifact['edges'] = unique(artifact['edges'])
                key = (kind, json.dumps(artifact, sort_keys=True) if kind == 'code_assets' else fingerprint(artifact))
                if key not in seen_artifacts:
                    seen_artifacts.add(key)
                    artifacts.append(artifact)
            section[kind] = artifacts
    for section in result['sections']:
        if section.get('key') == 'appendix':
            for table in section['tables']:
                if table['title'] == 'Generated artifact index':
                    table['rows'] = [[owner['title'], artifact.get('title', artifact.get('name', artifact.get('filename', '')))]
                                     for owner in result['sections']
                                     for kind in ('diagrams', 'screens', 'code_assets') for artifact in owner[kind]]
    return result
