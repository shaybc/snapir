"""Verify project profiles and workspace isolation boundaries."""

from pathlib import Path

import pytest
import yaml

from runtime.configuration import load_configuration
from runtime.workspace_paths import resolve_run_directory


def test_profile_paths_are_relative_to_profile(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (tmp_path / "mapper.jar").touch()
    profile = tmp_path / "project.yaml"
    profile.write_text(yaml.safe_dump({"source_root": "source", "mapper_jar": "mapper.jar",
                                       "output_root": "outputs", "channels": ["INTERNET"]}))
    config = load_configuration(profile)
    assert config.source_root == str(source.resolve())
    assert config.output_root == str((tmp_path / "outputs").resolve())


@pytest.mark.parametrize("run_id", ["../outside", "a/b", "a\\b", "", "."])
def test_run_directory_rejects_path_identifiers(tmp_path, run_id):
    with pytest.raises(ValueError):
        resolve_run_directory(str(tmp_path), run_id)


def test_run_directory_is_contained(tmp_path):
    assert resolve_run_directory(str(tmp_path), "run-1") == tmp_path / "run-1"
