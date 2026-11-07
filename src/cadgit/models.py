from __future__ import annotations
from typing import Literal,Any
from pydantic import BaseModel, Field,ConfigDict,model_validator

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
    library_material_revision: str | None = None
    required_features: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def gate_library_assignment(self):
        if self.library_material_revision:
            from .compatibility import MATERIAL_LIBRARY_FEATURE
            self.required_features=list(dict.fromkeys([*self.required_features,MATERIAL_LIBRARY_FEATURE]))
        return self

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

class RevisionLink(ExtensibleModel):
    revision_id: str = Field(min_length=1)
    role: str = Field(min_length=1,pattern=r'.*\S.*')

class AssetRevision(Record):
    id: str
    asset_id: str
    kind: Literal['material','image','document','shader','texture_set','other']
    revision_number: int = Field(ge=1)
    label: str
    created_at: str
    parents: list[RevisionLink] = Field(default_factory=list)
    dependencies: list[RevisionLink] = Field(default_factory=list)
    provenance: dict = Field(default_factory=dict)
    definition: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    change_note: str = ''
    entry_layer: str
    files: list[dict] = Field(default_factory=list)
