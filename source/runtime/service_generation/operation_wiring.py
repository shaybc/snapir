"""Generate and verify real Spring wiring for constructor-injected native operations."""

import re
from pathlib import Path
from xml.etree import ElementTree

from runtime.java_public_type import _code
from runtime.behavior_conversion.method_contracts import java_type_resolver
from runtime.service_generation.bean_methods import bean_methods

WIRING_VERSION = "operation-wiring-v4"
WIRING_INSTRUCTION = """Use operation.contract.step_dependencies and runtime_resources as the
authoritative constructor wiring contract. Generate a Spring @Configuration class with @Bean
factories for EVERY configured step role and the operation service. Pass the real step objects
to the service constructor, never Mockito/test substitutes. Instantiate steps through their
actual accepted constructors and configure their exact XML attributes; preserve approved source.
Use binding_id as a distinct bean name and @Qualifier when different configured roles use the
same type. Declare each role factory as @Bean(name = "exact binding_id"), preserving case.
Putting @Qualifier on a factory does not set its bean name; @Bean without a name defaults
to the Java method name, which may differ from binding_id. Qualify injection parameters
with that exact bean name. Supply other constructor dependencies through their actual accepted APIs.
For runtime_resources providers, generate real configuration, not TODOs or manual-code instructions.
For JDBC DataSource, bind spring.datasource.url, username and password to deployment environment
placeholders; a driver/configuration may be supplied through settings. Use current known library
coordinates, never assume a vendor or invent credentials. Connections are acquired/released by
the accepted operation implementation. Preserve original error and transaction behavior.
Other external clients must also be configured using supplied evidence and deployment properties.
Include an executable wiring test that starts the generated Spring configuration with test
substitutes for external resources, retrieves the real service and real step beans and verifies
constructor roles. This test needs no real database/API. Do not mock the operation service or
rewrite approved code. Missing deployment VALUES are configuration, not missing Java code.
Report missing behavioral information explicitly rather than generating incomplete production wiring."""

from runtime.service_generation.startup_resources import STARTUP_EXAMPLE, validate_startup_substitutes

WIRING_INSTRUCTION += '\n' + STARTUP_EXAMPLE + '''
Production driver-class-name must come from deployment settings, never a hard-coded
setDriverClassName literal. If you supply a default driver class, declare its actual
verified artifact in compile/runtime scope with that class in required_classes. Use known
coordinates/versions. Do not silently select H2 or another vendor absent source evidence.
External production clients must execute the real integration, never return canned success replies.'''


def validate_operation_wiring(files, contract):
    """Require typed bean factories and an executable Spring wiring test."""
    if not contract or not contract.get("step_dependencies"):
        return
    required = [contract["service_api"]["type_name"]]
    required.extend(item["type_name"] for item in contract["step_dependencies"])
    required.extend(item["provider_type"] for item in contract.get("runtime_resources", []))
    bean_types, configurations, roles = set(), [], set()
    for path, source in files.items():
        if not path.startswith("src/main/java/"):
            continue
        code = _code(source)
        if re.search(r"\borg\.mockito\b|\bMockito\s*\.", code):
            raise ValueError("Production wiring must supply real objects, not test mocks: " + path)
        if not re.search(r"@(?:[\w.]+\.)?Configuration\b", code):
            continue
        configurations.append(path)
        resolve = java_type_resolver(source, required)
        for return_type, method_name, aliases in bean_methods(source):
            bean_type = resolve(return_type)
            bean_types.add(bean_type)
            roles.add((bean_type, aliases[0]))
    missing = set(required) - bean_types
    if missing:
        raise ValueError("Spring configuration is missing real bean factories for: " + ", ".join(sorted(missing)))
    absent = [(item["type_name"], item["binding_id"]) for item in contract["step_dependencies"]
              if (item["type_name"], item["binding_id"]) not in roles]
    if absent:
        raise ValueError("Spring configuration must provide distinct named step-role beans: " + str(absent)
                         + '. Set @Bean(name = "binding_id") on each factory using the exact case-sensitive binding_id. '
                         'A factory @Qualifier alone does not set its bean name; keep matching @Qualifier values on injection parameters.')
    tests = [source for path, source in files.items() if path.startswith("src/test/java/")]
    if not any("AnnotationConfigApplicationContext" in _code(source) and ".getBean(" in _code(source)
               and re.search(r"@(?:[\w.]+\.)?Test\b", _code(source)) for source in tests):
        raise ValueError("Generate an executable Spring wiring test using AnnotationConfigApplicationContext and getBean for the real service")
    if contract.get("runtime_resources"):
        validate_startup_substitutes(files, contract)
        properties = "\n".join(source for path, source in files.items() if path.endswith("application.properties"))
        if any(item["provider_type"] == "javax.sql.DataSource" for item in contract["runtime_resources"]):
            if not all(re.search(r"(?m)^\s*" + re.escape(name) + r"\s*=\s*\$\{[^}]+\}", properties)
                       for name in ("spring.datasource.url", "spring.datasource.username", "spring.datasource.password")):
                raise ValueError("Generated JDBC configuration must bind URL, username and password to deployment settings")


def validate_wiring_execution(project, files, contract, result):
    """Require the generated startup test to execute successfully, not just compile."""
    if not contract or not contract.get("step_dependencies"):
        return
    required = set()
    for path, source in files.items():
        code = _code(source)
        if path.startswith("src/test/java/") and "AnnotationConfigApplicationContext" in code and ".getBean(" in code:
            required.add(path[len("src/test/java/"):-len(".java")].replace("/", "."))
    passed = set()
    for report in (Path(project) / "target/surefire-reports").glob("TEST-*.xml"):
        root = ElementTree.parse(report).getroot()
        for case in root.iter("testcase"):
            if not any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
                passed.add(case.get("classname"))
    result["wiring_passed"] = bool(required) and required <= passed
    if not result["wiring_passed"]:
        result["test_status"] = "failed"
        result.setdefault("failure_class", "wiring_test_not_executed")
        result["wiring_feedback"] = "Run the generated Spring startup tests successfully: " + ", ".join(sorted(required - passed))
