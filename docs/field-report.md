# Field report

## Repo/context

Initial validation used `examples/sample-trace.jsonl`, a deterministic local JSONL trace that simulates an agent debugging a failed test.

## Command

```bash
python -m agent_trace_lens examples/sample-trace.jsonl
python -m agent_trace_lens examples/sample-trace.jsonl --format markdown -o /tmp/agent-trace-report.md
```

## Observed result

The CLI extracted five events, counted two tool calls, detected one explicit error, counted token usage from nested `usage`, and generated a Markdown report with a Mermaid sequence diagram.

## Product lesson

The useful wedge is not replacing observability platforms. It is the fast local path from "the agent failed" to "here is the timeline I can paste into an issue." The next valuable step is adding fixtures from real agent tools.
