"""Build isolated native component candidates and retain revision-bound Maven/test evidence."""
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from models.native_unit_bundle import NativeUnitBundle
from models.native_component_result import NativeComponentResult
from models.maven_dependency import MavenDependency
from runtime.behavior_conversion.bundle_output import validate_bundle, accept_bundle
from runtime.behavior_conversion.testing_contract import validate_testing_contract
from runtime.behavior_conversion.validation import build_candidate
from runtime.component_conversion.scope import require_component_task
from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
from tools.state_store_tools.conversion_components import register_component_contracts, save_component_results


def owned_component_sources(files, dependency_files, extracted=()):
    """A configured root owns its extracted parts, but never shared native prerequisites."""
    if any(name not in dependency_files or not name.startswith('src/main/java/') for name in extracted):
        raise ValueError('Extracted format ownership must name built production prerequisites')
    return sorted({name for name in files if name.startswith('src/main/java/')} | set(extracted))


def revalidate_components(profile, factory, *, config=None, units=None, boundaries=None, conn=None):
    """Run fresh builds in disposable copies without changing retained artifact/report bytes."""
    def validate(contracts, results):
        roots = {result.artifact_root: result for result in results.values()}
        for root, result in roots.items():
            with tempfile.TemporaryDirectory(prefix='snapir-component-reuse-') as folder:
                project = Path(folder) / 'component'
                project.mkdir()
                shutil.copy2(Path(root) / 'pom.xml', project / 'pom.xml')
                shutil.copytree(Path(root) / 'src', project / 'src')
                from runtime.retained_libraries.artifacts import DIRECTORY, restore_portable
                restore_portable(Path(root) / DIRECTORY, project / DIRECTORY)
                report = json.loads((Path(root) / result.validation_report).read_text(encoding='utf-8'))
                if report.get('format_partition_records'):
                    from runtime.component_conversion.unit_artifacts import require_partition_records
                    from tools.conversion_tools.component_identity import checked_plan,component_group
                    if conn is None or config is None:
                        raise ValueError('Partition reuse requires current component state')
                    plan=checked_plan(json.loads(conn.execute('SELECT plan_json FROM conversion_component_plans WHERE run_id=?',
                        (config.run_id,)).fetchone()[0]))
                    require_partition_records(conn,config,component_group(plan,report['component_id']).group_id,
                        report['format_partition_records'])
                context = factory(profile, project, 'component')
                validation = build_candidate(project, context, True, report.get('required_tests', []))
                if not validation.build_passed or not validation.tests_passed or validation.issues:
                    raise ValueError('Saved component failed fresh Maven/test validation: ' + '; '.join(validation.issues))
                if report.get('test_assets'):
                    from types import SimpleNamespace
                    from runtime.test_assets.junit_support import check_execution
                    assets=report['test_assets']
                    check_execution(project,SimpleNamespace(scenario_methods=assets['scenario_methods'],fixture_manifest_hash=assets['manifest_hash']))
                if report.get('configured_format') is not None:
                    from runtime.component_conversion.format_verification import recheck_format
                    recheck_format(config,profile,contracts,results,project,context,validation,report,units,boundaries)
        return True
    return validate


