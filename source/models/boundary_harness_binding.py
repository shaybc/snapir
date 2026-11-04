"""Explicit framework/API bridges, never inferred business behavior."""
from pydantic import BaseModel, ConfigDict, Field
from models.native_unit_bundle import NativeSourceFile
from models.native_verification_binding import NativeVerificationBinding


class BoundaryHarnessBinding(BaseModel):
    """Declare framework APIs and native boundary sources without inventing behavior."""
    model_config = ConfigDict(extra='forbid')
    adapter_class: str
    sources: list[NativeSourceFile] = Field(default_factory=list)
    context_class: str = 'com.ibm.dse.base.Context'
    tag_class: str = 'com.ibm.dse.base.Tag'
    context_writer: str = 'setValueAt'
    context_remover: str = 'removeValueAt'
    context_reader: str = 'getValueAt'
    context_snapshot: str = 'snapshot'
    step_context_setter: str = 'setContext'
    external_bindings: dict[str, str] = Field(default_factory=dict)
    settings_bindings: dict[str, dict[str, str]] = Field(default_factory=dict)
    classpath: list[str] = Field(default_factory=list)
    native_entry: NativeVerificationBinding | None = None
    original_action: str | None = Field(default=None,exclude_if=lambda value:value is None)
    original_context_getters: dict[str,list[str]] = Field(default_factory=dict,exclude_if=lambda value:not value)
    original_output_getters: list[str] = Field(default_factory=list,exclude_if=lambda value:not value)

