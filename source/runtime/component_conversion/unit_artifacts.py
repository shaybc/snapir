"""Check transitive component evidence before whole-unit promotion or downstream packaging."""
import json
from pathlib import Path
from models.native_component_result import NativeComponentResult
from tools.state_store_tools import component_records as records
from tools.state_store_tools.behavior_units import snapshot, save
from tools.state_store_tools.conversion_components import reuse_component_result
from tools.conversion_tools.component_identity import checked_plan, component_group, external_group
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def load_unit_artifacts(conn, config, profile, plan, unit_id):
    """Verify original sources, every transitive revision and artifact hash without AI calls."""
    root = plan.unit_roots[unit_id]
    output = Path(config.output_root) / 'components'
    result = reuse_component_result(conn, config.run_id, plan, root, profile, output, validator=lambda *args: True)
    if result is None:
        raise ValueError('Configured unit root is not component_validated: ' + unit_id)
    group = component_group(plan, root)
    groups = {item.group_id:item for item in plan.groups}
    pending, needed = [group.group_id], set()
    while pending:
        key = pending.pop()
        if key in needed:
            continue
        needed.add(key)
        pending.extend(groups[key].dependencies)
    heads, reports, contracts = {}, {}, {}
    for item in plan.groups:
        if item.group_id not in needed:
            continue
        head = records.head(conn, config.run_id, item.group_id)
        heads[item.group_id] = head
        if head['status'] != 'component_validated' or external_group(plan, item):
            continue
        contract = records.read_record(conn, config.run_id, item.group_id, 'contract', head['contract_revision'])
        data = records.read_record(conn, config.run_id, item.group_id, 'result', head['result_revision'])
        contracts.update(contract['contracts'])
        for key, value in data['results'].items():
            artifact = NativeComponentResult.model_validate(value)
            reports[key] = json.loads((Path(artifact.artifact_root) / artifact.validation_report).read_text(encoding='utf-8'))
    # The root already retains the precise complete production tree and executed root tests.
    files = {name:(Path(result.artifact_root)/name).read_text(encoding='utf-8')
        for name in result.files if name.startswith(('src/main/java/', 'src/test/java/')) and name.endswith('.java')}
    from runtime.test_assets.component_assets import restore_component_assets
    assets=restore_component_assets(result.artifact_root,reports[root],files)
    proof = dict(version='component-unit-v1', unit_id=unit_id, root=root,
        plan_fingerprint=plan.fingerprint, heads=heads, files=digest(files),
        test_asset_manifest=assets['manifest_hash'] if assets else None,
        allowed_ibm_classes=sorted(profile.allowed_ibm_classes),
        partition_records=reports[root].get('format_partition_records', []))
    require_partition_records(conn, config, group.group_id, proof['partition_records'])
    from runtime.component_conversion.shared_dependencies import attach_shared_components
    files, root_report, shared = attach_shared_components(conn, config, profile, plan, needed, files, reports[root])
    proof['shared_components'] = shared
    return dict(proof=proof, root_report=root_report, reports=reports, contract=contracts[root], files=files,test_assets=assets)


def save_unit_component_receipt(conn, config, artifacts, candidate_hash):
    """Bind final unit output to current component revisions independently of component progress."""
    proof = dict(artifacts['proof'], candidate_hash=candidate_hash)
    save(conn, config.run_id, 'unit_components', proof['unit_id'], digest(proof), proof)
    return digest(proof)


def require_unit_components(conn, config, unit_id, candidate_hash, *, revision=None):
    """Packaging/resume rejects changed dependency bytes or heads, even if unit XML is unchanged."""
    row = snapshot(conn, config.run_id, 'unit_components', unit_id)
    if row is None or row['status'] != 'accepted':
        raise ValueError('Unit component receipt is missing: ' + unit_id)
    proof = json.loads(row['data_json'])
    if row['fingerprint'] != digest(proof) or revision is not None and revision != row['fingerprint'] or proof['candidate_hash'] != candidate_hash:
        raise ValueError('Unit component acceptance receipt changed')
    registered = conn.execute('SELECT plan_json FROM conversion_component_plans WHERE run_id=?', (config.run_id,)).fetchone()
    if registered is None:
        raise ValueError('Unit component plan is missing')
    plan = checked_plan(json.loads(registered['plan_json']))
    if plan.unit_roots.get(unit_id) != proof['root']:
        raise ValueError('Unit component plan changed')
    for key, head in proof['heads'].items():
        if records.head(conn, config.run_id, key) != head:
            raise ValueError('Unit component dependency revision changed: ' + key)
    # Reading immutable proof never authorizes a new generation task.
    from types import SimpleNamespace
    from tools.state_store_tools.conversion_components import _verify_results
    from tools.behavior_verification.component_artifacts import verify_original_sources
    for group in plan.groups:
        if group.group_id in proof['heads']:
            verify_original_sources(plan, group)
    # _verify_results checks reports/compiled files/configuration and transitive revisions.
    _verify_results(conn, config.run_id, plan, component_group(plan, proof['root']).group_id,
        SimpleNamespace(allowed_ibm_classes=proof['allowed_ibm_classes']), Path(config.output_root)/'components', lambda *args: True)
    require_partition_records(conn, config, component_group(plan, proof['root']).group_id, proof.get('partition_records', []))
    return proof


def require_partition_records(conn, config, group_id, identities):
    """Include CF6 part artifact receipts in transitive checks, not just copied root sources."""
    from runtime.behavior_conversion.bundle_output import verify_manifest
    folder = (Path(config.output_root)/'components/format-parts'/group_id).resolve()
    for identity in identities:
        if len(identity) != 64 or any(character not in '0123456789abcdef' for character in identity):
            raise ValueError('Invalid subtree receipt identity')
        row = snapshot(conn, config.run_id, 'format_subtree_artifact', identity)
        if row is None or row['status'] != 'component_validated':
            raise ValueError('Subtree artifact receipt is unavailable')
        record = json.loads(row['data_json'])
        receipt = folder/(identity+'.json')
        if digest(record) != row['fingerprint'] or not receipt.is_file() or json.loads(receipt.read_text(encoding='utf-8')) != record:
            raise ValueError('Subtree artifact receipt changed')
        root = (folder/record['artifact']).resolve()
        if root.parent != folder:
            raise ValueError('Subtree artifact escaped its root')
        verify_manifest(root, record['manifest'])
