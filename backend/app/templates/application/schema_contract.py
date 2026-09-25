"""Conservative data migration contract, shared by compiler and deployed runtime."""
def compatibility(previous, current):
    if not previous:
        return []
    issues = []
    entities = {e['name']: e for e in current['entities']}
    for old in previous['entities']:
        new = entities.get(old['name'])
        if not new:
            issues.append(f"Removing {old['name']} requires a reviewed migration. Keep the entity to preserve access to its records.")
            continue
        fields = {f['name']: f for f in new['fields']}
        for field in old['fields']:
            updated = fields.get(field['name'])
            if not updated or updated['kind'] != field['kind'] or updated.get('reference') != field.get('reference'):
                issues.append(f"Removing or changing the type/reference of {old['name']}.{field['name']} requires a migration.")
            elif (not field['required'] and updated['required']) or not set(field.get('options', [])) <= set(updated.get('options', [])):
                issues.append(f"Tightening constraints on {old['name']}.{field['name']} needs existing-data validation.")
        for field in new['fields']:
            if field['name'] not in {f['name'] for f in old['fields']} and field['required']:
                issues.append(f"New field {old['name']}.{field['name']} must initially be optional for existing records.")
    if not set(previous['roles']) <= set(current['roles']):
        issues.append('Removing roles requires migrating existing accounts first.')
    return issues
