"""Check component artifact/contract/report integrity without granting whole-unit acceptance."""
import json
from pathlib import Path,PurePosixPath
from models.native_component_result import NativeComponentResult
from models.native_unit_bundle import NativeUnitBundle,NativeSourceFile
from models.native_unit_validation import NativeUnitValidation
from runtime.behavior_conversion.bundle_output import validate_bundle
from tools.composer_mapper_tools.scoped_intake_evidence import file_digest


def verify_component_artifacts(contract,result,output_root,allowed_classes=()):
    """Read retained source, compiled files and revision-bound executed-test evidence."""
    result=NativeComponentResult.model_validate(result)
    root=Path(result.artifact_root).resolve()
    if not root.is_relative_to(Path(output_root).resolve()) or not root.is_dir():
        raise ValueError('Component artifact root must exist within run output')
    def path(name):
        relative=PurePosixPath(name)
        resolved=(root/name).resolve()
        if '\\' in name or ':' in name or relative.is_absolute() or '..' in relative.parts or not resolved.is_relative_to(root):
            raise ValueError('Unsafe component artifact path')
        if not resolved.is_file(): raise ValueError('Component artifact disappeared: '+name)
        return resolved
    sources=[]
    for name,expected in result.files.items():
        actual=path(name)
        if file_digest(actual)!=expected: raise ValueError('Component artifact bytes changed: '+name)
        if name.startswith(('src/main/java/','src/test/java/')):
            sources.append(NativeSourceFile(path=name,content=actual.read_text(encoding='utf-8')))
    if 'pom.xml' not in result.files or not any(name.startswith('src/main/java/') and name.endswith('.java') for name in result.files):
        raise ValueError('Component manifest needs its POM and native main source')
    if not any(name.startswith('target/') and name.endswith(('.class','.jar')) for name in result.files):
        raise ValueError('Component manifest needs retained compiled artifacts')
    if not any(name.startswith(('src/test/java/','target/test-classes/')) for name in result.files):
        raise ValueError('Component manifest needs retained test inputs')
    validate_bundle(NativeUnitBundle(files=sources),apis=contract.apis,allowed_classes=allowed_classes)
    report=path(result.validation_report)
    if file_digest(report)!=result.validation_report_hash: raise ValueError('Component validation report changed')
    evidence=json.loads(report.read_text(encoding='utf-8'))
    for key in ('component_id','input_revision','contract_revision','files','validation_scope'):
        if evidence.get(key)!=getattr(result,key): raise ValueError('Component validation report does not match '+key)
    validation=NativeUnitValidation.model_validate(evidence.get('validation',{}))
    if not validation.build_passed or not validation.tests_passed or validation.test_count<1 or validation.issues:
        raise ValueError('Component needs a passing build and executed tests')


def verify_original_sources(plan,group):
    """Recheck original source bytes; a stale saved plan cannot authorize source reuse."""
    for member in group.members:
        node=plan.components[member]
        if node.kind=='java_implementation':
            for source in [node.provenance, *node.provenance.get('supporting_sources', [])]:
                path=source.get('source_file')
                if not path or not Path(path).is_file() or file_digest(Path(path))!=source.get('source_hash'):
                    raise ValueError('Original component source changed or disappeared: '+source.get('fqcn',node.label))
