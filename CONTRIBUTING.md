# Contributing

Thanks for helping make agent debugging less opaque.

## Good first contributions

- Add trace-shape fixtures from real tools: Cursor, Claude Code, Codex, LangGraph, CrewAI, MCP clients.
- Improve event normalization without adding heavy dependencies.
- Add renderers: HTML, SARIF, GitHub issue markdown, or OpenTelemetry span export.
- Add failure classifiers for common agent loops: repeated tool call, stuck browser step, auth failure, CI failure.

## Local setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e . pytest
pytest
python -m agent_trace_lens examples/sample-trace.jsonl
```

Keep PRs small and include a trace fixture or test when changing parsing behavior.
