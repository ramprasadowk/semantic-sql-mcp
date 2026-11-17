"""Apply the versioned demo migration and verify its known results."""
import argparse
import hashlib
from decimal import Decimal
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', default='.env.local')
    args = parser.parse_args()
    env = dotenv_values(ROOT / args.env_file)
    url = env.get('DATABASE_URL_UNPOOLED')
    if not url:
        raise SystemExit('Missing DATABASE_URL_UNPOOLED in the selected env file.')
    migration = ROOT / 'sql/001_sales_demo.sql'
    sql = migration.read_text()
    checksum = hashlib.sha256(sql.encode()).hexdigest()
    try:
        with psycopg2.connect(url, connect_timeout=20) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '30s'")
                cursor.execute("SELECT pg_advisory_xact_lock(78012026)")
                cursor.execute('''CREATE TABLE IF NOT EXISTS public.mcp_demo_migrations (
                    version text PRIMARY KEY, checksum text NOT NULL,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )''')
                cursor.execute('SELECT checksum FROM public.mcp_demo_migrations WHERE version=%s', (migration.name,))
                existing = cursor.fetchone()
                if existing and existing[0] != checksum:
                    raise ValueError('Applied migration checksum differs; create a new migration.')
                if not existing:
                    cursor.execute(sql)
                    cursor.execute('INSERT INTO public.mcp_demo_migrations(version, checksum) VALUES (%s,%s)', (migration.name, checksum))
                counts = {}
                for table in ('customers', 'products', 'orders', 'order_items'):
                    # These identifiers come exclusively from the fixed list above.
                    cursor.execute('SELECT count(*) FROM sales_demo.' + table)
                    counts[table] = cursor.fetchone()[0]
                cursor.execute('''SELECT sum(i.quantity * i.unit_price), count(DISTINCT o.order_id)
                    FROM sales_demo.orders o JOIN sales_demo.order_items i USING (order_id)
                    WHERE o.status = 'completed' ''')
                revenue, orders = cursor.fetchone()
                if counts != dict(customers=3, products=3, orders=6, order_items=8):
                    raise ValueError('Demo row counts differ from the expected seed data.')
                if revenue != Decimal('700.00') or orders != 4:
                    raise ValueError('Revenue verification failed.')
        print('Migration already applied.' if existing else 'Migration applied.')
        print('Verified: 3 customers, 3 products, 6 orders, 8 order items.')
        print('Completed-order revenue: USD 700.00; completed orders: 4.')
    except Exception as error:
        # Driver exceptions can contain connection details. Never print them.
        raise SystemExit('Database setup failed (' + type(error).__name__ + '). No credentials were logged.') from None


if __name__ == '__main__':
    main()
