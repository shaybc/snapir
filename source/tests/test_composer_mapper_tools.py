from __future__ import annotations

from models.common_models import RunConfig, RunMode, TargetLanguage
from tools.composer_mapper_tools.format_parser import parse_format_note
from tools.composer_mapper_tools.frontmatter_parser import parse_frontmatter
from tools.composer_mapper_tools.java_class_parser import parse_java_class_note
from tools.composer_mapper_tools.opstep_parser import parse_opstep_note
from tools.composer_mapper_tools.vault_importer import import_vault
from tools.state_store_tools.db import create_all_tables, get_connection


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def run_config(tmp_path, *, include=None, exclude=None):
    return RunConfig(
        run_id="run-1",
        run_mode=RunMode.single_channel,
        source_root=str(tmp_path / "composer"),
        vault_root=str(tmp_path / "vault"),
        output_root=str(tmp_path / "out"),
        db_path=str(tmp_path / "state.db"),
        target_channels=["INTERNET"],
        composer_mapper_channel_filter="INTERNET",
        target_languages=[TargetLanguage.java],
        enable_git=False,
        artifact_schema_version="v1",
        max_agent_task_retries=3,
        max_parallel_conversion_workers=4,
        max_parallel_llm_tasks=2,
        max_parallel_build_tasks=2,
        max_operations_per_batch=5,
        model_name="model",
        model_base_url="http://localhost",
        auto_rerun_impacted_operations=True,
        include_operations=include,
        exclude_operations=exclude,
    )


def make_vault(tmp_path):
    vault = tmp_path / "vault"
    (vault / "analysis").mkdir(parents=True)
    (vault / "channels").mkdir()
    (vault / "operations").mkdir()
    (vault / "opsteps").mkdir()
    (vault / "formats").mkdir()
    (vault / "contexts").mkdir()
    (vault / "classes" / "com" / "bank").mkdir(parents=True)
    (vault / "analysis" / "channel-operation-registry.md").write_text(
        """
# Channel Operation Registry

| Operation | Channel | XML File Path |
|---|---|---|
| OpA | INTERNET | `OpA.xml` |
| OpB | INTERNET | `OpB.xml` |
"""
    )
    (vault / "channels" / "INTERNET.md").write_text(
        """
# Channel: INTERNET

---
entity_type: channel
entity_id: INTERNET
---

## Tag Mappings
- CCString: com.ibm.CCString
"""
    )
    for op in ["OpA", "OpB"]:
        (vault / "operations" / f"{op}.md").write_text(
            f"""
# {op}

---
entity_type: operation
entity_id: {op}
conversion_status: not_started
channel: INTERNET
source_file: {op}.xml
source_hash: hash-{op}
---

## Steps
- Step{op}
"""
        )
    return vault


def test_parse_frontmatter_handles_missing_delimiters_gracefully():
    assert parse_frontmatter("# No frontmatter") == {}


def test_parse_opstep_note_extracts_return_body_switches():
    md = """
# StepA

---
entity_type: opStep
entity_id: StepA
conversion_status: not_started
used_by_operations:
  - OpA
source_file: OpA.xml
source_hash: hash-step
---

## Implementation
- com.bank.StepA

## Return Body Switches
- When these return codes occur, the reply format body is switched to the named error format before the response is built.
- RC `4` -> switch reply body to `ErrorBody`
"""
    step = parse_opstep_note(md, "StepA.md")

    assert step.return_body_switches == {"4": "ErrorBody"}


def test_parse_format_note_builds_decorator_chains_from_structure():
    md = """
# RequestFmt

---
entity_type: format
entity_id: RequestFmt
conversion_status: not_started
shared: false
used_by_operations:
  - OpA
source_file: format.xml
source_hash: hash-format
---

## Structure
```xml
<CCString dataName="AccountId">
</CCString>
  decorator: <RemoveLeadingZerosDecorator/>
  decorator: <CCPadding/>
```
"""
    fmt = parse_format_note(md, "RequestFmt.md")

    assert fmt.decorator_chains == {
        "AccountId/CCString": ["RemoveLeadingZerosDecorator", "CCPadding"]
    }


def test_parse_java_class_note_sets_ibm_dependency_warning():
    md = """
# com.bank.StepA

---
entity_type: java_class
entity_id: com.bank.StepA
conversion_status: not_started
shared: false
used_by_steps:
  - StepA
parent_class: com.ibm.StepBase
interfaces: []
source_file: StepA.java
source_hash: hash-java
---

## IBM Dependency Warning
- This class imports IBM/WebSphere APIs and must be converted for non-WAS runtimes.
- `com.ibm.wsbcc.StepBase`
"""
    java_class = parse_java_class_note(md, "StepA.md")

    assert java_class.has_ibm_dependency is True
    assert java_class.ibm_imports == ["com.ibm.wsbcc.StepBase"]


def test_import_vault_with_include_operations_excludes_other_operations(tmp_path):
    conn = memory_conn()
    vault = make_vault(tmp_path)

    summary = import_vault(conn, str(vault), run_config(tmp_path, include=["OpA"]))

    rows = conn.execute("SELECT operation_id FROM operations ORDER BY operation_id").fetchall()
    assert [row["operation_id"] for row in rows] == ["OpA"]
    assert summary.channel_operations == 2


def test_import_vault_with_exclude_operations_removes_operation(tmp_path):
    conn = memory_conn()
    vault = make_vault(tmp_path)

    import_vault(conn, str(vault), run_config(tmp_path, exclude=["OpA"]))

    rows = conn.execute("SELECT operation_id FROM operations ORDER BY operation_id").fetchall()
    assert [row["operation_id"] for row in rows] == ["OpB"]
