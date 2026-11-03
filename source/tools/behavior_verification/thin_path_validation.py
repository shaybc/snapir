"""Build/test native candidates and compare original/native boundaries without production acceptance."""
import json
import shutil
import uuid
from pathlib import Path
from models.boundary_harness_binding import BoundaryHarnessBinding
from runtime.behavior_conversion.bundle_output import validate_bundle, accept_bundle
from runtime.behavior_conversion.testing_contract import validate_testing_contract
from runtime.behavior_conversion.verification_binding import validate_binding
from runtime.behavior_conversion.verification_cases import controlled_cases
from runtime.behavior_conversion.verification_classpath import native_runtime_classpath
from runtime.behavior_conversion.verification_feedback import VerificationFailure, VerificationIncomplete
from runtime.behavior_conversion.compiler_feedback import CompilerCorrectionError
from runtime.behavior_conversion.test_feedback import TestCorrectionError
from tools.behavior_verification.thin_path_comparison import compare_thin_boundary


def difference_feedback(report):
    """Send only concrete compared-value differences, without probes or checklist inventories."""
    return dict(stage='thin_path_boundary',status=report.status,failing_cases=[dict(
        input=case['case'],differences=[{key: value for key,value in item.items() if key!='related_checklist_ids'}
            for item in case['differences']]) for case in report.cases if case['differences']][:8])


def require_observed_match(report):
    """Require both sides to execute, all samples to match, and at least one successful legacy path."""
    if any(case['differences'] for case in report.cases):
        raise VerificationFailure(difference_feedback(report))
    if report.status != 'matched_observed_cases' or report.issues or report.unexecuted_case_ids or not report.cases or getattr(report,'limitations',[]):
        raise VerificationIncomplete(dict(stage='thin_path_tooling',status=report.status,issues=report.issues,
            limitations=getattr(report,'limitations',[])[:8],unexecuted_case_ids=report.unexecuted_case_ids))
    if any(case['legacy']['status'] != 'completed' or case['native']['status'] != 'completed' or case['differences']
           for case in report.cases):
        raise VerificationIncomplete(dict(stage='thin_path_tooling',issues=['One or more sides could not execute']))
    if not any(case['legacy']['status'] == case['native']['status'] == 'completed' and
               case['legacy']['exception'] is None and case['native']['exception'] is None for case in report.cases):
        raise VerificationIncomplete(dict(stage='thin_path_coverage', errors=['No successful paired execution; error-only samples are insufficient']))


