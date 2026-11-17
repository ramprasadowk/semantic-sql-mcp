"""Exercise the real stdio MCP protocol, tools and Neon connection."""
import asyncio
import json
import sys
import argparse
import subprocess
import socket
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]


def payload(result):
    assert not result.is_error, 'MCP tool returned an error.'
    return json.loads(next(block.text for block in result.content if block.type == 'text'))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--http', action='store_true')
    args = parser.parse_args()
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / 'main.py')], cwd=ROOT)
    process = None
    if args.http:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen([sys.executable, str(ROOT / 'main.py'), '--transport', 'streamable-http', '--port', str(port)], cwd=ROOT)
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.1):
                    break
            except OSError:
                await asyncio.sleep(0.1)
        params = f'http://127.0.0.1:{port}/mcp'
    try:
        await exercise(params)
    finally:
        if process:
            process.terminate()
            process.wait(timeout=10)


async def exercise(params):
    sys.path.insert(0, str(ROOT))
    from db import readonly_connection
    with readonly_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user, current_setting('transaction_read_only'), has_table_privilege(current_user, 'sales_demo.orders', 'SELECT'), has_table_privilege(current_user, 'sales_demo.orders', 'INSERT,UPDATE,DELETE,TRUNCATE')")
            role, readonly, can_read, can_write = cursor.fetchone()
            assert role == 'sales_mcp_reader' and readonly == 'on' and can_read and not can_write
    async with Client(params) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {'get_catalog', 'verify_schema', 'run_readonly_query'}
        assert all(tool.annotations.read_only_hint for tool in tools.tools)
        catalog = payload(await client.call_tool('get_catalog', {}))
        assert catalog['verification']['valid']
        verified = payload(await client.call_tool('verify_schema', {}))
        assert verified['valid']
        total = payload(await client.call_tool('run_readonly_query', {'sql': catalog['examples'][0]['sql']}))
        assert total['rows'] == [['700.00', 4]], total
        monthly = payload(await client.call_tool('run_readonly_query', {'sql': catalog['examples'][1]['sql']}))
        assert [row[1] for row in monthly['rows']] == ['250.00', '450.00'], monthly
        limited = payload(await client.call_tool('run_readonly_query', {'sql': 'SELECT order_id FROM sales_demo.orders ORDER BY order_id', 'max_rows': 2}))
        assert limited['row_count'] == 2 and limited['truncated']
        rejected = await client.call_tool('run_readonly_query', {'sql': 'DELETE FROM sales_demo.orders'})
        assert rejected.is_error
        print('PASS: MCP discovery, catalog, schema, revenue, monthly totals, truncation, and write rejection.')


if __name__ == '__main__':
    asyncio.run(main())
