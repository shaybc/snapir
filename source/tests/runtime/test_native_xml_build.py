"""Build a representative Jackson native mapping bundle against locally cached jars."""

import shutil
from pathlib import Path

import pytest

from models.maven_dependency import MavenDependency
from runtime.behavior_conversion.bundle_output import accept_bundle, validate_bundle
from runtime.behavior_conversion.ownership import create_native_context
from runtime.java_toolchain import java_scope, run_java
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tests.runtime.test_behavior_conversion import profile
from models.native_unit_bundle import NativeUnitBundle
from types import SimpleNamespace


class OfflineVerifier:
    """Use local Maven cache only; no model or remote repository is contacted."""

    def __call__(self, dependency):
        jar = Path.home() / ".m2/repository" / dependency.group_id.replace(".", "/") / dependency.artifact_id / dependency.version
        if not (jar / f"{dependency.artifact_id}-{dependency.version}.jar").is_file():
            raise ValueError("Offline fixture dependency is missing: " + dependency.artifact_id)

    def compile_project(self, project, allowed=(), *, goal="compile"):
        return run_java([shutil.which("mvn"), "-o", "-B", "-q", "-Dmaven.repo.local=" + str(Path.home() / ".m2/repository"),
                        "-f", str(Path(project) / "pom.xml"), goal],
                        capture_output=True, text=True, timeout=120)


def test_jackson_structure_implied_decimals_and_response_mapping_build(tmp_path):
    if not shutil.which("mvn"):
        pytest.skip("Maven is unavailable for the optional real-build fixture")
    dependencies = [MavenDependency(group_id="com.fasterxml.jackson.dataformat", artifact_id="jackson-dataformat-xml",
                    version="2.17.2", reason="Fixture XML mapping"),
                    MavenDependency(group_id="org.junit.jupiter", artifact_id="junit-jupiter", version="5.10.2", scope="test", reason="Fixture behavior tests")]
    verifier = OfflineVerifier()
    try:
        for dependency in dependencies:
            verifier(dependency)
    except ValueError as exc:
        pytest.skip(str(exc))
    package = "com.company.generated.xmlfixture"
    prefix = "package " + package + ";\n"
    sources = {
        "Request": prefix + '''import com.fasterxml.jackson.dataformat.xml.annotation.*;
@JacksonXmlRootElement(localName="Request")
public class Request {
 @JacksonXmlProperty(isAttribute=true, localName="account") public String account;
 @JacksonXmlProperty(localName="Amount") public String amount;
}''',
        "Response": prefix + '''import com.fasterxml.jackson.dataformat.xml.annotation.*;
@JacksonXmlRootElement(localName="Response")
public class Response {
 @JacksonXmlProperty(isAttribute=true, localName="account") public String account;
 @JacksonXmlProperty(localName="Amount") public String amount;
}''',
        "BusinessInput": prefix + '''import java.math.BigDecimal;
public record BusinessInput(String account, BigDecimal amount) {}''',
        "RequestMapper": prefix + '''import java.math.BigDecimal;
public class RequestMapper {
 public BusinessInput unformat(Request wire) {
  return new BusinessInput(wire.account, new BigDecimal(wire.amount).movePointLeft(2));
 }
 public Response format(BusinessInput result) {
  Response wire = new Response(); wire.account = result.account();
  wire.amount = result.amount().movePointRight(2).toBigIntegerExact().toString(); return wire;
 }
}''',
    }
    test = prefix + '''import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import java.math.BigDecimal;
public class RequestMapperTest {
 @Test public void parsesStructureAndConvertsMinorUnits() throws Exception {
  Request request = new XmlMapper().readValue("<Request account=\\\"A&amp;B\\\"><Amount>1250</Amount></Request>", Request.class);
  BusinessInput result = new RequestMapper().unformat(request);
  assertEquals("A&B", result.account()); assertEquals(new BigDecimal("12.50"), result.amount());
 }
 @Test public void formatsResponseAndEscapesAttributes() throws Exception {
  Response response = new RequestMapper().format(new BusinessInput("A&B", new BigDecimal("12.50")));
  String xml = new XmlMapper().writeValueAsString(response);
  assertTrue(xml.startsWith("<Response")); assertTrue(xml.contains("account=\\\"A&amp;B\\\""));
  assertTrue(xml.contains("<Amount>1250</Amount>"));
 }
 @Test public void invalidNumericInputIsRejected() {
  Request request = new Request(); request.amount = "invalid";
  assertThrows(NumberFormatException.class, () -> new RequestMapper().unformat(request));
 }
 @Test public void lossyResponseScalingIsRejected() {
  assertThrows(ArithmeticException.class, () -> new RequestMapper().format(new BusinessInput("A", new BigDecimal("12.501"))));
 }
}'''
    files = [dict(path="src/main/java/" + package.replace(".", "/") + "/" + name + ".java", content=content) for name, content in sources.items()]
    files.append(dict(path="src/test/java/" + package.replace(".", "/") + "/RequestMapperTest.java", content=test))
    settings = profile(java_version=25)
    config = SimpleNamespace(run_id="offline-xml-fixture")
    def context(settings, project, artifact):
        return create_native_context(config, settings, project,
            lambda settings, project, artifact: ManagedBuildContext(str(project / "pom.xml"), verifier))
    with java_scope(settings):
        result, manifest = accept_bundle(tmp_path / "xml-fixture", validate_bundle(NativeUnitBundle(files=files)),
                                         context, settings, dependencies)
    assert result["build_passed"] and result["tests_passed"] and result["test_count"] == 4
    assert manifest and result["behavioral_equivalence"] == "not_available"
