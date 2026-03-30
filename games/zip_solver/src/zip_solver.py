from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


Direction = str


@dataclass(slots=True)
class ZipSolveResult:
    solved: bool
    path: list[tuple[int, int]] | None
    directions: list[Direction] | None
    iterations: int
    error: str | None = None


class ZipSolver:
    def __init__(self) -> None:
        self._iterations = 0

    @property
    def iterations(self) -> int:
        return self._iterations

    def solve(
        self,
        size: int,
        blocked_h: Iterable[Iterable[bool]],
        blocked_v: Iterable[Iterable[bool]],
        clues: dict[tuple[int, int], int],
    ) -> ZipSolveResult:
        if size <= 1:
            return ZipSolveResult(
                solved=False,
                path=None,
                directions=None,
                iterations=0,
                error="Board size must be at least 2.",
            )

        horizontal = [list(row) for row in blocked_h]
        vertical = [list(row) for row in blocked_v]

        if len(horizontal) != size - 1 or any(len(row) != size for row in horizontal):
            return ZipSolveResult(
                solved=False,
                path=None,
                directions=None,
                iterations=0,
                error=f"Expected blocked_h to have shape {(size - 1, size)}.",
            )

        if len(vertical) != size or any(len(row) != size - 1 for row in vertical):
            return ZipSolveResult(
                solved=False,
                path=None,
                directions=None,
                iterations=0,
                error=f"Expected blocked_v to have shape {(size, size - 1)}.",
            )

        if not clues:
            return ZipSolveResult(
                solved=False,
                path=None,
                directions=None,
                iterations=0,
                error="No numbered clues detected.",
            )

        clue_values = sorted(clues.values())
        if clue_values[0] != 1:
            return ZipSolveResult(
                solved=False,
                path=None,
                directions=None,
                iterations=0,
                error="Clue sequence must start at 1.",
            )

        if len(set(clue_values)) != len(clue_values):
            return ZipSolveResult(
                solved=False,
                path=None,
                directions=None,
                iterations=0,
                error="Duplicate clue values found.",
            )

        total_cells = size * size

        def to_index(row: int, col: int) -> int:
            return row * size + col

        clue_by_index: dict[int, int] = {}
        for (row, col), value in clues.items():
            if row < 0 or row >= size or col < 0 or col >= size:
                return ZipSolveResult(
                    solved=False,
                    path=None,
                    directions=None,
                    iterations=0,
                    error=f"Clue cell ({row}, {col}) is out of bounds.",
                )

            index = to_index(row, col)
            if index in clue_by_index:
                return ZipSolveResult(
                    solved=False,
                    path=None,
                    directions=None,
                    iterations=0,
                    error=f"Multiple clues mapped to cell ({row}, {col}).",
                )

            clue_by_index[index] = int(value)

        clue_order = sorted(clue_values)
        index_by_clue_value = {value: index for index, value in clue_by_index.items()}

        if 1 not in index_by_clue_value:
            return ZipSolveResult(
                solved=False,
                path=None,
                directions=None,
                iterations=0,
                error="Could not locate clue 1 on the board.",
            )

        start_index = index_by_clue_value[1]
        neighbors: list[list[int]] = [[] for _ in range(total_cells)]

        for row in range(size):
            for col in range(size):
                index = to_index(row, col)

                if row > 0 and not horizontal[row - 1][col]:
                    neighbors[index].append(to_index(row - 1, col))
                if row < size - 1 and not horizontal[row][col]:
                    neighbors[index].append(to_index(row + 1, col))
                if col > 0 and not vertical[row][col - 1]:
                    neighbors[index].append(to_index(row, col - 1))
                if col < size - 1 and not vertical[row][col]:
                    neighbors[index].append(to_index(row, col + 1))

        all_mask = (1 << total_cells) - 1
        self._iterations = 0
        failed_states: set[tuple[int, int, int]] = set()

        def clue_value_for(index: int) -> int | None:
            return clue_by_index.get(index)

        def required_clue_value(required_position: int) -> int | None:
            if required_position >= len(clue_order):
                return None
            return clue_order[required_position]

        def available_mask(visited_mask: int) -> int:
            return all_mask ^ visited_mask

        def is_unvisited(index: int, visited_mask: int) -> bool:
            return ((visited_mask >> index) & 1) == 0

        def is_node_allowed_for_reachability(index: int, required_position: int, target_index: int) -> bool:
            if index == target_index:
                return True

            clue_value = clue_value_for(index)
            if clue_value is None:
                return True

            next_required_value = required_clue_value(required_position)
            if next_required_value is None:
                return True

            return clue_value < next_required_value

        def residual_connected(head: int, visited_mask: int) -> bool:
            remain = available_mask(visited_mask)
            if remain == 0:
                return True

            stack = [head]
            seen = {head}

            while stack:
                current = stack.pop()
                for neighbor in neighbors[current]:
                    if neighbor != head and not is_unvisited(neighbor, visited_mask):
                        continue
                    if neighbor in seen:
                        continue
                    seen.add(neighbor)
                    stack.append(neighbor)

            unvisited_count = remain.bit_count()
            return len(seen) == unvisited_count + 1

        def next_required_reachable(head: int, visited_mask: int, required_position: int) -> bool:
            target_value = required_clue_value(required_position)
            if target_value is None:
                return True

            target_index = index_by_clue_value[target_value]
            if not is_unvisited(target_index, visited_mask):
                return True

            stack = [head]
            seen = {head}

            while stack:
                current = stack.pop()
                for neighbor in neighbors[current]:
                    if neighbor == head:
                        continue
                    if not is_unvisited(neighbor, visited_mask):
                        continue
                    if not is_node_allowed_for_reachability(neighbor, required_position, target_index):
                        continue
                    if neighbor in seen:
                        continue
                    if neighbor == target_index:
                        return True
                    seen.add(neighbor)
                    stack.append(neighbor)

            return False

        def residual_degree_ok(head: int, visited_mask: int) -> bool:
            remain = available_mask(visited_mask)
            if remain == 0:
                return True

            degree_one_nodes = 0

            for node in range(total_cells):
                if not is_unvisited(node, visited_mask):
                    continue

                degree = 0
                for neighbor in neighbors[node]:
                    if neighbor == head or is_unvisited(neighbor, visited_mask):
                        degree += 1

                if degree < 1:
                    return False
                if degree == 1:
                    degree_one_nodes += 1
                    if degree_one_nodes > 1:
                        return False

            return True

        def legal_moves(head: int, visited_mask: int, required_position: int) -> list[tuple[int, int]]:
            candidates: list[tuple[int, int]] = []
            next_required_value = required_clue_value(required_position)

            for neighbor in neighbors[head]:
                if not is_unvisited(neighbor, visited_mask):
                    continue

                clue_value = clue_value_for(neighbor)
                if clue_value is not None and clue_value != next_required_value:
                    continue

                next_position = required_position + 1 if clue_value is not None else required_position
                candidates.append((neighbor, next_position))

            if not candidates:
                return []

            ranked: list[tuple[int, int, int, int]] = []

            for neighbor, next_position in candidates:
                next_required = required_clue_value(next_position)
                if next_required is not None:
                    target_index = index_by_clue_value[next_required]
                    target_row, target_col = divmod(target_index, size)
                    row, col = divmod(neighbor, size)
                    target_distance = abs(target_row - row) + abs(target_col - col)
                else:
                    target_distance = 0

                next_visited = visited_mask | (1 << neighbor)
                onward = 0
                upcoming_required = required_clue_value(next_position)

                for after in neighbors[neighbor]:
                    if not is_unvisited(after, next_visited):
                        continue
                    after_clue = clue_value_for(after)
                    if after_clue is not None and after_clue != upcoming_required:
                        continue
                    onward += 1

                ranked.append((onward, target_distance, neighbor, next_position))

            ranked.sort(key=lambda item: (item[0], item[1]))
            return [(neighbor, next_position) for _, _, neighbor, next_position in ranked]

        def dfs(head: int, visited_mask: int, required_position: int, steps: int) -> tuple[int, ...] | None:
            self._iterations += 1

            state_key = (head, visited_mask, required_position)
            if state_key in failed_states:
                return None

            if steps == total_cells:
                if required_position == len(clue_order):
                    return (head,)
                failed_states.add(state_key)
                return None

            if not residual_connected(head, visited_mask):
                failed_states.add(state_key)
                return None

            if not residual_degree_ok(head, visited_mask):
                failed_states.add(state_key)
                return None

            if not next_required_reachable(head, visited_mask, required_position):
                failed_states.add(state_key)
                return None

            for neighbor, next_position in legal_moves(head, visited_mask, required_position):
                next_visited = visited_mask | (1 << neighbor)
                suffix = dfs(neighbor, next_visited, next_position, steps + 1)
                if suffix is None:
                    continue
                return (head,) + suffix

            failed_states.add(state_key)
            return None

        path_indices = dfs(
            head=start_index,
            visited_mask=(1 << start_index),
            required_position=1,
            steps=1,
        )

        if path_indices is None:
            return ZipSolveResult(
                solved=False,
                path=None,
                directions=None,
                iterations=self._iterations,
                error="No valid Zip path found.",
            )

        path_cells = [divmod(index, size) for index in path_indices]
        directions = self._path_directions(path_cells)

        return ZipSolveResult(
            solved=True,
            path=path_cells,
            directions=directions,
            iterations=self._iterations,
            error=None,
        )

    def _path_directions(self, path: list[tuple[int, int]]) -> list[Direction]:
        directions: list[Direction] = []

        for (row_a, col_a), (row_b, col_b) in zip(path, path[1:]):
            if row_b == row_a - 1 and col_b == col_a:
                directions.append("up")
            elif row_b == row_a + 1 and col_b == col_a:
                directions.append("down")
            elif row_b == row_a and col_b == col_a - 1:
                directions.append("left")
            elif row_b == row_a and col_b == col_a + 1:
                directions.append("right")
            else:
                raise ValueError(
                    f"Non-adjacent path step detected: ({row_a}, {col_a}) -> ({row_b}, {col_b})."
                )

        return directions
