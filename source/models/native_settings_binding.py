"""Exact settings-target schema; runtime consumers continue receiving ordinary dictionaries."""
from typing_extensions import TypedDict
from pydantic import ConfigDict

NativeSettingsBinding = TypedDict('NativeSettingsBinding', {'class':str, 'method':str})
NativeSettingsBinding.__pydantic_config__ = ConfigDict(extra='forbid')
