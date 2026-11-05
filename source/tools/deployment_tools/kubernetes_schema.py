"""Validate rendered built-in resources against a pinned Kubernetes OpenAPI schema."""
import hashlib
import json
from pathlib import Path
import re
from urllib.request import urlopen
from jsonschema import Draft4Validator, RefResolver


def validate_kubernetes(documents, directory, version='1.34.0'):
    """Download/cache only the official versioned schema; a missing schema is a validation failure."""
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):raise ValueError('Invalid Kubernetes schema version')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    path=directory/('kubernetes-'+version+'.json')
    source='https://raw.githubusercontent.com/kubernetes/kubernetes/v'+version+'/api/openapi-spec/swagger.json'
    if not path.exists():
        with urlopen(source,timeout=60) as response:raw=response.read()
        parsed=json.loads(raw)
        if 'definitions' not in parsed:raise ValueError('Kubernetes schema has no definitions')
        path.write_bytes(raw)
    raw=path.read_bytes();schema=json.loads(raw)
    def openapi_types(value):
        # Kubernetes OpenAPI v2 expresses IntOrString as a string with a special format.
        # JSON Schema must explicitly retain both supported JSON types.
        if isinstance(value,dict):
            if value.get('format')=='int-or-string': value['type']=['integer','string']
            for child in value.values():openapi_types(child)
        elif isinstance(value,list):
            for child in value:openapi_types(child)
    openapi_types(schema)
    resolver=RefResolver.from_schema(schema)
    definitions={}
    for definition in schema['definitions'].values():
        for identity in definition.get('x-kubernetes-group-version-kind',[]):
            group=identity.get('group','');api=(group+'/' if group else '')+identity['version']
            definitions[(api,identity['kind'])]=definition
    checked=[]
    for document in documents:
        if document is None:continue
        key=(document.get('apiVersion'),document.get('kind'))
        if key not in definitions:raise ValueError('No Kubernetes schema for rendered resource: '+str(key))
        Draft4Validator(definitions[key],resolver=resolver).validate(document)
        checked.append(document['kind'])
    return dict(passed=True,version=version,source=source,schema_hash=hashlib.sha256(raw).hexdigest(),kinds=checked)
