from __future__ import annotations

from typing import Protocol


class FrameRecorder(Protocol):
    def save_frame(self, board, constraints, position, label: str) -> None: ...
    def create_gif(self, output_path: str, duration: int, cleanup_frames: bool) -> str: ...
