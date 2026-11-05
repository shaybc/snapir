"""Represent inventory sequences that live on disk instead of in Pydantic lists."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StoredJavaDependencyGraph:
    """Keep the ordinary graph fields while large collections are lazy database sequences."""

    dependencies: Any = field(default_factory=list)
    uses: Any = field(default_factory=list)
    issues: Any = field(default_factory=list)
    analysis_scope: str = 'Static source-type references; reflection, overload resolution and runtime dispatch are not proven'


@dataclass
class StoredComponentInventory:
    """Expose the existing inventory contract without materializing its collection fields."""

    workspace_id: str
    implementations: Any = field(default_factory=list)
    definitions: Any = field(default_factory=list)
    uses: Any = field(default_factory=list)
    diagnostics: Any = field(default_factory=list)
    java_dependencies: Any = field(default_factory=StoredJavaDependencyGraph)
    analysis_scope: str = 'Composer XML references and statically identified Java source dependencies'
