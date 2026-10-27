from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..domain.models import JsonDict


class FileCaptureStore:
    def __init__(self, directory: Path, repo_root: Path, enabled: bool = True) -> None:
        self.directory = directory
        self.repo_root = repo_root
        self.enabled = enabled
        self._lock = threading.Lock()

    def save(self, puzzle: str, image: bytes, response: JsonDict, from_cache: bool) -> None:
        try:
            self._archive_board_capture(puzzle, image, response, from_cache)
        except (OSError, ValueError, TypeError) as exc:
            logging.getLogger(__name__).warning("Board capture archive skipped: %s", exc)

    def _make_dataset_path_editable(self, path: Path) -> None:
        try:
            repo_stat = self.repo_root.stat()
            os.chown(path, repo_stat.st_uid, repo_stat.st_gid)
        except (AttributeError, OSError, PermissionError):
            pass

        try:
            if path.is_dir():
                path.chmod(0o775)
            else:
                path.chmod(0o664)
        except (OSError, PermissionError):
            pass

    def _image_suffix(self, payload: bytes) -> str:
        if payload.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if payload.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if payload.startswith(b"BM"):
            return ".bmp"
        if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
            return ".webp"
        return ".img"

    def _archive_board_capture(self, puzzle: str, payload: bytes, response: JsonDict, from_cache: bool) -> None:
        with self._lock:
            self._archive_board_capture_unlocked(puzzle, payload, response, from_cache)

    def _archive_board_capture_unlocked(self, puzzle: str, payload: bytes, response: JsonDict, from_cache: bool) -> None:
        if not self.enabled:
            return

        digest = hashlib.sha256(payload).hexdigest()
        now = datetime.now(timezone.utc)
        day = now.strftime("%Y-%m-%d")

        target_dir = self.directory / puzzle / day
        target_dir.mkdir(parents=True, exist_ok=True)
        for directory in (self.directory, self.directory / puzzle, target_dir):
            self._make_dataset_path_editable(directory)

        image_path = target_dir / f"{digest}{self._image_suffix(payload)}"
        metadata_path = target_dir / f"{digest}.json"

        existing_digest = hashlib.sha256(image_path.read_bytes()).hexdigest() if image_path.exists() else None
        if existing_digest != digest:
            image_temp_path = image_path.with_suffix(f"{image_path.suffix}.tmp")
            image_temp_path.write_bytes(payload)
            image_temp_path.replace(image_path)
            self._make_dataset_path_editable(image_path)
        artifact_digest = hashlib.sha256(image_path.read_bytes()).hexdigest()

        metadata: dict[str, Any] = {
            "puzzle": puzzle,
            "sha256": digest,
            "original_sha256": digest,
            "artifact_sha256": artifact_digest,
            "artifact_filename": image_path.name,
            "captured_at": now.isoformat(),
            "from_cache": bool(from_cache),
            "solved": bool(response.get("solved")),
            "error": response.get("error"),
            "board_size": response.get("board_size"),
            "details": response.get("details"),
            "words": response.get("words"),
        }

        if metadata_path.exists():
            try:
                existing = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                existing = {}

            seen_count = int(existing.get("seen_count") or 1)
            metadata["first_captured_at"] = existing.get("first_captured_at") or existing.get("captured_at") or metadata["captured_at"]
            metadata["seen_count"] = seen_count + 1
        else:
            metadata["first_captured_at"] = metadata["captured_at"]
            metadata["seen_count"] = 1

        metadata_temp_path = metadata_path.with_suffix(".json.tmp")
        metadata_temp_path.write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")
        metadata_temp_path.replace(metadata_path)
        self._make_dataset_path_editable(metadata_path)
