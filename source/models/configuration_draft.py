"""Transient configuration answers; drafts never create persistent run or config state."""

from dataclasses import dataclass, field


@dataclass
class ConfigurationDraft:
    """Keep committed section data, prompt defaults and discovery results while editing."""

    sections: dict = field(default_factory=dict)
    answers: dict = field(default_factory=dict)
    discovery: dict = field(default_factory=dict)
    section: int = 0
    review_return: bool = False
    dirty: set = field(default_factory=set)

    def values(self):
        """Merge committed section results without leaking inactive map-mode answers."""
        values = {}
        for section in sorted(self.sections):
            values.update(self.sections[section])
        return values
