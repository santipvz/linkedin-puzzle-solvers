from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from ..application.solve_puzzle import SolvePuzzle
from ..domain.errors import EmptyImage, ImageTooLarge, InvalidBoard, SolverBusy, SolverError, SolverTimeout, UnknownPuzzle, UnsupportedImage, WorkerFailure
from ..domain.models import JsonDict, SolveRequest


ERROR_STATUS = {
    EmptyImage: 400,
    InvalidBoard: 422,
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
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            close = getattr(service.solver, "close", None)
            if close is not None:
                close()

    app = FastAPI(
        lifespan=lifespan,
        title="LinkedIn Puzzle Solver API",
        version="0.3.1",
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

    public_directory = Path(__file__).resolve().parents[1] / "public"

    def public_page(filename: str) -> HTMLResponse:
        return HTMLResponse((public_directory / filename).read_text(encoding="utf-8"), headers={
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff",
        })

    @app.get("/", include_in_schema=False)
    def homepage() -> HTMLResponse:
        return public_page("index.html")

    @app.get("/privacy", include_in_schema=False)
    def privacy() -> HTMLResponse:
        return public_page("privacy.html")

    @app.get("/support", include_in_schema=False)
    def support() -> HTMLResponse:
        return public_page("support.html")

    def handler_for(puzzle: str):
        async def solve(
            image: UploadFile = File(...),
            board_capture: str | None = Header(default=None, alias="X-Board-Capture"),
            parsed_board: str | None = Form(default=None, max_length=4096),
        ) -> JsonDict:
            page_board = None
            if parsed_board is not None:
                try:
                    page_board = json.loads(parsed_board)
                except (ValueError, RecursionError) as exc:
                    raise HTTPException(status_code=422, detail="Invalid page board JSON.") from exc
                if not isinstance(page_board, dict):
                    raise HTTPException(status_code=422, detail="Page board JSON must be an object.")
            request = SolveRequest(
                puzzle=puzzle,
                image=await image.read(service.max_upload_bytes + 1),
                filename=image.filename,
                content_type=image.content_type,
                capture=bool(board_capture and board_capture.strip().lower() == "start"),
                parsed_board=page_board,
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
