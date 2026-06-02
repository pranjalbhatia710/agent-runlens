# agent-runlens

Local-first CLI for turning raw AI agent traces into readable timelines and failure reports.

When an AI coding agent fails, the useful signal is usually buried in JSON, JSONL, or tool-call dumps. `agent-runlens` extracts the run timeline, tools used, token counts when present, explicit errors, and a Markdown report with a Mermaid sequence diagram.

No API key. No hosted dashboard. No telemetry.

## Install

```bash
git clone https://github.com/pranjalbhatia710/agent-runlens.git
cd agent-runlens
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

## Quickstart

```bash
agent-runlens examples/sample-trace.jsonl
```

Output:

```text
agent-runlens summary
events: 5
errors: 1
tokens seen: 963
tools: pytest x1, read_file x1

timeline:
- 001 | 2026-06-02T12:00:00Z | agent_start | Debug failing test
- 002 | 2026-06-02T12:00:03Z | tool_call | tool=read_file | 120ms | Read tests/test_api.py
- 003 | 2026-06-02T12:00:06Z | llm | 963 tok | The failure is a missing edge case
- 004 | 2026-06-02T12:00:08Z | tool_call | tool=pytest | 1840ms | pytest tests/test_api.py
! 005 | 2026-06-02T12:00:10Z | error | AssertionError: expected 404, got 500
```

Generate a report:

```bash
agent-runlens examples/sample-trace.jsonl --format markdown -o report.md
```

The report includes:

- event count
- error count and failure points
- tool-call counts
- token usage when the trace includes it
- Mermaid sequence diagram
- normalized raw event list

## Supported input

`agent-runlens` accepts:

- JSON arrays
- JSON objects
- JSONL files
- nested event shapes from agent frameworks and tool-call logs

It uses permissive normalization because agent trace formats are still fragmented. The first goal is to make failed runs readable, not force a new schema.

## Why this can matter

Agent adoption is moving faster than agent debugging. Cursor has an agent trace format, and every coding-agent or MCP workflow is producing its own logs. A small local CLI that turns failed runs into pasteable reports can sit next to those tools instead of competing with them.

Good bug reports for agents should include what happened, which tools ran, where it failed, and enough timeline context for a maintainer to reproduce the issue. This repo is aimed at that gap.

## Examples

Text summary:

```bash
agent-runlens examples/sample-trace.jsonl
```

Markdown report:

```bash
agent-runlens examples/sample-trace.jsonl --format markdown -o /tmp/agent-trace-report.md
```

JSON summary for scripts:

```bash
agent-runlens examples/sample-trace.jsonl --format json
```

## Roadmap

- Real fixtures for Cursor `agent-trace`, Claude Code, Codex, LangGraph, CrewAI, and MCP clients
- HTML renderer for sharing local reports
- Failure classifiers for repeated tool loops, auth failures, browser dead ends, and CI failures
- OpenTelemetry span export
- GitHub issue template generator from a failed trace

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The best first contribution is a sanitized trace fixture from a real agent run.

## License

MIT
