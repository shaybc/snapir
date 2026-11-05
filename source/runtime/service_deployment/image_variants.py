"""Create immutable, separate image contexts sharing one validated application JAR."""
import json
import hashlib
from pathlib import Path
from runtime.operation_layout import application_project, service_artifacts, service_record
from jinja2 import Environment, StrictUndefined
from runtime.fixture_jdbc_tools.releases import digest, file_hash, verify_directory
from runtime.service_deployment.driver_artifacts import selected_driver, audit_application

LAUNCHER=['java','-Dloader.path=/opt/jdbc/','-cp','/app/application.jar',
         'org.springframework.boot.loader.launch.PropertiesLauncher']


def stage_image_variant(project, spec, *, variant='production', definition_root=None):
    """Publish one content-addressed context; no image build, driver download or JAR rewrite."""
    project=Path(project);definition_root=Path(definition_root or project)
    jars=list((application_project(project)/'target').glob('*.jar'))
    if len(jars)!=1:raise ValueError('Expected one validated application JAR for image variants')
    jar=jars[0];driver=None
    from zipfile import ZipFile
    with ZipFile(jar) as application:
        if 'org/springframework/boot/loader/launch/PropertiesLauncher.class' not in application.namelist() or \
                b'Start-Class:' not in application.read('META-INF/MANIFEST.MF'):
            raise ValueError('Application is not a validated Spring Boot executable with PropertiesLauncher')
    if variant=='demo':
        demo=spec.demoInfrastructure
        if not demo or demo.status!='prepared':raise ValueError('Demo fixtures are unavailable')
        release=verify_directory(definition_root/demo.toolRoot,demo.bundleId,demo.manifestHash)
        expected=release.files['jdbc/fixture-jdbc-driver.jar'].sha256
        artifact=spec.deployment.image.jdbcDriver
        if not artifact or artifact.sha256!=expected:raise ValueError('Demo image driver is not the pinned fixture tool artifact')
    elif spec.demoInfrastructure is not None:
        raise ValueError('Production context cannot use demo values')
    selected=spec.databases.get(spec.operation.database)
    artifact=spec.deployment.image.jdbcDriver
    driver=selected_driver(project,spec,definition_root)
    if driver:
        if not selected:raise ValueError('External driver configured without a selected database')
        if variant=='production':
            from zipfile import ZipFile
            from runtime.service_deployment.driver_artifacts import class_names
            with ZipFile(driver) as archive:
                if any(name.startswith('il/co/dcd/fixtures/') for name in class_names(archive)):
                    raise ValueError('Production external JDBC driver contains fixture tooling')
    audit_application(jar,driver,production=True)
    if selected and selected.driverClass and driver is None:
        from runtime.service_deployment.jdbc_driver import driver_available
        if driver_available(project,spec):
            raise ValueError('Selected driver is embedded in this historical JAR; build a new managed wrapper package with external driver ownership before demo swapping')
    template=Path(__file__).resolve().parents[2]/'templates/microservice/Dockerfile.j2'
    identity=dict(variant=variant,application_sha256=file_hash(jar),driver_sha256=file_hash(driver) if driver else None,
        base_image=spec.deployment.image.baseImage,launcher=LAUNCHER,port=spec.http.port,
        docker_template_sha256=file_hash(template))
    if variant=='demo':
        identity.update(bundle_id=demo.bundleId,manifest_hash=demo.manifestHash,catalogue_hash=demo.catalogueHash)
    root=service_artifacts(project)/'images'/variant/digest(identity)
    docker=Environment(undefined=StrictUndefined,variable_start_string='[[',variable_end_string=']]').from_string(
        template.read_text(encoding='utf-8')).render(base_image=identity['base_image'],jar_name='application.jar',jar_source='target/application.jar',
            port=spec.http.port,external_driver=bool(driver))+'\n'
    files={'target/application.jar':jar.read_bytes(),'Dockerfile':docker.encode(),
           '.dockerignore':b'*\n!Dockerfile\n!target/\n!target/application.jar\n!jdbc/\n!jdbc/jdbc-driver.jar\n'}
    if driver:files['jdbc/jdbc-driver.jar']=driver.read_bytes()
    manifest=dict(identity=identity,files={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()})
    files['variant.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    for name,raw in files.items():
        path=root/name
        if path.exists() and path.read_bytes()!=raw:raise ValueError('Immutable image context changed: '+name)
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():path.write_bytes(raw)
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual!=set(files):raise ValueError('Image context contains unlisted files')
    return dict(context=str(root.resolve()),**identity)


def stage_server_image(project,spec,definition_root):
    """Server image contains only prebuilt tooling; fixture data is a read-only runtime mount."""
    demo=spec.demoInfrastructure
    release=verify_directory(Path(definition_root)/demo.toolRoot,demo.bundleId,demo.manifestHash)
    server=Path(definition_root)/demo.toolRoot/'server/fixture-server.jar'
    identity=dict(bundle_id=demo.bundleId,server_sha256=release.files['server/fixture-server.jar'].sha256,
                  base_image=spec.deployment.image.baseImage)
    root=service_artifacts(project)/'images/fixture-server'/digest(identity)
    root.mkdir(parents=True,exist_ok=True)
    docker='FROM '+identity['base_image']+'\nWORKDIR /server\nCOPY fixture-server.jar /server/fixture-server.jar\nUSER 10001\nENTRYPOINT ["java","-jar","/server/fixture-server.jar"]\n'
    for name,data in {'fixture-server.jar':server.read_bytes(),'Dockerfile':docker.encode(),
        '.dockerignore':b'*\n!Dockerfile\n!fixture-server.jar\n'}.items():
        path=root/name
        if path.exists() and path.read_bytes()!=data:raise ValueError('Immutable fixture server context changed')
        if not path.exists():path.write_bytes(data)
    if {p.name for p in root.iterdir() if p.is_file()}!={'fixture-server.jar','Dockerfile','.dockerignore'}:
        raise ValueError('Fixture server image context contains unlisted files')
    return dict(context=str(root.resolve()),**identity)


def prepare_image_variants(project,spec,values_path,*,overlays=()):
    """Prepare production plus an explicitly separate demo recipe, recording optional unavailability."""
    from runtime.service_generation.deployment_configuration import read_deployment
    base=Path(values_path);result={}
    try:result['production']=stage_image_variant(project,read_deployment(base),definition_root=base.parent)
    except (ValueError,OSError) as error:result['production']=dict(status='unavailable',reason=str(error))
    demo_path=base.parent/'demo-values.yaml'
    if demo_path.exists():
        try:
            demo=read_deployment(base,overlays=[demo_path])
            result['demo']=stage_image_variant(project,demo,variant='demo',definition_root=base.parent)
            result['fixture_server']=stage_server_image(project,demo,base.parent)
            if result['production'].get('application_sha256')!=result['demo']['application_sha256']:
                raise ValueError('Production/demo application JAR identities differ')
        except (ValueError,OSError) as error:result['demo']=dict(status='unavailable',reason=str(error))
    service_record(project,'image-variants.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result
