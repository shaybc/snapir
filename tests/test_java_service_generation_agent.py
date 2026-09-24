from __future__ import annotations

import subprocess

from agents.java_service_generation.agent import (
    run_java_service_generation_agent,
    validate_generated_project,
)
from tools.state_store_tools.agent_tasks import get_agent_task, upsert_agent_task
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.generated_artifacts import get_generated_artifact


RUN_ID = "run-1"
TASK_ID = "task-service-generation"
OPERATION_ID = "TransferFunds"
CHANNEL = "INTERNET"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def compiled(returncode: int, stderr: str = ""):
    return subprocess.CompletedProcess(args=["mvn"], returncode=returncode, stdout="", stderr=stderr)


def add_task(conn, max_retries: int = 3):
    upsert_agent_task(
        conn,
        task_id=TASK_ID,
        run_id=RUN_ID,
        agent_name="JavaServiceGenerationAgent",
        scope_type="operation",
        scope_id=OPERATION_ID,
        channel=CHANNEL,
        target_language="java",
        status="pending",
        max_retries=max_retries,
    )


def project_files(pom_extra: str = "", controller_extra: str = "", repository_source: str | None = None):
    base = "src/main/java/com/company/internet/transferfunds"
    repository = repository_source or """
package com.company.internet.transferfunds.repository;
import org.springframework.jdbc.core.JdbcTemplate;
public class AccountRepository {
    private final JdbcTemplate jdbcTemplate;
    public AccountRepository(JdbcTemplate jdbcTemplate) { this.jdbcTemplate = jdbcTemplate; }
}
"""
    return {
        "pom.xml": f"""
<project>
  <properties><java.version>17</java.version></properties>
  <dependencies>
    <dependency><groupId>com.company.migration</groupId><artifactId>composer-common-lib</artifactId></dependency>
    {pom_extra}
  </dependencies>
</project>
""",
        "src/main/resources/application.properties": "server.port=8080\nspring.datasource.url=jdbc:h2:mem:test\nlogging.level.root=INFO\n",
        f"{base}/Application.java": "package com.company.internet.transferfunds; public class Application {}",
        f"{base}/controller/TransferFundsController.java": f"""
package com.company.internet.transferfunds.controller;
import org.springframework.web.bind.annotation.RestController;
@RestController
public class TransferFundsController {{
    private final TransferFundsService service;
    public TransferFundsController(TransferFundsService service) {{ this.service = service; }}
    public String execute(String body) {{ return service.execute(body); }}
    {controller_extra}
}}
""",
        f"{base}/service/TransferFundsServiceImpl.java": "package com.company.internet.transferfunds.service; public class TransferFundsServiceImpl {}",
        f"{base}/repository/AccountRepository.java": repository,
        f"{base}/xml/JaxbConfig.java": "package com.company.internet.transferfunds.xml; public class JaxbConfig {}",
        f"{base}/error/GlobalExceptionHandler.java": "package com.company.internet.transferfunds.error; public class GlobalExceptionHandler {}",
    }


def test_controller_generated_with_no_business_logic():
    issues = validate_generated_project(project_files(), OPERATION_ID)

    assert "controller contains business logic" not in issues


def test_controller_business_logic_is_rejected():
    issues = validate_generated_project(project_files(controller_extra="public void bad() { if (true) {} }"), OPERATION_ID)

    assert "controller contains business logic" in issues


def test_repository_generated_with_jdbc_template():
    issues = validate_generated_project(project_files(), OPERATION_ID)

    assert not any(issue.startswith("repository missing JdbcTemplate") for issue in issues)


def test_pom_contains_no_ibm_dependency():
    issues = validate_generated_project(project_files(pom_extra="<dependency><groupId>com.ibm</groupId></dependency>"), OPERATION_ID)

    assert "pom contains forbidden dependency: com.ibm" in issues


def test_mvn_compile_failure_triggers_retry(monkeypatch, tmp_path):
    conn = memory_conn()
    add_task(conn)
    calls = {"compile": 0, "generator_errors": []}

    def fake_compile(project_root):
        calls["compile"] += 1
        if calls["compile"] == 1:
            return compiled(1, "compile failed")
        return compiled(0)

    def generator(error):
        calls["generator_errors"].append(error)
        return project_files()

    monkeypatch.setattr("agents.java_service_generation.agent._mvn_compile", fake_compile)

    result = run_java_service_generation_agent(
        conn,
        TASK_ID,
        OPERATION_ID,
        CHANNEL,
        RUN_ID,
        generator,
        output_root=str(tmp_path),
    )

    task = get_agent_task(conn, TASK_ID)
    artifact = get_generated_artifact(conn, f"{RUN_ID}:java_service:{OPERATION_ID}:{TASK_ID}")
    assert result == "compiled"
    assert calls["generator_errors"] == [None, "compile failed"]
    assert task["status"] == "completed"
    assert artifact["status"] == "converted"
