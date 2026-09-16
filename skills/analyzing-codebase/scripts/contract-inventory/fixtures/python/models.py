from pydantic import BaseModel, Field, model_validator
from typing import Literal, TypedDict, NotRequired, TypeAlias
from imaginary_dependency_with_import_side_effects import run

raise RuntimeError("This module must never be imported by the inventory adapter")


class StartRequest(BaseModel):
    call_id: str = Field(alias="callId")
    required_nullable: str | None
    optional_nullable: str | None = None
    retries: int = Field(default=0, ge=0, le=5)
    mode: Literal["preview", "execute"]
    child: "StartRequest | None" = None
    unknown: ExternalOpaqueType

    @model_validator(mode="after")
    def conditional_rule(self):
        if self.mode == "execute" and not self.call_id:
            raise ValueError("missing identifier")
        return self


class StartResponse(BaseModel):
    accepted: bool


class Headers(TypedDict):
    correlation_id: str
    label: NotRequired[str]


class UnsupportedContainer:
    arbitrary: complex


UnsupportedAlias: TypeAlias = tuple[str, complex]
