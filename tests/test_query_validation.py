import unittest

from tools.catalog import load_catalog
from tools.query import validate_query


class QueryValidationTests(unittest.TestCase):
    def test_documented_examples(self):
        for example in load_catalog()['examples']:
            self.assertTrue(validate_query(example['sql']))

    def test_rejects_writes_and_escape_routes(self):
        queries = [
            'DELETE FROM sales_demo.orders',
            'SELECT order_id FROM sales_demo.orders; DROP TABLE sales_demo.orders',
            'SELECT order_id INTO stolen FROM sales_demo.orders',
            'SELECT order_id FROM sales_demo.orders FOR UPDATE',
            'WITH x AS (DELETE FROM sales_demo.orders RETURNING order_id) SELECT order_id FROM x',
            'SELECT pg_sleep(10) FROM sales_demo.orders',
            "SELECT pg_catalog.set_config('search_path', 'public', false) FROM sales_demo.orders",
            'SELECT * FROM sales_demo.orders',
            'SELECT password FROM sales_demo.customers',
            'SELECT order_id FROM public.orders',
            'SELECT oid FROM pg_catalog.pg_class',
            'SELECT order_id FROM orders',
            'SELECT (SELECT order_id FROM sales_demo.orders) FROM sales_demo.orders',
            'SELECT order_id FROM sales_demo.orders UNION SELECT order_id FROM sales_demo.orders',
            "SELECT order_id::text FROM sales_demo.orders",
            'SELECT o.order_id FROM sales_demo.orders o, sales_demo.order_items i',
        ]
        for query in queries:
            with self.subTest(query=query), self.assertRaises(ValueError):
                validate_query(query)


if __name__ == '__main__':
    unittest.main()
