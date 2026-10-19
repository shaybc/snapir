"""Publish and look up completed service contracts independently of conversion runs."""

import json
from pathlib import Path

from models.converted_service_contract import ConvertedServiceContract
from tools.state_store_tools._json import utc_now
from tools.state_store_tools.db import get_connection


def initialize_registry(conn):
    """Create only the shared registry table; reject a conversion-run database."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name IN ('runs','service_api_uses')").fetchone():
        raise ValueError("The shared service registry must be separate from a run database")
    conn.execute("""CREATE TABLE IF NOT EXISTS converted_operation_services (
        application_id TEXT NOT NULL, channel TEXT NOT NULL, operation_id TEXT NOT NULL,
        api_revision TEXT NOT NULL, contract_json TEXT NOT NULL, published_at TEXT NOT NULL,
        PRIMARY KEY(application_id,channel,operation_id,api_revision))""")


def open_registry(database_path):
    """Open/create a shared SQLite registry and its parent; close on setup failure."""
    path = Path(database_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(str(path))
    try:
        initialize_registry(conn)
        conn.commit()
    except Exception:
        conn.close()
        raise
    return conn


def publish_service(conn, contract):
    """Commit a complete service record idempotently; reject a changed saved revision.

    The publishing converter supplies completion evidence. This function checks
    its schema, not the target service again, and performs no network/model calls.
    """
    if isinstance(contract, ConvertedServiceContract):
        contract = contract.model_dump(mode="json")
    contract = ConvertedServiceContract.model_validate(contract)
    initialize_registry(conn)
    key = (contract.application_id, contract.channel, contract.operation_id, contract.api_revision)
    payload = json.dumps(contract.model_dump(mode="json"), sort_keys=True)
    with conn:
        conn.execute("INSERT OR IGNORE INTO converted_operation_services VALUES (?,?,?,?,?,?)",
                     (*key, payload, utc_now()))
        saved = conn.execute("""SELECT contract_json FROM converted_operation_services
            WHERE application_id=? AND channel=? AND operation_id=? AND api_revision=?""", key).fetchone()[0]
        if saved != payload:
            raise ValueError("Published service revisions are immutable; use a new api_revision")
    return ConvertedServiceContract.model_validate_json(saved)


def get_service(conn, application_id, channel, operation_id, *, api_revision=None):
    """Read a published API revision, or the most recently published revision.

    A caller can pin the returned revision in run state. Lookup does not contact
    the service, read its source files or repeat conversion validation.
    """
    initialize_registry(conn)
    sql = "SELECT contract_json FROM converted_operation_services WHERE application_id=? AND channel=? AND operation_id=?"
    values = [application_id, channel, operation_id]
    if api_revision is not None:
        sql += " AND api_revision=?"
        values.append(api_revision)
    row = conn.execute(sql + " ORDER BY published_at DESC,rowid DESC LIMIT 1", values).fetchone()
    return ConvertedServiceContract.model_validate_json(row[0]) if row else None


def list_services(conn, application_id, *, channel=None):
    """List published revisions for one application, optionally restricted by channel."""
    initialize_registry(conn)
    sql = "SELECT contract_json FROM converted_operation_services WHERE application_id=?"
    values = [application_id]
    if channel is not None:
        sql += " AND channel=?"
        values.append(channel)
    rows = conn.execute(sql + " ORDER BY channel,operation_id,published_at,rowid", values)
    return [ConvertedServiceContract.model_validate_json(row[0]) for row in rows]
