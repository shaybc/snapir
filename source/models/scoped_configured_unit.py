"""Configured native-unit inputs bound to one qualified execution occurrence."""

from models.behavior_unit import BehaviorUnitInput


class ScopedConfiguredUnit(BehaviorUnitInput):
    """Keep business labels while distinguishing configurations and source analysis."""

    operation_identity: str
    occurrence_id: str
    source_definition_id: str
    effective_configuration: dict
