"""A deliberately small SELECT dialect, parsed before it reaches PostgreSQL."""
from datetime import date, datetime
from decimal import Decimal

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify

from db import readonly_connection
from tools.catalog import check_schema, load_catalog

ALLOWED_FUNCTIONS = {'SUM', 'COUNT', 'AVG', 'MIN', 'MAX', 'COALESCE', 'NULLIF', 'ROUND', 'DATE_TRUNC', 'TIMESTAMP_TRUNC'}
ALLOWED_NODES = set('Select Alias Column Identifier Table TableAlias From Join Where Group Having Order Ordered Limit Offset Literal Boolean Null Distinct Sum Count Avg Min Max Coalesce Nullif Round DateTrunc TimestampTrunc Var EQ NEQ GT GTE LT LTE And Or Not Paren Add Sub Mul Div Mod Neg Between In Is Like ILike Case If'.split())


def validate_query(sql):
    if len(sql) > 12000:
        raise ValueError('SQL exceeds the 12000 character limit.')
    try:
        statements = sqlglot.parse(sql, read='postgres')
        if len(statements) != 1 or not isinstance(statements[0], exp.Select):
            raise ValueError('Only one SELECT statement is allowed.')
        tree = statements[0]
        if len(list(tree.find_all(exp.Select))) != 1 or tree.find(exp.With):
            raise ValueError('CTEs and subqueries are not supported in this demo.')
        if any(tree.args.get(k) for k in ('into', 'locks')):
            raise ValueError('SELECT INTO and row locks are forbidden.')
        if any(tree.find_all(exp.Star)):
            raise ValueError('Select explicit columns; use COUNT(order_id) instead of COUNT(*).')
        catalog = load_catalog()
        tables = list(tree.find_all(exp.Table))
        if not tables:
            raise ValueError('Query at least one catalogued table.')
        for table in tables:
            if table.catalog or table.db != catalog['schema'] or table.name not in catalog['tables'] or not isinstance(table.this, exp.Identifier):
                raise ValueError('Only fully qualified sales_demo catalog tables are allowed.')
        for function in tree.find_all(exp.Func):
            if function.sql_name() not in ALLOWED_FUNCTIONS:
                raise ValueError('Unsupported function. Use simple aggregates or DATE_TRUNC.')
        # Block schema-qualified functions, casts, special operators, and exotic clauses.
        for node in tree.walk():
            if type(node).__name__ not in ALLOWED_NODES:
                raise ValueError('Unsupported SQL construct: ' + type(node).__name__)
            if isinstance(node, exp.Var) and not isinstance(node.parent, (exp.TimestampTrunc, exp.DateTrunc)):
                raise ValueError('Only DATE_TRUNC date units are supported.')
            if isinstance(node, (exp.Dot, exp.Cast, exp.TryCast, exp.Command, exp.Parameter, exp.Placeholder)):
                raise ValueError('Qualified functions, casts, parameters and commands are unsupported.')
            if isinstance(node, exp.Column) and (node.db or node.catalog):
                raise ValueError('Use table aliases for column references.')
        for join in tree.find_all(exp.Join):
            if not join.args.get('on') or join.args.get('method'):
                raise ValueError('Use explicit JOIN ON conditions.')
        mapping = {catalog['schema']: {name: definition['columns'] for name, definition in catalog['tables'].items()}}
        qualify(tree.copy(), dialect='postgres', schema=mapping, validate_qualify_columns=True)
        return tree.sql(dialect='postgres')
    except ValueError:
        raise
    except Exception:
        raise ValueError('SQL could not be validated against the schema catalog. Check column names and aliases.') from None


def run_readonly_query(sql: str, max_rows: int = 100) -> dict:
    """Run a single catalog-validated SELECT. Call get_catalog first to obtain business definitions.

    Returns columns and rows, capped at 200 rows, with a truncation flag.
    Monetary decimals are strings to preserve precision. No writes, system
    tables, arbitrary functions, subqueries or CTEs. SQL must use sales_demo tables.
    """
    if not isinstance(max_rows, int) or isinstance(max_rows, bool) or not 1 <= max_rows <= 200:
        raise ValueError('max_rows must be between 1 and 200.')
    validated = validate_query(sql)
    with readonly_connection() as connection:
        verification = check_schema(connection)
        if not verification['valid']:
            raise ValueError('Schema differs from the catalog; query refused. Run verify_schema.')
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM (' + validated + ') AS mcp_result LIMIT %s', (max_rows + 1,))
            columns = [column.name for column in cursor.description]
            rows = cursor.fetchall()
    def encode(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return value
    return {'columns': columns, 'rows': [[encode(v) for v in row] for row in rows[:max_rows]],
            'row_count': min(len(rows), max_rows), 'truncated': len(rows) > max_rows}
