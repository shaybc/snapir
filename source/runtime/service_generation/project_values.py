"""Retain editable Helm values with paths relative to the generated service project."""
import os
import shutil
from pathlib import Path
import yaml
from runtime.service_generation.deployment_configuration import read_deployment, service_name


def stage_values(project, source):
    """Copy values to the chart and relocate only local driver/demo asset references."""
    project, source = Path(project), Path(source)
    spec = read_deployment(source)
    chart = project / 'helm' / service_name(*spec.operation.identity.split('/', 1))
    chart.mkdir(parents=True, exist_ok=True)
    target = chart / 'values.yaml'
    values = yaml.safe_load(source.read_text(encoding='utf-8'))
    driver = values.get('image', {}).get('jdbcDriver')
    if driver:
        from runtime.service_deployment.driver_artifacts import verified_driver
        artifact = spec.deployment.image.jdbcDriver
        original = verified_driver(artifact, source.parent, artifact.driverClass)
        destination = project / 'jdbc/jdbc-driver.jar'
        destination.parent.mkdir(exist_ok=True)
        if original.resolve()!=destination.resolve():shutil.copyfile(original, destination)
        driver['path'] = os.path.relpath(destination, chart).replace('\\', '/')
        if target.exists() and yaml.safe_load(target.read_text(encoding='utf-8'))!=values:
            raise ValueError('Existing edited Helm values differ from the approved creation inputs')
        if not target.exists():target.write_text(yaml.safe_dump(values, sort_keys=False), encoding='utf-8')
    elif source.resolve() != target.resolve():
        if target.exists() and yaml.safe_load(target.read_text(encoding='utf-8'))!=values:
            raise ValueError('Existing edited Helm values differ from the approved creation inputs')
        if not target.exists():shutil.copyfile(source, target)
    overlay = source.parent / 'demo-values.yaml'
    if overlay.exists():
        data = yaml.safe_load(overlay.read_text(encoding='utf-8'))
        for section, key in [(data.get('image', {}).get('jdbcDriver', {}), 'path'),
                             (data.get('demoInfrastructure', {}), 'toolRoot'),
                             (data.get('demoInfrastructure', {}), 'catalogue')]:
            if section.get(key):
                section[key] = os.path.relpath((source.parent / section[key]).resolve(), chart).replace('\\', '/')
        demo_target=chart / 'demo-values.yaml'
        if demo_target.exists() and yaml.safe_load(demo_target.read_text(encoding='utf-8'))!=data:
            raise ValueError('Existing edited demo Helm values differ from the approved creation inputs')
        if not demo_target.exists():demo_target.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
    return read_deployment(target), target
