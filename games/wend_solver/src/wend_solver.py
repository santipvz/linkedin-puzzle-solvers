from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from typing import Iterable, Iterator, Mapping, Sequence, TypeAlias, overload


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


@dataclass(frozen=True, slots=True)
class WendSolveResult:
    solutions: tuple[WendSolution, ...]
    solution_count_is_exact: bool
    solution_limit: int

    def __bool__(self) -> bool:
        return bool(self.solutions)

    def __len__(self) -> int:
        return len(self.solutions)

    def __iter__(self) -> Iterator[WendSolution]:
        return iter(self.solutions)

    @overload
    def __getitem__(self, index: int) -> WendSolution: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[WendSolution, ...]: ...

    def __getitem__(self, index: int | slice) -> WendSolution | tuple[WendSolution, ...]:
        return self.solutions[index]


class WendSolver:
    def __init__(self, dictionary: Iterable[str]) -> None:
        normalized: set[str] = set()
        for word in dictionary:
            candidate = self._normalize_word(word)
            if not candidate or not candidate.isascii() or not candidate.isalpha():
                raise ValueError(f"Invalid Wend dictionary word: {word!r}")
            normalized.add(candidate)
        if not normalized:
            raise ValueError("Wend dictionary cannot be empty.")
        self.dictionary = tuple(sorted(normalized))
        self._tries: dict[frozenset[int], dict[str, object]] = {}

    def solve(
        self,
        board: Board,
        lengths: Iterable[int],
        *,
        letter_options: LetterOptions | None = None,
        max_solutions: int = 25,
    ) -> WendSolveResult:
        if isinstance(max_solutions, bool) or not isinstance(max_solutions, int) or max_solutions <= 0:
            raise ValueError("max_solutions must be a positive integer.")
        normalized_board = self._normalize_board(board)
        target_lengths = tuple(self._normalize_length(length) for length in lengths)
        if not target_lengths:
            return WendSolveResult((), True, max_solutions)

        all_cells = frozenset(
            (row_index, col_index)
            for row_index, row in enumerate(normalized_board)
            for col_index, value in enumerate(row)
            if value is not None
        )
        if sum(target_lengths) != len(all_cells):
            return WendSolveResult((), True, max_solutions)

        length_counts = Counter(target_lengths)
        candidates = self.find_candidates(normalized_board, length_counts.keys(), letter_options=letter_options)
        candidates_by_length: dict[int, list[WendPathCandidate]] = defaultdict(list)
        for candidate in candidates:
            candidates_by_length[len(candidate.word)].append(candidate)

        for length in length_counts:
            if not candidates_by_length[length]:
                return WendSolveResult((), True, max_solutions)

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

        solution_costs: list[float] = []
        search_exhaustive = True

        def backtrack(
            used_mask: int,
            remaining: Counter[int],
            chosen: list[WendPathCandidate],
            cost: float,
        ) -> None:
            nonlocal search_exhaustive

            if len(solution_costs) >= max_solutions and cost >= solution_costs[-1] - 1e-9:
                search_exhaustive = False
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
        return WendSolveResult(tuple(solutions), search_exhaustive, max_solutions)

    def find_candidates(
        self,
        board: Board,
        lengths: Iterable[int],
        *,
        letter_options: LetterOptions | None = None,
    ) -> list[WendPathCandidate]:
        normalized_board = self._normalize_board(board)
        target_lengths = {self._normalize_length(length) for length in lengths}
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
        visible_cells = {
            (row_index, col_index)
            for row_index, row in enumerate(board)
            for col_index, value in enumerate(row)
            if value is not None
        }
        if letter_options is not None:
            invalid_cells = set(letter_options) - visible_cells
            if invalid_cells:
                raise ValueError(f"OCR options reference invalid board cells: {sorted(invalid_cells)!r}")
        for row_index, row in enumerate(board):
            for col_index, value in enumerate(row):
                if value is None:
                    continue
                cell = (row_index, col_index)
                supplied = letter_options.get(cell, ()) if letter_options is not None else ()
                options: dict[str, float] = {}
                for letter, cost in supplied:
                    normalized_letter = cls._normalize_word(letter)
                    if len(normalized_letter) != 1 or not normalized_letter.isascii() or not normalized_letter.isalpha():
                        raise ValueError(f"Invalid OCR letter option at {cell}: {letter!r}")
                    normalized_cost = float(cost)
                    if not math.isfinite(normalized_cost) or normalized_cost < 0.0:
                        raise ValueError(f"Invalid OCR cost at {cell}: {cost!r}")
                    options[normalized_letter] = min(normalized_cost, options.get(normalized_letter, float("inf")))
                if value != "?":
                    options[value] = min(0.0, options.get(value, float("inf")))
                elif not options:
                    options = {letter: 1.0 for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
                normalized[cell] = tuple(sorted(options.items(), key=lambda item: item[1]))
        return normalized

    def _build_trie(self, target_lengths: set[int]) -> dict[str, object]:
        cache_key = frozenset(target_lengths)
        cached = self._tries.get(cache_key)
        if cached is not None:
            return cached
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
        self._tries[cache_key] = trie
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
            normalized_row: list[str | None] = []
            for value in row:
                if value is None:
                    normalized_row.append(None)
                    continue
                normalized_value = cls._normalize_word(value)
                if normalized_value != "?" and (
                    len(normalized_value) != 1
                    or not normalized_value.isascii()
                    or not normalized_value.isalpha()
                ):
                    raise ValueError(f"Invalid Wend board cell: {value!r}")
                normalized_row.append(normalized_value)
            normalized.append(normalized_row)
        return normalized

    @staticmethod
    def _normalize_length(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"Invalid Wend word length: {value!r}")
        return value

    @staticmethod
    def _normalize_word(value: str) -> str:
        return str(value).strip().upper()
