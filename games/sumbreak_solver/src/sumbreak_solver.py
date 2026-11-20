"""Search for a Sumbreak merge sequence.

Rules (verified against the live LinkedIn game):

* Each tile shows a positive number; ``None`` cells are empty or blocked.
* Some tiles are operators ("wildcards") such as ``"x2"`` or ``"+3"``.
* A move picks a tile and drops it on an orthogonally adjacent tile. Two
  numbers must be equal and the target becomes their sum. A number and an
  operator can merge in either direction and the target becomes the number
  with the operator applied. Two operators never merge. The source cell
  becomes empty and nothing slides or falls.
* The puzzle is solved when exactly one tile remains and it is a number.

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

Operators keep the smallest-first rule as long as every operator makes numbers
strictly larger (``xN`` with N >= 2, ``+N`` with N >= 1): the smallest tile can
then only merge with an equal tile or with an operator that is already on the
board, so the first smallest tile branches on both. The doubling-based pruning
only holds once every operator is used up. Operators that could keep a number
the same or shrink it fall back to trying every legal merge.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field


Cell = tuple[int, int]
Board = list[list[int | str | None]]

DEFAULT_TIME_LIMIT_SECONDS = 20.0
MAX_SAFE_INTEGER = (1 << 53) - 1
"""The game rejects merges whose result is not a JavaScript safe integer."""

MULTIPLY = "x"
ADD = "+"
_WILDCARD = re.compile(r"^\s*([x×*+])\s*(-?\d+)\s*$")


def parse_wildcard(cell: object) -> tuple[str, int] | None:
    """Read an operator tile such as ``"x2"`` or ``"+3"`` as ``(op, operand)``."""
    if not isinstance(cell, str):
        return None
    match = _WILDCARD.match(cell)
    if not match:
        return None
    return (ADD if match.group(1) == "+" else MULTIPLY), int(match.group(2))


def apply_wildcard(number: int, wildcard: tuple[str, int]) -> int:
    op, operand = wildcard
    return number * operand if op == MULTIPLY else number + operand


def merge_values(source: int | str | None, target: int | str | None) -> int | None:
    """Value left on ``target`` after merging ``source`` into it, or None if illegal."""
    if source is None or target is None:
        return None
    source_wild, target_wild = parse_wildcard(source), parse_wildcard(target)
    if source_wild and target_wild:
        return None
    if source_wild:
        result = apply_wildcard(target, source_wild) if isinstance(target, int) else None
    elif target_wild:
        result = apply_wildcard(source, target_wild) if isinstance(source, int) else None
    elif isinstance(source, int) and source == target:
        result = source + target
    else:
        return None
    if result is None or not 1 <= result <= MAX_SAFE_INTEGER:
        return None
    return result


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

        # Cells are 0 when empty, the number for number tiles and -(k + 1) for
        # the k-th distinct operator in ``wildcards``.
        start: list[int] = []
        wildcards: list[tuple[str, int]] = []
        for row in board:
            for value in row:
                wildcard = parse_wildcard(value)
                if value is None:
                    start.append(0)
                elif wildcard is not None:
                    if wildcard not in wildcards:
                        wildcards.append(wildcard)
                    start.append(-(wildcards.index(wildcard) + 1))
                elif isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    return SumbreakResult(solved=False, error="Tiles must be positive integers, operators like \"x2\" or None.")
                else:
                    start.append(int(value))
        # Operators that always make a number larger keep the smallest-first rule.
        growing = all(operand >= 2 if op == MULTIPLY else operand >= 1 for op, operand in wildcards)

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

        def merged(source: int, target: int) -> int:
            """Number left on ``target`` after the merge, or 0 when it is illegal."""
            if source < 0 and target < 0:
                return 0
            if source < 0:
                result = apply_wildcard(target, wildcards[-source - 1])
            elif target < 0:
                result = apply_wildcard(source, wildcards[-target - 1])
            elif source == target:
                result = source + target
            else:
                return 0
            return result if 1 <= result <= MAX_SAFE_INTEGER else 0

        def to_cell(index: int) -> Cell:
            return divmod(index, cols)

        start_wild = sum(value < 0 for value in start)
        if not any(value > 0 for value in start):
            return SumbreakResult(solved=False, error="Board has no number tiles.")
        if not connected(start, len(tiles)):
            return SumbreakResult(solved=False, error="Tiles are split into disconnected groups.")
        if not start_wild:
            if not _pairable([start[index] for index in tiles]):
                return SumbreakResult(solved=False, error="Tile values cannot be merged down to a single tile.")
            if len(tiles) > 1 and any(stranded(start, index) for index in tiles):
                return SumbreakResult(solved=False, error="A tile has no neighbour it can ever merge with.")

        deadline = time.monotonic() + self.time_limit_seconds
        dead: set[tuple[int, ...]] = set()
        path: list[tuple[int, int, int]] = []
        nodes = 0
        state = start

        def candidates() -> list[tuple[int, int]]:
            if growing:
                smallest = min(value for value in state if value > 0)
                # Any order of the smallest tiles' merges works, so always
                # extend from the first smallest tile.
                first = state.index(smallest)
                pairs = []
                for partner in neighbors[first]:
                    if state[partner] == smallest or state[partner] < 0:
                        pairs.append((first, partner))
                        pairs.append((partner, first))
                return pairs
            return [
                (source, target)
                for source, value in enumerate(state)
                if value
                for target in neighbors[source]
                if state[target]
            ]

        def search(count: int, wild: int) -> bool:
            nonlocal nodes
            if count == 1:
                return wild == 0
            key = tuple(state)
            if key in dead:
                return False
            nodes += 1
            if not nodes & 0x3FF and time.monotonic() > deadline:
                raise _SearchTimeLimit
            if wild == count:
                dead.add(key)
                return False

            for source, target in candidates():
                source_value, target_value = state[source], state[target]
                result = merged(source_value, target_value)
                if not result:
                    continue
                remaining_wild = wild - (source_value < 0 or target_value < 0)
                state[source] = 0
                state[target] = result
                viable = count == 2 or connected(state, count - 1)
                if viable and not remaining_wild and count > 2:
                    if wild:
                        # The last operator is gone: the plain number rules apply.
                        values = [value for value in state if value]
                        viable = _pairable(values) and not any(state[n] and stranded(state, n) for n in range(len(state)))
                    else:
                        viable = not any(
                            state[n] and stranded(state, n) for n in (target, *neighbors[target], *neighbors[source])
                        )
                if viable:
                    path.append((source, target, result))
                    if search(count - 1, remaining_wild):
                        return True
                    path.pop()
                state[source] = source_value
                state[target] = target_value

            dead.add(key)
            return False

        try:
            found = search(len(tiles), start_wild)
        except _SearchTimeLimit:
            return SumbreakResult(solved=False, nodes=nodes, error="Search time limit reached before finding a solution.")

        if not found:
            return SumbreakResult(solved=False, nodes=nodes, error="No merge sequence leaves a single tile.")

        if path:
            final_index, final_value = path[-1][1], path[-1][2]
        elif start_wild:
            return SumbreakResult(solved=False, nodes=nodes, error="The last tile must be a number.")
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
        result = merge_values(grid[sr][sc], grid[tr][tc])
        if result is None:
            raise ValueError(f"Move {move} does not merge two compatible tiles.")
        grid[sr][sc] = None
        grid[tr][tc] = result
        if grid[tr][tc] != move.value:
            raise ValueError(f"Move {move} reports the wrong merged value.")
    return grid
