from __future__ import annotations

import sqlite3

from tools.state_store_tools.db import create_all_tables, get_connection, reconcile_on_startup


def initialize_database(db_path: str, run_id: str) -> sqlite3.Connection:
    conn = get_connection(db_path)
    create_all_tables(conn)
    reconcile_on_startup(conn, run_id)
    return conn
