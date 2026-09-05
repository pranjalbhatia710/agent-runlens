from pathlib import Path

from agent_trace_lens.cli import build_summary, load_trace, main, normalize, render_markdown, render_text


def test_jsonl_trace_is_loaded_and_summarized(tmp_path: Path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"type":"start","message":"go"}\n'
        '{"type":"tool_call","tool":"pytest","duration_ms":50}\n'
        '{"type":"error","message":"Traceback: bad","usage":{"total_tokens":7}}\n',
        encoding="utf-8",
    )

    events = normalize(load_trace(trace))
    summary = build_summary(events)

    assert summary["events"] == 3
    assert summary["errors"] == 1
    assert summary["tools"] == {"pytest": 1}
    assert summary["tokens"] == 7
    assert summary["duration_ms"] == 50
    assert summary["slowest_event"].tool == "pytest"
    rendered = render_text(events)
    assert "pytest" in rendered
    assert "slowest event: 002 tool_call (50 ms)" in rendered


def test_nested_agent_trace_shape_is_discovered(tmp_path: Path):
    trace = tmp_path / "nested.json"
    trace.write_text(
        '{"run":{"steps":[{"event":"tool_call","function_name":"browser_click","content":"clicked"}]}}',
        encoding="utf-8",
    )

    events = normalize(load_trace(trace))

    assert len(events) >= 1
    assert events[0].tool == "browser_click"


def test_markdown_report_contains_mermaid(tmp_path: Path):
    trace = tmp_path / "trace.json"
    trace.write_text('[{"type":"tool_call","tool":"terminal","text":"run tests","duration_ms":25}]', encoding="utf-8")

    events = normalize(load_trace(trace))
    markdown = render_markdown(events, trace)

    assert "```mermaid" in markdown
    assert "terminal" in markdown
    assert "Slowest event: `001` tool_call" in markdown


def test_fail_on_error_returns_nonzero_for_error_traces(tmp_path: Path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text('{"type":"error","message":"Traceback: bad"}\n', encoding="utf-8")

    assert main([str(trace), "--fail-on-error", "--format", "json"]) == 1


def test_summary_classifies_repeated_tool_and_auth_failures(tmp_path: Path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"type":"tool_call","tool":"gh","message":"gh api user"}\n'
        '{"type":"tool_call","tool":"gh","message":"gh repo view"}\n'
        '{"type":"tool_call","tool":"gh","message":"gh issue list"}\n'
        '{"type":"error","message":"403 forbidden: permission denied"}\n',
        encoding="utf-8",
    )

    events = normalize(load_trace(trace))
    summary = build_summary(events)

    assert summary["failure_categories"] == ["auth-or-permission", "repeated-tool-loop"]
    assert "failure categories: auth-or-permission, repeated-tool-loop" in render_text(events)
