"""Read existing Mapper evidence without editing historical runs or inventing source behavior."""
import json
import sqlite3
from pathlib import Path
from models.common_models.common import RunConfig
from tools.behavior_verification.thin_path_request import OPERATION,select_units
from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
from tools.conversion_tools.behavior_evidence_freshness import verify_configuration_sources


def load_trial_inputs(directory):
    """Return the three exact configured units and a source/configuration freshness check."""
    preparation=json.loads(next((directory/'reports').rglob('scoped_workflow_preparation.json')).read_text(encoding='utf-8'))
    units=select_units(preparation)
    database=directory/'state/migration.db'
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as conn:
        row=conn.execute('SELECT run_config_json FROM runs WHERE run_id=?',(preparation['run_id'],)).fetchone()
    config=RunConfig.model_validate_json(row[0])
    origins={item.get('definition_id'):item for item in preparation['operations'][OPERATION]['behavior_request']['java_origins']}
    def fresh():
        with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as conn:
            conn.row_factory=sqlite3.Row
            verify_configuration_sources(conn,config,'GetClientLinksOp','INTERNET')
        for unit in units:
            for source in unit['sources']:
                origin=origins.get(source['identity'])
                if (not origin or origin['status']!='verified_source' or origin['source_hash']!=source['content_hash']
                    or file_digest(Path(origin['source_file']))!=source['content_hash']
                    or Path(origin['source_file']).read_text(encoding='utf-8-sig')!=source['content']):
                    raise ValueError('Original source evidence changed: '+source['identity'])
    fresh()
    return preparation,units,fresh
