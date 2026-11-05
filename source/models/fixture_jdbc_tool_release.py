"""Pinned converter tool distribution identities, not generated operation configuration."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class FixtureToolFile(BaseModel):
    """One immutable distribution file with an explicit size, digest, and role."""
    model_config = ConfigDict(extra='forbid')
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    size: int = Field(ge=0)
    role: Literal['driver', 'server', 'wrapper', 'evidence']


class FixtureJdbcToolRelease(BaseModel):
    """A caller-pinned release; bundle_id hashes this descriptor excluding itself."""
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['fixture-jdbc-tool-release-v1'] = 'fixture-jdbc-tool-release-v1'
    tool_version: str = Field(pattern=r'^\d+\.\d+\.\d+$')
    bundle_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    protocol_major: Literal[1] = 1
    protocol_minor: Literal[0] = 0
    minimum_java: Literal[21] = 21
    driver_class: Literal['il.co.dcd.fixtures.jdbc.FixtureDriver'] = 'il.co.dcd.fixtures.jdbc.FixtureDriver'
    server_main: Literal['il.co.dcd.fixtures.server.FixtureServerCommand'] = 'il.co.dcd.fixtures.server.FixtureServerCommand'
    fixture_schemas: list[str]
    source_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    files: dict[str, FixtureToolFile]

    @field_validator('files')
    @classmethod
    def safe_files(cls, files):
        """Paths are portable and bounded; a manifest cannot escape its release root."""
        from pathlib import PurePosixPath
        if not 4 <= len(files) <= 64:
            raise ValueError('Invalid fixture tool file count')
        for name in files:
            path = PurePosixPath(name)
            if path.is_absolute() or '\\' in name or ':' in name or '..' in path.parts or str(path) != name:
                raise ValueError('Unsafe fixture tool file path')
        required = {'jdbc/fixture-jdbc-driver.jar': 'driver', 'server/fixture-server.jar': 'server'}
        if any(name not in files or files[name].role != role for name, role in required.items()):
            raise ValueError('Fixture driver and server artifacts are required')
        return files
