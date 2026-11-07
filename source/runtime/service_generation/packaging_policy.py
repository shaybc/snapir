"""Bind wrapper approval/reuse to maintained JDBC/image/chart packaging code."""
import hashlib
import json
from pathlib import Path


def packaging_fingerprint():
    """Template or packaging-policy changes require fresh Gate 4 evidence."""
    source=Path(__file__).resolve().parents[2]
    paths=[*source.joinpath('templates/microservice').rglob('*'),*source.joinpath('templates/helm').rglob('*'),
        source/'runtime/service_generation/project_output.py',source/'runtime/service_generation/external_jdbc.py',
        source/'runtime/service_deployment/driver_artifacts.py',source/'runtime/service_deployment/image_variants.py',
        source/'runtime/service_generation/values_overlays.py',source/'models/jdbc_image_variant.py',source/'runtime/operation_layout.py',
        source/'runtime/service_generation/maven_reactor.py',source/'runtime/service_generation/project_values.py',
        source/'runtime/service_addresses.py',source/'runtime/operation_reuse/runtime_settings.py',
        source/'runtime/component_conversion/shared_dependencies.py']
    identity={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
    return hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
