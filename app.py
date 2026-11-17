"""Local chat UI: python -m streamlit run app.py"""
import asyncio
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from chat_backend import ChatError, chat, settings

st.set_page_config(page_title="Semantic SQL MCP", page_icon="💬", layout="centered")
st.title("Chat with your sales data")
st.caption("semantic-sql-mcp · Ask a question. Get an answer backed by your database.")


def render_result(trace):
    for event in trace:
        result = event["result"]
        if event["tool"] != "run_readonly_query" or "columns" not in result:
            continue
        columns, rows = result["columns"], result["rows"]
        frame = pd.DataFrame(rows, columns=columns)
        st.dataframe(frame, hide_index=True, use_container_width=True)
        if result.get("truncated"):
            st.warning("Result truncated. Ask for a narrower date range or fewer groups.")
        # Chart only recognized time + metric columns. Keep exact decimals in the table.
        time_col = next((c for c in columns if c.lower() in ("month", "order_date", "date")), None)
        value_col = next((c for c in columns if c.lower() in ("revenue", "revenue_usd", "total_revenue", "completed_orders")), None)
        if time_col and value_col and rows:
            try:
                chart = frame[[time_col, value_col]].copy()
                chart[time_col] = pd.to_datetime(chart[time_col], utc=True).dt.strftime("%Y-%m-%d")
                chart[value_col] = [float(Decimal(str(value))) for value in chart[value_col]]
                st.bar_chart(chart, x=time_col, y=value_col)
            except (ValueError, TypeError, InvalidOperation, OverflowError):
                pass  # Keep the data table if a result cannot be charted.
    if trace:
        with st.expander("SQL and tool activity"):
            for event in trace:
                st.markdown("**" + event["tool"] + "**")
                if event["tool"] == "run_readonly_query":
                    st.code((event["arguments"] or {}).get("sql", ""), language="sql")
                st.json(event["result"], expanded=False)


if "messages" not in st.session_state:
    st.session_state.messages = []
with st.sidebar:
    st.header("Sales demo")
    st.write("Ask about revenue, orders, products, or regions.")
    st.caption("Revenue includes completed orders only. Currency: USD.")
    st.caption("Questions, schema context, and query results are sent to OpenAI. API usage is billed separately.")
    st.caption("Model: " + settings()["model"])
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        render_result(message.get("trace", []))

prompt = None
if not st.session_state.messages:
    for example in ("What is our revenue by month?", "Which region has the most revenue?", "What is our average order value?"):
        if st.button(example, use_container_width=True):
            prompt = example

config = settings()
if not config["api_key"]:
    st.info("Add OPENAI_API_KEY to your local .env.local file to start chatting.")
input_text = st.chat_input("Ask about your sales data…", max_chars=4000, disabled=not config["api_key"])
prompt = input_text or prompt
if prompt and config["api_key"]:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    try:
        with st.chat_message("assistant"):
            with st.spinner("Checking the catalog and querying your database…"):
                response = asyncio.run(chat(st.session_state.messages))
            st.markdown(response["answer"])
            render_result(response["trace"])
        st.session_state.messages.append({"role": "assistant", "content": response["answer"], "trace": response["trace"]})
    except ChatError as error:
        st.error(str(error))
        # Do not replay an unanswered request in a later conversation turn.
        st.session_state.messages.pop()
