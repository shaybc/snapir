"""Discover and resolve Java sources across a legacy workspace."""

from tools.source_discovery_tools.discovery import discover_java_sources
from tools.source_discovery_tools.resolver import resolve_indexed_source

__all__ = ["discover_java_sources", "resolve_indexed_source"]
