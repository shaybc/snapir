"""Verify per-run Java selection, child environments, and compiler target isolation."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from runtime.java_toolchain import java_scope, java_version, java_environment, resolve_java_home, run_java
from tools.maven_dependency_tools.pom_manager import initialize_managed_pom, validate_java_target


def jdk(tmp_path, version):
    home = tmp_path / f"jdk-{version}"
    (home / "bin").mkdir(parents=True)
    suffix = ".exe" if os.name == "nt" else ""
    for command in ("java", "javac"):
        (home / "bin" / (command + suffix)).touch()
    (home / "release").write_text(f'JAVA_VERSION="{version}.0.1"', encoding="utf-8")
    return str(home)


@pytest.mark.parametrize("version", [21, 25])
def test_selected_jdk_controls_pom_and_child_only(tmp_path, monkeypatch, version):
    home = jdk(tmp_path, version)
    profile = SimpleNamespace(java_version=version, java_home=home)
    monkeypatch.setenv("JAVA_HOME", "original-user-home")
    calls = []
    monkeypatch.setattr("subprocess.run", lambda command, **kwargs: calls.append((command, kwargs)))
    with java_scope(profile):
        assert java_version() == str(version)
        environment = java_environment()
        assert environment["JAVA_HOME"] == home
        assert environment["PATH"].startswith(str(Path(home) / "bin"))
        run_java(["javac", "-version"])
        assert calls[0][1]["env"]["JAVA_HOME"] == home
        pom = tmp_path / "pom.xml"
        initialize_managed_pom(str(pom), "org.example", "demo")
        text = pom.read_text(encoding="utf-8")
        assert f"[{version},{version + 1})" in text
        validate_java_target(text)
    assert os.environ["JAVA_HOME"] == "original-user-home"
    assert java_version() == "25"


def test_mismatched_jdk_rejected(tmp_path):
    with pytest.raises(ValueError, match="must use Java 25"):
        resolve_java_home(25, jdk(tmp_path, 21))


def test_config_default_and_override_saved_values():
    from models.pipeline_configuration import PipelineConfiguration
    assert PipelineConfiguration().java_version == 25
    profile = PipelineConfiguration(java_version=21, java_home="some-jdk")
    saved = PipelineConfiguration.model_validate_json(profile.model_dump_json())
    assert (saved.java_version, saved.java_home) == (21, "some-jdk")
    with pytest.raises(ValueError):
        PipelineConfiguration(java_version=17)
