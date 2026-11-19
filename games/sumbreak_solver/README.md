# Sumbreak Solver

Sumbreak reads tile values straight from the LinkedIn page and searches for a merge order that leaves a single tile.

## Rules

Checked against the live game on its launch day (Sumbreak #1, 2026-11-18):

- Drag a tile onto an orthogonally adjacent tile with the same number, or tap one tile and then the other. The second tile becomes the sum and the first cell becomes empty.
- Nothing slides or falls. Empty cells stay empty.
- The puzzle is solved when exactly one tile remains.

## Input

The board is fully described in the page DOM (`[data-numo-design]` with `data-numo-rows` and `data-numo-columns`, one `[data-numo-index]` cell per position and a `button[data-numo-kind="number"]` for each tile), so there is no OCR. The extension sends `{"board": [[1, 1, 64], [4, 2, 32], [4, 4, 16]]}` as `parsed_board`, using `null` for empty cells. Boards from 2x2 to 8x8 are accepted and they may be rectangular. A request without page data returns `solved: false`.

## Search

A merge only touches its own two cells, so merges on different cells can be reordered freely. The smallest number on the board can only merge with another copy of itself, so every solution can be rewritten to merge two of the current smallest tiles first. The solver therefore pairs up the smallest tiles level by level, trying each equal neighbour of the first unpaired tile and both merge directions. It prunes a branch when:

- the remaining tiles split into disconnected groups, because tiles never move;
- a tile has no neighbour that equals it now or can reach it by doubling;
- the state was already shown to be a dead end.

Before searching, the solver also checks that equal values can pair off level by level, so an odd number of smallest tiles fails at once.

Random solvable boards packed with tiles solve in well under a second up to 8x8. The worker stops after 20 seconds.

## Output

`moves` lists merges in order. Each one moves the tile at `row`/`col` onto the equal neighbour at `to_row`/`to_col`, which then holds `value`. The extension taps the source, waits until the game marks it selected, taps the target and checks that the board shows the merge. Each merge then animates for about 0.2–0.9 s (the two tiles carry the `source`/`destination` paint roles) and the game ignores taps until every tile is `resting` again, so the extension waits for that before the next merge.

## Command line

```bash
python3 games/sumbreak_solver/main.py '[[1, 1, 64], [4, 2, 32], [4, 4, 16]]'
```

`tests/fixtures/linkedin-2026-11-18.json` records the launch puzzle. `examples/sample1.png` is a screenshot of the same board.
