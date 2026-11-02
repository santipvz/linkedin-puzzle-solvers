from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from ..domain.errors import EmptyImage, ImageTooLarge, InvalidBoard, UnknownPuzzle, UnsupportedImage
from ..domain.models import JsonDict, SolveRequest
from ..domain.wend_board import validate_wend_board
from .cache_policy import should_recompute
from .ports import CaptureStore, SolutionCache, Solver


def cache_key(puzzle: str, revision: int, image: bytes) -> str:
    return f"{puzzle}:{revision}:{hashlib.sha256(image).hexdigest()}"


class SolvePuzzle:
    def __init__(
        self,
        solver: Solver,
        cache: SolutionCache,
        captures: CaptureStore,
        cache_revisions: Mapping[str, int],
        max_upload_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self.solver = solver
        self.cache = cache
        self.captures = captures
        self.cache_revisions = dict(cache_revisions)
        self.max_upload_bytes = max_upload_bytes

    def execute(self, request: SolveRequest) -> JsonDict:
        if request.puzzle not in self.cache_revisions:
            raise UnknownPuzzle(f"Unknown puzzle: {request.puzzle}")
        if request.content_type and not request.content_type.startswith("image/"):
            raise UnsupportedImage("Only image uploads are supported.")
        if not request.image:
            raise EmptyImage("Uploaded image is empty.")
        if len(request.image) > self.max_upload_bytes:
            raise ImageTooLarge(f"Uploaded image exceeds {self.max_upload_bytes} bytes.")

        parsed_board = None
        if request.parsed_board is not None:
            if request.puzzle != "wend":
                raise InvalidBoard("Page board data is only supported for Wend.")
            parsed_board = validate_wend_board(request.parsed_board)

        key = cache_key(request.puzzle, self.cache_revisions[request.puzzle], request.image)
        if parsed_board is not None:
            # OCR and page-derived responses must never share a cache entry.
            encoded = json.dumps(parsed_board, sort_keys=True, separators=(",", ":")).encode()
            key += ":page:" + hashlib.sha256(encoded).hexdigest()
        response = self.cache.get(key)
        from_cache = response is not None and not should_recompute(request.puzzle, response)
        if not from_cache:
            if parsed_board is None:
                response = self.solver.solve(request.puzzle, request.image, request.filename)
            else:
                response = self.solver.solve(request.puzzle, request.image, request.filename, parsed_board=parsed_board)
            self.cache.put(key, response)

        if request.capture:
            self.captures.save(request.puzzle, request.image, response, from_cache)
        return response
