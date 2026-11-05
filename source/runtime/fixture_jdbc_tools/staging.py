"""Atomic copy of already built converter tools; operation fixture data is never copied."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from runtime.fixture_jdbc_tools.releases import canonical, digest, locate_release, verify_directory


def stage_release(bundle_id, destination, store=None):
    """Copy exact tools and return a trusted binding for later demo integration."""
    source, release = locate_release(bundle_id, store)
    target = Path(destination).resolve()
    source = source.resolve()
    if target == source or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError('Staging must be separate from the converter tool release')
    manifest_hash = digest(release.model_dump(mode='json'))
    if target.exists():
        verify_directory(target, bundle_id, manifest_hash)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix='.fixture-tools-', dir=target.parent))
        try:
            shutil.copytree(source, temporary, dirs_exist_ok=True)
            verify_directory(temporary, bundle_id, manifest_hash)
            try:
                os.rename(temporary, target)
            except OSError:
                if not target.exists():
                    raise
                verify_directory(target, bundle_id, manifest_hash)
        finally:
            if temporary.exists():
                if temporary.resolve().parent != target.parent.resolve() or not temporary.name.startswith('.fixture-tools-'):
                    raise ValueError('Temporary tool cleanup escaped its staging directory')
                shutil.rmtree(temporary)
    return dict(bundle_id=bundle_id, manifest_hash=manifest_hash, root=str(target),
        driver_jar='jdbc/fixture-jdbc-driver.jar', server_jar='server/fixture-server.jar',
        driver_class=release.driver_class, minimum_java=release.minimum_java,
        protocol_major=release.protocol_major, fixture_schemas=release.fixture_schemas)
