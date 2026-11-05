"""Verify external driver bytes, class ownership and vendor API compatibility."""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import re
import struct
import json
from runtime.fixture_jdbc_tools.releases import file_hash


def class_names(archive):
    """Read actual class ownership, ignoring versioned aliases of the same library."""
    return {name[:-6] for name in archive.namelist() if name.endswith('.class')
            and not name.startswith('META-INF/') and name!='module-info.class'}


def verified_driver(artifact, directory, expected_class):
    """A filename is insufficient: check hash and the configured public class."""
    path=(Path(directory)/artifact.path).resolve()
    if not path.is_file() or file_hash(path)!=artifact.sha256:
        raise ValueError('External JDBC driver artifact changed or is missing')
    if artifact.driverClass!=expected_class:
        raise ValueError('External JDBC driver class differs from selected database configuration')
    with ZipFile(path) as driver:
        if expected_class.replace('.','/') not in class_names(driver):
            raise ValueError('External JDBC driver does not contain the configured class')
    return path


def selected_driver(project,spec,definition_root=None):
    """Resolve an explicit artifact or the managed wrapper's verified Maven owner receipt."""
    if not spec.operation.database:return None
    driver=spec.databases[spec.operation.database].driverClass
    artifact=spec.deployment.image.jdbcDriver
    directory=Path(definition_root or project)
    if artifact is None:
        receipt=Path(project)/'external-jdbc/driver.json'
        if not receipt.exists():return None
        from models.jdbc_image_variant import JdbcDriverArtifact
        artifact=JdbcDriverArtifact.model_validate(json.loads(receipt.read_text(encoding='utf-8')))
        directory=Path(project)
    return verified_driver(artifact,directory,driver)


def class_references(data):
    """Read JVM class constants/descriptors; do not interpret generated Java syntax."""
    if data[:4]!=b'\xca\xfe\xba\xbe':raise ValueError('Invalid compiled class')
    count=struct.unpack_from('>H',data,8)[0];offset=10;index=1;utf={};classes=[]
    sizes={3:4,4:4,5:8,6:8,7:2,8:2,9:4,10:4,11:4,12:4,15:3,16:2,17:4,18:4,19:2,20:2}
    while index<count:
        tag=data[offset];offset+=1
        if tag==1:
            length=struct.unpack_from('>H',data,offset)[0];offset+=2
            utf[index]=data[offset:offset+length].decode('utf-8',errors='replace');offset+=length
        else:
            if tag not in sizes:raise ValueError('Unsupported JVM constant-pool tag')
            if tag==7:classes.append(struct.unpack_from('>H',data,offset)[0])
            offset+=sizes[tag]
        index+=2 if tag in (5,6) else 1
    return {utf[i] for i in classes if i in utf} | {name for text in utf.values() for name in re.findall(r'L([^;<]+)',text)}


def audit_application(application, driver_path=None, *, production=False):
    """Block class shadowing, embedded fixture tooling and direct swappable-driver API use."""
    driver_classes=set()
    if driver_path:
        with ZipFile(driver_path) as driver:driver_classes=class_names(driver)
    with ZipFile(application) as archive:
        libraries=[];owned=[]
        for name in archive.namelist():
            if name.startswith('BOOT-INF/classes/') and name.endswith('.class'):
                owned.append((name,archive.read(name)))
            elif name.startswith('BOOT-INF/lib/') and name.endswith('.jar'):
                libraries.append((name,archive.read(name)))
            elif production and name.startswith('BOOT-INF/classes/') and name.endswith(('.json','.yaml','.yml')):
                raw=archive.read(name)
                if b'fixture-jdbc-catalogue-v1' in raw or b'shared-fixtures-v1' in raw:
                    raise ValueError('Production application contains a fixture catalogue or dataset')
        names={name.removeprefix('BOOT-INF/classes/')[:-6] for name,_ in owned}
        for _,raw in libraries:
            with ZipFile(BytesIO(raw)) as library:names |= class_names(library)
        if production and any(name.startswith('il/co/dcd/fixtures/') for name in names):
            raise ValueError('Production application contains fixture tooling')
        if names & driver_classes:
            raise ValueError('External JDBC driver shadows a packaged application/runtime class; externalize the managed driver dependency first')
        for name,raw in owned:
            if class_references(raw)&driver_classes:
                raise ValueError('Application directly references swappable vendor APIs: '+name)
        for name,raw in libraries:
            with ZipFile(BytesIO(raw)) as library:
                for member in library.namelist():
                    if member.endswith('.class') and not member.startswith('META-INF/') and class_references(library.read(member))&driver_classes:
                        raise ValueError('Runtime dependency directly references swappable vendor APIs: '+name)


def driver_coordinates(path):
    """Require unambiguous embedded Maven ownership before excluding a packaged driver."""
    with ZipFile(path) as driver:
        metadata=[name for name in driver.namelist() if name.startswith('META-INF/maven/') and name.endswith('/pom.properties')]
        if len(metadata)!=1:raise ValueError('Externalizing this driver requires unambiguous verified Maven artifact ownership')
        values=dict(line.strip().split('=',1) for line in driver.read(metadata[0]).decode('iso-8859-1').splitlines()
                    if '=' in line and not line.startswith('#'))
        if not all(values.get(k) for k in ('groupId','artifactId','version')):
            raise ValueError('External JDBC driver Maven identity is incomplete')
        return values
