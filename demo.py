"""Run the existing catalog and query tools directly, without an MCP client."""
import json

from tools.catalog import get_catalog
from tools.query import run_readonly_query


def main():
    try:
        catalog = get_catalog()
        if "error" in catalog:
            raise ValueError("Schema verification failed; update the catalog before querying.")
        print("Connected to Neon. Schema catalog verified.")
        print("Using predefined catalog examples; no LLM is generating SQL in this demo.")
        for example in catalog["examples"]:
            print("\nQuestion:", example["question"])
            print("SQL:", example["sql"])
            result = run_readonly_query(example["sql"])
            print("Result:")
            print(json.dumps(result, indent=2))
    except ValueError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
