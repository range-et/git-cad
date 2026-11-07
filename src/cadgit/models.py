from __future__ import annotations
from typing import Literal,Any
from pydantic import BaseModel, Field,ConfigDict

class ExtensibleModel(BaseModel):
    # Preserve fields written by newer compatible releases when validating and
    # serializing a record. Pydantic's default would silently discard them.
    model_config=ConfigDict(extra='allow',allow_inf_nan=False)

class Record(ExtensibleModel):
    schema_version: Literal[1] = 1
    schema_minor: int = Field(default=0,ge=0)
    required_features: list[str] = Field(default_factory=list)
    extensions: dict[str,Any] = Field(default_factory=dict)

class Selection(ExtensibleModel):
    snapshot_id: str
    prim_path: str
    label: str = "Part"
    translation: tuple[float, float, float] = (0, 0, 0)
    material_revision: str | None = None

class Snapshot(Record):
    id: str
    source: str
    branch: str = "main"
    parent: str | None = None
    created_at: str
    label: str
    trigger: str = "ingest"
    entry_layer: str = "scene.usdz"
    files: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

class Assembly(Record):
    id: str
    created_at: str
    label: str
    selections: list[Selection]
    files: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