class ComponentCandidateValidator:
    """Adapt the canonical bundle builder to CF2 state without writing unit acceptance."""
    def __init__(self, conn, config, profile, plan, group, request, output, factory, dependency_files, dependencies, *, units=None, boundaries=None, owned_dependency_sources=()):
        self.conn, self.config, self.profile = conn, config, profile
        self.plan, self.group, self.request = plan, group, request
        self.output, self.factory = Path(output), factory
        self.dependency_files, self.dependencies = dependency_files, dependencies
        from runtime.dependency_policy import canonical_dependencies
        self.dependencies=canonical_dependencies(profile,dependencies,historical=True)
        self.results = {}
        self.units,self.boundaries=units,boundaries
        self.owned_dependency_sources=tuple(owned_dependency_sources)
        from runtime.behavior_conversion.stage_compilation import production_compiler
        self.stage_prerequisites=dict(dependency_files)
        self.compile_implementation=production_compiler(profile,factory,prerequisites=dependency_files,dependencies=dependencies)
        self.last=None

    def validate_metadata(self,bundle):
        """Check frozen step/format contracts before generating tests; never publish here."""
        require_component_task(self.conn,self.config,self.profile,self.group.group_id,self.request)
        from runtime.component_conversion.steps import validate_step_candidate
        validate_step_candidate(bundle,self.request,self.dependency_files)
        if self.request.get('configured_format') is not None:
            from runtime.component_conversion.format_verification import format_bundle,session_for
            identity=self.request['configured_format']['unit_id']
            session=session_for(self.config,self.profile,self.units[identity],self.boundaries['boundaries'][identity])
            self.preparation=session.prepare_tests(format_bundle(bundle,self.request,self.dependency_files))
            return self.preparation

    def __call__(self, bundle, cached=False):
        """Validate interfaces/citations, compile/test, then record only component progress."""
        self.last=None
        require_component_task(self.conn, self.config, self.profile, self.group.group_id, self.request)
        from runtime.behavior_conversion.typed_boundaries import validate_typed_boundary
        validate_typed_boundary(bundle, self.request.get('typed_boundary_contract'))
        if set(bundle.contracts) != set(self.group.members):
            raise ValueError('Contracts must cover the complete coordinated component group')
        evidence = {source['identity'] for source in self.request['sources']}
        evidence.update(self.request.get('configuration_evidence_ids', []))
        evidence.update(item for dependency in self.request['prerequisite_components'] for item in dependency.get('evidence_ids', []))
        apis = []
        for key, contract in bundle.contracts.items():
            if contract.component_id != key or set(contract.dependencies) != set(self.plan.components[key].dependencies):
                raise ValueError('Component contract identity/dependencies changed')
            mode = 'specialized' if self.plan.components[key].kind in {'configured_step','format_composition'} else 'parameterized'
            if contract.source_entry_points != self.request['source_entry_points'][key] or contract.configuration_mode != mode:
                raise ValueError('Component must declare supplied entry points and '+mode+' configuration: '+
                    json.dumps(dict(component_id=key,configuration_mode=mode,source_entry_points=self.request['source_entry_points'][key])))
            if not set(contract.evidence_ids).issubset(evidence):
                raise ValueError('Component contract cites unavailable source evidence: '+json.dumps(dict(
                    unknown_evidence_ids=sorted(set(contract.evidence_ids)-evidence),allowed_evidence_ids=sorted(evidence))))
            if any(not api.type_name.startswith(self.request['native_package'] + '.') for api in contract.apis):
                raise ValueError('Component API must use its assigned native package: '+self.request['native_package'])
            apis.extend(contract.apis)
        if len({api.type_name for api in apis}) != len(apis):
            raise ValueError('Component contracts cannot own the same API')
        requirements = self.request['requirements']
        native = NativeUnitBundle(files=bundle.files, dependencies=bundle.dependencies, coverage=bundle.coverage,
                                  evidence_ids=bundle.evidence_ids, unresolved_questions=bundle.unresolved_questions)
        files = validate_bundle(native, apis, requirements, evidence, self.profile.allowed_ibm_classes,
                                dependency_files=self.dependency_files.items())
        if set(files).intersection(self.dependency_files):
            raise ValueError('Component response must not overwrite prerequisite files')
        if self.request.get('testing_contract'):
            validate_testing_contract(native, self.request['testing_contract'])
        from runtime.component_conversion.steps import validate_step_candidate
        validate_step_candidate(bundle, self.request, self.dependency_files)
        all_files = {**self.dependency_files, **files}
        session=None; comparison=None
        if self.request.get('configured_format') is not None:
            from runtime.component_conversion.format_verification import format_bundle,session_for
            identity=self.request['configured_format']['unit_id']
            verified_bundle=format_bundle(bundle,self.request,self.dependency_files)
            session=session_for(self.config,self.profile,self.units[identity],self.boundaries['boundaries'][identity])
            session.static(verified_bundle)
        expected = {item['id'] for item in self.request['parser_checklist']}
        from runtime.behavior_conversion.verification_mode import executable_mode,conversion_mode,facts_disabled
        if session is None and not executable_mode(self.profile) and not facts_disabled(self.profile):
            from runtime.behavior_conversion.metadata_checklist_validation import validate_component_mappings
            validate_component_mappings(bundle.checklist_implementations,expected,all_files,require_code=conversion_mode(self.profile))
        known = {(item['group_id'], item['artifact_id']): item for item in self.request.get('known_dependencies', [])}
        for dependency in bundle.dependencies:
            pin = known.get((dependency.group_id, dependency.artifact_id))
            if pin and (dependency.version, dependency.scope) != (pin['version'], pin['scope']):
                raise ValueError('Component changed a known dependency pin')
        registered = register_component_contracts(self.conn, self.config.run_id, self.plan, self.group.group_id, bundle.contracts, self.profile)
        project = self.output / (self.group.group_id[-16:] + '-' + uuid.uuid4().hex[:12])
        required_tests = sorted({name for key in requirements for name in bundle.coverage[key]})
        diagnostic_classpath = []
        def retain(staged, context, validation):
            nonlocal comparison, diagnostic_classpath
            self.last=dict(build_validation=validation.model_dump(mode='json'),component_only=True)
            require_component_task(self.conn, self.config, self.profile, self.group.group_id, self.request)
            if session is not None:
                from runtime.component_conversion.format_verification import retain_format_evidence
                session.complete(staged,context,verified_bundle,build_validation=validation.model_dump(mode='json'))
                comparison=retain_format_evidence(session,project)
            from runtime.test_assets.preparation import enabled as shared_assets_enabled
            if self.profile.format_comparison.enabled and (self.request.get('configured_format') is not None or
                    shared_assets_enabled(self.profile) and self.request.get('configured_unit') is not None):
                from runtime.behavior_conversion.verification_classpath import native_runtime_classpath
                try:
                    diagnostic_classpath = native_runtime_classpath(staged, context)
                except Exception:
                    diagnostic_classpath = []  # Missing runtime dependencies stay unavailable in the diagnostic.
            shutil.copytree(staged / 'target', project / 'target')
        dependencies = [MavenDependency.model_validate(item) for item in self.dependencies] + bundle.dependencies
        validation, _ = accept_bundle(project, files, self.factory, self.profile, dependencies,
            dependency_files=self.dependency_files.items(), require_tests=True, required_tests=required_tests,
            testing_contract=self.request.get('testing_contract'), pre_publish=retain)
        # accept_bundle publishes owned files; retain the exact prerequisites used by its build too.
        for name, content in self.dependency_files.items():
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8', newline='\n')
        if self.profile.format_comparison.enabled and self.request.get('configured_format') is not None:
            from runtime.format_comparison.component_diagnostics import diagnose_component
            diagnose_component(self, bundle, all_files, project / 'format-diagnostic', native_classpath=diagnostic_classpath)
        if self.request.get('configured_unit') is not None:
            from runtime.step_comparison.component_diagnostics import diagnose_step
            diagnose_step(self,all_files,project/'step-diagnostic',diagnostic_classpath)
        manifest = {path.relative_to(project).as_posix(): file_digest(path) for path in project.rglob('*') if path.is_file()}
        results = {}
        for key in self.group.members:
            report_name = 'component-' + key[-16:] + '.json'
            report = dict(component_id=key, input_revision=registered['input_revision'], contract_revision=registered['contract_revision'],
                files=manifest, validation_scope='build_and_tests', validation=validation, required_tests=required_tests,
                owned_sources=owned_component_sources(files,self.dependency_files,self.owned_dependency_sources),
                dependencies=[item.model_dump(mode='json') for item in dependencies],
                parser_checklist=self.request['parser_checklist'],
                analysis_tool_hash=self.request['analysis_tool_hash'], component_generation_policy=self.request['component_generation_policy'],
                checklist_implementations={item: [location.model_dump() for location in locations] for item, locations in bundle.checklist_implementations.items()},
                source_entry_points=self.request['source_entry_points'], comparison_limitations=self.request['comparison_limitations'])
            from runtime.test_assets.preparation import current
            assets=current()
            if assets:report['test_assets']=dict(manifest_hash=assets['manifest_hash'],
                resource_path='src/test/resources/shared-test-assets/'+assets['manifest_hash'],
                scenario_methods=assets['tests'].scenario_methods)
            report['requirements'] = self.request['requirements']
            report['format_chains'] = self.request.get('format_chains',[])
            report['format_chain_policy'] = self.request.get('format_chain_policy')
            report['composition_obligations'] = self.request.get('composition_obligations',[])
            from runtime.component_conversion.format_chain_ownership import chain_ownership
            report['format_chain_ownership'] = chain_ownership(self.request)
            report['whole_unit_feedback'] = self.request.get('whole_unit_feedback')
            report['format_partition_records'] = self.request.get('format_partition_records', [])
            if self.request.get('configured_unit') is not None:
                report['configured_unit'] = self.request['configured_unit']
            if session is not None:
                report.update(configured_format=self.request['configured_format'],format_comparison=comparison,
                    format_candidate=dict(checklist_answers=bundle.checklist_answers.model_dump(mode='json') if bundle.checklist_answers else None,
                        verification_binding=bundle.verification_binding.model_dump(mode='json') if bundle.verification_binding else None,
                        requirements=requirements,evidence_ids=bundle.evidence_ids))
            path = project / report_name
            path.write_text(json.dumps(report, indent=2), encoding='utf-8')
            results[key] = NativeComponentResult(component_id=key, artifact_root=str(project), files=manifest,
                input_revision=registered['input_revision'], contract_revision=registered['contract_revision'],
                validation_report=report_name, validation_report_hash=file_digest(path))
        require_component_task(self.conn, self.config, self.profile, self.group.group_id, self.request)
        save_component_results(self.conn, self.config.run_id, self.plan, self.group.group_id, results, self.profile,
                               self.output, validator=revalidate_components(self.profile, self.factory,config=self.config,units=self.units,boundaries=self.boundaries,conn=self.conn))
        self.results = results
