"""Database connections for tools; never fall back to the setup/admin login."""
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent


@contextmanager
def readonly_connection():
    config = dotenv_values(ROOT / '.env.local')
    url = os.environ.get('MCP_DATABASE_URL') or config.get('MCP_DATABASE_URL')
    if not url:
        raise ValueError('MCP_DATABASE_URL is missing. Run scripts/create_readonly_user.py first.')
    connection = None
    try:
        connection = psycopg2.connect(url, connect_timeout=15, application_name='sales-mcp')
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '1s'")
            cursor.execute("SET LOCAL search_path = sales_demo, pg_catalog")
        yield connection
    except psycopg2.Error:
        raise ValueError('Database request failed or timed out. Connection details were withheld.') from None
    finally:
        if connection is not None:
            connection.rollback()
            connection.close()
