from __future__ import annotations

import argparse
from pathlib import Path


def build_wordlist(source: Path, output: Path, *, min_length: int = 3, max_length: int = 16) -> int:
    words = {
        line.strip().upper()
        for line in source.read_text(encoding="utf-8", errors="ignore").splitlines()
        if min_length <= len(line.strip()) <= max_length
        and line.strip().isascii()
        and line.strip().isalpha()
    }
    output.write_text("\n".join(sorted(words)) + "\n", encoding="utf-8")
    return len(words)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the portable Wend wordlist.")
    parser.add_argument("source", type=Path, help="Source SCOWL/wamerican wordlist")
    parser.add_argument("output", type=Path, help="Normalized output path")
    args = parser.parse_args()
    count = build_wordlist(args.source, args.output)
    print(f"Wrote {count} words to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
