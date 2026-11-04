"""Connect parser obligations, existing build guards and isolated boundary comparison."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import shutil
import uuid
from pathlib import Path
from models.boundary_harness_binding import BoundaryHarnessBinding
from tools.behavior_verification.static_checks import validate_unit_static
from tools.behavior_verification.boundary_verification import verify_boundary
from tools.behavior_verification.checklist_mapping import candidate_files, candidate_digest
from runtime.behavior_conversion.verification_binding import validate_binding
from runtime.behavior_conversion.verification_cases import controlled_cases
from runtime.behavior_conversion.verification_classpath import native_runtime_classpath
from runtime.behavior_conversion.verification_feedback import VerificationFailure, VerificationIncomplete, comparison_feedback

_active = ContextVar('unit_technical_verification', default=None)


def active_verification():
    """Only the scoped unit generation path enables the pre-publication check hook."""
    return _active.get()


@contextmanager
def verification_session(session):
    token = _active.set(session)
    try: yield session
    finally: _active.reset(token)


class UnitVerificationSession:
    """Candidate evidence belongs to this exact unit/source/configuration and current build."""
    def __init__(self, config, unit, boundary, *, extra_types=(), tool=None, policy=None, authorizations=(), mutation_settings=None, executable_settings=None):
        self.unit, self.boundary, self.extra_types, self.tool = unit, boundary, extra_types, tool
        self.policy, self.authorizations = policy, authorizations
        self.mutation_settings = mutation_settings
        self.executable_settings=executable_settings
        key = hashlib.sha256(unit['unit_id'].encode()).hexdigest()[:24]
        self.root = Path(config.output_root) / '.unit-verification' / key
        self.root.mkdir(parents=True, exist_ok=True)
        from tools.behavior_verification.java_tool import default_tool_path
        from tools.behavior_verification.tool_snapshot import snapshot_tool
        self.tool=snapshot_tool(tool or default_tool_path(),self.root/'analysis-tools')
        self.last_report = None
        self.static_report = None

    def prepare_tests(self,bundle):
        """Finish source, invocation, settings and case preparation before test generation."""
        self.static(bundle)
        if self.executable_settings is not None and self.executable_settings.mode=='conversion_checklist_v1':
            return dict(mapping_status=self.static_report.status,behavioral_equivalence='not_assessed',
                native_settings_apis=self.native_settings_apis)
        if self.executable_settings is not None and self.executable_settings.mode=='executable_boundary_v1':
            return self.executable_structure['comparison_preparation']
        from runtime.behavior_conversion.settings_readiness import prepare_settings
        return prepare_settings(self.unit,self.boundary,bundle,self.static_report.configuration_controls,tool=self.tool)

    def static(self, bundle):
        """Schema/mapping/exclusion checks happen before compilation or file publication."""
        if self.executable_settings is not None and self.executable_settings.mode=='conversion_checklist_v1':
            from runtime.behavior_conversion.conversion_readiness import prepare_conversion
            return prepare_conversion(self,bundle)
        if self.executable_settings is not None and self.executable_settings.mode=='executable_boundary_v1':
            from runtime.behavior_conversion.executable_verification import prepare_boundary
            return prepare_boundary(self,bundle)
        self.last_report = None
        if bundle.checklist_answers is None:
            raise VerificationFailure(dict(stage='checklist', errors=['Missing checklist_answers']))
        validate_binding(bundle, self.extra_types)
        # Retained evidence inherits the run directory ACL; private temp ACLs can block later Windows resumes.
        self.attempt = self.root / ('attempt-' + uuid.uuid4().hex)
        self.attempt.mkdir()
        report = validate_unit_static(self.unit, self.boundary, bundle.files, bundle.checklist_answers,
                                    tool=self.tool, directory=self.attempt / 'static', policy=self.policy, authorizations=self.authorizations)
        self.static_report = report
        if report.status == 'mapping_invalid':
            raise VerificationFailure(dict(stage='checklist', errors=report.errors,
                decisions=[item for item in report.decisions if item['status'] == 'rejected'], evidence=str(self.attempt)))
        if report.status != 'mapping_valid':
            raise VerificationIncomplete(dict(stage='checklist', errors=report.errors, decisions=report.decisions, evidence=str(self.attempt)))

    def complete(self,project,context,bundle,*,build_validation=None):
        """Complete the selected policy without invoking legacy execution in conversion mode."""
        if self.executable_settings is not None and self.executable_settings.mode=='conversion_checklist_v1':
            from runtime.behavior_conversion.conversion_readiness import complete_conversion
            return complete_conversion(self,bundle,build_validation)
        return self.compare(project,context,bundle,build_validation=build_validation)

    def compare(self, project, context, bundle, *, build_validation=None):
        """Called after Maven compile/tests and before candidate files are copied into the project."""
        if self.executable_settings is not None and self.executable_settings.mode=='executable_boundary_v1':
            from runtime.behavior_conversion.executable_verification import compare_boundary
            return compare_boundary(self,project,context,bundle,build_validation)
        if self.static_report is None or self.static_report.candidate_hash != candidate_digest(candidate_files(bundle.files)):
            raise VerificationFailure(dict(stage='revision', errors=['Candidate changed after static verification']))
        if not build_validation or not build_validation.get('build_passed') or not build_validation.get('tests_passed') or build_validation.get('test_count', 0) < 1 or build_validation.get('issues'):
            raise VerificationIncomplete(dict(stage='build', errors=['Passing managed compilation and executed tests are required before boundary acceptance']))
        cases = controlled_cases(self.unit, self.boundary, bundle.verification_binding, self.static_report.configuration_controls)
        project = Path(project)
        sources = [dict(path=str(path.relative_to(project)).replace('\\', '/'), content=path.read_text(encoding='utf-8'))
                   for path in sorted((project / 'src/main/java').rglob('*.java'))]
        native = BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.TypedBoundaryAdapter',
            native_entry=bundle.verification_binding, sources=sources,
            settings_bindings=bundle.verification_binding.settings_bindings,
            classpath=native_runtime_classpath(project, context))
        from tools.behavior_verification.java_tool import default_tool_path
        harness = self.attempt / 'harness-tool.jar'
        shutil.copyfile(self.tool or default_tool_path(), harness)
        if hashlib.sha256(harness.read_bytes()).hexdigest() != self.static_report.tool_hash:
            raise VerificationIncomplete(dict(stage='tool_revision', errors=['Analysis tool changed before boundary execution']))
        legacy = BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter')
        report = verify_boundary(self.unit, self.boundary, legacy, native, cases, self.attempt / 'comparison',
                                 tool=harness, candidate_label='current_generated_native_unit')
        feedback = comparison_feedback(report)
        feedback['evidence'] = str(self.attempt / 'comparison' / 'boundary-comparison.json')
        if report.status == 'differences_found': raise VerificationFailure(dict(stage='boundary', **feedback))
        if report.status != 'matched_observed_cases': raise VerificationIncomplete(dict(stage='boundary', **feedback))
        catch_ids = {item.id for item in self.boundary.parser_checklist.items if item.kind == 'branch' and item.detail == 'catch'}
        successful = [case for case in report.cases if case['legacy']['exception'] is None and case['native']['exception'] is None
                      and not any(probe['id'] in catch_ids for probe in case['legacy']['probes'])]
        if not successful:
            raise VerificationIncomplete(dict(stage='coverage', errors=['No observed successful source path; error-only samples cannot establish business behavior'],
                                               evidence=str(self.attempt)))
        from runtime.behavior_conversion.method_contracts import _signature, java_type_resolver, _normalize_constructor_contract
        from runtime.behavior_conversion.java_api_types import public_api_types
        observed_apis = {probe['id'] for case in report.cases for probe in case['native']['probes']}
        required_apis = set()
        known = {name for source in sources for name in public_api_types(source['content'])}
        for api in bundle.unit_contract.apis:
            content = next(source['content'] for source in sources if api.type_name in public_api_types(source['content']))
            resolve = java_type_resolver(content, known)
            for declared in api.method_signatures:
                owner = public_api_types(content)[api.type_name]
                signature = _signature(_normalize_constructor_contract(content, declared, owner), resolve)
                if signature is None: raise VerificationFailure(dict(stage='native_api', errors=['Invalid declared API signature']))
                if signature[0] == owner['name']:
                    continue
                required_apis.add('native:' + api.type_name.replace('$', '.') + '.' + signature[0] + '(' + ', '.join(signature[2]) + ')')
        if required_apis - observed_apis:
            raise VerificationIncomplete(dict(stage='native_api', errors=['The verified boundary did not execute all declared unit APIs'],
                unobserved_apis=sorted(required_apis - observed_apis), evidence=str(self.attempt)))
        # Samples cannot resolve unknown call targets, missing paths or source-control branches.
        excluded = {item['checklist_id'] for item in self.static_report.decisions if item['status'] == 'not_applicable'}
        gaps = [item for item in report.coverage.get('branches', []) if item['unexercised_outcomes'] and item['checklist_id'] not in excluded]
        if report.coverage.get('unresolved_edges') or gaps:
            raise VerificationIncomplete(dict(stage='coverage', gaps=gaps, unresolved_edges=report.coverage.get('unresolved_edges', []),
                                              source_manifest_hash=report.source_manifest_hash, evidence=str(self.attempt)))
        current = {file.path for file in bundle.files if file.path.startswith('src/main/java/')}
        other = [source for source in sources if source['path'] not in current]
        signals = validate_unit_static(self.unit, self.boundary, bundle.files, bundle.checklist_answers,
            comparison_report=report, trusted_harness_sources=other, tool=harness, directory=self.attempt / 'static-observed',
            policy=self.policy, authorizations=self.authorizations)
        if signals.status != 'mapping_valid': raise VerificationFailure(dict(stage='observed_mapping', errors=signals.errors))
        self.last_report = dict(source_manifest_hash=self.boundary.source_manifest_hash, configuration_hash=self.boundary.configuration_hash,
            candidate_hash=signals.candidate_hash, evidence=str(self.attempt), boundary_status=report.status,
            report_hash=hashlib.sha256((self.attempt / 'comparison/boundary-comparison.json').read_bytes()).hexdigest(),
            observed_cases=len(report.cases), coverage=report.coverage, warnings=signals.warnings,
            observed_native_apis=sorted(observed_apis),
            build_validation=build_validation,
            binding=bundle.verification_binding.model_dump(mode='json'), exhaustive_equivalence=False)
        from runtime.behavior_conversion.verification_test_strength import prepare_measurement
        prepare_measurement(self, project, bundle)
