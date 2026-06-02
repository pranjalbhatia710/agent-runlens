# Launch plan

## Positioning

agent-runlens turns raw AI agent trace JSON/JSONL into readable timelines, failure points, and Mermaid reports locally. No SaaS, no API key, no telemetry.

## Why now

Agent frameworks are getting adoption, but debugging artifacts are still messy. Cursor has an agent trace format. Claude Code, Codex, LangGraph, CrewAI, MCP clients, and custom agents all emit slightly different logs. Developers need a small local tool that can turn those logs into something a teammate or maintainer can read.

## X draft

I built `agent-runlens`: a local CLI that turns AI agent traces into readable timelines and failure reports.

Raw JSON/JSONL from agents is usually useless when a run fails.

This extracts events, tools, token usage, errors, and generates a Mermaid timeline.

No SaaS. No API key. Works on local trace files.

Repo: https://github.com/pranjalbhatia710/agent-runlens

## LinkedIn draft

I built a small open-source tool for debugging AI agent runs: `agent-runlens`.

The problem is simple: when an agent fails, the useful information is buried in raw trace JSON, terminal logs, or tool-call dumps. That makes it hard to explain what happened, file good issues, or compare runs.

`agent-runlens` is a local-first CLI that reads JSON/JSONL traces and outputs:

- a readable event timeline
- tool-call counts
- token usage when present
- explicit failure points
- a Markdown report with a Mermaid sequence diagram

No API key. No SaaS. No telemetry.

Repo: https://github.com/pranjalbhatia710/agent-runlens

## Show HN title

Show HN: agent-runlens, a local CLI for readable AI agent trace reports

## Target communities

- Hacker News Show HN
- r/LocalLLaMA, if framed around local-first debugging
- Cursor/Claude Code/Codex users sharing failed-agent traces
- LangGraph/CrewAI Discords as a debugging helper, not a competing framework
- MCP builder communities

## Metrics to track

- Stars in first 48 hours
- Issues opened with real trace formats
- Trace fixtures contributed by tool users
- Mentions from Cursor/Claude Code/Codex/LangGraph communities