class ThinPathValidator:
    """Retain each attempt's build and paired observations; never write unit acceptance receipts."""
    def __init__(self, unit, boundary, controls, request, profile, directory, fresh, *, tool=None, factory=None):
        from runtime.behavior_conversion.verification_mode import conversion_mode
        if conversion_mode(profile):
            raise ValueError('Thin-path execution experiments require an explicit comparison policy; use staged unit conversion for conversion_checklist_v1')
        from runtime.managed_projects import create_build_context
        self.unit, self.boundary, self.controls, self.request = unit, boundary, controls, request
        self.profile, self.directory, self.fresh = profile, Path(directory), fresh
        self.tool, self.factory = tool, factory or create_build_context
        self.last = None

    def side_road_validate(self, bundle, stage):
        """Build and compare stage candidates in isolated folders without accepting the parent."""
        candidate = ThinPathValidator(self.unit,self.boundary,self.controls,self.request,self.profile,
            self.directory/('side-road-'+stage),self.fresh,tool=self.tool,factory=self.factory)
        candidate(bundle)
        self.side_road_last = candidate.last
        return candidate.last

    def compile_implementation(self,bundle):
        """Compile production code in isolation before asking for tests or comparison metadata."""
        self.fresh()
        if any(not f.path.startswith('src/main/java/') for f in bundle.files):
            raise ValueError('Compile-only stage accepts production sources only')
        files=validate_bundle(bundle,bundle.unit_contract.apis,evidence_ids={s['identity'] for s in self.unit['sources']})
        prerequisites={file['path']:file['content'] for item in self.request.get('converted_dependency_apis',[]) for file in item['files']}
        if set(files)&set(prerequisites):raise ValueError('Cannot overwrite accepted prerequisite source')
        directory=self.directory/('compile-'+uuid.uuid4().hex)
        directory.mkdir(parents=True)
        (directory/'implementation.json').write_text(bundle.model_dump_json(indent=2),encoding='utf-8')
        dependencies={(d.group_id,d.artifact_id):d for d in bundle.dependencies}
        from models.maven_dependency import MavenDependency
        for item in self.request.get('converted_dependency_apis',[]):
            for pin in item['dependencies']:
                value=MavenDependency.model_validate(pin);key=(value.group_id,value.artifact_id)
                if key in dependencies and (value.version,value.scope)!=(dependencies[key].version,dependencies[key].scope):
                    raise ValueError('Prerequisite dependency pin changed')
                dependencies[key]=value
        validation,_=accept_bundle(directory/'native',{**prerequisites,**files},self.factory,self.profile,
            list(dependencies.values()),require_tests=False)
        (directory/'compile-validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
        self.fresh()
        return validation

    def validate_metadata(self,bundle):
        """Finish native invocation/settings preparation before a tests-only request."""
        self.fresh()
        from runtime.behavior_conversion.settings_readiness import prepare_settings
        prerequisites=[dict(path=f['path'],content=f['content']) for dependency in self.request.get('converted_dependency_apis',[])
                       for f in dependency['files']]
        from models.native_unit_bundle import NativeSourceFile
        prepared=bundle.model_copy(deep=True)
        owned={f.path for f in prepared.files}
        prepared.files.extend(NativeSourceFile.model_validate(f) for f in prerequisites if f['path'] not in owned)
        return prepare_settings(self.unit,self.boundary,prepared,self.controls,tool=self.tool)

    def __call__(self, bundle, cached=False):
        self.last = None
        self.fresh()
        if bundle.unit_contract is None or bundle.unit_contract.unit_id != self.unit['unit_id']:
            raise ValueError('Native contract must identify this selected configured unit')
        evidence = {source['identity'] for source in self.unit['sources']}
        files = validate_bundle(bundle, bundle.unit_contract.apis, self.request['requirements'], evidence,
                                self.profile.allowed_ibm_classes)
        if not set(bundle.unit_contract.evidence_ids).issubset(evidence):
            raise ValueError('Native contract cites unavailable evidence')
        validate_testing_contract(bundle, self.request['testing_contract'])
        dependency_files = {file['path']: file['content'] for dependency in self.request.get('converted_dependency_apis', [])
                            for file in dependency['files']}
        if set(files).intersection(dependency_files):
            raise ValueError('Reuse accepted native types without copying or overwriting their files')
        extra_types = [api['type_name'] for dependency in self.request.get('converted_dependency_apis', [])
                       for api in dependency['apis']]
        if self.unit['kind']=='request_unformat':
            # Getter/presence projection is determined from compiled signatures and legacy observations.
            bundle=bundle.model_copy(deep=True)
            if bundle.verification_binding is None:
                raise VerificationFailure(dict(stage='binding',issues=['Native entry API is not declared']))
            bundle.verification_binding.output='none'
            bundle.verification_binding.output_getters=[]
            bundle.verification_binding.context_writes=[]
        validate_binding(bundle, extra_types)
        cases = controlled_cases(self.unit, self.boundary, bundle.verification_binding, self.controls)
        attempt = self.directory / ('attempt-' + uuid.uuid4().hex)
        attempt.mkdir(parents=True)
        (attempt/'candidate-bundle.json').write_text(bundle.model_dump_json(indent=2),encoding='utf-8')
        self.last = dict(status='validation_in_progress', evidence=str(attempt), experiment_only=True)
        required = sorted({path for key in self.request['requirements'] for path in bundle.coverage[key]})
        def compare(staged, context, validation):
            self.fresh()
            (attempt/'build-validation.json').write_text(validation.model_dump_json(indent=2), encoding='utf-8')
            shutil.copytree(staged/'target', attempt/'build-evidence')
            sources = [dict(path=str(path.relative_to(staged)).replace('\\', '/'), content=path.read_text(encoding='utf-8'))
                       for path in sorted((staged/'src/main/java').rglob('*.java'))]
            native = BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',
                native_entry=bundle.verification_binding, sources=sources,
                settings_bindings=bundle.verification_binding.settings_bindings,
                classpath=native_runtime_classpath(staged, context))
            legacy = BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter')
            report = compare_thin_boundary(self.unit, self.boundary, legacy, native, cases, attempt/'comparison', tool=self.tool)
            self.last = dict(status=report.status, evidence=str(attempt), observed_cases=len(report.cases),
                coverage=report.coverage, build_validation=validation.model_dump(mode='json'),
                exhaustive_equivalence=False, full_operation_accepted=False, experiment_only=True)
            self.last['limitations']=report.limitations
            self.fresh()
            require_observed_match(report)
        try:
            dependencies = {(item.group_id,item.artifact_id):item for item in bundle.dependencies}
            from models.maven_dependency import MavenDependency
            for prerequisite in self.request.get('converted_dependency_apis', []):
                for value in prerequisite['dependencies']:
                    item = MavenDependency.model_validate(value)
                    key = (item.group_id,item.artifact_id)
                    if key in dependencies and (dependencies[key].version,dependencies[key].scope)!=(item.version,item.scope):
                        raise VerificationFailure(dict(stage='dependencies',issues=['Accepted dependency pin changed: '+str(key)]))
                    dependencies[key] = item
            accept_bundle(attempt/'native', {**dependency_files, **files}, self.factory, self.profile, list(dependencies.values()),
                require_tests=True, required_tests=required, testing_contract=self.request['testing_contract'], pre_publish=compare)
        except Exception as error:
            (attempt/'failure.json').write_text(json.dumps(dict(error=str(error), evidence=self.last), indent=2), encoding='utf-8')
            if not isinstance(error,(VerificationFailure,CompilerCorrectionError,TestCorrectionError)):
                raise VerificationIncomplete(dict(stage='build_or_environment',issues=[str(error)],evidence=str(attempt))) from error
            raise
        return self.last
