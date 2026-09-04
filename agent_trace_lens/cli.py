from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

TIME_KEYS = ("timestamp", "time", "ts", "started_at", "start_time", "created_at")
EVENT_KEYS = ("type", "event", "name", "kind", "phase")
TEXT_KEYS = ("message", "content", "text", "summary", "error", "exception")
TOOL_KEYS = ("tool", "tool_name", "function", "function_name", "name")
TOKEN_KEYS = ("tokens", "total_tokens", "input_tokens", "output_tokens", "prompt_tokens", "completion_tokens")
DURATION_KEYS = ("duration_ms", "elapsed_ms", "latency_ms", "duration", "elapsed")


@dataclass
class Event:
    index: int
    path: str
    event_type: str = "event"
    timestamp: str | None = None
    text: str | None = None
    tool: str | None = None
    tokens: int = 0
    duration_ms: float | None = None
    raw_keys: list[str] = field(default_factory=list)

    @property
    def is_error(self) -> bool:
        haystack = " ".join(x for x in [self.event_type, self.text] if x).lower()
        return any(word in haystack for word in ("error", "exception", "failed", "traceback"))


def load_trace(path: Path) -> list[Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []

    try:
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        items: list[Any] = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: not valid JSON or JSONL: {exc}") from exc
        return items


def walk_objects(value: Any, prefix: str = "$", depth: int = 0) -> Iterable[tuple[str, dict[str, Any]]]:
    if depth > 12:
        return
    if isinstance(value, dict):
        if looks_like_event(value):
            yield prefix, value
        for key, child in value.items():
            yield from walk_objects(child, f"{prefix}.{key}", depth + 1)
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            yield from walk_objects(child, f"{prefix}[{idx}]", depth + 1)


def looks_like_event(obj: dict[str, Any]) -> bool:
    keys = set(obj.keys())
    return bool(keys.intersection(EVENT_KEYS + TIME_KEYS + TEXT_KEYS + TOOL_KEYS))


def first_string(obj: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = obj.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            return one_line(value)
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            nested = first_string(value, keys)
            if nested:
                return nested
    return None


def one_line(text: str, limit: int = 180) -> str:
    collapsed = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def extract_tokens(obj: dict[str, Any]) -> int:
    total = 0
    for key in TOKEN_KEYS:
        value = obj.get(key)
        if isinstance(value, int):
            total += value
        elif isinstance(value, dict):
            total += extract_tokens(value)
    usage = obj.get("usage")
    if isinstance(usage, dict):
        total += extract_tokens(usage)
    return total


def extract_duration(obj: dict[str, Any]) -> float | None:
    for key in DURATION_KEYS:
        value = obj.get(key)
        if isinstance(value, (int, float)):
            if key in {"duration", "elapsed"} and value < 10_000:
                return float(value) * 1000
            return float(value)
    return None


def normalize(items: list[Any]) -> list[Event]:
    events: list[Event] = []
    seen: set[int] = set()
    for item in items:
        for path, obj in walk_objects(item):
            oid = id(obj)
            if oid in seen:
                continue
            seen.add(oid)
            event_type = first_string(obj, EVENT_KEYS) or "event"
            text = first_string(obj, TEXT_KEYS)
            tool = first_string(obj, TOOL_KEYS)
            timestamp = first_string(obj, TIME_KEYS)
            events.append(
                Event(
                    index=len(events) + 1,
                    path=path,
                    event_type=event_type,
                    timestamp=timestamp,
                    text=text,
                    tool=tool if tool != event_type else None,
                    tokens=extract_tokens(obj),
                    duration_ms=extract_duration(obj),
                    raw_keys=sorted(str(k) for k in obj.keys())[:12],
                )
            )
    return events


def build_summary(events: list[Event]) -> dict[str, Any]:
    tool_counts: dict[str, int] = {}
    errors = []
    total_tokens = 0
    durations = []
    slowest_event: Event | None = None
    for event in events:
        if event.tool:
            tool_counts[event.tool] = tool_counts.get(event.tool, 0) + 1
        if event.is_error:
            errors.append(event)
        total_tokens += event.tokens
        if event.duration_ms is not None:
            durations.append(event.duration_ms)
            if slowest_event is None or event.duration_ms > (slowest_event.duration_ms or 0):
                slowest_event = event
    return {
        "events": len(events),
        "tools": tool_counts,
        "errors": len(errors),
        "error_events": errors,
        "tokens": total_tokens,
        "duration_ms": sum(durations) if durations else None,
        "slowest_event": slowest_event,
    }


def render_text(events: list[Event], *, limit: int = 50) -> str:
    summary = build_summary(events)
    lines = [
        "agent-runlens summary",
        f"events: {summary['events']}",
        f"errors: {summary['errors']}",
        f"tokens seen: {summary['tokens']}",
    ]
    if summary["duration_ms"] is not None:
        lines.append(f"duration seen: {summary['duration_ms']:.0f} ms")
    if summary["slowest_event"] is not None:
        slowest = summary["slowest_event"]
        lines.append(f"slowest event: {slowest.index:03d} {slowest.event_type} ({slowest.duration_ms:.0f} ms)")
    if summary["tools"]:
        top = ", ".join(f"{name} x{count}" for name, count in sorted(summary["tools"].items(), key=lambda item: (-item[1], item[0]))[:10])
        lines.append(f"tools: {top}")
    lines.append("")
    lines.append("timeline:")
    for event in events[:limit]:
        bits = [f"{event.index:03d}", event.timestamp or "", event.event_type]
        if event.tool:
            bits.append(f"tool={event.tool}")
        if event.duration_ms is not None:
            bits.append(f"{event.duration_ms:.0f}ms")
        if event.tokens:
            bits.append(f"{event.tokens} tok")
        if event.text:
            bits.append(event.text)
        marker = "!" if event.is_error else "-"
        lines.append(f"{marker} " + " | ".join(bit for bit in bits if bit))
    if len(events) > limit:
        lines.append(f"… {len(events) - limit} more events omitted; use --limit to show more")
    return "\n".join(lines)


def render_markdown(events: list[Event], source: Path, *, limit: int = 100) -> str:
    summary = build_summary(events)
    lines = [
        f"# Agent trace report: `{source.name}`",
        "",
        "## Summary",
        f"- Events: {summary['events']}",
        f"- Errors: {summary['errors']}",
        f"- Tokens observed: {summary['tokens']}",
    ]
    if summary["duration_ms"] is not None:
        lines.append(f"- Duration observed: {summary['duration_ms']:.0f} ms")
    if summary["slowest_event"] is not None:
        slowest = summary["slowest_event"]
        lines.append(f"- Slowest event: `{slowest.index:03d}` {slowest.event_type} ({slowest.duration_ms:.0f} ms)")
    if summary["tools"]:
        lines.append("- Tools: " + ", ".join(f"`{k}` × {v}" for k, v in sorted(summary["tools"].items())))
    lines.extend(["", "## Failure points"])
    if summary["error_events"]:
        for event in summary["error_events"][:10]:
            lines.append(f"- Event {event.index}: **{event.event_type}** {event.text or ''}".rstrip())
    else:
        lines.append("- No explicit error events found.")
    lines.extend(["", "## Timeline", "", "```mermaid", "sequenceDiagram", "    participant A as Agent", "    participant T as Tools"])
    for event in events[:25]:
        label = one_line(event.text or event.event_type, 60).replace('"', "'")
        if event.tool:
            lines.append(f"    A->>T: {event.tool}: {label}")
        else:
            lines.append(f"    A->>A: {label}")
    lines.extend(["```", "", "## Raw events"])
    for event in events[:limit]:
        lines.append(f"- `{event.index:03d}` **{event.event_type}**" + (f" `{event.tool}`" if event.tool else "") + (f": {event.text}" if event.text else ""))
    if len(events) > limit:
        lines.append(f"- {len(events) - limit} more events omitted.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize AI agent trace JSON/JSONL files into readable timelines.")
    parser.add_argument("trace", type=Path, help="Path to a trace JSON or JSONL file")
    parser.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    parser.add_argument("--output", "-o", type=Path, help="Write output to a file")
    parser.add_argument("--limit", type=int, default=50, help="Max timeline events to print")
    parser.add_argument("--fail-on-error", action="store_true", help="exit 1 when the trace contains error events")
    args = parser.parse_args(argv)

    try:
        events = normalize(load_trace(args.trace))
    except Exception as exc:  # deliberate CLI boundary
        print(f"agent-runlens: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        payload = {
            "summary": {
                k: (v.__dict__ if isinstance(v, Event) else v)
                for k, v in build_summary(events).items()
                if k != "error_events"
            },
            "events": [event.__dict__ for event in events[: args.limit]],
        }
        rendered = json.dumps(payload, indent=2)
    elif args.format == "markdown":
        rendered = render_markdown(events, args.trace, limit=args.limit)
    else:
        rendered = render_text(events, limit=args.limit)

    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 1 if args.fail_on_error and build_summary(events)["errors"] else 0
