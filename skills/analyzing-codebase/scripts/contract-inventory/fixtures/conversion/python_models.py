"""Synthetic native model used only by conversion conformance tests."""
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class Child(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    enabled: bool


class PythonPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    required_nullable: str | None
    optional_nullable: str | None = None
    action: Literal["keep", "drop"]
    child: Child
    children: list[Child]

    @field_validator("name")
    @classmethod
    def reserved_name(cls, value: str) -> str:
        if value == "reserved":
            raise ValueError("The synthetic native-only rule rejects this name")
        return value


if __name__ == "__main__":
    print(json.dumps(PythonPayload.model_json_schema()))
