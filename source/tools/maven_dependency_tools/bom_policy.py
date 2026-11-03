"""Resolve an explicitly chosen BOM with Maven, retaining its exact effective managed versions."""
import hashlib
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from models.maven_dependency import MavenDependency
from models.shared_dependency_policy import SharedDependencyPolicy
from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier


def resolve_bom(profile,group,artifact,version,dependencies,output):
    """Never guess release versions; ask the configured Maven repositories for the selected BOM."""
    MavenDependency(group_id=group,artifact_id=artifact,version=version)
    verifier=MavenRepositoryVerifier(profile.maven_settings_path,profile.approved_maven_repository_urls,profile.maven_local_repository)
    with tempfile.TemporaryDirectory(prefix='snapir-bom-policy-') as folder:
        root=ET.Element('project',xmlns='http://maven.apache.org/POM/4.0.0')
        for key,value in [('modelVersion','4.0.0'),('groupId','snapir.policy'),('artifactId','dependency-policy'),('version','1')]:ET.SubElement(root,key).text=value
        node=ET.SubElement(ET.SubElement(ET.SubElement(root,'dependencyManagement'),'dependencies'),'dependency')
        for key,value in [('groupId',group),('artifactId',artifact),('version',version),('type','pom'),('scope','import')]:ET.SubElement(node,key).text=value
        path=Path(folder);ET.ElementTree(root).write(path/'pom.xml',encoding='utf-8',xml_declaration=True)
        effective=path/'effective.xml'
        result=verifier._run(verifier._arguments()+['help:effective-pom',f'-Doutput={effective}'],path)
        if result.returncode or not effective.exists():raise ValueError('Maven could not resolve the selected dependency BOM')
        content=effective.read_bytes();parsed=ET.fromstring(content);managed={}
        for item in parsed.findall('{*}dependencyManagement/{*}dependencies/{*}dependency'):
            if item.findtext('{*}type','jar')!='jar':continue
            pin=MavenDependency(group_id=item.findtext('{*}groupId'),artifact_id=item.findtext('{*}artifactId'),version=item.findtext('{*}version'))
            managed[pin.group_id+':'+pin.artifact_id]=pin.version
    if not managed:raise ValueError('Selected BOM has no resolved managed artifact versions')
    policy=SharedDependencyPolicy(description='Shared versions resolved from the explicitly approved BOM',
        bom=dict(group_id=group,artifact_id=artifact,version=version,effective_pom_sha256=hashlib.sha256(content).hexdigest()),
        managed_versions=managed,dependencies=dependencies)
    output=Path(output)
    if output.exists():raise ValueError('Do not overwrite an existing dependency policy revision')
    output.write_text(policy.model_dump_json(indent=2),encoding='utf-8')
    output.with_suffix('.effective-pom.xml').write_bytes(content)
    return policy
