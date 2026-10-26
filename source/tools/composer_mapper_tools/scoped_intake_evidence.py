"""Snapshot channel mappings and configured origin evidence without claiming classpath proof."""

import hashlib
import time
from datetime import datetime
from pathlib import Path

from tools.composer_mapper_tools.frontmatter_parser import parse_frontmatter


def validation_progress(callback=None):
    """Report bounded validation progress before the inventory transaction starts."""
    started, last = time.monotonic(), 0.0

    def report(message):
        nonlocal last
        now = time.monotonic()
        if not last or now - last >= 5 or 'effective operations' in message:
            (callback or print)(f'[{datetime.now().astimezone().isoformat(timespec="seconds")}] '
                                f'{message} | elapsed={now - started:.1f}s')
            last = now

    return report


def file_digest(path):
    """Hash a file with bounded buffering, including enterprise-size manifests."""
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def intake_evidence(root, manifest, config):
    """Snapshot channel notes and safe origin settings; source relocation remains unverified."""
    channels = {}
    for path in sorted((root / 'channels').glob('*/channel.md')):
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Unsafe scoped channel note: ' + str(path))
        text = path.read_text(encoding='utf-8-sig')
        channel = str(parse_frontmatter(text).get('channel', ''))
        if not channel or channel in channels:
            raise ValueError('Missing or duplicate scoped channel identity: ' + str(path))
        channels[channel] = dict(note=path.relative_to(root).as_posix(),
                                 note_hash=file_digest(path), markdown=text)
    missing = set(manifest.get('channels', [])) - channels.keys()
    if missing:
        raise ValueError('Missing channel mapping evidence: ' + ', '.join(sorted(missing)))
    settings = {}
    env_file = getattr(config, 'env_file', None)
    if env_file and not Path(env_file).is_file():
        raise ValueError('Missing intake configuration evidence: ' + env_file)
    from tools.workspace_intake_tools.env_loader import load_env_with_fallbacks
    values = load_env_with_fallbacks(env_file)
    for key in ('SOURCE_WORKSPACE_ID', 'CLASSPATH_JARS', 'ECLIPSE_CLASSPATH_VARIABLES',
                'MAVEN_SETTINGS_PATH', 'MAVEN_LOCAL_REPOSITORY'):
        settings[key] = values.get(key)
    from tools.conversion_tools.scoped_reuse.evidence import source_layout
    return dict(workspace_id=manifest['workspace_id'], vault_root=str(root.resolve()),
                source_layout=source_layout(getattr(config, 'source_root', None)),
                source_root=str(getattr(config, 'source_root', '')), origin_settings=settings,
                source_origin_status='unverified; conversion requires source revision and classpath proof',
                target_channels=config.target_channels, run_mode=config.run_mode.value,
                include_operations=config.include_operations, exclude_operations=config.exclude_operations,
                channels=channels, diagnostics=manifest.get('diagnostics', []))
