"""Verify source imports and project defaults after source-folder relocation."""

from pathlib import Path
import sys

import constants
from runtime.project_paths import project_root, source_root
from runtime.configuration import load_configuration
from tools.workspace_intake_tools.env_loader import load_env_with_fallbacks


def test_layout_and_defaults_are_independent_of_working_directory(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(tmp_path)
    assert project_root() == root
    assert source_root() == root / "source"
    assert Path(constants.__file__).parent == source_root()
    assert str(root) not in sys.path
    assert not (root / "__init__.py").exists()
    assert not (source_root() / "__init__.py").exists()
    values = load_env_with_fallbacks()
    assert Path(values["COMPOSER_ROOT"]) == root / "bank-demo/composer/Workspace"
    assert Path(values["TEMPLATES_ROOT"]) == source_root() / "templates"
    assert Path(values["COMPOSER_MAPPER_JAR"]).parent == source_root() / "composer-mapper/target"
    profile = load_configuration(root / "configs/bank_demo.yaml")
    assert Path(profile.mapper_jar) == Path(values["COMPOSER_MAPPER_JAR"])
