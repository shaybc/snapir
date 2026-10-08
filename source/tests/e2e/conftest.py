from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.state_store_tools.db import create_all_tables, get_connection


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def e2e_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


@pytest.fixture
def mock_llm():
    responses = json.loads((FIXTURES / "mock_llm_responses" / "default.json").read_text(encoding="utf-8"))

    def respond(prompt_name: str):
        return responses[prompt_name]

    return respond
