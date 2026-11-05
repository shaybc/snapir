"""Run explicitly requested image and Helm actions after validation and environment preflight."""
import hashlib
import json
import subprocess
from pathlib import Path
from runtime.service_deployment.receipt import verify_package
from runtime.service_generation.deployment_configuration import deployment_readiness


def execute_deployment(project, spec, *, build=False, publish=False, deploy=False, docker='docker', helm='helm', kubectl='kubectl', values_path=None, overlays=()):
    """No action runs by default; never infer deployment success from a generated chart."""
    project=Path(project).resolve();verify_package(project)
    result=dict(image_built=False,image_published=False,deployed=False,commands=[])
    def run(arguments,timeout=300):
        completed=subprocess.run(arguments,cwd=project,capture_output=True,text=True,timeout=timeout)
        result['commands'].append(dict(arguments=arguments,returncode=completed.returncode))
        if completed.returncode:raise ValueError('Deployment action failed: '+arguments[0]+' '+arguments[1])
        return completed.stdout
    image=spec.deployment.image
    variant='demo' if spec.demoInfrastructure is not None else 'production'
    image_receipt=project/('image-build-demo.json' if variant=='demo' else 'image-build.json')
    def image_inputs():
        jars=list((project/'target').glob('*.jar'))
        if len(jars)!=1:raise ValueError('Expected one validated executable service JAR')
        result=dict(repository=image.repository,base_image=image.baseImage,variant=variant,
            jar_hash=hashlib.sha256(jars[0].read_bytes()).hexdigest(),driver=None)
        from runtime.service_deployment.driver_artifacts import selected_driver
        path=selected_driver(project,spec,Path(values_path).parent if values_path else project)
        if path:
            from runtime.fixture_jdbc_tools.releases import file_hash
            result['driver']=dict(sha256=file_hash(path),driverClass=spec.databases[spec.operation.database].driverClass)
        if variant=='demo':
            from runtime.fixture_demo.approval import demo_evidence
            result['demo_evidence']=demo_evidence(Path(values_path).parent if values_path else project,spec.demoInfrastructure)
        return result
    if (build or publish) and not image.repository:raise ValueError('An explicit image repository is required')
    staged=chart=None
    if deploy:
        readiness=deployment_readiness(spec)
        if not readiness['deployment_ready']:raise ValueError('Deployment settings are incomplete: '+', '.join(readiness['unresolved']))
        from runtime.service_deployment.jdbc_driver import driver_available
        if not driver_available(project,spec,definition_root=Path(values_path).parent if values_path else project):raise ValueError('Selected JDBC driver is absent from the validated executable JAR or verified external artifact')
    if build and '@sha256:' not in image.baseImage:
        raise ValueError('Pin the container base image digest before building')
    if (build or publish or deploy) and variant=='demo' and spec.demoInfrastructure.status!='prepared':
        raise ValueError('Demo is unavailable; retain a coherent saved operation scenario before image actions')
    if build or deploy:
        from runtime.service_deployment.staging import stage_deployment
        staged,chart=stage_deployment(project,spec,values_path=values_path,overlays=overlays)
        from tools.deployment_tools.helm_validation import validate_helm
        values_path=Path(values_path) if values_path is not None else staged/'values.yaml'
        validate_helm(chart,spec,helm,values_path=values_path,overlays=overlays)
        result['staged_project']=str(staged)
    if build:
        from runtime.service_deployment.image_variants import stage_image_variant
        context=stage_image_variant(project,spec,variant=variant,definition_root=Path(values_path).parent if values_path else project)
        inputs=dict(**image_inputs(),context_identity={k:v for k,v in context.items() if k!='context'})
        from runtime.fixture_jdbc_tools.releases import digest
        tag=image.repository+':candidate-'+variant+'-'+digest(inputs)[:16]
        result['image_context']=context['context']
        run([docker,'build','--tag',tag,context['context']],600);result['image_built']=True
        built=dict(inputs=inputs,tag=tag,image_id=run([docker,'image','inspect',tag,'--format','{{.Id}}']).strip())
        if not built['image_id']:raise ValueError('Built image has no Docker image identity')
        image_receipt.write_text(json.dumps(built,indent=2)+'\n',encoding='utf-8')
    if publish:
        if not image_receipt.exists():raise ValueError('Build this validated service image before publishing it')
        built=json.loads(image_receipt.read_text(encoding='utf-8'))
        from runtime.service_deployment.image_variants import stage_image_variant
        context=stage_image_variant(project,spec,variant=variant,definition_root=Path(values_path).parent if values_path else project)
        inputs=dict(**image_inputs(),context_identity={k:v for k,v in context.items() if k!='context'})
        if built.get('inputs')!=inputs:raise ValueError('Image build does not match the current validated JAR, driver, recipe and base image')
        from runtime.fixture_jdbc_tools.releases import digest
        tag=image.repository+':candidate-'+variant+'-'+digest(inputs)[:16]
        if built.get('tag')!=tag:raise ValueError('Image build tag does not match its immutable variant identity')
        current=run([docker,'image','inspect',tag,'--format','{{.Id}}']).strip()
        if current!=built.get('image_id'):raise ValueError('Local image tag changed after the validated build')
        run([docker,'push',tag],600);result['image_published']=True
        result['published_digests']=json.loads(run([docker,'image','inspect',tag,'--format','{{json .RepoDigests}}']))
    if deploy:
        if variant=='demo':
            from runtime.fixture_demo.approval import demo_evidence
            demo_evidence(Path(values_path).parent if values_path else project,spec.demoInfrastructure)
            claim=json.loads(run([kubectl,'get','pvc',spec.demoInfrastructure.fixtureClaim,'--namespace',
                spec.deployment.namespace,'-o','json']))
            if claim.get('status',{}).get('phase')!='Bound':raise ValueError('Fixture PVC is not bound')
        if spec.operation.database:
            database=spec.databases[spec.operation.database]
            keys=run([kubectl,'get','secret',database.credentialsSecret.name,'--namespace',spec.deployment.namespace,
                '-o','go-template={{range $key, $value := .data}}{{$key}}{{"\n"}}{{end}}']).splitlines()
            if not {database.credentialsSecret.usernameKey,database.credentialsSecret.passwordKey}<=set(keys):
                raise ValueError('Database Secret lacks required credential keys')
        run([helm,'upgrade','--install',chart.name,str(chart),'--namespace',spec.deployment.namespace,
             '--values',str(values_path),*[arg for path in overlays for arg in ('--values',str(path))],
             '--wait','--timeout','5m'],360)
        run([kubectl,'rollout','status','deployment/'+chart.name,'--namespace',spec.deployment.namespace,'--timeout=300s'],330)
        result['deployed']=True
    (project/'deployment-result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
