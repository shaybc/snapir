"""Keep configured Composer behavior and operation consumers separate from Java identity."""

from pydantic import BaseModel, ConfigDict, Field
from models.source_component_identity import SourceImplementationRecord
from models.java_source_dependencies import JavaSourceDependencyGraph


class ConfiguredComponentDefinition(BaseModel):
    """Preserve one original configured definition, including currently unused definitions."""

    definition_id: str
    component_kind: str
    channel: str | None = None
    source_path: str
    selector: str
    logical_id: str | None = None
    configuration_hash: str
    configuration_xml: str
    implementation_id: str | None = None
    resolution_issue: str | None = None


class ConfiguredComponentUse(BaseModel):
    """Record one XML-node use by one original operation definition."""

    model_config = ConfigDict(extra="forbid")
    use_id: str
    definition_id: str
    operation_key: str
    operation_id: str
    channel: str | None = None
    component_kind: str
    definition_path: str
    definition_selector: str
    configuration_hash: str
    configuration_xml: str
    implementation_id: str | None = None
    mapping_source: str | None = None
    referenced_by: str
    resolution_issue: str | None = None


class ComponentInventory(BaseModel):
    """Capture full-workspace source identity and usage evidence, including limitations."""

    workspace_id: str
    implementations: list[SourceImplementationRecord] = Field(default_factory=list)
    definitions: list[ConfiguredComponentDefinition] = Field(default_factory=list)
    uses: list[ConfiguredComponentUse] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    java_dependencies: JavaSourceDependencyGraph = Field(default_factory=JavaSourceDependencyGraph)
    analysis_scope: str = "Composer XML references and statically identified Java source dependencies"
