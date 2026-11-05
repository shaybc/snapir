from __future__ import annotations

from pathlib import Path
from runtime.composer_map_progress import composer_map_validation_progress


REQUIRED_VAULT_PATHS = [
    "analysis",
    "analysis/channel-operation-registry.md",
]


def validate_vault_structure(vault_root: str) -> list[str]:
    return validate_vault_input(vault_root, [])[0]


def validate_existing_composer_map(vault_root: str, target_channels: list[str]) -> None:
    """Reject unavailable maps or missing selected channels without modifying input."""
    if not Path(vault_root).is_dir():
        raise ValueError("existing_composer_map must identify an existing map directory")
    with composer_map_validation_progress(vault_root) as progress:
        missing, channels = validate_vault_input(vault_root, target_channels, progress=progress)
        if missing:
            raise ValueError("Existing Composer map is missing required paths: " + "; ".join(missing))
        if channels:
            raise ValueError("Existing Composer map is missing selected channels: " + ", ".join(channels))


def validate_vault_input(vault_root: str, target_channels: list[str], *, progress=None) -> tuple[list[str], list[str]]:
    """Validate notes once and check requested execution channels without a legacy registry."""
    root = Path(vault_root)
    missing: list[str] = []
    if not root.exists():
        return [vault_root], list(target_channels)
    from tools.composer_mapper_tools.vault_manifest import read_vault_manifest
    manifest = read_vault_manifest(root, retain_inventory=False, allow_shared=True, progress=progress)
    if manifest is not None:
        contexts = manifest.get('operation_contexts', manifest['entities'])
        available = {entry['channel'] for entry in contexts if entry.get('operation_id')}
        return [], [channel for channel in target_channels if channel not in available]
    for relative_path in REQUIRED_VAULT_PATHS:
        path = root / relative_path
        if not path.exists():
            missing.append(str(path))
    from tools.workspace_intake_tools.channel_validator import _extract_channels
    registry = root / 'analysis/channel-operation-registry.md'
    available = _extract_channels(registry.read_text()) if registry.is_file() else set()
    return missing, [channel for channel in target_channels if channel not in available]
