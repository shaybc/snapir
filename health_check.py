from __future__ import annotations

import argparse
import importlib
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

import constants


@dataclass(frozen=True)
class CheckResult:
    """One production-readiness health check result."""

    name: str
    passed: bool
    message: str
    blocking: bool = True

    @property
    def status(self) -> str:
        if self.passed:
            return "PASS"
        return "FAIL" if self.blocking else "WARN"


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess]
ImportChecker = Callable[[str], bool]
UrlChecker = Callable[[str, bytes | None], bool]


def run_health_checks(
    *,
    env_path: str | None = None,
    command_runner: CommandRunner | None = None,
    import_checker: ImportChecker | None = None,
    url_checker: UrlChecker | None = None,
) -> list[CheckResult]:
    """Run all blocking and warning health checks."""
    if env_path:
        _load_env_file(env_path)
    command_runner = command_runner or _run_command
    import_checker = import_checker or _can_import
    url_checker = url_checker or _check_url
    checks = [
        _check_python_version(),
        _check_adk(import_checker),
        _check_requirements(import_checker),
        _check_java(command_runner),
        _check_javac(command_runner),
        _check_maven(command_runner),
        _check_composer_mapper(command_runner),
        _check_composer_root(),
        _check_vault_root(),
        _check_output_root(),
        _check_db_dir(),
        _check_litellm(url_checker),
        _check_legacy_service(url_checker),
        _check_sqlite_rw(),
        _check_forbidden_dependencies(),
    ]
    return checks


def exit_code(results: list[CheckResult]) -> int:
    """Return process exit code for health check results."""
    return 1 if any(not result.passed and result.blocking for result in results) else 0


