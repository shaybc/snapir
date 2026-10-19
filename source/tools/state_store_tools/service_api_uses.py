"""Pin published service contracts inside the existing conversion-run database."""

import json

from models.converted_service_contract import ConvertedServiceContract
from models.service_api_use import ServiceApiUse


def initialize_service_uses(conn):
    """Add API-use records to run state without opening another database."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='converted_operation_services'").fetchone():
        raise ValueError("Run API-use records must be separate from the shared registry")
    conn.execute("""CREATE TABLE IF NOT EXISTS service_api_uses (
        run_id TEXT NOT NULL, application_id TEXT NOT NULL, channel TEXT NOT NULL,
        operation_id TEXT NOT NULL, use_json TEXT NOT NULL,
        PRIMARY KEY(run_id,application_id,channel,operation_id))""")


def record_service_use(conn, run_id, contract, environment):
    """Commit an immutable run binding to an API revision and its selected environment.

    The contract comes from shared-registry lookup. Repeated saves are idempotent;
    a different revision/address requires an explicit revised plan, not overwrite.
    """
    if isinstance(contract, ConvertedServiceContract):
        contract = contract.model_dump(mode="json")
    contract = ConvertedServiceContract.model_validate(contract)
    if environment not in contract.addresses:
        raise ValueError("Published service has no address for environment: " + environment)
    use = ServiceApiUse(run_id=run_id, environment=environment, contract=contract,
                        address=contract.addresses[environment])
    initialize_service_uses(conn)
    key = (use.run_id, contract.application_id, contract.channel, contract.operation_id)
    payload = json.dumps(use.model_dump(mode="json"), sort_keys=True)
    with conn:
        conn.execute("INSERT OR IGNORE INTO service_api_uses VALUES (?,?,?,?,?)", (*key, payload))
        saved = conn.execute("""SELECT use_json FROM service_api_uses
            WHERE run_id=? AND application_id=? AND channel=? AND operation_id=?""", key).fetchone()[0]
        if saved != payload:
            raise ValueError("Run already uses another API contract/address; revise its approved plan explicitly")
    return ServiceApiUse.model_validate_json(saved)


def get_service_use(conn, run_id, application_id, channel, operation_id):
    """Return the saved run binding without consulting or revalidating the service."""
    initialize_service_uses(conn)
    row = conn.execute("""SELECT use_json FROM service_api_uses
        WHERE run_id=? AND application_id=? AND channel=? AND operation_id=?""",
        (run_id, application_id, channel, operation_id)).fetchone()
    return ServiceApiUse.model_validate_json(row[0]) if row else None


def list_service_uses(conn, run_id):
    """Read this run's saved API-use records in a deterministic identity order."""
    initialize_service_uses(conn)
    rows = conn.execute("SELECT use_json FROM service_api_uses WHERE run_id=? ORDER BY application_id,channel,operation_id", (run_id,))
    return [ServiceApiUse.model_validate_json(row[0]) for row in rows]
