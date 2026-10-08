"""Normalize Composer reference sentinels without altering literal field data."""


def reference_value(value):
    """Treat empty and nil references as absent."""
    return None if value is None or value.strip().lower() in {"", "nil"} else value
