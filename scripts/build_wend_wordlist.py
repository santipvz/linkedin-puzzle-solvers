from __future__ import annotations

import argparse
from pathlib import Path


def _source_words(source: Path, min_length: int, max_length: int) -> list[str]:
    return [
        line.strip()
        for line in source.read_text(encoding="utf-8", errors="ignore").splitlines()
        if min_length <= len(line.strip()) <= max_length
        and line.strip().isascii()
        and line.strip().isalpha()
    ]


def build_wordlist(source: Path, output: Path, *, min_length: int = 3, max_length: int = 16) -> int:
    words = {word.upper() for word in _source_words(source, min_length, max_length)}
    output.write_text("\n".join(sorted(words)) + "\n", encoding="utf-8")
    return len(words)


def build_proper_nouns(source: Path, output: Path, *, min_length: int = 3, max_length: int = 16) -> int:
    """Entries that appear only capitalized in the source: names, places, acronyms.

    They stay valid answers but lose ties against covers made of common words.
    """
    source_words = _source_words(source, min_length, max_length)
    common = {word.upper() for word in source_words if word[0].islower()}
    proper = {word.upper() for word in source_words} - common
    output.write_text("\n".join(sorted(proper)) + "\n", encoding="utf-8")
    return len(proper)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the portable Wend wordlist.")
    parser.add_argument("source", type=Path, help="Source SCOWL/wamerican wordlist")
    parser.add_argument("output", type=Path, help="Normalized output path")
    parser.add_argument("--proper-nouns", type=Path, help="Also write the capitalized-only entries here")
    args = parser.parse_args()
    count = build_wordlist(args.source, args.output)
    print(f"Wrote {count} words to {args.output}")
    if args.proper_nouns:
        proper = build_proper_nouns(args.source, args.proper_nouns)
        print(f"Wrote {proper} proper nouns to {args.proper_nouns}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
