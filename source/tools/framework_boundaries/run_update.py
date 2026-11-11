"""Apply a framework-only saved-profile update without changing imported evidence or progress."""
import json
import os
import sqlite3
from uuid import uuid4
from pathlib import Path
import yaml
from models.pipeline_configuration import PipelineConfiguration
from tools.framework_boundaries.inventory import scan
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def update_run(directory, configuration):
    """Validate archives first, then persist an audited profile revision; never invoke intake."""
    directory = Path(directory)
    path = Path(configuration).resolve()
    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    except yaml.YAMLError as error:
        raise ValueError('Invalid framework configuration YAML') from error
    if not isinstance(data, dict) or set(data) != {'framework_jars'}:
        raise ValueError('Framework update accepts only framework_jars; other saved settings cannot change')
    selected = PipelineConfiguration.model_validate(dict(framework_jars=data['framework_jars'])).framework_jars
    selected = list(dict.fromkeys(str((path.parent / value).resolve()) for value in selected))
    inventory = scan(selected)
    profile_path = directory / 'state/profile.json'
    if not (directory / 'state/migration.db').is_file():
        raise ValueError('Run database does not exist')
    with sqlite3.connect(directory / 'state/migration.db') as conn:
        conn.execute('BEGIN IMMEDIATE')
        previous = profile_path.read_bytes()
        profile = PipelineConfiguration.model_validate_json(previous)
        effective = profile.model_copy(update={'framework_jars': selected})
        row = conn.execute('SELECT status FROM runs WHERE run_id=?', (directory.name,)).fetchone()
        if row is None: raise ValueError('Run does not exist')
        if row[0] == 'in_progress': raise ValueError('Stop the active run before updating framework configuration')
        conn.execute('CREATE TABLE IF NOT EXISTS framework_boundary_updates (run_id TEXT, revision TEXT, record_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(run_id,revision))')
        latest = conn.execute('SELECT record_json FROM framework_boundary_updates WHERE run_id=? ORDER BY rowid DESC LIMIT 1', (directory.name,)).fetchone()
        if latest and profile.framework_jars == selected and json.loads(latest[0]).get('inventory') == inventory:
            return profile
        record = dict(previous_framework_jars=profile.framework_jars, framework_jars=selected,
            inventory=inventory, packages=sorted({name.rsplit('.', 1)[0] for name in inventory if '.' in name}),
            policy='framework-binary-v1')
        revision = digest(record)
        conn.execute('INSERT OR IGNORE INTO framework_boundary_updates(run_id,revision,record_json) VALUES(?,?,?)',
            (directory.name, revision, json.dumps(record, sort_keys=True)))
        # Inherit the run directory ACL; private temporary-file ACLs can break later Windows resumes.
        temporary = profile_path.parent / ('framework-profile-' + uuid4().hex + '.json')
        try:
            with temporary.open('x', encoding='utf-8') as stream:
                stream.write(effective.model_dump_json(indent=2))
            os.replace(temporary, profile_path)
            try: conn.commit()
            except BaseException:
                profile_path.write_bytes(previous)
                raise
        finally:
            if Path(temporary).exists(): Path(temporary).unlink()
    return effective
