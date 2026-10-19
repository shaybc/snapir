"""Discover existing JDBC input requirements and verify connection acquisition/release."""

import json
from pathlib import Path
import re

from runtime.java_public_type import _code
from runtime.behavior_conversion.method_contracts import java_type_resolver
from runtime.behavior_conversion.operation_dependencies import constructor_parameters


def required_resources(steps, accepted, connections=None):
    """Find JDBC connections read from a step's input without changing the accepted API."""
    result = {}
    for identity in {step["unit_id"] for step in steps}:
        unit = accepted[identity]
        for name in unit["files"]:
            if not name.startswith("src/main/java/"):
                continue
            source = (Path(unit["project"]) / name).read_text(encoding="utf-8")
            code = _code(source)
            resolve = java_type_resolver(source)
            for read in re.finditer(r'\(([\w.]+)\)\s*[\w.]+\.get\(\s*("(?:\\.|[^"\\])*")\s*\)', source):
                if not code[read.start():read.start() + 1].strip() or resolve(read[1]) != "java.sql.Connection":
                    continue
                key = json.loads(read[2])
                selected = (connections or {}).get(identity, [])
                jdbc = [item for item in selected if item.get('resource_kind') == 'jdbc']
                if jdbc:
                    for item in jdbc:
                        result[(key, item['connection_id'])] = dict(input_key=key, resource_type='java.sql.Connection',
                            provider_type='javax.sql.DataSource', connection_id=item['connection_id'])
                else:
                    result[key] = dict(input_key=key, resource_type="java.sql.Connection", provider_type="javax.sql.DataSource")
    return list(result.values())


def validate_runtime_resources(bundle, required):
    """Require the real operation to acquire, pass and release its JDBC connection."""
    if not required:
        return
    contract = bundle.operation_contract
    identified = any(item.get('connection_id') for item in required)
    resources = {(item.input_key, item.connection_id) if identified else item.input_key: item for item in contract.runtime_resources}
    expected_keys = {(item['input_key'], item.get('connection_id')) if identified else item['input_key'] for item in required}
    if len(resources) != len(contract.runtime_resources) or set(resources) != expected_keys:
        raise ValueError("Operation runtime_resources must configure every required input key: " + str(required))
    path = "src/main/java/" + contract.service_api.type_name.replace(".", "/") + ".java"
    source = next(file.content for file in bundle.files if file.path == path)
    code = _code(source)
    resolve = java_type_resolver(source, ["java.sql.Connection", "javax.sql.DataSource"])
    constructors = constructor_parameters(source, contract.service_api.type_name, ["javax.sql.DataSource"])
    for expected in required:
        item = resources[(expected['input_key'], expected.get('connection_id')) if identified else expected['input_key']]
        if (item.resource_type, item.provider_type) != (expected["resource_type"], expected["provider_type"]):
            raise ValueError(path + ": runtime resource type/provider changed for " + item.input_key)
        if not constructors or any((item.provider_type, item.parameter_name) not in args for args, _ in constructors):
            raise ValueError(path + ": constructor must receive runtime provider " + item.provider_type)
        for _, body in constructors:
            if not re.search(r"this\." + re.escape(item.field_name) + r"\s*=\s*(?:(?:[\w.]+\.)?requireNonNull\s*\(\s*)?" + re.escape(item.parameter_name) + r"\s*(?:\))?\s*;", body):
                raise ValueError(path + ": store supplied runtime provider " + item.parameter_name)
        acquisition = re.search(r"\btry\s*\(\s*([\w.]+)\s+(\w+)\s*=\s*(?:this\.)?" + re.escape(item.field_name) + r"\.getConnection\s*\(\s*\)\s*\)", code)
        if not acquisition or resolve(acquisition[1]) != item.resource_type:
            raise ValueError(path + ": acquire " + item.resource_type + " from supplied " + item.field_name + " with try-with-resources")
        passed = False
        for put in re.finditer(r'\.put\(\s*("(?:\\.|[^"\\])*")\s*,\s*' + re.escape(acquisition[2]) + r"\s*\)", source):
            if code[put.start():put.start() + 4].strip() and json.loads(put[1]) == item.input_key:
                passed = True
        if not passed:
            raise ValueError(path + ": pass the acquired connection as input key " + item.input_key)
