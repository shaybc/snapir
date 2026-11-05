"""Validate native bundles and stage candidate Maven projects before publishing."""

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from runtime.operation_layout import artifact_name
from runtime.java_public_type import converted_java_identity, _code
from tools.validation_tools.ibm_dependency_guard_tool import scan_source
from constants import FORBIDDEN_DEPENDENCIES
from runtime.behavior_conversion.method_contracts import has_method_contract
from runtime.behavior_conversion.java_api_types import public_api_types
from runtime.behavior_conversion.validation_progress import progress_step
from runtime.behavior_conversion.side_road_policy import baseline_stage, ForbiddenFrameworkDependency
from runtime.behavior_conversion.native_reflection_policy import reject_native_reflection


def validate_bundle(bundle, apis=(), requirements=(), evidence_ids=(), allowed_classes=(), *, dependency_files=(), api_inventory=None):
    """Reject unsafe paths, incomplete code, undeclared contracts and unsupported claims."""
    if bundle.unresolved_questions:
        raise ValueError("Unresolved behavior: " + "; ".join(bundle.unresolved_questions))
    files = {}
    for item in bundle.files:
        name = item.path
        path = PurePosixPath(name)
        if "\\" in name or ":" in name or path.is_absolute() or ".." in path.parts or str(path) != name:
            raise ValueError("Unsafe native bundle path: " + name)
        if not name.startswith(("src/main/java/", "src/test/java/")) or not name.endswith(".java"):
            raise ValueError("Native bundles contain only Java main/test sources")
        if name in files:
            raise ValueError("Duplicate generated path: " + name)
        reject_native_reflection(name, item.content)
        code = _code(item.content)
        unfinished_exception = re.search(r'\bUnsupportedOperationException\b(?!\s*\.\s*class\b)', code)
        if "TODO" in item.content or unfinished_exception:
            raise ValueError("Native bundle contains unfinished implementation: " + name)
        package, type_name = converted_java_identity(item.content)
        source_root = "src/test/java/" if name.startswith("src/test/java/") else "src/main/java/"
        if name != source_root + package.replace(".", "/") + "/" + type_name + ".java":
            raise ValueError("Source filename/package mismatch: " + name)
        findings = scan_source(item.content, FORBIDDEN_DEPENDENCIES, allowed_classes=allowed_classes, include_locations=True)
        if findings:
            references = sorted(set(re.findall(r"\bcom\.ibm(?:\.\w+)+", _code(item.content))))
            raise ForbiddenFrameworkDependency("Prohibited framework dependency in " + name + " (type " + package + "." + type_name +
                "): " + "; ".join(references or findings) + " (line:pattern " + "; ".join(findings) + ")" +
                ". Remove these imports/references from implementation and tests. If the unit needs this supporting behavior, "
                "include a native companion implementation derived from the supplied supporting source evidence and wire its "
                "callers, public API metadata and tests to that returned type. Reuse an accepted native API if supplied; "
                "retain ordinary external APIs only through declared dependencies. Do not invent a migrated package, "
                "restore an IBM import, or supply only an interface/mock for required production behavior. "
                "Use typed inputs/results for steps and Jackson wire models with plain mapper transformations for formats; "
                "do not recreate a Composer runtime.")
        recreated = re.search(r"\b(?:class|interface)\s+(Context|CCOperationStep|AbstractFormatElement|FormatDecoratorHolder)\b", _code(item.content))
        if recreated and not baseline_stage():
            raise ValueError("Do not recreate a Composer runtime type: " + recreated.group(1) + " in " + name +
                ". Remove this type and its callers. Generate typed arguments/results instead of Context; "
                "implement formatting and decorator behavior as plain mapper methods with Jackson XML models. "
                "Do not copy or rename holders, Tag initialization or decorator-chain classes.")
        files[name] = item.content
    combined = "\n".join(value for name, value in files.items() if name.startswith("src/main/java/"))
    api_sources = {identity: name for name, content in files.items() if name.startswith("src/main/java/")
                   for identity in public_api_types(content)}
    known_types = set(api_sources)
    inventory = api_inventory
    for api in apis:
        expected = api_sources.get(api.type_name)
        if expected is None:
            raise ValueError("Planned native API is missing: " + api.type_name)
        for signature in api.method_signatures:
            if not has_method_contract(files[expected], signature, known_types, owner_type=api.type_name):
                if inventory is None and re.search(r'\b(?:extends|implements)\b', _code(files[expected])):
                    from models.native_unit_bundle import NativeSourceFile
                    from runtime.behavior_conversion.native_metadata import inspect_native
                    combined_files={**dict(dependency_files),**files}
                    inventory=inspect_native([NativeSourceFile(path=p,content=t) for p,t in combined_files.items() if p.startswith('src/main/java/')])
                from runtime.behavior_conversion.native_inheritance import has_resolved_method
                if inventory is None or not has_resolved_method(inventory,api.type_name,signature,files[expected]):
                    raise ValueError("Native method contract is missing or changed: " + signature)
    if evidence_ids and not set(bundle.evidence_ids).issubset(set(evidence_ids)):
        raise ValueError("Bundle cites unavailable evidence")
    tests = {name for name in files if name.startswith("src/test/java/")}
    for requirement in requirements:
        if not set(bundle.coverage.get(requirement, [])).intersection(tests):
            raise ValueError("No executable test covers requirement: " + requirement +
                ". Coverage metadata is missing a link to a returned test source; tests have not been run. " +
                json.dumps(dict(missing_requirement_ids=[key for key in requirements
                    if not set(bundle.coverage.get(key, [])).intersection(tests)],
                    returned_coverage_keys=sorted(bundle.coverage), available_test_paths=sorted(tests))) +
                ". Use the exact requirement IDs as coverage keys and link each to actual returned test files "
                "that exercise it. Example labels such as business do not replace supplied IDs.")
    return files


