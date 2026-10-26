"""Replay format corrections and verify nil stays on its evidenced child element."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from agents.behavior_conversion.format_mapping import INSTRUCTION, XML_NULL_MAPPING_GUIDANCE
from models.native_unit_bundle import NativeUnitBundle, NativeSourceFile
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.bundle_output import accept_bundle, validate_bundle
from runtime.behavior_conversion.ownership import create_native_context
from runtime.behavior_conversion.testing_contract import testing_contract as get_testing_contract
from runtime.java_toolchain import java_scope
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tests.runtime.test_behavior_conversion import profile, state
from tests.runtime.test_native_xml_build import OfflineVerifier


def failures():
    return json.loads((Path(__file__).parent / "fixtures/transfer_response_nil_failures.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind", ["request_unformat", "response_format"])
def test_format_prompt_and_saved_failure_corrections_explain_element_scope(kind):
    conn, config = state()
    saved = failures()
    requests = []
    def model(instruction, encoded):
        requests.append(json.loads(encoded))
        assert XML_NULL_MAPPING_GUIDANCE in instruction
        assert "nullable child must not make a populated response nil" in instruction
        return json.dumps(saved[len(requests) - 1]["response"])
    def validate(candidate, cached):
        raise ValueError(saved[len(requests) - 1]["error"])
    with pytest.raises(ValueError, match="Maven test"):
        generate(conn, config, profile(max_agent_task_retries=len(saved)), "unit", "format", INSTRUCTION, {"kind": kind},
            NativeUnitBundle, validator=validate, model_call=model)
    assert len(requests) == 3
    for index in (1, 2):
        feedback = requests[index]["correction_feedback"]
        assert saved[index - 1]["error"] in feedback
        assert XML_NULL_MAPPING_GUIDANCE in feedback
        assert "null guard" in feedback and "specific element" in feedback
    assert conn.execute("select error from behavior_attempts order by attempt desc limit 1").fetchone()[0].endswith(XML_NULL_MAPPING_GUIDANCE)


def test_xml_guidance_is_not_injected_into_op_step_corrections():
    conn, config = state()
    candidate = NativeUnitBundle.model_validate(failures()[2]["response"])
    requests = []
    def model(instruction, encoded):
        requests.append(json.loads(encoded))
        return candidate.model_dump_json()
    def validate(candidate, cached):
        raise ValueError("step failure")
    with pytest.raises(ValueError, match="step failure"):
        generate(conn, config, profile(), "unit", "step", "Convert step", {"kind": "configured_step"},
            NativeUnitBundle, validator=validate, model_call=model)
    assert requests[1]["correction_feedback"] == "step failure"


def test_latest_response_reproduces_failure_and_child_level_fix_preserves_values(tmp_path):
    jdk = Path("C:/Program Files/Java/jdk-25.0.3")
    if not shutil.which("mvn") or not jdk.is_dir():
        pytest.skip("Offline Maven/JDK unavailable")
    candidate = NativeUnitBundle.model_validate(failures()[2]["response"])
    settings = profile(java_version=25, java_home=str(jdk))
    verifier = OfflineVerifier()
    def context(settings, project, artifact):
        return create_native_context(SimpleNamespace(run_id="xml-null-replay"), settings, project,
            lambda settings, project, artifact: ManagedBuildContext(str(project / "pom.xml"), verifier))
    def build(name):
        files = validate_bundle(candidate, candidate.unit_contract.apis, candidate.unit_contract.requirements, candidate.evidence_ids)
        return accept_bundle(tmp_path / name, files, context, settings, candidate.dependencies,
            required_tests={file for paths in candidate.coverage.values() for file in paths},
            testing_contract=get_testing_contract(settings))
    with java_scope(settings):
        with pytest.raises(ValueError, match="testNilDecoratorHandling"):
            build("original")
    for file in candidate.files:
        if file.path.endswith("TransferFundsResponseXml.java"):
            file.content = file.content.replace("public String fraudCheckSkipped;", "public NullableText fraudCheckSkipped;")
            file.content = file.content.replace("public String xsiNil;", "public static class NullableText {\n" +
                "    @com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlText public String value;\n" +
                "    @JacksonXmlProperty(localName=\"nil\", isAttribute=true, namespace=\"http://www.w3.org/2001/XMLSchema-instance\") public String nil;\n}")
            # The previous root attribute annotation must move to the child wrapper only.
            file.content = file.content.replace("    @JacksonXmlProperty(localName = \"nil\", isAttribute = true, namespace = \"http://www.w3.org/2001/XMLSchema-instance\")\n", "")
        if file.path.endswith("TransferFundsResponseMapper.java"):
            file.content = file.content.replace('xml.fraudCheckSkipped = business.getFraudCheckSkipped() ? "true" : "false";',
                'xml.fraudCheckSkipped = new TransferFundsResponseXml.NullableText();\n            xml.fraudCheckSkipped.value = business.getFraudCheckSkipped() ? "true" : "false";')
            file.content = file.content.replace('xml.xsiNil = "true";', 'xml.fraudCheckSkipped = new TransferFundsResponseXml.NullableText();\n            xml.fraudCheckSkipped.nil = "true";')
            file.content = file.content.replace('"true".equalsIgnoreCase(xml.xsiNil) || (xml.fraudCheckSkipped == null || xml.fraudCheckSkipped.isBlank())',
                'xml.fraudCheckSkipped == null || "true".equalsIgnoreCase(xml.fraudCheckSkipped.nil) || xml.fraudCheckSkipped.value == null || xml.fraudCheckSkipped.value.isBlank()')
            file.content = file.content.replace('Boolean.parseBoolean(xml.fraudCheckSkipped)', 'Boolean.parseBoolean(xml.fraudCheckSkipped.value)')
    package = candidate.unit_contract.apis[0].type_name.rsplit(".", 1)[0]
    candidate.files.append(NativeSourceFile(path="src/test/java/" + package.replace(".", "/") + "/XmlNilScopeTest.java", content="package " + package + ";\n" + '''
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
public class XmlNilScopeTest {
 @Test public void nullChildPreservesRootAndSibling() throws Exception {
  TransferFundsResponseBusiness business = new TransferFundsResponseBusiness();
  business.setTransferId("REFERENCE"); business.setFraudCheckSkipped(null);
  TransferFundsResponseMapper mapper = new TransferFundsResponseMapper();
  String xml = mapper.format(business);
  var factory = javax.xml.parsers.DocumentBuilderFactory.newInstance(); factory.setNamespaceAware(true);
  var root = factory.newDocumentBuilder().parse(new java.io.ByteArrayInputStream(xml.getBytes(java.nio.charset.StandardCharsets.UTF_8))).getDocumentElement();
  String xsi = "http://www.w3.org/2001/XMLSchema-instance";
  assertFalse(root.hasAttributeNS(xsi, "nil"));
  var child = (org.w3c.dom.Element) root.getElementsByTagName("FraudCheckSkipped").item(0);
  assertEquals("true", child.getAttributeNS(xsi, "nil"));
  assertEquals("REFERENCE", root.getElementsByTagName("TransferId").item(0).getTextContent());
  var result = mapper.unformat(xml); assertNotNull(result);
  assertEquals("REFERENCE", result.getTransferId()); assertNull(result.getFraudCheckSkipped());
 }
}'''))
    with java_scope(settings):
        result, _ = build("corrected")
    assert result["build_passed"] and result["tests_passed"] and result["test_count"] == 4
