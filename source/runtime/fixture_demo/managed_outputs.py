"""Refresh converter-owned demo metadata without overwriting user edits."""
import json
from pathlib import Path
from runtime.fixture_jdbc_tools.releases import digest,file_hash
from runtime.fixture_demo.artifact_paths import demo_artifact,migrate_demo_artifacts


def ownership(project):
    """Load generated-file hashes; no production configuration or credentials are read."""
    migrate_demo_artifacts(project)
    path=demo_artifact(project,'.demo-owned-files.json');path.parent.mkdir(parents=True,exist_ok=True)
    return path,json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def set_demo_binding(path,demo):
    """Replace only an unchanged generated demo entry, preserving all ordinary runner settings."""
    path=Path(path);owner,record=ownership(path.parent.parent)
    binding=json.loads(path.read_text(encoding='utf-8'));current=binding.get('demo')
    if current is not None and current!=demo and record.get('binding')!=digest(current):
        raise ValueError('Existing user-edited demo binding differs; it was preserved')
    if current!=demo:
        binding['demo']=demo
        path.write_text(json.dumps(binding,indent=2)+'\n',encoding='utf-8')
        record['binding']=digest(demo);owner.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')


def write_demo_overlay(path,text,*,legacy_placeholder=None):
    """Refresh generated overlays; recognize only the exact previous unavailable placeholder."""
    path=Path(path);owner,record=ownership(path.parent)
    if path.exists():
        raw=path.read_bytes()
        if raw==text.encode('utf-8'):return True
        if record.get('overlay')!=file_hash(path) and (legacy_placeholder is None or raw!=legacy_placeholder.encode('utf-8')):
            return False
    path.write_bytes(text.encode('utf-8'));record['overlay']=file_hash(path)
    owner.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return True


def write_demo_request(project,xml):
    """Publish the selected full-operation request while preserving a user-edited demo XML."""
    project=Path(project);path=project/'standalone/demo-request.xml';owner,record=ownership(project)
    raw=xml.encode('utf-8')
    if path.exists() and path.read_bytes()!=raw and record.get('request')!=file_hash(path):return None
    if not path.exists() or path.read_bytes()!=raw:path.write_bytes(raw)
    record['request']=file_hash(path);owner.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return path
