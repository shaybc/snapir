"""Persist small run identity and resume activity records independently of source inventories."""

import json
from pathlib import Path

from tools.state_store_tools._json import utc_now


def _write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def _selection(values):
    names = values or []
    return ', '.join(names[:3]) + (f' (+{len(names) - 3} more)' if len(names) > 3 else '')


def write_run_identity(directory, profile, configuration_path=None):
    """Save creation provenance before intake; direct API calls have no YAML origin."""
    configuration = Path(configuration_path).resolve() if configuration_path else None
    _write(directory / 'state/run_identity.json', dict(
        run_id=directory.name,
        configuration_name=configuration.stem if configuration else 'Direct profile',
        configuration_path=str(configuration) if configuration else None,
        created_at=utc_now(),
        channels=_selection(profile.channels),
        operations=_selection(profile.include_operations) or 'All operations',
        conversion_strategy=profile.conversion_strategy,
    ))


def record_resume_started(directory):
    """Record actual resume entry without changing the checkpoint or gate decisions."""
    _write(directory / 'state/run_activity.json', dict(last_resumed_at=utc_now()))
