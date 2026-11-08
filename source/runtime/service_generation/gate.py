"""Require evidence-bound Gate 4 approval before creating a native microservice."""
import hashlib
import json

from runtime.human_gates import evaluate_gate
from runtime.service_generation.deployment_configuration import load_deployment
from runtime.workspace_paths import write_run_report
from tools.state_store_tools.runs import update_run_status


def require_microservice_approval(conn, config, profile, directory, evidence, *, approved_report, settings_identity):
    """Prepare editable root values and require approval before creating any microservice."""
    operations=[]
    blockers=[]
    for item in sorted(evidence,key=lambda value:(value['channel'],value['operation_id'])):
        identity=item['channel']+'/'+item['operation_id']
        issues=list(item['issues'])
        deployment=None
        demo=None
        if not issues:
            try:
                deployment=load_deployment(item,persist=True,profile=profile).model_dump(mode='json')
                from pathlib import Path
                from runtime.service_generation.deployment_configuration import read_deployment
                from runtime.fixture_jdbc_tools.releases import file_hash,verify_directory
                overlay=Path(item['project'])/'demo-values.yaml'
                if not overlay.exists():
                    from runtime.fixture_demo.preparation import prepare_operation_demo
                    prepare_operation_demo(item['project'],config.output_root,identity)
                if overlay.exists():
                    effective=read_deployment(overlay.parent/'values.yaml',overlays=[overlay])
                    demo=dict(overlay_hash=file_hash(overlay),effective=effective.model_dump(mode='json'))
                    infrastructure=effective.demoInfrastructure
                    if infrastructure and infrastructure.status=='prepared':
                        verify_directory(overlay.parent/infrastructure.toolRoot,infrastructure.bundleId,infrastructure.manifestHash)
                        from runtime.fixture_demo.approval import demo_evidence
                        demo['evidence']=demo_evidence(overlay.parent,infrastructure)
            except (ValueError,OSError) as error:
                issues.append(str(error))
        blockers.extend(identity+': '+issue for issue in issues)
        operations.append(dict(operation=identity,native_fingerprint=item['fingerprint'],deployment=deployment,demo=demo))
    if not operations:blockers.append('No accepted operations are available for microservice creation')
    report='=== Human Gate 4: Create microservices ===\n'+json.dumps(dict(
        purpose='Approve Spring Boot wrapper, executable JAR and Helm chart creation; no image publication or deployment.',
        gate_3_report_hash=hashlib.sha256(approved_report.encode()).hexdigest(),
        generation_settings_hash=hashlib.sha256(settings_identity.encode()).hexdigest(),
        operations=operations,blockers=blockers),sort_keys=True,indent=2)
    write_run_report(directory,'gate_4_report.txt',report)
    decision=evaluate_gate(conn,config.run_id,4,report,profile.gate_policies.get('4','human'),not blockers)
    if decision=='approved':return 'approved'
    phase='gate_4_'+decision
    update_run_status(conn,config.run_id,'paused' if decision=='pending' else 'stopped' if decision=='rejected' else 'blocked',phase)
    return phase
