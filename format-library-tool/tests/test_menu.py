"""The numbered exit action terminates the standalone CLI without redisplaying its menu."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_library import __main__ as cli


@pytest.mark.parametrize('choice', ['6', '0'])
def test_exit_returns_success_without_redisplaying_menu(monkeypatch, capsys, choice):
    monkeypatch.setattr(cli, 'load_config', lambda path: {})
    answers = iter([choice])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))
    assert cli.main([]) == 0
    output = capsys.readouterr().out
    assert output.count('Format library tool') == 1
    assert '6. Exit' in output
