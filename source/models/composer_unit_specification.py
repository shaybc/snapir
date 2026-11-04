"""Select an original Composer format/decorator without conversion authority."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from models.boundary_harness_binding import BoundaryHarnessBinding


class ComposerUnitSpecification(BaseModel):
    """The resolved XML tree is an input; source lists are discovered, never required."""
    model_config=ConfigDict(extra='forbid')
    kind: Literal['format','decorator']='format'
    action: Literal['format','unformat','decorate','undecorate','format_attributes']='format'
    unit: dict
    framework: BoundaryHarnessBinding=Field(default_factory=lambda:BoundaryHarnessBinding(adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'))
    max_sources: int=Field(default=5000,ge=1)
    max_source_bytes: int=Field(default=50000000,ge=1)
    input_types: list[str]=Field(default_factory=list)

    @model_validator(mode='after')
    def scope(self):
        if self.kind=='format' and self.action not in {'format','unformat'}:raise ValueError('Format action required')
        if self.kind=='decorator' and self.action not in {'decorate','undecorate','format_attributes'}:raise ValueError('Decorator action required')
        if self.unit.get('kind')=='configured_step':raise ValueError('Operation steps are outside Composer unit preparation')
        if not isinstance(self.unit.get('effective_configuration'),dict):raise ValueError('A resolved configuration tree is required')
        def configuration(node,depth=0):
            if depth>64 or not isinstance(node,dict) or not isinstance(node.get('attributes',{}),dict):raise ValueError('Invalid original configuration node')
            for field in ['children','decorators']:
                if not isinstance(node.get(field,[]),list):raise ValueError('Configuration children/decorators must be lists')
                for child in node.get(field,[]):configuration(child,depth+1)
        configuration(self.unit['effective_configuration'])
        if not isinstance(self.unit.get('referenced_definitions',[]),list):raise ValueError('Referenced definitions must be a list')
        for node in self.unit.get('referenced_definitions',[]):configuration(node)
        if self.framework.sources or self.framework.native_entry or self.framework.external_bindings:raise ValueError('Framework bindings cannot inject implementation or replay overrides')
        return self
