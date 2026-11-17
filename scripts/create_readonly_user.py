"""Create a least-privilege tool login and store it privately in .env.local."""
import secrets
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg2
from psycopg2 import sql
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / '.env.local'
    env = dotenv_values(path)
    if env.get('MCP_DATABASE_URL'):
        print('MCP_DATABASE_URL already exists; preserved. No role changes made.')
        return
    admin = env.get('DATABASE_URL_UNPOOLED')
    if not admin:
        raise SystemExit('Missing setup connection.')
    password = secrets.token_urlsafe(32)
    role = 'sales_mcp_reader'
    try:
        with psycopg2.connect(admin, connect_timeout=20) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,))
                if cursor.fetchone():
                    raise ValueError('Role exists without a local MCP connection; refusing to rotate credentials.')
                cursor.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(role), sql.Literal(password)))
                cursor.execute(sql.SQL('ALTER ROLE {} SET default_transaction_read_only=on').format(sql.Identifier(role)))
                cursor.execute(sql.SQL("ALTER ROLE {} SET statement_timeout='5s'").format(sql.Identifier(role)))
                cursor.execute('SELECT current_database()')
                database = cursor.fetchone()[0]
                cursor.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(database), sql.Identifier(role)))
                cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA sales_demo TO {}').format(sql.Identifier(role)))
                for table in ('customers', 'products', 'orders', 'order_items'):
                    cursor.execute(sql.SQL('GRANT SELECT ON sales_demo.{} TO {}').format(sql.Identifier(table), sql.Identifier(role)))
        parts = urlsplit(env['DATABASE_URL'])
        host = parts.hostname + (f':{parts.port}' if parts.port else '')
        url = urlunsplit((parts.scheme, f'{role}:{quote(password, safe="")}@{host}', parts.path, parts.query, parts.fragment))
        set_key(str(path), 'MCP_DATABASE_URL', url)
        path.chmod(0o600)
        print('Read-only login created; MCP_DATABASE_URL saved privately. Existing settings preserved.')
    except Exception as error:
        raise SystemExit(f'Read-only setup failed ({type(error).__name__}); no credentials logged.') from None


if __name__ == '__main__':
    main()
