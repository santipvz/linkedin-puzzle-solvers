from __future__ import annotations

from typing import Protocol

from ..domain.models import JsonDict


class Solver(Protocol):
    def solve(self, puzzle: str, image: bytes, filename: str | None) -> JsonDict: ...


class SolutionCache(Protocol):
    def get(self, key: str) -> JsonDict | None: ...
    def put(self, key: str, value: JsonDict) -> None: ...


class CaptureStore(Protocol):
    def save(self, puzzle: str, image: bytes, response: JsonDict, from_cache: bool) -> None: ...
