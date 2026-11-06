"""Pin a run to an immutable map revision and its original analysis policy."""

from pathlib import Path
import json


def pin_map(conn, config, analysis):
    """Reject evidence replacement on resume; stage publication is owned by the caller."""
    conn.execute('''CREATE TABLE IF NOT EXISTS map_analysis_snapshot(run_id TEXT PRIMARY KEY,
        map_root TEXT,descriptor_hash TEXT,analysis_hash TEXT,workspace_id TEXT,selection TEXT)''')
    selection = json.dumps(dict(channels=config.target_channels,include=config.include_operations,exclude=config.exclude_operations),sort_keys=True)
    evidence = (str(analysis.root),analysis.manifest_hash,analysis['analysis_hash'],analysis['workspace_id'],selection)
    previous = conn.execute('SELECT map_root,descriptor_hash,analysis_hash,workspace_id,selection FROM map_analysis_snapshot WHERE run_id=?', (config.run_id,)).fetchone()
    if previous is not None and tuple(previous) != evidence:
        raise ValueError('Pinned Composer map revision or selection changed; start a fresh intake')
    conn.execute('INSERT OR IGNORE INTO map_analysis_snapshot VALUES (?,?,?,?,?,?)', (config.run_id,*evidence))


def mapped_layout(mapped):
    """Represent membership/registry proof by the verified immutable analysis revision."""
    return dict(status='captured',source_root=str(mapped.workspace),analysis_hash=mapped.analysis['analysis_hash'],
                registries={},documents={},projects={})


def validation_receipt(output_root,map_root):
    """Keep immutable-generation validation receipts outside the readonly input map."""
    import hashlib
    key=hashlib.sha256(str(Path(map_root).resolve()).encode()).hexdigest()
    return Path(output_root)/'.map-validation'/(key+'.json')
