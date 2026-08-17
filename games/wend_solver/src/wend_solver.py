from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, TypeAlias


Cell: TypeAlias = tuple[int, int]
Board: TypeAlias = list[list[str | None]]
LetterOptions: TypeAlias = Mapping[Cell, Sequence[tuple[str, float]]]

_END = "__end__"


@dataclass(frozen=True, slots=True)
class WendPathCandidate:
    word: str
    path: tuple[Cell, ...]
    ocr_cost: float = 0.0

    @property
    def cells(self) -> frozenset[Cell]:
        return frozenset(self.path)


@dataclass(frozen=True, slots=True)
class WendSolution:
    words: tuple[WendPathCandidate, ...]


class WendSolver:
    def __init__(self, dictionary: Iterable[str]) -> None:
        self.dictionary = tuple(self._normalize_word(word) for word in dictionary)

    def solve(
        self,
        board: Board,
        lengths: Iterable[int],
        *,
        letter_options: LetterOptions | None = None,
        max_solutions: int = 25,
    ) -> list[WendSolution]:
        normalized_board = self._normalize_board(board)
        target_lengths = tuple(int(length) for length in lengths)
        if not target_lengths:
            return []

        all_cells = frozenset(
            (row_index, col_index)
            for row_index, row in enumerate(normalized_board)
            for col_index, value in enumerate(row)
            if value is not None
        )
        if sum(target_lengths) != len(all_cells):
            return []

        length_counts = Counter(target_lengths)
        candidates = self.find_candidates(normalized_board, length_counts.keys(), letter_options=letter_options)
        candidates_by_length: dict[int, list[WendPathCandidate]] = defaultdict(list)
        for candidate in candidates:
            candidates_by_length[len(candidate.word)].append(candidate)

        for length in length_counts:
            if not candidates_by_length[length]:
                return []

        solutions: list[WendSolution] = []
        cell_indices = {cell: index for index, cell in enumerate(sorted(all_cells))}
        all_cells_mask = (1 << len(cell_indices)) - 1
        candidate_masks = {
            candidate: sum(1 << cell_indices[cell] for cell in candidate.path)
            for candidate in candidates
        }
        candidates_by_cell: dict[Cell, list[WendPathCandidate]] = defaultdict(list)
        for candidate in candidates:
            for cell in candidate.path:
                candidates_by_cell[cell].append(candidate)

        best_cost_by_state: dict[tuple[int, tuple[tuple[int, int], ...]], float] = {}
        solution_costs: list[float] = []

        def backtrack(
            used_mask: int,
            remaining: Counter[int],
            chosen: list[WendPathCandidate],
            cost: float,
        ) -> None:
            state = (used_mask, tuple(sorted((length, count) for length, count in remaining.items() if count > 0)))
            previous_cost = best_cost_by_state.get(state)
            if previous_cost is not None and cost > previous_cost + 1e-9:
                return
            best_cost_by_state[state] = min(cost, previous_cost) if previous_cost is not None else cost

            if len(solution_costs) >= max_solutions and cost >= solution_costs[-1] - 1e-9:
                return

            if not remaining:
                if used_mask == all_cells_mask:
                    insertion_index = next(
                        (index for index, existing_cost in enumerate(solution_costs) if cost < existing_cost),
                        len(solution_costs),
                    )
                    solution_costs.insert(insertion_index, cost)
                    solutions.insert(insertion_index, WendSolution(words=tuple(chosen)))
                    del solution_costs[max_solutions:]
                    del solutions[max_solutions:]
                return

            uncovered_cells = (
                cell for cell, index in cell_indices.items() if not used_mask & (1 << index)
            )
            compatible_by_cell: list[tuple[int, Cell, list[WendPathCandidate]]] = []
            for cell in uncovered_cells:
                compatible = [
                    candidate
                    for candidate in candidates_by_cell[cell]
                    if remaining.get(len(candidate.word), 0) > 0
                    and not candidate_masks[candidate] & used_mask
                ]
                compatible_by_cell.append((len(compatible), cell, compatible))

            if not compatible_by_cell:
                return
            _, _, compatible_candidates = min(compatible_by_cell, key=lambda item: item[0])
            if not compatible_candidates:
                return

            for candidate in sorted(compatible_candidates, key=lambda item: item.ocr_cost):
                length = len(candidate.word)
                next_remaining = remaining.copy()
                next_remaining[length] -= 1
                if next_remaining[length] == 0:
                    del next_remaining[length]

                chosen.append(candidate)
                backtrack(
                    used_mask | candidate_masks[candidate],
                    next_remaining,
                    chosen,
                    cost + candidate.ocr_cost,
                )
                chosen.pop()

        backtrack(0, length_counts, [], 0.0)
        return solutions

    def find_candidates(
        self,
        board: Board,
        lengths: Iterable[int],
        *,
        letter_options: LetterOptions | None = None,
    ) -> list[WendPathCandidate]:
        normalized_board = self._normalize_board(board)
        target_lengths = {int(length) for length in lengths}
        if not target_lengths:
            return []

        trie = self._build_trie(target_lengths)
        max_length = max(target_lengths)
        normalized_options = self._normalize_letter_options(normalized_board, letter_options)
        candidates: dict[tuple[str, tuple[Cell, ...]], WendPathCandidate] = {}

        def dfs(
            row: int,
            col: int,
            node: dict[str, object],
            path: list[Cell],
            used: set[Cell],
            cost: float,
        ) -> None:
            for letter, letter_cost in normalized_options.get((row, col), ()):
                next_node = node.get(letter)
                if not isinstance(next_node, dict):
                    continue

                path.append((row, col))
                used.add((row, col))
                next_cost = cost + letter_cost

                word = next_node.get(_END)
                if isinstance(word, str) and len(word) in target_lengths:
                    candidate_path = tuple(path)
                    key = (word, candidate_path)
                    existing = candidates.get(key)
                    if existing is None or next_cost < existing.ocr_cost:
                        candidates[key] = WendPathCandidate(word=word, path=candidate_path, ocr_cost=next_cost)

                if len(path) < max_length:
                    for next_row, next_col in self._neighbors(normalized_board, row, col):
                        if (next_row, next_col) not in used:
                            dfs(next_row, next_col, next_node, path, used, next_cost)

                used.remove((row, col))
                path.pop()

        for row_index, row in enumerate(normalized_board):
            for col_index, value in enumerate(row):
                if value is not None:
                    dfs(row_index, col_index, trie, [], set(), 0.0)

        return sorted(candidates.values(), key=lambda candidate: (len(candidate.word), candidate.word, candidate.path))

    @classmethod
    def _normalize_letter_options(
        cls,
        board: Board,
        letter_options: LetterOptions | None,
    ) -> dict[Cell, tuple[tuple[str, float], ...]]:
        normalized: dict[Cell, tuple[tuple[str, float], ...]] = {}
        for row_index, row in enumerate(board):
            for col_index, value in enumerate(row):
                if value is None:
                    continue
                cell = (row_index, col_index)
                supplied = letter_options.get(cell, ()) if letter_options is not None else ()
                options: dict[str, float] = {}
                for letter, cost in supplied:
                    normalized_letter = cls._normalize_word(letter)
                    if len(normalized_letter) != 1 or not normalized_letter.isalpha():
                        continue
                    options[normalized_letter] = min(float(cost), options.get(normalized_letter, float("inf")))
                if value != "?":
                    options[value] = min(0.0, options.get(value, float("inf")))
                elif not options:
                    options = {letter: 1.0 for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
                normalized[cell] = tuple(sorted(options.items(), key=lambda item: item[1]))
        return normalized

    def _build_trie(self, target_lengths: set[int]) -> dict[str, object]:
        trie: dict[str, object] = {}
        for word in self.dictionary:
            if len(word) not in target_lengths:
                continue
            node = trie
            for letter in word:
                child = node.setdefault(letter, {})
                if not isinstance(child, dict):
                    raise TypeError("Invalid trie node")
                node = child
            node[_END] = word
        return trie

    @staticmethod
    def _neighbors(board: Board, row: int, col: int) -> Iterable[Cell]:
        for row_delta, col_delta in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            next_row = row + row_delta
            next_col = col + col_delta
            if 0 <= next_row < len(board) and 0 <= next_col < len(board[next_row]):
                if board[next_row][next_col] is not None:
                    yield next_row, next_col

    @classmethod
    def _normalize_board(cls, board: Board) -> Board:
        if not board:
            raise ValueError("Board cannot be empty.")

        width = len(board[0])
        if width == 0:
            raise ValueError("Board rows cannot be empty.")

        normalized: Board = []
        for row in board:
            if len(row) != width:
                raise ValueError("Board must be rectangular.")
            normalized.append([None if value is None else cls._normalize_word(value) for value in row])
        return normalized

    @staticmethod
    def _normalize_word(value: str) -> str:
        return str(value).strip().upper()
