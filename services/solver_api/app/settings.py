from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def parse_cors_origins(raw_value: str) -> list[str]:
    values = [part.strip() for part in str(raw_value).split(",") if part.strip()]
    return ["*"] if not values or "*" in values else values


@dataclass(frozen=True)
class Settings:
    repo_root: Path = REPO_ROOT
    capture_directory: Path = REPO_ROOT / "datasets"
    capture_enabled: bool = True
    worker_mode: str = "subprocess"
    worker_timeout: int = 60
    max_upload_bytes: int = 10 * 1024 * 1024
    max_concurrent_workers: int = 0
    cors_origins: tuple[str, ...] = ("*",)
    cors_origin_regex: str | None = None

    @classmethod
    def from_env(cls) -> Settings:
        hosted = os.getenv("VERCEL") == "1"
        return cls(
            capture_directory=Path(os.getenv("DATASET_CAPTURE_DIR") or REPO_ROOT / "datasets").expanduser(),
            capture_enabled=os.getenv("DATASET_CAPTURE_ENABLED", "0" if hosted else "1").strip().lower() not in {"0", "false", "no"},
            worker_mode=os.getenv("SOLVER_WORKER_MODE", "subprocess").strip().lower(),
            max_upload_bytes=4 * 1024 * 1024 if hosted else 10 * 1024 * 1024,
            max_concurrent_workers=1 if hosted else 0,
            cors_origins=tuple(parse_cors_origins(os.getenv("CORS_ALLOW_ORIGINS", "*"))),
            cors_origin_regex=(os.getenv("CORS_ALLOW_ORIGIN_REGEX") or "").strip() or None,
        )
