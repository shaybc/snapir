"""Verify documentation and exit actions without real browser or pipeline calls."""

from pathlib import Path

import pytest

from cli import interactive, readme
from cli.main import main


@pytest.fixture
def menu_only(monkeypatch):
    monkeypatch.setattr(interactive, "is_interactive", lambda: True)
    def forbidden(*args, **kwargs):
        pytest.fail("Documentation/exit must not load configuration or touch runs")
    for name in ("load_configuration", "complete_run_selection", "run_pipeline", "resume_pipeline"):
        monkeypatch.setattr(f"cli.main.{name}", forbidden)
    monkeypatch.setattr(interactive, "discover_configurations", forbidden)
    monkeypatch.setattr(interactive, "discover_runs", forbidden)


def test_exit_returns_success_without_configuration(monkeypatch, menu_only):
    def select(title, options):
        assert options[-1] == ("exit", "Exit")
        assert ("documentation", "Help / README") in options
        return "exit"
    monkeypatch.setattr(interactive, "select_option", select)
    assert main([]) == 0


def test_menu_help_matches_parser_help(monkeypatch, menu_only, capsys):
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    expected = capsys.readouterr().out
    choices = iter(["documentation", "help", "exit"])
    menus = []
    def select(title, options):
        menus.append(title)
        if title == "Help / README":
            assert options == [("help", "Show help screen"), ("readme", "Open README in browser")]
        return next(choices)
    monkeypatch.setattr(interactive, "select_option", select)
    assert main([]) == 0
    assert capsys.readouterr().out == expected
    assert "--verbose" in expected
    assert menus == ["What would you like to do?", "Help / README", "What would you like to do?"]


def test_rendering_escapes_html_and_resolves_local_links(tmp_path):
    document = tmp_path / "README.md"
    document.write_text('''# Project

| Name | Value |
| --- | --- |
| Demo | `code` |

```python
print("<hello>")
```

[Guide](docs/guide.md) ![Logo](images/logo.png)

<script>alert("raw")</script>
''', encoding="utf-8")
    content = readme.render_readme(document)
    assert "<h1>Project</h1>" in content
    assert "<table>" in content and "<code>code</code>" in content
    assert '<pre><code class="language-python">' in content
    assert "&lt;hello&gt;" in content
    assert "<script>" not in content and "&lt;script&gt;" in content
    assert (tmp_path / "docs" / "guide.md").as_uri() in content
    assert (tmp_path / "images" / "logo.png").as_uri() in content


@pytest.mark.parametrize("opened", [True, False, "error"])
def test_readme_menu_requests_new_browser_tab(tmp_path, monkeypatch, menu_only, opened, capsys):
    monkeypatch.setattr(readme.tempfile, "tempdir", str(tmp_path))
    choices = iter(["documentation", "readme", "exit"])
    menus = []
    def select(title, options):
        menus.append(title)
        return next(choices)
    monkeypatch.setattr(interactive, "select_option", select)
    calls = []
    def browser(url, new):
        calls.append((url, new))
        if opened == "error":
            raise readme.webbrowser.Error("No browser")
        return opened
    monkeypatch.setattr(readme.webbrowser, "open", browser)
    assert main([]) == (0 if opened is True else 1)
    generated, = tmp_path.glob("snapir-readme-*.html")
    assert calls == [(generated.as_uri(), 2)]
    content = generated.read_text(encoding="utf-8")
    assert "Migration run folder contents" in content and "<table>" in content
    if opened is not True:
        assert "Could not open README in a browser" in capsys.readouterr().out
        assert menus == ["What would you like to do?", "Help / README"]
    else:
        assert menus == ["What would you like to do?", "Help / README", "What would you like to do?"]


def test_help_returns_to_menu_then_executes_next_command(monkeypatch, menu_only, capsys):
    choices = iter(["documentation", "help", "start", "exit"])
    menus = []
    def select(title, options):
        menus.append(title)
        if len(menus) == 3:
            assert "--verbose" in capsys.readouterr().out
        return next(choices)
    monkeypatch.setattr(interactive, "select_option", select)
    loaded = []
    monkeypatch.setattr("cli.main.load_configuration", lambda path: loaded.append(path) or "profile")
    monkeypatch.setattr("cli.main.complete_run_selection", lambda *_: None)
    calls = []
    monkeypatch.setattr("cli.main.run_pipeline", lambda profile, run_id: calls.append((profile, run_id)) or "workspace")
    assert main(["--config", "supplied.yaml", "--run-id", "supplied"]) == 0
    assert loaded == ["supplied.yaml"]
    assert calls == [("profile", "supplied")]
    assert menus == ["What would you like to do?", "Help / README", "What would you like to do?", "What would you like to do?"]
