"""Read channels and operation identities from a legacy Composer workspace."""

import os
from pathlib import Path
import xml.etree.ElementTree as ET


def discover_channel_directories(source_root: Path) -> dict[str, list[Path]]:
    """Find Channel/<name> directories, excluding build and dependency folders."""
    channels: dict[str, list[Path]] = {}
    excluded = {".git", ".venv", "node_modules", "target", "__pycache__", "generated"}
    for folder, directories, _ in os.walk(source_root):
        directories[:] = [name for name in directories if name not in excluded]
        if Path(folder).name.lower() == "channel":
            for name in sorted(directories):
                channels.setdefault(name, []).append(Path(folder) / name)
    return dict(sorted(channels.items()))


def discover_operations(channel_directories: dict[str, list[Path]], selected_channels: list[str]) -> list[str]:
    """Return distinct operation IDs defined within the selected channels."""
    operations = set()
    for channel in selected_channels:
        for directory in channel_directories[channel]:
            for definition in sorted(directory.rglob("*")):
                if not definition.is_file() or definition.suffix.lower() != ".xml":
                    continue
                try:
                    document = ET.parse(definition)
                except ET.ParseError as exc:
                    raise ValueError(f"Cannot read Composer definition {definition}: {exc}") from exc
                for element in document.iter():
                    if element.tag.rsplit("}", 1)[-1] == "CCDSEServerOperation" and element.get("id"):
                        operations.add(element.get("id"))
    return sorted(operations)
