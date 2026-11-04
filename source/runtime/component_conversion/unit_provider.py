"""Promote complete component trees only through the existing whole-unit technical ladder."""
from pathlib import Path
from models.native_unit_bundle import NativeUnitBundle
from models.operation_data_contract import UnitContract
from runtime.component_conversion.unit_artifacts import load_unit_artifacts, save_unit_component_receipt
from runtime.component_conversion.unit_binding import resolve_checklist, native_unit_binding
from runtime.behavior_conversion.verification_feedback import VerificationFailure, VerificationIncomplete
from tools.conversion_tools.component_identity import checked_plan, component_group
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from tools.state_store_tools.behavior_units import save


class ComponentUnitProvider:
    """Supply immutable assembled code, with bounded root corrections and unchanged prerequisite reuse."""
    def __init__(self, conn, config, profile, preparation, classpath, factory, model_call):
        self.conn, self.config, self.profile = conn, config, profile
        self.preparation, self.classpath, self.factory, self.model_call = preparation, classpath, factory, model_call
        self.plan = checked_plan(preparation['component_plan'])
        from tools.behavior_verification.boundaries import build_boundary_report
        from runtime.component_conversion.steps import default_step_mappings
        from runtime.behavior_conversion.verification_mode import facts_disabled
        self.boundaries = build_boundary_report(preparation, mappings=default_step_mappings(self.plan), collect_checklists=not facts_disabled(profile))
        self.units = {unit['unit_id']:unit for item in preparation['operations'].values() for unit in item['units']}

    def __call__(self, unit, payload, validator):
        """Never ask the unit generator to rewrite already validated component code."""
        from runtime.scoped_native.scope import require_task
        require_task(self.conn,self.config,self.profile,'unit',unit.unit_id,payload)
        from tools.behavior_verification.boundary_contracts import boundary_contract
        boundary = self.boundaries['boundaries'][unit.unit_id]
        current = boundary_contract(unit.model_dump(mode='json'),self.default_mapping(unit))
        if any(boundary[name] != getattr(current,name) for name in ('unit_fingerprint','source_manifest_hash','configuration_hash')):
            raise VerificationIncomplete(dict(stage='component_revision', errors=['Original unit boundary changed']))
        limit = max(1,self.profile.max_agent_task_retries)
        for attempt in range(limit):
            artifacts = load_unit_artifacts(self.conn,self.config,self.profile,self.plan,unit.unit_id)
            from runtime.behavior_conversion.verification_mode import executable_mode, facts_disabled
            answers = None if executable_mode(self.profile) or facts_disabled(self.profile) else resolve_checklist(artifacts,boundary)
            def build(metadata):
                from runtime.behavior_conversion.compatibility import versioned_requirements
                declared = versioned_requirements(self.profile,'unit',payload)
                platform = payload.get('testing_contract',{}).get('requirement',{}).get('requirement_id')
                requirements = {item['requirement_id']:item['description'] for item in declared if item['requirement_id'] != platform}
                available = artifacts['root_report'].get('requirements', artifacts['root_report'].get('format_candidate',{}).get('requirements',{}))
                missing = set(requirements)-{'business'}-set(available)
                if missing:
                    raise VerificationIncomplete(dict(stage='component_requirements',missing_requirements=sorted(missing)))
                tests = artifacts['root_report']['required_tests']
                if not tests or any(name not in artifacts['files'] for name in tests):
                    raise ValueError('Complete component unit lacks its executed test sources')
                return NativeUnitBundle(files=[dict(path=name,content=text) for name,text in artifacts['files'].items()],
                    dependencies=artifacts['root_report']['dependencies'],
                    coverage={key:tests for key in requirements},evidence_ids=payload['evidence_ids'],
                    unit_contract=UnitContract(unit_id=unit.unit_id,apis=artifacts['contract']['apis'],
                        requirements=requirements,evidence_ids=payload['evidence_ids']),
                    checklist_answers=answers, verification_binding=metadata.verification_binding,
                    input_type=metadata.input_type,output_type=metadata.output_type,wire_type=metadata.wire_type)
            def checked(bundle,cached=False):
                fresh = load_unit_artifacts(self.conn,self.config,self.profile,self.plan,unit.unit_id)
                if fresh['proof'] != artifacts['proof']:
                    raise ValueError('Component changed before whole-unit verification')
                validator(bundle,cached=False)
                if load_unit_artifacts(self.conn,self.config,self.profile,self.plan,unit.unit_id)['proof'] != artifacts['proof']:
                    raise ValueError('Component changed during whole-unit verification')
            try:
                from runtime.test_assets.preparation import asset_scope
                with asset_scope(artifacts.get('test_assets')):
                    bundle = native_unit_binding(self.conn,self.config,self.profile,unit,artifacts,build,checked,self.model_call)
            except VerificationIncomplete:
                raise
            except VerificationFailure as error:
                if attempt + 1 >= limit:
                    raise
                self._repair(unit,error)
                continue
            from runtime.behavior_conversion.verification_ladder import active_verification
            session = active_verification()
            if session is None or session.last_report is None:
                raise VerificationIncomplete(dict(stage='component_boundary',errors=['No whole-unit comparison was produced']))
            revision = save_unit_component_receipt(self.conn,self.config,artifacts,session.last_report['candidate_hash'])
            session.last_report['component_receipt'] = revision
            fingerprint = digest(dict(unit=unit.fingerprint,components=artifacts['proof'],bundle=bundle.model_dump(mode='json')))
            from runtime.scoped_native.scope import require_task
            from runtime.scoped_native.results import record_result
            binding = require_task(self.conn,self.config,self.profile,'unit',unit.unit_id,payload)
            record_result(binding,self.conn,self.config,self.profile,'unit',unit.unit_id,fingerprint,bundle.model_dump(mode='json'))
            save(self.conn,self.config.run_id,'unit',unit.unit_id,fingerprint,bundle.model_dump(mode='json'))
            return bundle,fingerprint

    def default_mapping(self, unit):
        """Use the qualified default binding already recorded by CF1, without another class search."""
        if unit.kind != 'configured_step' or unit.effective_configuration.get('attributes',{}).get('implClass'):
            return {}
        node = self.plan.components[self.plan.unit_roots[unit.unit_id]]
        return {'opStep':node.provenance['resolved_implementation']}

    def _repair(self, unit, error):
        """Invalidate only the failing configured root; retain dependency artifacts and siblings."""
        from tools.state_store_tools import component_records as records
        from runtime.component_conversion.scope import component_execution
        from runtime.component_conversion.runner import _convert_group
        group = component_group(self.plan,self.plan.unit_roots[unit.unit_id])
        save(self.conn,self.config.run_id,'component_unit_feedback',group.group_id,
            digest(error.verification_feedback),error.verification_feedback,status='failed')
        records.invalidate(self.conn,self.config.run_id,[group.group_id])
        with component_execution(self.conn,self.config,self.profile,self.classpath,self.preparation,include_steps=True,include_formats=True):
            _convert_group(self.conn,self.config,self.profile,self.plan,group,self.boundaries,
                Path(self.config.output_root)/'components',self.factory,self.model_call,units=self.units)
