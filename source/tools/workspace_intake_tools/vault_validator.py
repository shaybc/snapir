from __future__ import annotations

from pathlib import Path


REQUIRED_VAULT_PATHS = [
    "analysis",
    "analysis/channel-operation-registry.md",
]


def validate_vault_structure(vault_root: str) -> list[str]:
    return validate_vault_input(vault_root, [])[0]


def validate_vault_input(vault_root: str, target_channels: list[str]) -> tuple[list[str], list[str]]:
    """Validate notes once and check requested execution channels without a legacy registry."""
    root = Path(vault_root)
    missing: list[str] = []
    if not root.exists():
        return [vault_root], list(target_channels)
    from tools.composer_mapper_tools.vault_manifest import read_vault_manifest
    manifest = read_vault_manifest(root, retain_inventory=False, allow_shared=True)
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
