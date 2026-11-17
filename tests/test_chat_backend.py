import json
import unittest
from types import SimpleNamespace as Item
from unittest.mock import AsyncMock

from chat_backend import ChatError, run_turn


def response(*calls, answer=""):
    return Item(output=list(calls), output_text=answer, status="completed")


def call(name, arguments, identifier):
    return Item(type="function_call", name=name, arguments=json.dumps(arguments), call_id=identifier)


def result(value):
    return Item(is_error=False, content=[Item(type="text", text=json.dumps(value))])


class ChatBackendTests(unittest.IsolatedAsyncioTestCase):
    def clients(self, responses, results):
        mcp = Item(list_tools=AsyncMock(return_value=Item(tools=[
            Item(name=name, description=name, input_schema={"type": "object", "properties": {}})
            for name in ("get_catalog", "verify_schema", "run_readonly_query")
        ])), call_tool=AsyncMock(side_effect=results))
        ai = Item(responses=Item(create=AsyncMock(side_effect=responses)))
        return mcp, ai

    async def test_catalog_then_query_then_answer(self):
        mcp, ai = self.clients([
            response(call("get_catalog", {}, "c1")),
            response(call("run_readonly_query", {"sql": "SELECT order_id FROM sales_demo.orders"}, "c2")),
            response(answer="There are four completed orders."),
        ], [result({"verification": {"valid": True}}), result({"columns": ["order_id"], "rows": [[1]]})])
        output = await run_turn(mcp, ai, "test-model", [{"role": "user", "content": "How many orders?"}])
        self.assertEqual([e["tool"] for e in output["trace"]], ["get_catalog", "run_readonly_query"])
        self.assertEqual(ai.responses.create.call_args_list[0].kwargs["tool_choice"]["name"], "get_catalog")
        self.assertFalse(ai.responses.create.call_args.kwargs["store"])
        outputs = [item for item in ai.responses.create.call_args.kwargs["input"] if isinstance(item, dict) and item.get("type") == "function_call_output"]
        self.assertEqual([item["call_id"] for item in outputs], ["c1", "c2"])

    async def test_query_is_blocked_until_catalog_verified(self):
        mcp, ai = self.clients([
            response(call("run_readonly_query", {"sql": "SELECT order_id FROM sales_demo.orders"}, "c1")),
            response(answer="Unable to query."),
        ], [])
        output = await run_turn(mcp, ai, "test-model", [{"role": "user", "content": "Orders?"}])
        mcp.call_tool.assert_not_called()
        self.assertIn("error", output["trace"][0]["result"])

    async def test_schema_failure_stops_model_loop(self):
        mcp, ai = self.clients([response(call("get_catalog", {}, "c1"))], [result({"error": "schema drift"})])
        with self.assertRaises(ChatError):
            await run_turn(mcp, ai, "test-model", [{"role": "user", "content": "Revenue?"}])
        self.assertEqual(ai.responses.create.await_count, 1)


if __name__ == "__main__":
    unittest.main()
