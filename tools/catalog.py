import json

from db import ROOT, readonly_connection


def load_catalog():
    schema = json.loads((ROOT / 'catalog/schema.json').read_text())
    return {**schema, **json.loads((ROOT / 'catalog/metrics.json').read_text())}


def check_schema(connection):
    catalog = load_catalog()
    with connection.cursor() as cursor:
        cursor.execute('''SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns WHERE table_schema = %s''', (catalog['schema'],))
        actual = {(t, c): (kind, nullable) for t, c, kind, nullable in cursor.fetchall()}
        cursor.execute('''SELECT t.relname, a.attname
            FROM pg_catalog.pg_constraint k
            JOIN pg_catalog.pg_class t ON t.oid=k.conrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
            JOIN pg_catalog.pg_attribute a ON a.attrelid=t.oid AND a.attnum=ANY(k.conkey)
            WHERE n.nspname=%s AND k.contype='p' ''', (catalog['schema'],))
        keys = set(cursor.fetchall())
        cursor.execute('''SELECT t.relname, a.attname, ft.relname, fa.attname
            FROM pg_catalog.pg_constraint k
            JOIN pg_catalog.pg_class t ON t.oid=k.conrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
            JOIN pg_catalog.pg_class ft ON ft.oid=k.confrelid
            JOIN pg_catalog.pg_namespace fn ON fn.oid=ft.relnamespace
            JOIN LATERAL unnest(k.conkey, k.confkey) AS cols(src,dst) ON true
            JOIN pg_catalog.pg_attribute a ON a.attrelid=t.oid AND a.attnum=cols.src
            JOIN pg_catalog.pg_attribute fa ON fa.attrelid=ft.oid AND fa.attnum=cols.dst
            WHERE n.nspname=%s AND fn.nspname=%s AND k.contype='f' ''', (catalog['schema'], catalog['schema']))
        relationships = {f'{t}.{c}->{ft}.{fc}' for t, c, ft, fc in cursor.fetchall()}
    errors = []
    for table, definition in catalog['tables'].items():
        for column, kind in definition['columns'].items():
            if actual.get((table, column)) != (kind, 'NO'):
                errors.append(f'{table}.{column}: missing or type/nullability differs')
        if {c for t, c in keys if t == table} != set(definition['primary_key']):
            errors.append(f'{table}: primary key differs')
    for rel in catalog['relationships']:
        if f"{rel['from']}->{rel['to']}" not in relationships:
            errors.append(f"Missing relationship: {rel['from']} -> {rel['to']}")
    return {'valid': not errors, 'errors': errors, 'checked_tables': list(catalog['tables'])}


def verify_schema():
    """Compare catalog columns, types, non-null constraints, primary keys and foreign keys with Neon."""
    with readonly_connection() as connection:
        return check_schema(connection)


def get_catalog():
    """Use before writing SQL. Return verified tables, relationships, metrics and sample SQL.

    Frame SQL from this context, then call run_readonly_query. The catalog is
    an allowlist; only these tables and columns may be queried.
    """
    verification = verify_schema()
    if not verification['valid']:
        return {'error': 'Schema catalog is out of date.', 'verification': verification}
    return {**load_catalog(), 'verification': verification,
            'query_rules': 'One SELECT; fully qualify tables with sales_demo; no CTEs, subqueries, UNION, SELECT *, or arbitrary functions. Use explicit JOIN ON conditions. Maximum 200 result rows. Revenue definitions guide the model; the SQL validator does not enforce metric meaning.'}
