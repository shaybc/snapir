"""Verify menu clearing and result visibility without using a live terminal."""

from types import SimpleNamespace

import pytest

from cli import interactive, multiselect, terminal_display, configuration_wizard
from cli.main import main


@pytest.mark.parametrize("input_tty, output_tty", [(False, False), (False, True), (True, False)])
def test_noninteractive_output_is_unchanged(monkeypatch, capsys, input_tty, output_tty):
    monkeypatch.setattr(terminal_display.sys, "stdin", SimpleNamespace(isatty=lambda: input_tty))
    monkeypatch.setattr(terminal_display.sys.stdout, "isatty", lambda: output_tty)
    monkeypatch.setattr("prompt_toolkit.shortcuts.clear", lambda: pytest.fail("Unexpected terminal clear"))
    terminal_display.clear_screen()
    terminal_display.separate_result_from_menu()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("multiple, result", [(False, "item"), (True, ["item"]), (False, None), (True, None)])
def test_completed_menus_clear_after_selection_or_cancellation(monkeypatch, capsys, multiple, result):
    monkeypatch.setattr(terminal_display, "_is_terminal", lambda: True)
    events = []
    monkeypatch.setattr("prompt_toolkit.shortcuts.clear", lambda: events.append("clear"))
    def run():
        events.append("selection")
        return result
    monkeypatch.setattr("prompt_toolkit.application.Application", lambda **kwargs: SimpleNamespace(run=run))
    select = multiselect.select_multiple if multiple else interactive.select_option
    if result is None:
        with pytest.raises(interactive.SelectionCancelled):
            select("Choose", [("item", "Item")])
    else:
        assert select("Choose", [("item", "Item")]) == result
    assert events == ["selection", "clear"]
    assert capsys.readouterr().out.startswith("\n\nChoose")


def test_wizard_text_clears_after_accepting_default(monkeypatch):
    events = []
    monkeypatch.setattr(terminal_display, "_is_terminal", lambda: True)
    monkeypatch.setattr("prompt_toolkit.prompt", lambda *args, **kwargs: events.append("input") or "")
    monkeypatch.setattr("prompt_toolkit.shortcuts.clear", lambda: events.append("clear"))
    assert configuration_wizard.prompt_text("source_root", "../default") == "../default"
    assert events == ["input", "clear"]


@pytest.mark.parametrize("action, result_text", [
    ("start", "Run created: supplied"),
    ("help", "Show exception stack traces and debug diagnostic logs."),
    ("readme", "README opened in browser"),
    ("create_config", "Configuration saved"),
])
def test_results_remain_above_two_blank_lines_and_next_main_menu(monkeypatch, capsys, action, result_text):
    monkeypatch.setattr(terminal_display, "_is_terminal", lambda: True)
    monkeypatch.setattr(interactive, "is_interactive", lambda: True)
    selections = iter((["documentation", action] if action in {"help", "readme"} else [action]) + ["exit"])
    events = []
    monkeypatch.setattr("prompt_toolkit.shortcuts.clear", lambda: events.append("clear"))
    def run():
        selected = next(selections)
        if selected == "exit":
            output = capsys.readouterr().out
            assert result_text in output
            if action == "start":
                assert "Intake warning remains visible" in output
            assert "\n\n\nWhat would you like to do?" in output
            # Action output remains until the next completed selection.
            assert events[-1] == ("pipeline" if action == "start" else "clear")
        events.append(selected)
        return selected
    monkeypatch.setattr("prompt_toolkit.application.Application", lambda **kwargs: SimpleNamespace(run=run))
    monkeypatch.setattr("cli.main.load_configuration", lambda _: SimpleNamespace(output_root="unused"))
    def start(*args):
        events.append("pipeline")
        print("Intake warning remains visible")
        return "workspace"
    monkeypatch.setattr("cli.main.run_pipeline", start)
    def clear_start_result():
        events.append("pipeline-cleared")
    monkeypatch.setattr("cli.main.clear_screen", clear_start_result)
    monkeypatch.setattr("cli.main.open_readme", lambda: print("README opened in browser"))
    monkeypatch.setattr("cli.main.create_configuration", lambda: print("Configuration saved"))
    assert main(["--config", "supplied.yaml", "--run-id", "supplied"]) == 0
    if action == "start":
        assert "pipeline-cleared" not in events
        assert events.index("pipeline") < events.index("exit")
