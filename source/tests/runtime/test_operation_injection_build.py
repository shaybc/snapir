"""Compile and execute saved operation routing with injected Mockito steps on Java 25."""

import json
from pathlib import Path
import re
import shutil
from types import SimpleNamespace

import pytest

from models.maven_dependency import MavenDependency
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.bundle_output import accept_bundle
from runtime.behavior_conversion.operation_dependencies import validate_step_injection
from runtime.behavior_conversion.operation_resources import validate_runtime_resources
from runtime.behavior_conversion.ownership import create_native_context
from runtime.java_toolchain import java_scope
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tests.runtime.test_behavior_conversion import profile
from tests.runtime.test_native_xml_build import OfflineVerifier
from tests.runtime.test_operation_dependencies import latest


def injected_latest():
    """Adapt the frozen failed service's construction only; preserve its routing body."""
    saved = latest()
    bundle = NativeUnitBundle.model_validate(saved["implementation"])
    file = bundle.files[0]
    source = file.content
    roles = []
    for binding, unit in saved["accepted_units"].items():
        for api in unit["apis"]:
            simple = api["type_name"].rsplit(".", 1)[-1]
            field = re.search(r"private final " + re.escape(simple) + r"\s+(\w+)\s*;", source)
            if field and simple.endswith("Step"):
                roles.append(dict(binding_id=binding, unit_id=unit["unit_id"], type_name=api["type_name"],
                                  parameter_name=field[1], field_name=field[1]))
    assert len(roles) == 14
    name = bundle.operation_contract.service_api.type_name.rsplit(".", 1)[-1]
    start = source.index("    public " + name + "(")
    body = source.index("{", start)
    end, depth = body + 1, 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    constructor = "    private final javax.sql.DataSource database;\n    public " + name + "("
    constructor += ", ".join(item["type_name"] + " " + item["parameter_name"] for item in roles) + ", javax.sql.DataSource database) {\n"
    constructor += '\n'.join("        this." + item["field_name"] + " = " + item["parameter_name"] + ";" for item in roles)
    constructor += '\n        this.database = database;\n        this.requestMapper = new TransferFundsRequestMapper();\n'
    constructor += '        this.responseMapper = new TransferFundsResponseMapper();\n        this.errorResponseMapper = new StandardErrorRSFmtMapper();\n    }'
    source = source[:start] + constructor + source[end:]
    execute = source.index("public String execute(")
    opening = source.index("{", execute)
    end, depth = opening + 1, 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    source = source[:opening + 1] + '\n        try(java.sql.Connection connection = this.database.getConnection()) {\n' + source[opening + 1:end - 1] + '\n        }\n' + source[end - 1:]
    source = source.replace("Map<String, Object> context = new HashMap<>();", 'Map<String, Object> context = new HashMap<>(); context.put("Connection", connection);')
    data = bundle.model_dump()
    data["files"][0]["content"] = source
    data["operation_contract"]["step_dependencies"] = roles
    data["operation_contract"]["runtime_resources"] = [dict(input_key="Connection", resource_type="java.sql.Connection", provider_type="javax.sql.DataSource", parameter_name="database", field_name="database")]
    return NativeUnitBundle.model_validate(data), saved, roles


def test_latest_routing_accepts_injected_steps_and_managed_connection():
    bundle, _, roles = injected_latest()
    validate_step_injection(bundle, [dict(binding_id=item["binding_id"], unit_id=item["unit_id"], allowed_types=[item["type_name"]]) for item in roles])
    validate_runtime_resources(bundle, [dict(input_key="Connection", resource_type="java.sql.Connection", provider_type="javax.sql.DataSource")])


def test_latest_route_java25_runs_without_real_database_and_releases_connection(tmp_path):
    if not shutil.which("mvn"):
        pytest.skip("Offline Maven unavailable")
    bundle, saved, roles = injected_latest()
    files = dict(saved["accepted_sources"])
    files.update({file.path: file.content for file in bundle.files})
    declarations = "\n".join(item["type_name"] + " " + item["parameter_name"] + " = mock(" + item["type_name"] + ".class);" for item in roles)
    arguments = ", ".join(item["parameter_name"] for item in roles) + ", database"
    request = saved["scenario"]["inputs"][0]
    source = ('package com.company.generated.operations.routing;\n'
        'import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*; import static org.mockito.Mockito.*; import static org.mockito.ArgumentMatchers.*;\n'
        'public class InjectedRouteTest { @Test public void followsSavedRouteWithoutJdbcServer() throws Exception {\n'
        + declarations + '\njavax.sql.DataSource database = mock(javax.sql.DataSource.class); java.sql.Connection connection = mock(java.sql.Connection.class); when(database.getConnection()).thenReturn(connection);\n'
        'when(validateTransferStep.execute(anyMap())).thenReturn(0); when(checkLimitsStep.execute(anyMap())).thenReturn(0); when(fraudCheckStep.execute(anyMap())).thenReturn(0); when(executeTransferStep.execute(anyMap())).thenReturn(0);\n'
        'var service = new com.company.generated.operations.TransferFundsOpService(' + arguments + ');\n'
        'String response = service.execute(' + json.dumps(request) + '); assertNotNull(response);\n'
        'var order = inOrder(validateTransferStep, checkLimitsStep, fraudCheckStep, executeTransferStep); order.verify(validateTransferStep).execute(anyMap()); order.verify(checkLimitsStep).execute(anyMap()); order.verify(fraudCheckStep).execute(anyMap()); order.verify(executeTransferStep).execute(anyMap());\n'
        'verify(connection).close();\n'
        'when(checkLimitsStep.execute(anyMap())).thenThrow(new IllegalStateException("fixture failure")); assertThrows(IllegalStateException.class, () -> service.execute(' + json.dumps(request) + ')); verify(connection, times(2)).close(); } }')
    files["src/test/java/com/company/generated/operations/routing/InjectedRouteTest.java"] = source
    settings = profile(java_version=25, java_home="C:/Program Files/Java/jdk-25.0.3")
    verifier = OfflineVerifier()
    def context(settings, project, artifact):
        return create_native_context(SimpleNamespace(run_id="injected-route-replay"), settings, project,
            lambda settings, project, artifact: ManagedBuildContext(str(project / "pom.xml"), verifier))
    with java_scope(settings):
        result, _ = accept_bundle(tmp_path / "project", files, context, settings,
            [MavenDependency.model_validate(item) for item in saved["known_dependencies"]])
    assert result["tests_passed"] and result["test_count"] == 1
