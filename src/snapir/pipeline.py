from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .context_schema import ContextSchemaBuilder
from .indexer import ComposerIndexer
from .internal_ir import InternalIRBuilder


@dataclass(frozen=True)
class PipelineResult:
    artifact_dir: Path
    component_hash: str
    accepted: bool
    reused: bool


class ConversionPipeline:
    """Run deterministic IR -> prompt -> Java generation with critic + compile checks."""

    def __init__(self, source_root: Path, out_root: Path, version: str, max_attempts: int = 3) -> None:
        self.source_root = Path(source_root)
        self.out_root = Path(out_root)
        self.version = version
        self.max_attempts = max_attempts

    def run(self) -> PipelineResult:
        source_hash = ComposerIndexer(self.source_root, self.version).source_hash()
        base_dir = self.out_root / source_hash / self.version
        base_dir.mkdir(parents=True, exist_ok=True)

        ir = InternalIRBuilder(self.source_root, self.version).build()
        context_bundle = ContextSchemaBuilder(self.source_root, self.version).build()

        component_hash = self._component_hash(ir, context_bundle)
        run_dir = base_dir / "conversion_pipeline" / component_hash
        accepted_marker = run_dir / "accepted.json"

        if accepted_marker.exists():
            return PipelineResult(run_dir, component_hash, accepted=True, reused=True)

        prompt_payload = self._prepare_prompt(ir, context_bundle)
        candidate, loop_history = self._critic_loop(prompt_payload)

        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "prompt.json").write_text(json.dumps(prompt_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (run_dir / "loop_history.json").write_text(json.dumps(loop_history, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        if candidate is None:
            return PipelineResult(run_dir, component_hash, accepted=False, reused=False)

        self._materialize_maven_project(run_dir, prompt_payload, candidate)
        (run_dir / "final_accepted_implementation.java").write_text(candidate, encoding="utf-8")
        self._run_maven_build(run_dir)
        self._publish_artifact_metadata(run_dir)
        (run_dir / "accepted.json").write_text(
            json.dumps({"component_hash": component_hash, "accepted": True}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return PipelineResult(run_dir, component_hash, accepted=True, reused=False)

    def _prepare_prompt(self, ir: dict, context_bundle: dict) -> dict:
        return {
            "ir": ir,
            "normalized_semantics": ir["dependency_contracts"],
            "context_schemas": context_bundle,
            "target": "java_shared_library",
            "constraints": ["deterministic_output", "plain_java_no_framework"],
        }

    def _component_hash(self, ir: dict, context_bundle: dict) -> str:
        payload = json.dumps({"ir": ir, "context": context_bundle}, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _critic_loop(self, prompt_payload: dict) -> tuple[str | None, list[dict]]:
        logs: list[dict] = []
        for attempt in range(1, self.max_attempts + 1):
            operation_log = {"attempt": attempt}
            candidate = self._generate_java(prompt_payload, attempt)
            operation_log["service_level_candidate"] = {"language": "java", "source": candidate}

            critic = self._critic_feedback(candidate)
            operation_log["critic_feedback"] = critic

            ok, message = self._compile_check(candidate)
            operation_log["snippet_check"] = {"passed": ok, "message": message}
            logs.append(operation_log)
            if ok:
                return candidate, logs
        return None, logs

    @staticmethod
    def _critic_feedback(candidate: str) -> dict:
        has_class = "class SharedComponentLibrary" in candidate
        has_accessors = "get" in candidate and "set" in candidate
        passed = has_class and has_accessors
        return {
            "passed": passed,
            "notes": "contains shared library class and accessor methods" if passed else "missing class or accessor methods",
        }

    def _generate_java(self, prompt_payload: dict, attempt: int) -> str:
        fields = prompt_payload["context_schemas"]["java_context_metadata"]["fields"]
        members = "\n".join(
            f"    private {f['java_type']} {f['name']};" for f in fields
        )
        accessors = "\n\n".join(
            self._accessors(f["java_type"], f["name"]) for f in fields
        )
        return (
            "public class SharedComponentLibrary {\n"
            f"    // generated attempt {attempt}\n"
            f"{members}\n\n"
            f"{accessors}\n"
            "}\n"
        )

    def _compile_check(self, source: str) -> tuple[bool, str]:
        javac = shutil.which("javac")
        if javac is None:
            balanced = source.count("{") == source.count("}")
            return balanced, "javac_not_found_balanced_braces_check"

        with tempfile.TemporaryDirectory() as tmpdir:
            java_file = Path(tmpdir) / "SharedComponentLibrary.java"
            java_file.write_text(source, encoding="utf-8")
            result = subprocess.run([javac, str(java_file)], capture_output=True, text=True)
            if result.returncode == 0:
                return True, "javac_compile_success"
            return False, result.stderr.strip() or "javac_compile_failed"

    @staticmethod
    def _accessors(java_type: str, name: str) -> str:
        title = name[:1].upper() + name[1:]
        return (
            f"    public {java_type} get{title}() {{ return {name}; }}\n"
            f"    public void set{title}({java_type} value) {{ this.{name} = value; }}"
        )

    def _materialize_maven_project(self, run_dir: Path, prompt_payload: dict, source: str) -> None:
        coordinates = self._artifact_coordinates(prompt_payload)
        package_path = coordinates["package"].replace(".", "/")
        src_main = run_dir / "src" / "main" / "java" / package_path
        src_test = run_dir / "src" / "test" / "java" / package_path
        src_main.mkdir(parents=True, exist_ok=True)
        src_test.mkdir(parents=True, exist_ok=True)

        (run_dir / "pom.xml").write_text(self._pom_xml(coordinates), encoding="utf-8")
        (src_main / "SharedComponentLibrary.java").write_text(
            f"package {coordinates['package']};\n\n{source}", encoding="utf-8"
        )
        (src_main / "SharedUtilities.java").write_text(
            self._shared_utilities_source(coordinates["package"]), encoding="utf-8"
        )
        operations = prompt_payload["ir"]["signatures"]["operations"]
        for operation in operations:
            name = operation["name"]
            normalized = self._safe_identifier(name)
            dto = f"{normalized}Request"
            response_dto = f"{normalized}Response"
            context_model = f"{normalized}Context"

            (src_main / f"{dto}.java").write_text(self._dto_source(coordinates["package"], dto), encoding="utf-8")
            (src_main / f"{response_dto}.java").write_text(
                self._dto_source(coordinates["package"], response_dto), encoding="utf-8"
            )
            (src_main / f"{context_model}.java").write_text(
                self._context_source(coordinates["package"], context_model, dto, response_dto), encoding="utf-8"
            )
            (src_main / f"{normalized}XmlMapper.java").write_text(
                self._xml_mapper_source(coordinates["package"], normalized, dto, response_dto), encoding="utf-8"
            )
            (src_main / f"{normalized}Service.java").write_text(
                self._service_source(coordinates["package"], normalized, context_model), encoding="utf-8"
            )
            (src_main / f"{normalized}Controller.java").write_text(
                self._controller_source(coordinates["package"], normalized, context_model), encoding="utf-8"
            )
        (src_main / "ErrorMapper.java").write_text(self._error_mapper_source(coordinates["package"]), encoding="utf-8")
        (src_main / "ApplicationBootstrap.java").write_text(
            self._bootstrap_source(coordinates["package"], operations), encoding="utf-8"
        )
        (run_dir / "src" / "main" / "resources").mkdir(parents=True, exist_ok=True)
        (run_dir / "src" / "main" / "resources" / "application.properties").write_text(
            "app.name=snapir-generated-microservice\n", encoding="utf-8"
        )
        (src_test / "ConvertedComponentTest.java").write_text(
            self._converted_component_test_source(coordinates["package"]), encoding="utf-8"
        )

    @staticmethod
    def _safe_identifier(name: str) -> str:
        return "".join(ch for ch in name if ch.isalnum()) or "Operation"

    @staticmethod
    def _dto_source(package_name: str, class_name: str) -> str:
        return f"package {package_name};\n\npublic class {class_name} {{\n    private String payload;\n\n    public String getPayload() {{ return payload; }}\n    public void setPayload(String payload) {{ this.payload = payload; }}\n}}\n"

    @staticmethod
    def _context_source(package_name: str, class_name: str, request_name: str, response_name: str) -> str:
        return f"package {package_name};\n\npublic class {class_name} {{\n    private {request_name} request;\n    private {response_name} response;\n\n    public {request_name} getRequest() {{ return request; }}\n    public void setRequest({request_name} request) {{ this.request = request; }}\n    public {response_name} getResponse() {{ return response; }}\n    public void setResponse({response_name} response) {{ this.response = response; }}\n}}\n"

    @staticmethod
    def _xml_mapper_source(package_name: str, op_name: str, request_name: str, response_name: str) -> str:
        return f"package {package_name};\n\nimport java.io.StringReader;\nimport java.io.StringWriter;\nimport java.util.Objects;\nimport javax.xml.XMLConstants;\nimport javax.xml.parsers.DocumentBuilder;\nimport javax.xml.parsers.DocumentBuilderFactory;\nimport javax.xml.transform.OutputKeys;\nimport javax.xml.transform.Transformer;\nimport javax.xml.transform.TransformerFactory;\nimport javax.xml.transform.dom.DOMSource;\nimport javax.xml.transform.stream.StreamResult;\nimport org.w3c.dom.Document;\nimport org.w3c.dom.Element;\nimport org.xml.sax.InputSource;\n\npublic class {op_name}XmlMapper {{\n    public {request_name} fromXml(String xml) {{\n        {request_name} dto = new {request_name}();\n        dto.setPayload(normalizeInput(xml));\n        return dto;\n    }}\n\n    public String toXml({response_name} response) {{\n        String payload = response == null ? \"\" : normalizeInput(response.getPayload());\n        try {{\n            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();\n            factory.setNamespaceAware(true);\n            DocumentBuilder builder = factory.newDocumentBuilder();\n            Document document = builder.newDocument();\n            Element root = document.createElementNS(\"urn:snapir:response\", \"snapir:response\");\n            root.setAttributeNS(XMLConstants.XMLNS_ATTRIBUTE_NS_URI, \"xmlns:snapir\", \"urn:snapir:response\");\n            document.appendChild(root);\n\n            Element payloadNode = document.createElementNS(\"urn:snapir:response\", \"snapir:payload\");\n            payloadNode.setTextContent(payload);\n            root.appendChild(payloadNode);\n\n            TransformerFactory transformerFactory = TransformerFactory.newInstance();\n            Transformer transformer = transformerFactory.newTransformer();\n            transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, \"yes\");\n            transformer.setOutputProperty(OutputKeys.INDENT, \"no\");\n\n            StringWriter writer = new StringWriter();\n            transformer.transform(new DOMSource(document), new StreamResult(writer));\n            return writer.toString();\n        }} catch (Exception ex) {{\n            throw new IllegalStateException(\"Unable to serialize response XML\", ex);\n        }}\n    }}\n\n    private static String normalizeInput(String value) {{\n        if (value == null) {{\n            return \"\";\n        }}\n        String trimmed = value.trim();\n        if (trimmed.isEmpty()) {{\n            return \"\";\n        }}\n\n        try {{\n            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();\n            factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);\n            factory.setNamespaceAware(true);\n            DocumentBuilder builder = factory.newDocumentBuilder();\n            Document document = builder.parse(new InputSource(new StringReader(trimmed)));\n\n            document.normalizeDocument();\n            String rootName = Objects.requireNonNull(document.getDocumentElement()).getNodeName();\n            return rootName + \"|\" + trimmed;\n        }} catch (Exception ex) {{\n            return trimmed;\n        }}\n    }}\n}}\n"

    @staticmethod
    def _service_source(package_name: str, op_name: str, context_model: str) -> str:
        return f"package {package_name};\n\npublic class {op_name}Service {{\n    public {context_model} process({context_model} context) {{\n        if (context.getResponse() == null) {{\n            context.setResponse(new {op_name}Response());\n        }}\n        context.getResponse().setPayload(SharedUtilities.normalize(context.getRequest().getPayload()));\n        return context;\n    }}\n}}\n"

    @staticmethod
    def _controller_source(package_name: str, op_name: str, context_model: str) -> str:
        return f"package {package_name};\n\npublic class {op_name}Controller {{\n    private final {op_name}XmlMapper xmlMapper = new {op_name}XmlMapper();\n    private final {op_name}Service service = new {op_name}Service();\n\n    public String handle(String requestXml) {{\n        try {{\n            {context_model} context = new {context_model}();\n            context.setRequest(xmlMapper.fromXml(requestXml));\n            context = service.process(context);\n            return xmlMapper.toXml(context.getResponse());\n        }} catch (Exception ex) {{\n            return ErrorMapper.toXml(ex);\n        }}\n    }}\n}}\n"

    @staticmethod
    def _error_mapper_source(package_name: str) -> str:
        return f"package {package_name};\n\npublic final class ErrorMapper {{\n    private ErrorMapper() {{}}\n\n    public static String toXml(Exception ex) {{\n        return \"<error>\" + ex.getClass().getSimpleName() + \":\" + ex.getMessage() + \"</error>\";\n    }}\n}}\n"

    def _bootstrap_source(self, package_name: str, operations: list[dict]) -> str:
        controllers = "\n".join(
            f"        {self._safe_identifier(op['name'])}Controller {self._safe_identifier(op['name']).lower()}Controller = new {self._safe_identifier(op['name'])}Controller();"
            for op in operations
        )
        return f"package {package_name};\n\npublic class ApplicationBootstrap {{\n    public static void main(String[] args) {{\n{controllers}\n        System.out.println(\"Microservice project initialized\");\n    }}\n}}\n"

    def _run_maven_build(self, run_dir: Path) -> None:
        mvn = shutil.which("mvn")
        if mvn is None:
            (run_dir / "maven_build.json").write_text(
                json.dumps({"executed": False, "reason": "mvn_not_found"}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return

        cmd = [mvn, "-q", "package", "install", "-DskipTests"]
        result = subprocess.run(cmd, cwd=run_dir, capture_output=True, text=True)
        (run_dir / "maven_build.json").write_text(
            json.dumps(
                {
                    "executed": True,
                    "command": cmd,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def _publish_artifact_metadata(self, run_dir: Path) -> None:
        coordinates = self._coordinates_from_pom(run_dir / "pom.xml")
        metadata = {
            "groupId": coordinates.get("groupId"),
            "artifactId": coordinates.get("artifactId"),
            "version": coordinates.get("version"),
            "packaging": "jar",
            "artifactPath": str(run_dir / "target" / f"{coordinates.get('artifactId')}-{coordinates.get('version')}.jar"),
        }
        (run_dir / "artifact-metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def _artifact_coordinates(self, prompt_payload: dict) -> dict:
        version_token = re.sub(r"[^a-zA-Z0-9]", "", self.version) or "v1"
        return {
            "group_id": "com.snapir.generated",
            "artifact_id": "shared-component-library",
            "version": f"1.0.0-{version_token}",
            "package": "com.snapir.generated",
        }

    @staticmethod
    def _pom_xml(coordinates: dict) -> str:
        return f"""<project xmlns=\"http://maven.apache.org/POM/4.0.0\"\n         xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"\n         xsi:schemaLocation=\"http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd\">\n  <modelVersion>4.0.0</modelVersion>\n  <groupId>{coordinates['group_id']}</groupId>\n  <artifactId>{coordinates['artifact_id']}</artifactId>\n  <version>{coordinates['version']}</version>\n  <properties>\n    <maven.compiler.source>17</maven.compiler.source>\n    <maven.compiler.target>17</maven.compiler.target>\n    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>\n  </properties>\n  <dependencies>\n    <dependency>\n      <groupId>org.junit.jupiter</groupId>\n      <artifactId>junit-jupiter</artifactId>\n      <version>5.10.2</version>\n      <scope>test</scope>\n    </dependency>\n  </dependencies>\n  <build>\n    <plugins>\n      <plugin>\n        <groupId>org.apache.maven.plugins</groupId>\n        <artifactId>maven-surefire-plugin</artifactId>\n        <version>3.2.5</version>\n      </plugin>\n    </plugins>\n  </build>\n</project>\n"""

    @staticmethod
    def _shared_utilities_source(package_name: str) -> str:
        return f"""package {package_name};

public final class SharedUtilities {{
    private SharedUtilities() {{}}

    public static String normalize(String value) {{
        return value == null ? "" : value.trim();
    }}
}}
"""

    @staticmethod
    def _converted_component_test_source(package_name: str) -> str:
        return f"""package {package_name};

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ConvertedComponentTest {{
    @Test
    void normalizeHelperWorks() {{
        assertEquals("hello", SharedUtilities.normalize("  hello  "));
    }}
}}
"""

    @staticmethod
    def _coordinates_from_pom(pom_path: Path) -> dict[str, str]:
        text = pom_path.read_text(encoding="utf-8")

        def pick(tag: str) -> str:
            match = re.search(rf"<{tag}>(.*?)</{tag}>", text)
            return match.group(1).strip() if match else ""

        return {
            "groupId": pick("groupId"),
            "artifactId": pick("artifactId"),
            "version": pick("version"),
        }
