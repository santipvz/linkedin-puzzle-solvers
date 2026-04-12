# Patches Solver

Computer vision parser + rectangle tiling solver for LinkedIn Patches.

## Rules modeled

- The board is tiled with non-overlapping axis-aligned rectangles.
- Every clue belongs to exactly one rectangle.
- If a clue has a number, the rectangle area must match it.
- Shape constraints:
  - `square`: width == height
  - `wide`: width > height
  - `tall`: height > width
  - `any`: no aspect restriction

## Local run

```bash
python3 games/patches_solver/main.py games/patches_solver/examples/sample1.png --json
```

Available board captures:

- `games/patches_solver/examples/sample1.png`
- `games/patches_solver/examples/sample2.png`
- `games/patches_solver/examples/sample3.png`
