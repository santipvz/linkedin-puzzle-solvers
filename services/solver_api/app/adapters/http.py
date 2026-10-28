from __future__ import annotations

import asyncio
from collections.abc import Sequence

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from ..application.solve_puzzle import SolvePuzzle
from ..domain.errors import EmptyImage, ImageTooLarge, SolverBusy, SolverError, SolverTimeout, UnknownPuzzle, UnsupportedImage, WorkerFailure
from ..domain.models import JsonDict, SolveRequest


ERROR_STATUS = {
    EmptyImage: 400,
    ImageTooLarge: 413,
    UnsupportedImage: 415,
    UnknownPuzzle: 404,
    SolverTimeout: 504,
    SolverBusy: 503,
    WorkerFailure: 500,
}


def create_http_app(
    service: SolvePuzzle,
    puzzles: Sequence[str],
    cors_origins: tuple[str, ...] = ("*",),
    cors_origin_regex: str | None = None,
) -> FastAPI:
    app = FastAPI(
        title="LinkedIn Puzzle Solver API",
        version="0.3.0",
        description="Local API wrapper for Queens, Tango, Mini Sudoku, Zip, Patches, and Wend image solvers.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_origin_regex=None if cors_origins == ("*",) else cors_origin_regex,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    def handler_for(puzzle: str):
        async def solve(
            image: UploadFile = File(...),
            board_capture: str | None = Header(default=None, alias="X-Board-Capture"),
        ) -> JsonDict:
            request = SolveRequest(
                puzzle=puzzle,
                image=await image.read(service.max_upload_bytes + 1),
                filename=image.filename,
                content_type=image.content_type,
                capture=bool(board_capture and board_capture.strip().lower() == "start"),
            )
            try:
                return await asyncio.to_thread(service.execute, request)
            except SolverError as exc:
                headers = {"Retry-After": "2"} if isinstance(exc, SolverBusy) else None
                raise HTTPException(status_code=ERROR_STATUS.get(type(exc), 500), detail=str(exc), headers=headers) from exc

        solve.__name__ = f"solve_{puzzle}"
        return solve

    for puzzle in puzzles:
        app.post(f"/solve/{puzzle}", name=f"solve_{puzzle}", response_model=None)(handler_for(puzzle))
    return app
