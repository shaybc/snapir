"""Carry a conversion component label through asynchronous model diagnostics."""

from contextvars import ContextVar

COMPONENT_LABEL = ContextVar("model_component_label", default="")


def component_suffix():
    """Return readable component context, leaving other model requests unchanged."""
    label = COMPONENT_LABEL.get()
    return " [" + label + "]" if label else ""
