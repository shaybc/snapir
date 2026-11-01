"""A proposed native interface for one source-bound conversion component."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from models.operation_data_contract import NativeApiContract


class NativeComponentContract(BaseModel):
    """Registration freezes a revision for consumers; it does not prove implementation behavior."""
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['native-component-contract-v1'] = 'native-component-contract-v1'
    component_id: str = Field(min_length=1)
    apis: list[NativeApiContract] = Field(min_length=1)
    source_entry_points: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    dependencies: list[str] = Field(default_factory=list)
    configuration_mode: Literal['specialized','parameterized'] = 'specialized'
    configuration_parameters: dict[str,str] = Field(default_factory=dict)
    runtime_inputs: dict[str,str] = Field(default_factory=dict)
    initialization: list[str] = Field(default_factory=list)
    observable_effects: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    unit_acceptance_enabled: Literal[False] = False

    @model_validator(mode='after')
    def require_distinct_interfaces(self):
        """Reject empty/duplicate declarations before freezing an interface revision."""
        names=[api.type_name for api in self.apis]
        if any(not name.strip() for name in names) or len(names)!=len(set(names)):
            raise ValueError('Component API types must be nonempty and distinct')
        if not any(api.method_signatures for api in self.apis):
            raise ValueError('Component contract must declare a native method')
        for values in (self.source_entry_points,self.evidence_ids,self.dependencies):
            if any(not value.strip() for value in values) or len(values)!=len(set(values)):
                raise ValueError('Component entry points, evidence and dependencies must be distinct')
        return self