def file_manifest(project, paths):
    """Fingerprint only accepted files without incorporating transient build output."""
    return {name: hashlib.sha256((Path(project) / name).read_bytes()).hexdigest() for name in sorted(paths)}


def verify_manifest(project, manifest):
    """Reject changed or missing accepted sources before cache reuse or approval."""
    for name, digest in manifest.items():
        path = (Path(project) / name).resolve()
        if not path.is_relative_to(Path(project).resolve()) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Accepted native source changed or disappeared: " + name)


def accept_bundle(project, files, context_factory, profile, dependencies, dependency_files=(), require_tests=True, owned_files=(), required_tests=(), testing_contract=None, excluded_test_files=(), remove_excluded_tests=False, pre_publish=None):
    """Build a disposable complete candidate, then publish source and its verified POM."""
    from runtime.dependency_policy import canonical_dependencies
    dependencies=canonical_dependencies(profile,dependencies)
    from tools.maven_dependency_tools.pom_manager import merge_dependencies
    from runtime.behavior_conversion.validation import build_candidate
    project = Path(project)
    with tempfile.TemporaryDirectory(prefix="snapir-native-bundle-") as temporary:
        with progress_step("Preparing temporary Maven project and Java sources"):
            staged = Path(temporary) / project.name
            staged.mkdir()
            if (project / "pom.xml").exists():
                shutil.copy2(project / "pom.xml", staged / "pom.xml")
            if (project / "src").exists():
                shutil.copytree(project / "src", staged / "src")
            for name in excluded_test_files:
                target = (staged / name).resolve()
                if not name.startswith("src/test/java/") or not target.is_relative_to((staged / "src/test/java").resolve()):
                    raise ValueError("Unsafe stale scenario test path")
                if target.is_file():
                    target.unlink()
            for name in owned_files:
                target = (staged / name).resolve()
                if not target.is_relative_to(staged.resolve()):
                    raise ValueError("Unsafe previously owned source path")
                if target.is_file():
                    target.unlink()
            context = context_factory(profile, staged, artifact_name(project))
            from runtime.test_assets.preparation import current as current_assets
            assets=current_assets() if require_tests else None
            if assets:
                from runtime.test_assets.junit_support import stage
                stage(staged,assets)
            for name, content in dict(dependency_files).items():
                target = staged / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8", newline="\n")
            for name, content in files.items():
                target = staged / name
                if target.exists() and target.read_text(encoding="utf-8") != content:
                    raise ValueError("Candidate would overwrite accepted source: " + name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8", newline="\n")
        with progress_step("Resolving and verifying dependencies"):
            if testing_contract:
                from runtime.behavior_conversion.testing_contract import apply_test_platform
                apply_test_platform(context.pom_path, testing_contract, context.verifier, context.allowed_ibm_artifacts)
            merge_dependencies(context.pom_path, dependencies, context.verifier,
                               allowed_ibm_artifacts=context.allowed_ibm_artifacts, task_id="behavior-bundle")
        result = build_candidate(staged, context, require_tests, required_tests)
        if result.issues:
            from runtime.behavior_conversion.compiler_feedback import compiler_correction, CompilerCorrectionError
            error = "Candidate validation failed: " + "; ".join(result.issues)
            correction = compiler_correction(error, staged=staged)
            if correction:
                raise CompilerCorrectionError(error, correction)
            from runtime.behavior_conversion.test_feedback import test_correction, TestCorrectionError
            correction = test_correction(error, staged=staged)
            if correction:
                raise TestCorrectionError(error, correction)
            raise ValueError(error)
        if assets:
            from runtime.test_assets.junit_support import check_execution
            check_execution(staged,assets['tests'])
        from runtime.behavior_conversion.stage_readiness import record_test_build
        record_test_build(result, files, dependencies, require_tests=require_tests)
        if pre_publish is not None:
            pre_publish(staged, context, result)
        project.mkdir(parents=True, exist_ok=True)
        if remove_excluded_tests:
            for name in set(excluded_test_files) - set(files):
                target = (project / name).resolve()
                if not name.startswith("src/test/java/") or not target.is_relative_to((project / "src/test/java").resolve()):
                    raise ValueError("Unsafe stale scenario test path")
                if target.is_file():
                    target.unlink()
        for name in set(owned_files) - set(files):
            target = (project / name).resolve()
            if not target.is_relative_to(project.resolve()):
                raise ValueError("Unsafe previously owned source path")
            if target.is_file():
                target.unlink()
        for name in files:
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged / name, target)
        if assets:
            from runtime.test_assets.junit_support import stage
            stage(project,assets)
        shutil.copy2(staged / "pom.xml", project / "pom.xml")
    return result.model_dump(mode="json"), file_manifest(project, files)
