"""Check the selected deployment driver in the actual packaged Spring Boot runtime."""
from io import BytesIO
from pathlib import Path
from runtime.operation_layout import application_project
from zipfile import ZipFile


def driver_available(project, spec, *, definition_root=None):
    """Inspect packaged classes without loading a driver or contacting a database."""
    if not spec.operation.database:return True
    driver=spec.databases[spec.operation.database].driverClass
    if not driver:return False
    from runtime.service_deployment.driver_artifacts import selected_driver,audit_application
    external=selected_driver(project,spec,definition_root)
    if external:
        jars=list((application_project(project)/'target').glob('*.jar'))
        if len(jars)!=1:raise ValueError('Expected one validated executable service JAR')
        audit_application(jars[0],external,production=True)
        return True
    jars=list((application_project(project)/'target').glob('*.jar'))
    if len(jars)!=1:raise ValueError('Expected one validated executable service JAR')
    name=driver.replace('.','/')+'.class'
    with ZipFile(jars[0]) as application:
        if 'BOOT-INF/classes/'+name in application.namelist():return True
        for member in application.namelist():
            if member.startswith('BOOT-INF/lib/') and member.endswith('.jar'):
                with ZipFile(BytesIO(application.read(member))) as library:
                    if name in library.namelist():return True
    return False
