# Title

Add LLM-powered Cypher query interface for Neo4j with FastMCP integration

## Description

### Summary

This PR introduces a full-stack interactive system for natural language querying and node creation in a Neo4j graph database, leveraging OpenAI's LLM through a FastMCP server-client framework.

The update includes:

* An `MCP server` (`server.py`) exposing the `query_neo4j_with_llm` tool.
* A `CLI client` (`mcp_client.py`) that allows users to input natural queries.
* A unified `entry point` (`main.py`) that launches both server and client, supporting structured SSE communication.
* Integration with Neo4j for both querying and data insertion.
* Schema enforcement and prompt-engineering rules to guide LLM outputs.

### Context

This is part of the **MCP architecture** aimed at enabling structured graph-based operations using plain language. The core objectives include:

* Abstracting Cypher generation away from the end-user.
* Ensuring schema-compliant Cypher generation via LLM system prompts.
* Supporting dual mode: query-only or query-with-node-creation.
* Enabling clean developer interface via `@mcp.tool()` registration and `ClientSession`.

The use of `FastMCP` as the backbone provides modularity and event-driven communication, making this system suitable for both real-time and asynchronous operations.

## Checklist

* [x] Neo4j integration with auth/env setup
* [x] LLM prompt template to enforce schema and logic rules
* [x] `@mcp.tool`-decorated function to expose LLM-based query tool
* [x] Node creation logic with parameterized Cypher query
* [x] `sse` server-client communication setup
* [x] CLI loop for user input and graceful exit
* [x] Structured output formatting and logging
* [x] Fallback for LLM unanswerable queries
* [x] Clean termination of server subprocess from `main.py`

## Additional Notes

* Ensure the `.env` file is correctly populated with `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, and `OPENAI_API_KEY`.
* The schema is hard-coded into the system prompt. Changes in schema must be reflected there.
* Future enhancements could include: caching generated Cypher queries, rate limiting for OpenAI calls, or exposing the server as a public API.

---

Want help creating a [GitHub-compatible PR template](f) or a [README update to match this functionality](f)?
