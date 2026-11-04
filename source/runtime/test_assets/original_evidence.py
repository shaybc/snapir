"""Supply complete original format dependencies to AI-owned fixture preparation."""
from models.composer_unit_specification import ComposerUnitSpecification
from runtime.composer_units.discovery import discover
from runtime.java_toolchain import java_scope


def complete_format_evidence(payload,configured,profile,direction):
    """Reuse automatic source discovery without executing code or modifying saved units."""
    with java_scope(profile):
        resolved,discovery=discover(ComposerUnitSpecification(unit=configured,action=direction),profile)
    return dict(payload,sources=resolved['sources'],comparison_dependency_discovery=discovery)
