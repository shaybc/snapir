"""Strict ordered Helm values merge, with explicit production/demo isolation checks."""
from copy import deepcopy
from pathlib import Path
import yaml
from runtime.service_generation.helm_values import deployment_from_values


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate keys instead of silently choosing one configuration."""


def _mapping(loader,node,deep=False):
    result={}
    for key,value in node.value:
        name=loader.construct_object(key,deep=deep)
        if not isinstance(name,str) or name in result:
            raise ValueError('Helm values require unique string keys')
        result[name]=loader.construct_object(value,deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,_mapping)


def merge_values(base, overlay):
    """Match Helm: recursively merge maps, replace lists/scalars, delete explicit nulls."""
    result=deepcopy(base)
    for key,value in overlay.items():
        if value is None:
            result.pop(key,None)
        elif isinstance(value,dict) and isinstance(result.get(key),dict):
            result[key]=merge_values(result[key],value)
        else:
            result[key]=deepcopy(value)
    return result


def read_values(paths):
    """Read the same ordered documents passed to Helm and reject invalid effective settings."""
    result={};base=None
    for path in paths:
        values=yaml.load(Path(path).read_text(encoding='utf-8'),Loader=UniqueKeyLoader)
        if not isinstance(values,dict):raise ValueError('Helm values must be a mapping')
        if base is None:base=deepcopy(values)
        result=merge_values(result,values)
    spec=deployment_from_values(result)
    demo=spec.demoInfrastructure
    selected=spec.databases.get(spec.operation.database)
    fixture=bool(selected and selected.jdbcUrl.startswith('jdbc:fixtures:'))
    if demo is None and (fixture or (selected and selected.driverClass.startswith('il.co.dcd.fixtures.'))):
        raise ValueError('Production values cannot select fixture JDBC tools; use an explicit demo overlay')
    if demo is not None and demo.status=='prepared':
        if not fixture or selected.driverClass!='il.co.dcd.fixtures.jdbc.FixtureDriver':
            raise ValueError('Demo overlay must select the fixture JDBC URL and driver together')
        original=base.get('databases',{}).get(base.get('operation',{}).get('database'),{})
        if selected.credentialsSecret.name==original.get('credentialsSecret',{}).get('name'):
            raise ValueError('Demo must use a separate credential Secret reference')
        if not spec.deployment.image.jdbcDriver:
            raise ValueError('Demo image requires the verified external fixture driver')
        base_image=base.get('image',{})
        if spec.deployment.image.baseImage!=base_image.get('baseImage','eclipse-temurin:25-jre'):
            raise ValueError('Production and demo images must share the same base image')
        if spec.deployment.image.repository and spec.deployment.image.repository==base_image.get('repository'):
            raise ValueError('Demo must select a separate application image repository')
        from urllib.parse import urlparse
        url=urlparse(selected.jdbcUrl.removeprefix('jdbc:fixtures:'))
        if demo.enabled and (url.hostname not in ('127.0.0.1','localhost','::1') or url.port!=demo.port):
            raise ValueError('Sidecar JDBC URL must use loopback and the configured fixture port')
    return result,spec
