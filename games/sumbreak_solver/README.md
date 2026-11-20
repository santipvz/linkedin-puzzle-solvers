# Sumbreak Solver

Sumbreak reads tile values straight from the LinkedIn page and searches for a merge order that leaves a single tile.

## Rules

Checked against the live game on its launch day (Sumbreak #1, 2026-11-18):

- Drag a tile onto an orthogonally adjacent tile with the same number, or tap one tile and then the other. The second tile becomes the sum and the first cell becomes empty.
- Nothing slides or falls. Empty cells stay empty.
- The puzzle is solved when exactly one tile remains.

Operator tiles first appeared on 2026-11-20 (Sumbreak #3). The game calls them wildcards and draws them as purple diamonds labelled `×2`; its code also supports `+N`. The rules below come from the game's own merge function:

- A number and an adjacent operator merge in either direction. Whichever tile is the target becomes the number with the operator applied, for example `4` and `×2` make `8`.
- Two operators never merge with each other.
- A result must be a positive safe integer.
- The puzzle is only solved when the last tile is a number, so every operator has to be used.

## Input

The board is fully described in the page DOM (`[data-numo-design]` with `data-numo-rows` and `data-numo-columns`, one `[data-numo-index]` cell per position and a `button[data-numo-kind="number"]` for each tile), so there is no OCR. Operator tiles are `button[data-numo-kind="wildcard"]` and their SVG label reads `×2` or `+3`. The extension sends `{"board": [[null, 2, 1], [null, 4, 1], [16, "x2", 4]]}` as `parsed_board`, using `null` for empty cells and `"xN"` / `"+N"` for operators. Boards from 2x2 to 8x8 are accepted and they may be rectangular. A request without page data returns `solved: false`.

## Search

A merge only touches its own two cells, so merges on different cells can be reordered freely. The smallest number on the board can only merge with another copy of itself, so every solution can be rewritten to merge two of the current smallest tiles first. The solver therefore pairs up the smallest tiles level by level, trying each equal neighbour of the first unpaired tile and both merge directions. It prunes a branch when:

- the remaining tiles split into disconnected groups, because tiles never move;
- a tile has no neighbour that equals it now or can reach it by doubling;
- the state was already shown to be a dead end.

Before searching, the solver also checks that equal values can pair off level by level, so an odd number of smallest tiles fails at once.

Operators keep the smallest-first rule as long as each one makes a number strictly larger (`×N` with N ≥ 2, `+N` with N ≥ 1). The smallest tile can then only merge with an equal tile or with an operator already on the board, so the first smallest tile branches on both. The doubling and pairing checks only apply once every operator is used up. If an operator could leave a number the same or shrink it, the solver tries every legal merge instead.

Random solvable boards packed with tiles solve in well under a second up to 8x8, including boards with a dozen operators. The worker stops after 20 seconds.

## Output

`moves` lists merges in order. Each one moves the tile at `row`/`col` onto the neighbour at `to_row`/`to_col`, which then holds `value`. Either tile may be an operator. The extension taps the source, waits until the game marks it selected, taps the target and checks that the board shows the merge. Each merge then animates for about 0.2–0.9 s (the two tiles carry the `source`/`destination` paint roles) and the game ignores taps until every tile is `resting` again, so the extension waits for that before the next merge.

## Command line

```bash
python3 games/sumbreak_solver/main.py '[[1, 1, 64], [4, 2, 32], [4, 4, 16]]'
python3 games/sumbreak_solver/main.py '[[null, 2, 1], [null, 4, 1], [16, "x2", 4]]'
```

`tests/fixtures/linkedin-2026-11-18.json` records the launch puzzle and `tests/fixtures/linkedin-2026-11-20.json` the first one with an operator. `examples/sample1.png` is a screenshot of the same board.
