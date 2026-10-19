"""Require configured step objects to be supplied rather than created by the service."""

import re

from runtime.java_public_type import _code
from runtime.behavior_conversion.method_contracts import java_type_resolver, _parameters

REQUIREMENT = dict(requirement_id="operation-step-injection", version=1,
    description="Receive all configured operation-step objects through the service constructor; never construct them inside the service. Preserve role bindings and configure required external resources.")


def required_steps(bindings, units, accepted):
    """Keep one constructor role per configured step, including repeated Java types."""
    return [dict(binding_id=binding, unit_id=identity,
                 allowed_types=[api["type_name"] for api in accepted[identity]["contract"]["apis"]])
            for binding, identity in bindings.items() if units[identity].kind == "configured_step"]


def constructor_parameters(source, type_name, known_types=()):
    """Read public constructors using balanced Java parameter/body delimiters."""
    code = _code(source)
    resolve = java_type_resolver(source, known_types)
    name = type_name.rsplit(".", 1)[-1]
    result = []
    for match in re.finditer(r"\bpublic\s+" + re.escape(name) + r"\s*\(", code):
        if code[:match.start()].count("{") - code[:match.start()].count("}") != 1:
            continue
        start, end, depth = match.end(), match.end(), 1
        while end < len(code) and depth:
            depth += (code[end] == "(") - (code[end] == ")")
            end += 1
        parameters = []
        for parameter in _parameters(code[start:end - 1]):
            parameter = re.sub(r"@[\w.]+(?:\([^()]*\))?\s*", "", parameter)
            parameter = re.sub(r"\bfinal\s+", "", parameter).strip()
            declaration = re.fullmatch(r"(.+?)\s+([\w$]+)", parameter, re.S)
            if not declaration:
                raise ValueError("Unsupported constructor parameter: " + parameter)
            parameters.append((resolve(declaration[1]), declaration[2]))
        body_start = code.find("{", end)
        if body_start < 0:
            continue
        body_end, depth = body_start + 1, 1
        while body_end < len(code) and depth:
            depth += (code[body_end] == "{") - (code[body_end] == "}")
            body_end += 1
        result.append((parameters, code[body_start + 1:body_end - 1]))
    return result


def validate_step_injection(bundle, steps):
    """Check actual Java wiring as well as immutable role/type metadata before compile."""
    if not steps:
        return
    contract = bundle.operation_contract
    if contract is None:
        raise ValueError("Operation constructor metadata is missing")
    declared = {item.binding_id: item for item in contract.step_dependencies}
    expected = {item["binding_id"]: item for item in steps}
    if len(declared) != len(contract.step_dependencies) or set(declared) != set(expected):
        raise ValueError("Service constructor must receive each configured step role: " + ", ".join(expected))
    for binding, item in declared.items():
        target = expected[binding]
        if item.unit_id != target["unit_id"] or item.type_name not in target["allowed_types"]:
            raise ValueError("Constructor role " + binding + " must use an accepted type from " + str(target["allowed_types"]))
    names = [item.parameter_name for item in declared.values()]
    fields = [item.field_name for item in declared.values()]
    if len(set(names)) != len(names) or len(set(fields)) != len(fields):
        raise ValueError("Each configured step role needs its own constructor argument and field")
    known = [name for item in steps for name in item["allowed_types"]]
    path = "src/main/java/" + contract.service_api.type_name.replace(".", "/") + ".java"
    files = {file.path: file.content for file in bundle.files}
    if path not in files:
        raise ValueError("Service constructor source is missing: " + path)
    constructors = constructor_parameters(files[path], contract.service_api.type_name, known)
    if not constructors:
        raise ValueError(path + ": public constructor accepting configured steps is missing")
    for parameters, body in constructors:
        for item in declared.values():
            if (item.type_name, item.parameter_name) not in parameters:
                raise ValueError(path + ": constructor must receive " + item.type_name + " as " + item.parameter_name)
            value = re.escape(item.parameter_name)
            assignment = (r"\bthis\." + re.escape(item.field_name) + r"\s*=\s*(?:" + value
                + r"|(?:[\w.]+\.)?requireNonNull\s*\(\s*" + value + r"\s*(?:,\s*[^;]*)?\))\s*;")
            if not re.search(assignment, body):
                raise ValueError(path + ": store supplied " + item.parameter_name + " in this." + item.field_name)
            code = _code(files[path])
            resolver = java_type_resolver(files[path], known)
            field = re.search(r"\b(?:private|protected|public)\s+(?:final\s+)?([\w.$<>?, ]+)\s+" + re.escape(item.field_name) + r"\s*;", code)
            if not field or resolver(field[1]) != item.type_name:
                raise ValueError(path + ": field " + item.field_name + " must have accepted type " + item.type_name)
            if not re.search(r"\b(?:this\.)?" + re.escape(item.field_name) + r"\s*\.\s*[\w$]+\s*\(", code):
                raise ValueError(path + ": supplied step field is not called: " + item.field_name)
    for name, source in files.items():
        if not name.startswith("src/main/java/"):
            continue
        resolver = java_type_resolver(source, known)
        for creation in re.finditer(r"\bnew\s+([\w.$]+)\s*\(", _code(source)):
            if resolver(creation[1]) in {item.type_name for item in declared.values()}:
                raise ValueError(name + ": do not construct " + creation[1] + "; use the supplied constructor argument")
