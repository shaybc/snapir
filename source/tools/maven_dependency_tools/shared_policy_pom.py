"""Publish approved version management into each canonical or temporary target POM."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from runtime.dependency_policy import load_policy,inventory
from tools.maven_dependency_tools.pom_manager import project_lock
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def apply_shared_policy(pom_path,profile):
    """Align dependency versions only; preserve Java, dependency scopes and unrelated POM settings."""
    policy=load_policy(profile)
    if policy is None:return
    versions={item['group_id']+':'+item['artifact_id']:item['version'] for item in inventory(profile)}
    path=Path(pom_path)
    with project_lock(path):
        original=path.read_bytes();root=ET.fromstring(original)
        ns=root.tag[:-len('project')];tag=lambda name:ns+name
        managed=root.find(tag('dependencyManagement'))
        if managed is None:managed=ET.SubElement(root,tag('dependencyManagement'))
        dependencies=managed.find(tag('dependencies'))
        if dependencies is None:dependencies=ET.SubElement(managed,tag('dependencies'))
        existing={node.findtext(tag('groupId'))+':'+node.findtext(tag('artifactId')):node for node in dependencies.findall(tag('dependency'))}
        changed=False
        for coordinate,version in sorted(versions.items()):
            node=existing.get(coordinate)
            if node is None:
                node=ET.SubElement(dependencies,tag('dependency'));group,artifact=coordinate.split(':')
                ET.SubElement(node,tag('groupId')).text=group;ET.SubElement(node,tag('artifactId')).text=artifact
            selected=node.find(tag('version'))
            if selected is None:selected=ET.SubElement(node,tag('version'))
            if selected.text!=version:selected.text=version;changed=True
        for node in root.findall(tag('dependencies')+'/'+tag('dependency')):
            coordinate=node.findtext(tag('groupId'))+':'+node.findtext(tag('artifactId'))
            if coordinate not in versions:continue
            selected=node.find(tag('version'))
            if selected is None:selected=ET.SubElement(node,tag('version'))
            if selected.text!=versions[coordinate]:selected.text=versions[coordinate];changed=True
        if not changed:return
        if ns:ET.register_namespace('',ns[1:-1])
        content=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        with path.with_name('dependency_policy_audit.jsonl').open('a',encoding='utf-8') as audit:
            audit.write(json.dumps(dict(policy=digest(policy.model_dump(mode='json')),before=hashlib.sha256(original).hexdigest(),after=hashlib.sha256(content).hexdigest(),managed_versions=versions))+'\n')
        descriptor,temporary=tempfile.mkstemp(dir=path.parent,prefix='.policy-',suffix='.tmp')
        try:
            with os.fdopen(descriptor,'wb') as output:output.write(content);output.flush();os.fsync(output.fileno())
            os.replace(temporary,path)
        finally:
            if Path(temporary).exists():Path(temporary).unlink()
