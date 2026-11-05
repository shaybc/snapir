"""Stage environment-specific artifacts without changing the validated service package."""
import hashlib
import shutil
from pathlib import Path


def stage_deployment(project, spec, *, values_path=None, overlays=()):
    """Copy the validated JAR and render the exact configuration used by deployment actions."""
    project=Path(project).resolve()
    identity=hashlib.sha256(spec.model_dump_json().encode()).hexdigest()
    staged=project/'deployment-work'/identity
    target=staged/'target';target.mkdir(parents=True,exist_ok=True)
    jars=list((project/'target').glob('*.jar'))
    if len(jars)!=1:raise ValueError('Expected one validated executable service JAR')
    shutil.copyfile(jars[0],target/jars[0].name)
    from tools.deployment_tools.helm_renderer import render_helm
    from runtime.service_deployment.driver_artifacts import selected_driver,audit_application
    driver=selected_driver(project,spec,Path(values_path).parent if values_path else project)
    if driver:
        # Preserve the managed owner receipt for the staged renderer as well.
        if not spec.deployment.image.jdbcDriver:
            from models.jdbc_image_variant import JdbcDriverArtifact
            from runtime.fixture_jdbc_tools.releases import file_hash
            (staged/'external-jdbc').mkdir(exist_ok=True)
            (staged/'external-jdbc/driver.json').write_text(JdbcDriverArtifact(path='jdbc/jdbc-driver.jar',
                sha256=file_hash(driver),driverClass=spec.databases[spec.operation.database].driverClass).model_dump_json(),encoding='utf-8')
        audit_application(target/jars[0].name,driver,production=True)
        (staged/'jdbc').mkdir(exist_ok=True)
        shutil.copyfile(driver,staged/'jdbc/jdbc-driver.jar')
    chart,_=render_helm(staged,spec,values_path=values_path,overlays=overlays)
    if driver:
        with (staged/'.dockerignore').open('a',encoding='utf-8') as stream:
            stream.write('!jdbc/\n!jdbc/jdbc-driver.jar\n')
    return staged,chart
