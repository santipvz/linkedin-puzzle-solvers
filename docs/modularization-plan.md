# Vision modules

See [Architecture](architecture.md) for the enforced ports-and-adapters boundaries.

Shared `core/` modules provide geometry, crop validation, projection grouping, OCR math, and parser metadata. Each game owns its thresholds, glyph segmentation, clue semantics, board selection, and search rules.

The remaining legacy constraint is the generic `src` import namespace used by some game CLIs. The worker adapter isolates these imports and serializes in-process execution; subprocess execution remains the default.
