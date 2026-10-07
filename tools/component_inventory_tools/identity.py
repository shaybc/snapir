"""Construct content-independent source identities and separate change fingerprints."""

import hashlib
import json
from pathlib import Path

from models.source_component_identity import SourceImplementationRecord


def stable_id(*values):
    """Hash a structured identity without delimiter collisions."""
    return hashlib.sha256(json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


def identify_java_source(workspace, workspace_id, source_root, source_path, fqcn, method_signature=None):
    """Identify a resolved definition, not a calling channel or configuration alias."""
    workspace = Path(workspace).resolve()
    path = Path(source_path).resolve()
    root = Path(source_root).resolve()
    relative = path.relative_to(workspace).as_posix()
    relative_root = root.relative_to(workspace).as_posix()
    package, _, name = fqcn.rpartition(".")
    return SourceImplementationRecord(
        implementation_id=stable_id(workspace_id, relative_root, relative, fqcn, method_signature),
        workspace_id=workspace_id, source_root=relative_root, source_path=relative,
        package_name=package, class_name=name, method_signature=method_signature,
        source_hash=hashlib.sha256(path.read_bytes()).hexdigest())

