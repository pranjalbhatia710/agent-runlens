import json
from pathlib import Path

from agent_trace_lens.cli import build_summary, filter_events, load_trace, main, normalize, parse_trace_text, render_markdown, render_text


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


def test_parse_trace_text_reports_source_line_for_invalid_jsonl():
    try:
        parse_trace_text('{"type":"start"}\nnot-json\n', "stdin")
    except ValueError as exc:
        assert "stdin:2: not valid JSON or JSONL" in str(exc)
    else:  # pragma: no cover - keeps assertion readable without pytest.raises import
        raise AssertionError("invalid JSONL should raise ValueError")


def test_stdin_trace_is_supported(monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO('{"type":"tool_call","tool":"pytest"}\n'))

    events = normalize(load_trace(Path("-")))

    assert len(events) == 1
    assert events[0].tool == "pytest"


def test_nested_agent_trace_shape_is_discovered(tmp_path: Path):
    trace = tmp_path / "nested.json"
    trace.write_text(
        '{"run":{"steps":[{"event":"tool_call","function_name":"browser_click","content":"clicked"}]}}',
        encoding="utf-8",
    )

    events = normalize(load_trace(trace))

    assert len(events) >= 1
    assert events[0].tool == "browser_click"


def test_structured_content_blocks_are_rendered(tmp_path: Path):
    trace = tmp_path / "content-blocks.json"
    trace.write_text(
        """[
          {
            "type": "assistant_message",
            "content": [
              {"type": "text", "text": "Investigating failure"},
              {"type": "tool_use", "name": "pytest"}
            ]
          }
        ]""",
        encoding="utf-8",
    )

    events = normalize(load_trace(trace))
    rendered = render_text(events)

    assert events[0].text == "Investigating failure pytest"
    assert "Investigating failure pytest" in rendered


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


def test_json_output_includes_error_event_details(tmp_path: Path, capsys):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"type":"tool_call","tool":"pytest","message":"run tests"}\n'
        '{"type":"error","message":"AssertionError: bad result"}\n',
        encoding="utf-8",
    )

    assert main([str(trace), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["summary"]["errors"] == 1
    assert payload["error_events"][0]["index"] == 2
    assert payload["error_events"][0]["is_error"] is True
    assert payload["events"][0]["is_error"] is False


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


def test_filter_events_can_focus_errors_slow_events_and_tools(tmp_path: Path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"type":"tool_call","tool":"read_file","duration_ms":5}\n'
        '{"type":"tool_call","tool":"pytest","duration_ms":250}\n'
        '{"type":"error","message":"AssertionError: bad result","duration_ms":10}\n',
        encoding="utf-8",
    )

    events = normalize(load_trace(trace))

    assert [event.index for event in filter_events(events, min_duration_ms=100)] == [2]
    assert [event.index for event in filter_events(events, only_errors=True)] == [3]
    assert [event.index for event in filter_events(events, tool="PYTEST")] == [2]


def test_filter_events_can_search_event_text_tool_path_and_keys(tmp_path: Path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"type":"agent_step","message":"Need to inspect auth failure","timestamp":"2026-10-06T12:00:00Z"}\n'
        '{"type":"tool_call","tool":"gh","message":"gh auth status","duration_ms":250}\n'
        '{"type":"error","message":"403 forbidden","extra_context":{"retryable":false}}\n',
        encoding="utf-8",
    )

    events = normalize(load_trace(trace))

    assert [event.index for event in filter_events(events, contains="AUTH")] == [1, 2]
    assert [event.index for event in filter_events(events, contains="extra_context")] == [3]
    assert [event.index for event in filter_events(events, contains="$")] == [1, 2, 3]


def test_cli_contains_filter_applies_to_json_output(tmp_path: Path, capsys):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"type":"tool_call","tool":"read_file","message":"read docs"}\n'
        '{"type":"tool_call","tool":"pytest","message":"run auth tests"}\n',
        encoding="utf-8",
    )

    assert main([str(trace), "--format", "json", "--contains", "auth"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["summary"]["events"] == 1
    assert payload["events"][0]["tool"] == "pytest"


def test_cli_filters_json_output_without_hiding_fail_on_error_status(tmp_path: Path, capsys):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"type":"tool_call","tool":"read_file","duration_ms":5}\n'
        '{"type":"tool_call","tool":"pytest","duration_ms":250}\n'
        '{"type":"error","message":"AssertionError: bad result","duration_ms":10}\n',
        encoding="utf-8",
    )

    assert main([str(trace), "--format", "json", "--min-duration-ms", "100", "--tool", "pytest", "--fail-on-error"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert payload["summary"]["events"] == 1
    assert [event["index"] for event in payload["events"]] == [2]
    assert payload["events"][0]["tool"] == "pytest"
    assert payload["summary"]["errors"] == 0


def test_cli_rejects_invalid_focus_filters(tmp_path: Path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text('{"type":"tool_call","tool":"pytest"}\n', encoding="utf-8")

    for args, message in [
        (["--limit", "0"], "--limit must be at least 1"),
        (["--min-duration-ms", "-1"], "--min-duration-ms must be zero or greater"),
    ]:
        try:
            main([str(trace), *args])
        except SystemExit as exc:
            assert str(exc) == message
        else:
            raise AssertionError("expected SystemExit")
