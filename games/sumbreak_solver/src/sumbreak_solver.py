"""Search for a Sumbreak merge sequence.

Rules (verified against the live LinkedIn game):

* Each tile shows a positive number; ``None`` cells are empty or blocked.
* A move picks a tile and drops it on an orthogonally adjacent tile with the
  same value. The target becomes the sum, the source cell becomes empty and
  nothing slides or falls.
* The puzzle is solved when exactly one tile remains.

Search idea
-----------
A merge only reads and writes its own two cells, so two merges on different
cells can be swapped freely. The smallest value on the board can only ever
merge with another copy of itself (merges only create larger numbers), so
every solution can be reordered to merge two of the current smallest tiles
first. The search therefore pairs up the smallest tiles level by level: take
the first unpaired smallest tile, try each equal neighbour and both merge
directions, and repeat. Two further facts prune dead ends early:

* Tiles never move, so once the remaining tiles fall into two disconnected
  groups the board can never finish.
* A tile is stranded when no neighbour can ever match it: neighbours only
  grow, so a neighbour must equal the tile now or reach it by doubling (or the
  tile must reach the neighbour's value by doubling).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


Cell = tuple[int, int]
Board = list[list[int | None]]

DEFAULT_TIME_LIMIT_SECONDS = 20.0


@dataclass(frozen=True, slots=True)
class SumbreakMove:
    source: Cell
    target: Cell
    value: int
    """Value of the merged tile left on ``target``."""


@dataclass(slots=True)
class SumbreakResult:
    solved: bool
    moves: list[SumbreakMove] = field(default_factory=list)
    final_cell: Cell | None = None
    final_value: int | None = None
    nodes: int = 0
    error: str | None = None


class _SearchTimeLimit(Exception):
    pass


def _can_meet(small: int, large: int) -> bool:
    """Whether ``small`` can reach ``large`` by repeated doubling."""
    while small < large:
        small *= 2
    return small == large


def _pairable(values: list[int]) -> bool:
    """Whether equal values can pair off level by level into a single tile."""
    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    while len(counts) > 1:
        smallest = min(counts)
        count = counts.pop(smallest)
        if count % 2:
            return False
        counts[smallest * 2] = counts.get(smallest * 2, 0) + count // 2
    (count,) = counts.values()
    return count & (count - 1) == 0


class SumbreakSolver:
    def __init__(self, time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS) -> None:
        self.time_limit_seconds = float(time_limit_seconds)

    def solve(self, board: Board) -> SumbreakResult:
        rows = len(board)
        cols = len(board[0]) if rows else 0
        if rows == 0 or cols == 0 or any(len(row) != cols for row in board):
            return SumbreakResult(solved=False, error="Board must be a non-empty rectangle.")

        start: list[int] = []
        for row in board:
            for value in row:
                if value is None:
                    start.append(0)
                elif isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    return SumbreakResult(solved=False, error="Tiles must be positive integers or None.")
                else:
                    start.append(int(value))

        tiles = [index for index, value in enumerate(start) if value]
        if not tiles:
            return SumbreakResult(solved=False, error="Board has no tiles.")

        neighbors: list[tuple[int, ...]] = []
        for index in range(rows * cols):
            row, col = divmod(index, cols)
            around = []
            if row > 0:
                around.append(index - cols)
            if row + 1 < rows:
                around.append(index + cols)
            if col > 0:
                around.append(index - 1)
            if col + 1 < cols:
                around.append(index + 1)
            neighbors.append(tuple(around))

        def connected(state: list[int], count: int) -> bool:
            first = next(index for index, value in enumerate(state) if value)
            seen = {first}
            stack = [first]
            while stack:
                for neighbor in neighbors[stack.pop()]:
                    if state[neighbor] and neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
            return len(seen) == count

        def stranded(state: list[int], index: int) -> bool:
            value = state[index]
            for neighbor in neighbors[index]:
                other = state[neighbor]
                if other and (_can_meet(value, other) if value <= other else _can_meet(other, value)):
                    return False
            return True

        def to_cell(index: int) -> Cell:
            return divmod(index, cols)

        if not connected(start, len(tiles)):
            return SumbreakResult(solved=False, error="Tiles are split into disconnected groups.")
        if not _pairable([start[index] for index in tiles]):
            return SumbreakResult(solved=False, error="Tile values cannot be merged down to a single tile.")
        if len(tiles) > 1 and any(stranded(start, index) for index in tiles):
            return SumbreakResult(solved=False, error="A tile has no neighbour it can ever merge with.")

        deadline = time.monotonic() + self.time_limit_seconds
        dead: set[tuple[int, ...]] = set()
        path: list[tuple[int, int, int]] = []
        nodes = 0
        state = start

        def search(count: int) -> bool:
            nonlocal nodes
            if count == 1:
                return True
            key = tuple(state)
            if key in dead:
                return False
            nodes += 1
            if not nodes & 0x3FF and time.monotonic() > deadline:
                raise _SearchTimeLimit

            smallest = min(value for value in state if value)
            # Any order of the smallest pairs works, so always extend the
            # pairing from the first unpaired smallest tile.
            first = state.index(smallest)
            for partner in neighbors[first]:
                if state[partner] != smallest:
                    continue
                for source, target in ((first, partner), (partner, first)):
                    state[source] = 0
                    state[target] = smallest * 2
                    viable = count == 2 or (
                        not any(state[n] and stranded(state, n) for n in (target, *neighbors[target], *neighbors[source]))
                        and connected(state, count - 1)
                    )
                    if viable:
                        path.append((source, target, smallest * 2))
                        if search(count - 1):
                            return True
                        path.pop()
                    state[source] = smallest
                    state[target] = smallest

            dead.add(key)
            return False

        try:
            found = search(len(tiles))
        except _SearchTimeLimit:
            return SumbreakResult(solved=False, nodes=nodes, error="Search time limit reached before finding a solution.")

        if not found:
            return SumbreakResult(solved=False, nodes=nodes, error="No merge sequence leaves a single tile.")

        if path:
            final_index, final_value = path[-1][1], path[-1][2]
        else:
            final_index, final_value = tiles[0], start[tiles[0]]
        return SumbreakResult(
            solved=True,
            moves=[SumbreakMove(source=to_cell(s), target=to_cell(t), value=v) for s, t, v in path],
            final_cell=to_cell(final_index),
            final_value=final_value,
            nodes=nodes,
        )


def apply_moves(board: Board, moves: list[SumbreakMove]) -> Board:
    """Replay moves under the game rules; raises ValueError on an illegal move."""
    grid = [list(row) for row in board]
    for move in moves:
        (sr, sc), (tr, tc) = move.source, move.target
        if abs(sr - tr) + abs(sc - tc) != 1:
            raise ValueError(f"Move {move} is not between adjacent cells.")
        source, target = grid[sr][sc], grid[tr][tc]
        if source is None or source != target:
            raise ValueError(f"Move {move} does not merge two equal tiles.")
        grid[sr][sc] = None
        grid[tr][tc] = source + target
        if grid[tr][tc] != move.value:
            raise ValueError(f"Move {move} reports the wrong merged value.")
    return grid
