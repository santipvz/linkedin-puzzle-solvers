from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


DEFAULT_MIN_WORD_LENGTH = 3
DEFAULT_MAX_WORD_LENGTH = 16
ENV_WORDLIST_PATH = "WEND_WORDLIST_PATH"


def load_wend_dictionary(
    *,
    extra_paths: Iterable[str | Path] = (),
    min_length: int = DEFAULT_MIN_WORD_LENGTH,
    max_length: int = DEFAULT_MAX_WORD_LENGTH,
) -> list[str]:
    if min_length < 1 or min_length > max_length:
        raise ValueError("Wend dictionary length bounds are invalid.")

    words: set[str] = set()
    for path in _candidate_paths(extra_paths):
        words.update(_load_words_from_path(path, min_length=min_length, max_length=max_length))

    if not words:
        raise ValueError("Wend dictionary contains no usable words.")
    return sorted(words)


def _candidate_paths(extra_paths: Iterable[str | Path]) -> list[Path]:
    candidates: list[Path] = []
    candidates.append(Path(__file__).resolve().parents[1] / "data" / "words.txt")
    env_path = os.getenv(ENV_WORDLIST_PATH)
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.extend(Path(path).expanduser() for path in extra_paths)

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _load_words_from_path(path: Path, *, min_length: int, max_length: int) -> set[str]:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Wend dictionary not found: {path}")

    words: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as exc:
        raise OSError(f"Could not read Wend dictionary: {path}") from exc

    for line in lines:
        word = line.strip().upper()
        if min_length <= len(word) <= max_length and word.isascii() and word.isalpha():
            words.add(word)
    return words
