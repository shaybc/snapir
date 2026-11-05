"""Bounded, cached whole-operation scenario generation without conversion-state mutations."""
import json
from pathlib import Path
from models.operation_demo_proposal import OperationDemoProposal
from runtime.fixture_jdbc_tools.releases import digest,file_hash
from runtime.fixture_demo.scenario_prompt import SCENARIO_PROMPT
from runtime.fixture_demo.scenario_evidence import collect_scenario_evidence
from runtime.fixture_demo.scenario_publication import validate_proposal,publish_proposal
from runtime.fixture_demo.scenario_reuse import reuse_saved_resources,PUBLICATION_VERSION
from runtime.fixture_demo.artifact_paths import demo_artifact,migrate_demo_artifacts,saved_generation_proposal


def generate_operation_scenarios(project,identity,profile,*,original=None,model_call=None):
    """Create the missing recipe, reusing valid generated or explicitly authored saved definitions.

    Attempts belong to this preparation role's input revision. No implementation
    counters, migration database, old fixture payloads or Java files are written.
    """
    project=Path(project).resolve()
    try:migrate_demo_artifacts(project)
    except (ValueError,OSError) as error:return dict(operation=identity,status='unavailable',issues=[str(error)])
    definition=demo_artifact(project,'operation-demo-scenarios.json')
    root=demo_artifact(project,'.demo-scenario-generation');head=root/'current.json'
    result=dict(operation=identity,status='unavailable',issues=[])
    try:
        previous=json.loads(head.read_text(encoding='utf-8')) if head.exists() else None
        if definition.exists() and (previous is None or file_hash(definition)!=previous.get('definition_hash')):
            from runtime.fixture_demo.catalogue import prepare_catalogue
            prepare_catalogue(project,identity)
            return dict(result,status='prepared',origin='retained_definition',issues=[])
        if profile is None:raise ValueError('Whole-operation scenario generation requires the configured model profile')
        evidence,locations=collect_scenario_evidence(project,identity,original)
        # Exclude our own derived fixture-only banks, so publication does not change its input identity.
        derived=[key for key,value in evidence['saved_banks'].items()
                 if value['boundary_identity']=='whole-operation-demo:'+identity]
        for key in derived:evidence['saved_banks'].pop(key);locations.pop(key)
        limit=profile.format_comparison.max_cases;settings=profile.test_preparation
        request=dict(**evidence,comparison_case_limit=limit,schema=OperationDemoProposal.model_json_schema())
        fingerprint=digest(dict(request=request,prompt=SCENARIO_PROMPT,settings=settings.model_dump(mode='json'),
            model=profile.model_name,provider=profile.model_provider,endpoint=profile.model_base_url))
        result['input_fingerprint']=fingerprint
        if previous and previous.get('fingerprint')==fingerprint and previous.get('publication_version')==PUBLICATION_VERSION and definition.exists():
            from runtime.fixture_demo.catalogue import prepare_catalogue
            retained=OperationDemoProposal.model_validate_json(saved_generation_proposal(project,previous['proposal']).read_text(encoding='utf-8'))
            validate_proposal(retained,evidence,settings.max_fixture_bytes,limit)
            prepare_catalogue(project,identity)
            return dict(result,status='prepared',origin='cached_generation',issues=[])
        if profile.model_provider=='mock' and model_call is None:raise ValueError('Mock whole-operation preparation requires an explicit fixture model callback')
        from runtime.behavior_conversion.request_context import encode_request
        _,encoded=encode_request(request,SCENARIO_PROMPT,settings.request_chars-settings.response_chars)
        revision=root/fingerprint;revision.mkdir(parents=True,exist_ok=True)
        state_path=revision/'state.json'
        from tools.maven_dependency_tools.pom_manager import project_lock
        with project_lock(state_path):
            state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else dict(attempts=[])
            from runtime.model_execution.adk_executor import AdkExecutor
            call=model_call or AdkExecutor(profile).execute
            proposal=None
            # Revalidate saved responses first. Fixing a preparation validator must not
            # require regenerating valid model output or replenishing its attempts.
            for retained in reversed(state['attempts']):
                response=revision/f"attempt-{retained['number']}"/'response.txt'
                if not response.exists():continue
                try:
                    from runtime.managed_conversion_response import _remove_response_fence
                    candidate=OperationDemoProposal.model_validate_json(_remove_response_fence(response.read_text(encoding='utf-8')))
                    validate_proposal(candidate,evidence,settings.max_fixture_bytes,limit)
                    proposal=candidate;retained['revalidated']=True
                    (revision/'proposal.json').write_text(candidate.model_dump_json(indent=2),encoding='utf-8')
                    break
                except (ValueError,KeyError):pass
            state_path.write_text(json.dumps(state,indent=2),encoding='utf-8')
            for number in range(len(state['attempts']),profile.max_agent_task_retries):
                if proposal is not None:break
                attempt=revision/f'attempt-{number+1}'
                attempt.mkdir(exist_ok=True)
                current=dict(number=number+1,status='in_progress');state['attempts'].append(current)
                (attempt/'request.json').write_text(encoded,encoding='utf-8')
                (attempt/'instruction.txt').write_text(SCENARIO_PROMPT,encoding='utf-8')
                state_path.write_text(json.dumps(state,indent=2),encoding='utf-8')
                try:
                    raw=call(SCENARIO_PROMPT,encoded)
                    (attempt/'response.txt').write_text(raw,encoding='utf-8')
                    from runtime.managed_conversion_response import _remove_response_fence
                    proposal=OperationDemoProposal.model_validate_json(_remove_response_fence(raw))
                    validate_proposal(proposal,evidence,settings.max_fixture_bytes,limit)
                    current['status']='validated'
                    (revision/'proposal.json').write_text(proposal.model_dump_json(indent=2),encoding='utf-8')
                    break
                except Exception as error:
                    from runtime.model_execution.error_details import sanitize_diagnostic
                    current.update(status='failed',error=sanitize_diagnostic(str(error)));proposal=None
                    request['preparation_feedback']=dict(error=current['error'],instruction='Correct preparation only; retain Java and source-supported expectations.')
                    _,encoded=encode_request(request,SCENARIO_PROMPT,settings.request_chars-settings.response_chars)
                finally:state_path.write_text(json.dumps(state,indent=2),encoding='utf-8')
            if proposal is None and (revision/'proposal.json').exists():
                proposal=OperationDemoProposal.model_validate_json((revision/'proposal.json').read_text(encoding='utf-8'))
                validate_proposal(proposal,evidence,settings.max_fixture_bytes,limit)
            if proposal is None:raise ValueError('Whole-operation preparation attempt budget exhausted; inspect '+str(state_path))
            if proposal.unresolved:raise ValueError('Unresolved whole-operation inputs: '+'; '.join(proposal.unresolved))
            fresh,_=collect_scenario_evidence(project,identity,original)
            for key in derived:fresh['saved_banks'].pop(key,None)
            if fresh!=evidence:raise ValueError('Saved Java, source evidence or fixtures changed during scenario preparation')
            materialized,reuse=reuse_saved_resources(proposal,evidence)
            validate_proposal(materialized,evidence,settings.max_fixture_bytes,limit)
            (revision/'materialized-proposal.json').write_text(materialized.model_dump_json(indent=2),encoding='utf-8')
            (revision/'resource-reuse.json').write_text(json.dumps(reuse,indent=2),encoding='utf-8')
            result_definition,published=publish_proposal(project,materialized,evidence,locations,fingerprint)
            (revision/'definition.json').write_text(result_definition.model_dump_json(indent=2)+'\n',encoding='utf-8')
            definition.write_bytes((revision/'definition.json').read_bytes())
            head.write_text(json.dumps(dict(fingerprint=fingerprint,definition_hash=file_hash(definition),
                fixture_revisions=published,proposal=str(revision/'proposal.json'),publication_version=PUBLICATION_VERSION),indent=2),encoding='utf-8')
            result.update(status='prepared',origin='generated',issues=[],scenarios=len(result_definition.scenarios),
                reused_banks=len({ref.bank for s in materialized.scenarios for ref in [s.input_xml,s.expected_xml,*[r for refs in s.resources.values() for r in refs]] if ref.bank!='generated'}),
                generated_fixtures=len(materialized.new_fixtures),resource_reuse=reuse)
    except Exception as error:
        from runtime.model_execution.error_details import sanitize_diagnostic
        result['issues']=[sanitize_diagnostic(str(error))]
    root.mkdir(parents=True,exist_ok=True)
    (root/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result