def print_results(results: list[CheckResult]) -> None:
    """Print check results in a stable console format."""
    for result in results:
        print(f"{result.status} {result.name}: {result.message}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for production readiness diagnostics."""
    parser = argparse.ArgumentParser(description="Run Snapir production readiness health checks.")
    parser.add_argument("--env", help="Optional .env file to load before checks.")
    args = parser.parse_args(argv)
    results = run_health_checks(env_path=args.env)
    print_results(results)
    return exit_code(results)


def _check_python_version() -> CheckResult:
    passed = sys.version_info >= (3, 11)
    return CheckResult("Python >= 3.11", passed, sys.version.split()[0])


def _check_adk(import_checker: ImportChecker) -> CheckResult:
    passed = import_checker("google.adk")
    return CheckResult("Google ADK importable", passed, "google.adk" if passed else "google.adk not importable")


def _check_requirements(import_checker: ImportChecker) -> CheckResult:
    requirements = Path("requirements.txt")
    if not requirements.exists():
        return CheckResult("requirements.txt packages", True, "requirements.txt not present")
    missing = []
    for line in requirements.read_text(encoding="utf-8").splitlines():
        package = _requirement_import_name(line)
        if package and not import_checker(package):
            missing.append(package)
    return CheckResult("requirements.txt packages", not missing, f"missing={missing}" if missing else "all importable")


def _check_java(command_runner: CommandRunner) -> CheckResult:
    return _check_java_command(command_runner, "java")


def _check_javac(command_runner: CommandRunner) -> CheckResult:
    return _check_java_command(command_runner, "javac")


def _check_java_command(command_runner: CommandRunner, executable: str) -> CheckResult:
    """Require the selected runtime/compiler to use the generated Java target."""
    name = f"{'Java' if executable == 'java' else 'javac'} {constants.JAVA_VERSION}"
    try:
        result = command_runner([executable, "-version"])
    except FileNotFoundError:
        return CheckResult(name, False, f"{executable} not found")
    output = f"{result.stdout}\n{result.stderr}"
    version = _first_version(output)
    passed = result.returncode == 0 and version is not None and version[0] == int(constants.JAVA_VERSION)
    return CheckResult(name, passed, output.strip() or "no version output")


def _check_maven(command_runner: CommandRunner) -> CheckResult:
    try:
        result = command_runner(["mvn", "-version"])
    except FileNotFoundError:
        return CheckResult("Maven 3.8+", False, "mvn not found")
    output = re.sub(r"\x1b\[[0-9;]*m", "", f"{result.stdout}\n{result.stderr}")
    maven = re.search(r"Apache Maven\s+(\d+)\.(\d+)", output)
    java = re.search(r"Java version:\s*(\d+)", output, re.IGNORECASE)
    passed = (result.returncode == 0 and maven is not None and
              tuple(map(int, maven.groups())) >= (3, 8) and
              java is not None and int(java.group(1)) == int(constants.JAVA_VERSION))
    return CheckResult("Maven 3.8+", passed,
                       f"Requires Maven 3.8+ running JDK {constants.JAVA_VERSION}: {output.strip() or 'no version output'}")


def _check_composer_mapper(command_runner: CommandRunner) -> CheckResult:
    jar = Path(os.getenv("COMPOSER_MAPPER_JAR", constants.COMPOSER_MAPPER_JAR))
    if not jar.exists():
        return CheckResult("composer-mapper JAR", False, f"missing: {jar}")
    result = command_runner(["java", "-jar", str(jar), "--help"])
    return CheckResult("composer-mapper JAR", result.returncode == 0, f"exit={result.returncode}")


def _check_composer_root() -> CheckResult:
    path = Path(os.getenv("COMPOSER_ROOT", constants.COMPOSER_ROOT))
    return CheckResult("COMPOSER_ROOT readable", path.exists() and os.access(path, os.R_OK), str(path))


def _check_vault_root() -> CheckResult:
    path = Path(os.getenv("VAULT_ROOT", constants.VAULT_ROOT))
    try:
        path.mkdir(parents=True, exist_ok=True)
        return CheckResult("VAULT_ROOT exists", True, str(path))
    except OSError as exc:
        return CheckResult("VAULT_ROOT exists", False, str(exc))


def _check_output_root() -> CheckResult:
    path = Path(os.getenv("OUTPUT_ROOT", constants.OUTPUT_ROOT))
    return _check_writable_dir("OUTPUT_ROOT writable", path)


def _check_db_dir() -> CheckResult:
    db_path = Path(os.getenv("DB_PATH", constants.DB_PATH))
    return _check_writable_dir("DB_PATH directory writable", db_path.parent)


def _check_litellm(url_checker: UrlChecker) -> CheckResult:
    base_url = os.getenv("LITELLM_BASE_URL", constants.LITELLM_BASE_URL).rstrip("/")
    payload = b'{"model":"health-check","messages":[{"role":"user","content":"ping"}],"max_tokens":1}'
    passed = url_checker(f"{base_url}/v1/chat/completions", payload)
    return CheckResult("LiteLLM proxy reachable", passed, base_url)


def _check_legacy_service(url_checker: UrlChecker) -> CheckResult:
    base_url = os.getenv("LEGACY_SERVICE_BASE_URL", constants.LEGACY_SERVICE_BASE_URL)
    if not base_url:
        return CheckResult("Legacy service reachable", True, "not configured", blocking=False)
    passed = url_checker(base_url, None)
    return CheckResult("Legacy service reachable", passed, base_url, blocking=False)


def _check_sqlite_rw() -> CheckResult:
    db_path = Path(os.getenv("DB_PATH", constants.DB_PATH))
    temp_path = None
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(dir=db_path.parent, suffix=".db")
        os.close(fd)
        temp_path = Path(temp_name)
        conn = sqlite3.connect(temp_name)
        conn.execute("CREATE TABLE health_check (id INTEGER)")
        conn.execute("INSERT INTO health_check VALUES (1)")
        row = conn.execute("SELECT id FROM health_check").fetchone()
        conn.close()
        return CheckResult("SQLite write/read", row == (1,), str(db_path.parent))
    except Exception as exc:
        return CheckResult("SQLite write/read", False, str(exc))
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def _check_forbidden_dependencies() -> CheckResult:
    return CheckResult(
        "FORBIDDEN_DEPENDENCIES configured",
        bool(constants.FORBIDDEN_DEPENDENCIES),
        f"{len(constants.FORBIDDEN_DEPENDENCIES)} patterns",
    )


def _check_writable_dir(name: str, path: Path) -> CheckResult:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, delete=True):
            pass
        return CheckResult(name, True, str(path))
    except OSError as exc:
        return CheckResult(name, False, str(exc))


def _run_command(command: list[str]) -> subprocess.CompletedProcess:
    if command[0] == "mvn":
        from tools.maven_dependency_tools.command import maven_executable
        command = [maven_executable(), *command[1:]]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _can_import(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def _check_url(url: str, payload: bytes | None) -> bool:
    try:
        if payload is None:
            with urlopen(url, timeout=5):
                return True
        request = Request(url, data=payload, method="POST", headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5):
            return True
    except (OSError, URLError):
        return False


def _first_version(output: str) -> tuple[int, int] | None:
    match = re.search(r"(\d+)(?:\.(\d+))?", output)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2) or 0)


def _requirement_import_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    name = re.split(r"[<>=~!;\[]", stripped, maxsplit=1)[0].strip()
    return name.replace("-", "_") if name else None


def _load_env_file(env_path: str) -> None:
    for line in Path(env_path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    raise SystemExit(main())
