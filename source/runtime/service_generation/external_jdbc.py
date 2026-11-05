"""Select the configured JDBC driver from Maven's actual managed runtime classpath."""
import json
import os
import shutil
from pathlib import Path
from runtime.operation_layout import service_record
from zipfile import ZipFile
from models.jdbc_image_variant import JdbcDriverArtifact
from runtime.fixture_jdbc_tools.releases import file_hash
from runtime.service_deployment.driver_artifacts import verified_driver


def prepare_external_driver(context,spec,definition_root):
    """Stage only the actual class owner; keep the native POM and unrelated libraries intact."""
    if spec.operation.database is None:return None
    driver=spec.databases[spec.operation.database].driverClass
    if not driver:return None
    project=Path(context.pom_path).parent
    artifact=spec.deployment.image.jdbcDriver
    if artifact:
        source=verified_driver(artifact,definition_root,driver)
    else:
        output=project/'target/external-driver-classpath.txt';output.parent.mkdir(exist_ok=True)
        verifier=context.verifier
        result=verifier._run(verifier._arguments()+[
            'org.apache.maven.plugins:maven-dependency-plugin:3.8.1:build-classpath',
            '-DincludeScope=runtime','-Dmdep.outputFile='+str(output.resolve())],project)
        if result.returncode or not output.exists():raise ValueError('Could not inspect managed JDBC driver class ownership')
        candidates=[]
        for path in set(output.read_text(encoding='utf-8').strip().split(os.pathsep)):
            if not path:continue
            with ZipFile(path) as archive:
                if driver.replace('.','/')+'.class' in archive.namelist():candidates.append(Path(path))
        if len(candidates)!=1:raise ValueError('Configured JDBC driver needs one unambiguous managed runtime class owner')
        source=candidates[0]
    if project.name=='application' and (project.parent/'pom.xml').exists():project=project.parent
    root=project/'external-jdbc'/file_hash(source)
    root.mkdir(parents=True,exist_ok=True)
    target=root/'jdbc-driver.jar'
    if target.exists() and file_hash(target)!=file_hash(source):raise ValueError('Staged production JDBC driver changed')
    if not target.exists():shutil.copyfile(source,target)
    artifact=JdbcDriverArtifact(path=target.relative_to(project).as_posix(),sha256=file_hash(target),driverClass=driver)
    receipt=service_record(project,'external-jdbc/driver.json');receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(artifact.model_dump_json(indent=2)+'\n',encoding='utf-8')
    return target
