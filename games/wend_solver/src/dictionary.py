from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


DEFAULT_MIN_WORD_LENGTH = 3
DEFAULT_MAX_WORD_LENGTH = 16
ENV_WORDLIST_PATH = "WEND_WORDLIST_PATH"
FALLBACK_WORDS = ("SQUARE", "MAGENTA", "BIOLOGIST", "RHINOCEROS")


def load_wend_dictionary(
    *,
    extra_paths: Iterable[str | Path] = (),
    min_length: int = DEFAULT_MIN_WORD_LENGTH,
    max_length: int = DEFAULT_MAX_WORD_LENGTH,
) -> list[str]:
    words: set[str] = set()
    for path in _candidate_paths(extra_paths):
        words.update(_load_words_from_path(path, min_length=min_length, max_length=max_length))

    words.update(FALLBACK_WORDS)
    return sorted(words)


def _candidate_paths(extra_paths: Iterable[str | Path]) -> list[Path]:
    candidates: list[Path] = []
    env_path = os.getenv(ENV_WORDLIST_PATH)
    if env_path:
        candidates.append(Path(env_path).expanduser())

    candidates.append(Path(__file__).resolve().parents[1] / "data" / "words.txt")
    candidates.extend(Path(path).expanduser() for path in extra_paths)

    # Development fallback only. The repository wordlist above is the portable source.
    candidates.extend((Path("/usr/share/dict/words"), Path("/usr/share/dict/american-english")))

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
        return set()

    words: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return set()

    for line in lines:
        word = line.strip().upper()
        if min_length <= len(word) <= max_length and word.isascii() and word.isalpha():
            words.add(word)
    return words
