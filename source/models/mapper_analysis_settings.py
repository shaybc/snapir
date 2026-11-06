"""Bound the reusable mapper's compiler, storage and JVM resource budgets."""

from pydantic import BaseModel,ConfigDict,Field


class MapperAnalysisSettings(BaseModel):
    """Expose conservative tuning within the analysis protocol's tested upper bounds."""
    model_config=ConfigDict(extra='forbid')
    batch_files:int=Field(default=100,ge=1,le=100)
    batch_mib:int=Field(default=4,ge=1,le=4)
    java_file_mib:int=Field(default=8,ge=1,le=8)
    sqlite_cache_mib:int=Field(default=32,ge=1,le=32)
    heap_mib:int=Field(default=768,ge=128,le=4096)
