"""An approved target-wide dependency lock, independent of individual AI generations."""
from pydantic import BaseModel,ConfigDict,Field,model_validator
from typing import Literal
from models.maven_dependency import MavenDependency


class SharedDependencyPolicy(BaseModel):
    """Freeze resolved BOM versions and supply class ownership hints for generation."""
    model_config=ConfigDict(extra='forbid')
    schema_version: Literal['shared-dependency-policy-v1']='shared-dependency-policy-v1'
    description: str=Field(min_length=1)
    bom: dict[str,str]=Field(default_factory=dict)
    managed_versions: dict[str,str]=Field(default_factory=dict)
    dependencies: list[MavenDependency]=Field(default_factory=list)

    @model_validator(mode='after')
    def pinned_coordinates(self):
        """Reject ambiguous coordinates and unpinned versions before any build changes."""
        known={}
        if self.bom:
            if {'group_id','artifact_id','version'}-self.bom.keys():raise ValueError('BOM provenance requires exact coordinates')
            MavenDependency(group_id=self.bom['group_id'],artifact_id=self.bom['artifact_id'],version=self.bom['version'])
        for coordinate,version in self.managed_versions.items():
            group,artifact=coordinate.split(':')
            MavenDependency(group_id=group,artifact_id=artifact,version=version)
        for dependency in self.dependencies:
            key=dependency.group_id+':'+dependency.artifact_id
            expected=self.managed_versions.get(key,dependency.version)
            if expected!=dependency.version or key in known:raise ValueError('Conflicting shared dependency policy pin: '+key)
            known[key]=dependency.version
        return self
