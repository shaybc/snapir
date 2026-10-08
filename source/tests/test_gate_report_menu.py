"""Check direct Markdown browser opening and non-exiting review choices."""

from runtime.workspace_paths import run_report_path, write_run_report
import pytest

from cli.gate_report_menu import offer_gate_one_report, offer_dependency_closure_report
from cli.interactive import SelectionCancelled


def test_open_uses_original_markdown_and_preserves_console(tmp_path, monkeypatch, capsys):
    report = run_report_path(tmp_path, "gate_1_report.md")
    report.parent.mkdir(parents=True)
    report.write_text("# Review\n")
    def select(title, options, **kwargs):
        assert kwargs == {"clear_after_selection": False}
        assert [key for key, _ in options] == ["open", "back"]
        return "open"
    monkeypatch.setattr("cli.gate_report_menu.select_option", select)
    calls = []
    monkeypatch.setattr("cli.gate_report_menu.webbrowser.open", lambda url, **kwargs: calls.append((url, kwargs)) or True)
    offer_gate_one_report(tmp_path)
    assert calls == [(report.as_uri(), {"new": 2})]
    assert list(tmp_path.rglob("*.md")) == [report]
    assert "report opened" in capsys.readouterr().out


@pytest.mark.parametrize("choice", ["back", "cancel"])
def test_return_or_escape_leaves_browser_closed(tmp_path, monkeypatch, choice):
    write_run_report(tmp_path, "gate_1_report.md", "# Review\n")
    def select(*_, **kwargs):
        if choice == "cancel":
            raise SelectionCancelled
        return choice
    monkeypatch.setattr("cli.gate_report_menu.select_option", select)
    monkeypatch.setattr("cli.gate_report_menu.webbrowser.open", lambda *_args, **_kwargs: pytest.fail("Opened browser"))
    offer_gate_one_report(tmp_path)


def test_browser_failure_reports_manual_path(tmp_path, monkeypatch, capsys):
    report = run_report_path(tmp_path, "gate_1_report.md")
    report.parent.mkdir(parents=True)
    report.write_text("# Review\n")
    monkeypatch.setattr("cli.gate_report_menu.select_option", lambda *_args, **_kwargs: "open")
    monkeypatch.setattr("cli.gate_report_menu.webbrowser.open", lambda *_args, **_kwargs: False)
    offer_gate_one_report(tmp_path)
    assert "Open this Markdown report manually" in capsys.readouterr().out


def test_dependency_report_opens_original_json(tmp_path, monkeypatch, capsys):
    report = write_run_report(tmp_path, "dependency_closure.json", '[{"blocking_issues": []}]')
    calls = []
    def select(title, options, **kwargs):
        assert title == "Dependency closure findings"
        assert options[0] == ("open", "Open dependency closure report")
        assert options[1] == ("back", "Return to main menu")
        assert kwargs == {"clear_after_selection": False}
        return "open"
    monkeypatch.setattr("cli.gate_report_menu.select_option", select)
    monkeypatch.setattr("cli.gate_report_menu.os.startfile", lambda path: calls.append(path))
    offer_dependency_closure_report(tmp_path)
    assert calls == [str(report)]
    assert list(tmp_path.rglob("*.html")) == []
    assert "review its blocking_issues" in capsys.readouterr().out


@pytest.mark.parametrize("choice", ["back", "cancel"])
def test_dependency_report_return_keeps_session_open(tmp_path, monkeypatch, choice):
    write_run_report(tmp_path, "dependency_closure.json", "[]")
    def select(*_, **kwargs):
        if choice == "cancel":
            raise SelectionCancelled
        return choice
    monkeypatch.setattr("cli.gate_report_menu.select_option", select)
    monkeypatch.setattr("cli.gate_report_menu.webbrowser.open", lambda *_args, **_kwargs: pytest.fail("Opened browser"))
    offer_dependency_closure_report(tmp_path)
