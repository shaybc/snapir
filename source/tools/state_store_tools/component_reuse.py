"""Pin selected shared component revisions in the consuming run and its portable lock file."""
import json
from pathlib import Path


def record_component_use(conn, run_id, output_root, key, manifest, *, group_id=None, decision='reused'):
    """Persist an immutable dependency selection; changed pins require an explicit new plan."""
    conn.execute('CREATE TABLE IF NOT EXISTS shared_component_uses (run_id TEXT, component_key TEXT, revision TEXT, manifest_json TEXT, PRIMARY KEY(run_id,component_key))')
    payload = json.dumps(manifest, sort_keys=True)
    old = conn.execute('SELECT revision FROM shared_component_uses WHERE run_id=? AND component_key=?', (run_id, key)).fetchone()
    if old and old[0] != manifest['revision']:
        raise ValueError('Run already pins another shared component revision: ' + key)
    with conn:
        conn.execute('CREATE TABLE IF NOT EXISTS shared_component_decisions (run_id TEXT, component_key TEXT, decision TEXT, PRIMARY KEY(run_id,component_key))')
        conn.execute('INSERT OR REPLACE INTO shared_component_decisions VALUES (?,?,?)', (run_id, key, decision))
        conn.execute('INSERT OR IGNORE INTO shared_component_uses VALUES (?,?,?,?)', (run_id, key, manifest['revision'], payload))
        conn.execute('CREATE TABLE IF NOT EXISTS shared_component_bindings (run_id TEXT, group_id TEXT, component_key TEXT, PRIMARY KEY(run_id,group_id))')
        if group_id:
            conn.execute('INSERT OR REPLACE INTO shared_component_bindings VALUES (?,?,?)', (run_id, group_id, key))
    write_dependency_lock(conn, run_id, output_root)


def write_dependency_lock(conn, run_id, output_root):
    """Write selected components without embedding absolute shared-store paths."""
    rows = conn.execute('SELECT component_key,revision,manifest_json FROM shared_component_uses WHERE run_id=? ORDER BY component_key', (run_id,)).fetchall()
    path = Path(output_root) / 'dependencies.lock.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(schema_version=1, components=[dict(key=row[0], revision=row[1], manifest=json.loads(row[2])) for row in rows])
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(path)


def group_uses(conn, run_id):
    """Return selected manifests indexed by the current plan's group identities."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='shared_component_bindings'").fetchone():
        return {}
    return {row[0]: json.loads(row[1]) for row in conn.execute(
        'SELECT b.group_id,u.manifest_json FROM shared_component_bindings b JOIN shared_component_uses u ON u.run_id=b.run_id AND u.component_key=b.component_key WHERE b.run_id=?', (run_id,))}


def record_consumers(conn, run_id, plan, units, *, source_root=None):
    """Preserve proven global unit consumers for the existing library threshold decisions."""
    from runtime.component_conversion.shared_consumers import original_consumers
    global_uses = original_consumers(conn, run_id, plan, source_root)
    with conn:
        conn.execute('CREATE TABLE IF NOT EXISTS shared_component_consumers (run_id TEXT, group_id TEXT, consumers_json TEXT, PRIMARY KEY(run_id,group_id))')
        for group in plan.groups:
            consumers = {name for member in group.members for name in plan.components[member].operations}
            for member in group.members:
                consumers.update(global_uses.get(member, set()))
                for identity in plan.components[member].unit_ids:
                    consumers.update(units.get(identity, {}).get('consumers', []))
            conn.execute('INSERT OR REPLACE INTO shared_component_consumers VALUES (?,?,?)',
                         (run_id, group.group_id, json.dumps(sorted(consumers))))
