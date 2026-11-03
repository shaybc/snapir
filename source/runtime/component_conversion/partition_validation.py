"""Build and retain subtree candidates; only the complete format can pass boundary comparison."""
import json
import tempfile
import uuid
from pathlib import Path
from models.native_unit_bundle import NativeUnitBundle
from models.maven_dependency import MavenDependency
from runtime.behavior_conversion.bundle_output import validate_bundle, accept_bundle, verify_manifest
from runtime.behavior_conversion.testing_contract import validate_testing_contract
from runtime.component_conversion.scope import require_component_task
from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from tools.state_store_tools.behavior_units import snapshot, save


class SubtreeCandidateValidator:
    """Keep immutable build/test receipts bound to full evidence and frozen child contracts."""
    def __init__(self, conn, config, profile, request, output, factory, files, dependencies):
        self.conn, self.config, self.profile, self.request = conn, config, profile, request
        self.output, self.factory = Path(output), factory
        self.files, self.dependencies = dict(files), list(dependencies)
        from runtime.dependency_policy import canonical_dependencies
        self.dependencies=canonical_dependencies(profile,dependencies,historical=True)
        self.descriptor = None
        self.generated_files = {}
        from runtime.behavior_conversion.stage_compilation import production_compiler
        self.stage_prerequisites=dict(files)
        self.compile_implementation=production_compiler(profile,factory,prerequisites=files,dependencies=dependencies)
        self.last=None

    def __call__(self, bundle, cached=False):
        """A cached model result still gets a fresh isolated compile/test and source check."""
        self.last=None
        request = self.request
        require_component_task(self.conn, self.config, self.profile, request['group_id'], request)
        if set(bundle.contracts) != set(request['components']):
            raise ValueError('Subtree must keep its original component ownership')
        apis = []
        evidence = {item['identity'] for item in request['sources']} | set(request['configuration_evidence_ids'])
        for dependency in request['prerequisite_components']:
            evidence.update(dependency.get('evidence_ids', []))
        for key, contract in bundle.contracts.items():
            if (contract.component_id != key or contract.configuration_mode != 'specialized' or
                    contract.source_entry_points != request['source_entry_points'][key] or
                    contract.dependencies != request['components'][key]['dependencies'] or
                    not contract.runtime_inputs.get('parent_environment') or not set(contract.evidence_ids).issubset(evidence)):
                raise ValueError('Subtree contract lost source, dependency or parent-environment obligations')
            if any(not api.type_name.startswith(request['native_package'] + '.') for api in contract.apis):
                raise ValueError('Subtree API must use its assigned native package')
            apis.extend(contract.apis)
        native = NativeUnitBundle(files=bundle.files, dependencies=bundle.dependencies, coverage=bundle.coverage,
            evidence_ids=bundle.evidence_ids, unresolved_questions=bundle.unresolved_questions)
        files = validate_bundle(native, apis, request['requirements'], evidence, self.profile.allowed_ibm_classes)
        validate_testing_contract(native, request['testing_contract'])
        if set(files).intersection(self.files):
            raise ValueError('Subtree cannot overwrite frozen prerequisite sources')
        all_files = {**self.files, **files}
        from runtime.behavior_conversion.metadata_checklist_validation import validate_component_mappings
        from runtime.behavior_conversion.verification_mode import executable_mode,conversion_mode
        if not executable_mode(self.profile):
            from runtime.behavior_conversion.verification_mode import facts_disabled
            if not facts_disabled(self.profile):
                validate_component_mappings(bundle.checklist_implementations,{item['id'] for item in request['parser_checklist']},all_files,require_code=conversion_mode(self.profile))
        pins = {(item['group_id'], item['artifact_id']): item for item in request['known_dependencies']}
        for pin in bundle.dependencies:
            known = pins.get((pin.group_id, pin.artifact_id))
            if known and (known['version'], known['scope']) != (pin.version, pin.scope):
                raise ValueError('Subtree changed a frozen dependency pin')
        dependencies = [MavenDependency.model_validate(item) for item in self.dependencies] + bundle.dependencies
        required = sorted({test for key in request['requirements'] for test in bundle.coverage[key]})
        # The durable generation record provides retry/reuse; artifact receipts are immutable.
        receipt_key = digest(dict(request=request, candidate=bundle.model_dump(mode='json'),
            prerequisites={name:digest(content) for name, content in sorted(self.files.items())}))
        receipt = self.output / (receipt_key + '.json')
        recorded = snapshot(self.conn, self.config.run_id, 'format_subtree_artifact', receipt_key)
        if receipt.is_file() and recorded is not None:
            saved = json.loads(receipt.read_text(encoding='utf-8'))
            if recorded['fingerprint'] != digest(saved) or saved['request_hash'] != digest(request):
                raise ValueError('Subtree artifact receipt changed')
            root = self.output / saved['artifact']
            if root.parent != self.output or not root.is_dir():
                raise ValueError('Subtree artifact escaped its output root')
            verify_manifest(root, saved['manifest'])
            with tempfile.TemporaryDirectory(prefix='snapir-subtree-reuse-') as folder:
                project = Path(folder) / 'project'
                validation,_ = accept_bundle(project, files, self.factory, self.profile, dependencies,
                    dependency_files=self.files.items(), require_tests=True, required_tests=required,
                    testing_contract=request['testing_contract'])
        else:
            root = self.output / (receipt_key + '-' + uuid.uuid4().hex[:8])
            root.parent.mkdir(parents=True, exist_ok=True)
            validation, _ = accept_bundle(root, files, self.factory, self.profile, dependencies,
                dependency_files=self.files.items(), require_tests=True, required_tests=required,
                testing_contract=request['testing_contract'])
            for name, content in self.files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8', newline='\n')
            manifest = {path.relative_to(root).as_posix():file_digest(path) for path in root.rglob('*') if path.is_file()}
            temporary = receipt.with_suffix('.tmp')
            record = dict(artifact=root.name, manifest=manifest, validation=validation, required_tests=required,
                request_hash=digest(request), final_unit_acceptance=False)
            temporary.write_text(json.dumps(record), encoding='utf-8')
            temporary.replace(receipt)
            save(self.conn, self.config.run_id, 'format_subtree_artifact', receipt_key, digest(record), record,
                status='component_validated')
        require_component_task(self.conn, self.config, self.profile, request['group_id'], request)
        self.last=dict(build_validation=validation,component_only=True)
        self.generated_files = {name:content for name,content in files.items() if name.startswith('src/main/java/')}
        self.descriptor = dict(group_id=request['group_id'], contract_revision=digest({key:value.model_dump(mode='json') for key,value in bundle.contracts.items()}),
            result_revision=receipt_key, contracts={key:value.model_dump(mode='json') for key,value in bundle.contracts.items()},
            evidence_ids=sorted(evidence), dependencies=[item.model_dump(mode='json') for item in dependencies],
            checklist_implementations={key:[location.model_dump(mode='json') for location in locations]
                for key,locations in bundle.checklist_implementations.items()})
        from runtime.component_conversion.format_chain_ownership import chain_ownership
        self.descriptor['format_chain_ownership']=chain_ownership(request)
