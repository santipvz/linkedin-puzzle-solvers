from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonDict: TypeAlias = dict[str, JsonValue]


@dataclass(frozen=True)
class SolveRequest:
    puzzle: str
    image: bytes
    filename: str | None = None
    content_type: str | None = None
    capture: bool = False
