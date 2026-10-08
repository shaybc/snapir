from __future__ import annotations

import subprocess

import health_check


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def command_runner(command: list[str]):
    if command[:2] == ["java", "-version"]:
        return completed(stderr='openjdk version "25.0.3"')
    if command[:2] == ["javac", "-version"]:
        return completed(stdout="javac 25.0.3")
    if command[:2] == ["mvn", "-version"]:
        return completed(stdout="Apache Maven 3.9.6\nJava version: 25.0.3")
    if command[:2] == ["java", "-jar"]:
        return completed(stdout="usage")
    raise FileNotFoundError(command[0])


def test_all_checks_pass_with_correct_mock_environment(tmp_path, monkeypatch):
    composer_root = tmp_path / "composer"
    composer_root.mkdir()
    mapper = tmp_path / "composer-mapper.jar"
    mapper.write_text("jar", encoding="utf-8")
    monkeypatch.setenv("COMPOSER_ROOT", str(composer_root))
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path / "vault"))
    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path / "out"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "state" / "migration.db"))
    monkeypatch.setenv("COMPOSER_MAPPER_JAR", str(mapper))

    results = health_check.run_health_checks(
        command_runner=command_runner,
        import_checker=lambda module: True,
        url_checker=lambda url, payload: True,
    )

    assert health_check.exit_code(results) == 0
    assert all(result.passed or not result.blocking for result in results)


def test_missing_java_returns_non_zero_exit(tmp_path, monkeypatch):
    composer_root = tmp_path / "composer"
    composer_root.mkdir()
    mapper = tmp_path / "composer-mapper.jar"
    mapper.write_text("jar", encoding="utf-8")
    monkeypatch.setenv("COMPOSER_ROOT", str(composer_root))
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path / "vault"))
    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path / "out"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "state" / "migration.db"))
    monkeypatch.setenv("COMPOSER_MAPPER_JAR", str(mapper))

    def missing_java(command: list[str]):
        if command[:2] == ["java", "-version"]:
            raise FileNotFoundError("java")
        return command_runner(command)

    results = health_check.run_health_checks(
        command_runner=missing_java,
        import_checker=lambda module: True,
        url_checker=lambda url, payload: True,
    )

    assert health_check.exit_code(results) == 1
    assert next(result for result in results if result.name == "Java 25").passed is False


def test_unreachable_legacy_service_returns_warning_only(tmp_path, monkeypatch):
    composer_root = tmp_path / "composer"
    composer_root.mkdir()
    mapper = tmp_path / "composer-mapper.jar"
    mapper.write_text("jar", encoding="utf-8")
    monkeypatch.setenv("COMPOSER_ROOT", str(composer_root))
    monkeypatch.setenv("VAULT_ROOT", str(tmp_path / "vault"))
    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path / "out"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "state" / "migration.db"))
    monkeypatch.setenv("COMPOSER_MAPPER_JAR", str(mapper))

    def urls(url: str, payload: bytes | None):
        return payload is not None

    results = health_check.run_health_checks(
        command_runner=command_runner,
        import_checker=lambda module: True,
        url_checker=urls,
    )

    legacy = next(result for result in results if result.name == "Legacy service reachable")
    assert legacy.status == "WARN"
    assert health_check.exit_code(results) == 0


def test_java_and_javac_reject_other_versions_and_command_failure():
    for executable in ("java", "javac"):
        for version in ("17", "26"):
            result = health_check._check_java_command(lambda command: completed(stdout=f"{executable} {version}"), executable)
            assert not result.passed
        assert not health_check._check_java_command(lambda command: completed(stdout=f"{executable} 25", returncode=1), executable).passed
        def missing(command):
            raise FileNotFoundError(executable)
        assert not health_check._check_java_command(missing, executable).passed


def test_maven_requires_its_actual_jdk_25():
    for output in ("Apache Maven 3.9.6\nJava version: 17.0.9", "Apache Maven 3.9.6", "Apache Maven 3.7.0\nJava version: 25"):
        assert not health_check._check_maven(lambda command: completed(stdout=output)).passed
    assert not health_check._check_maven(lambda command: completed(stdout="Apache Maven 3.9.6\nJava version: 25", returncode=1)).passed
