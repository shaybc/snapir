"""Reproducible unit-boundary inputs and controlled environment values."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field,field_validator
from models.native_boundary_value import NativeBoundaryValue


class BoundaryCase(BaseModel):
    """Use the same input, clock, seed, settings and replay responses on both sides."""
    model_config = ConfigDict(extra='forbid')
    case_id: str
    input_xml: str | None = None
    initial_context: dict[str, Any] = Field(default_factory=dict)
    clock_millis: int = 1704153600000
    random_seed: int = 1729
    settings: list[dict[str, Any]] = Field(default_factory=list)
    external_responses: list[dict[str, Any]] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    test_assets: dict[str, Any] = Field(default_factory=dict,exclude_if=lambda value:not value)
    decorator_value: Any = Field(default=None,exclude_if=lambda value:value is None)
    original_inputs: dict[str,NativeBoundaryValue] = Field(default_factory=dict,exclude_if=lambda value:not value)

    @field_validator('original_inputs')
    @classmethod
    def original_recipes(cls,values):
        """Reject ignored/executable recipe fields rather than silently changing input meaning."""
        def visit(recipe,inside=False,depth=0):
            if depth>12 or recipe.factory_method:raise ValueError('Unsupported original recipe depth/factory')
            if recipe.source=='object':
                if recipe.key or recipe.element:raise ValueError('Object recipes use constructors/setters only')
            elif recipe.source=='collection':
                if not recipe.key or recipe.type_name not in {'java.util.List','java.util.Set'} or recipe.element is None or recipe.arguments or recipe.properties:
                    raise ValueError('Original collection needs a key and typed element recipe')
            elif recipe.source in {'fixture','context','item'}:
                if recipe.key is None or recipe.arguments or recipe.properties or recipe.element:raise ValueError('Original scalar recipe reads exactly one input')
                if recipe.source=='item' and not inside:raise ValueError('Original item recipe requires a collection')
            else:raise ValueError('Unsupported original input recipe source')
            for child in [*recipe.arguments,*recipe.properties.values()]:visit(child,inside,depth+1)
            if recipe.element:visit(recipe.element,True,depth+1)
        for recipe in values.values():visit(recipe)
        return values

