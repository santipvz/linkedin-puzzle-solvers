from __future__ import annotations

from dataclasses import dataclass, replace
from math import isqrt
from typing import Iterable, TypedDict


VALID_SHAPES = {"any", "square", "wide", "tall"}


class PatchesClueInput(TypedDict, total=False):
    row: int
    col: int
    shape: str
    area: int | None
    value: int | None


@dataclass(slots=True)
class PatchesClue:
    row: int
    col: int
    shape: str = "any"
    area: int | None = None


@dataclass(slots=True)
class PatchesRegion:
    top: int
    left: int
    height: int
    width: int
    clue_row: int
    clue_col: int
    area: int


@dataclass(slots=True)
class PatchesSolveResult:
    solved: bool
    regions: list[PatchesRegion] | None
    iterations: int
    error: str | None = None
    relaxed_square_clues: int = 0
    solution_count: int = 0
    solution_count_is_exact: bool = True


@dataclass(slots=True)
class _CandidateRegion:
    top: int
    left: int
    height: int
    width: int
    area: int
    mask: int


class PatchesSolver:
    def __init__(self) -> None:
        self._iterations = 0

    @property
    def iterations(self) -> int:
        return self._iterations

    def solve(self, board_size: int, clues: Iterable[PatchesClue | PatchesClueInput], *, max_solutions: int = 1) -> PatchesSolveResult:
        if isinstance(max_solutions, bool) or not isinstance(max_solutions, int) or max_solutions < 1:
            raise ValueError("max_solutions must be a positive integer.")
        normalized_size = int(board_size)
        normalized_clues, error = self._normalize_clues(clues)
        if error:
            return PatchesSolveResult(solved=False, regions=None, iterations=0, error=error)

        primary_result = self._solve_once(normalized_size, normalized_clues, max_solutions)
        if primary_result.solved:
            return primary_result

        square_indexes = [index for index, clue in enumerate(normalized_clues) if clue.shape == "square"]
        if not square_indexes:
            return primary_result

        relaxed_clues = [replace(clue, shape="any") if clue.shape == "square" else clue for clue in normalized_clues]
        relaxed_result = self._solve_once(normalized_size, relaxed_clues, max_solutions)
        relaxed_result.relaxed_square_clues = len(square_indexes)
        relaxed_result.iterations += primary_result.iterations

        if relaxed_result.solved:
            return relaxed_result

        primary_result.relaxed_square_clues = len(square_indexes)
        primary_result.iterations += relaxed_result.iterations
        return primary_result

    def _solve_once(self, board_size: int, clues: list[PatchesClue], max_solutions: int) -> PatchesSolveResult:
        if board_size <= 0:
            return PatchesSolveResult(
                solved=False,
                regions=None,
                iterations=0,
                error="Board size must be positive.",
            )

        if not clues:
            return PatchesSolveResult(
                solved=False,
                regions=None,
                iterations=0,
                error="No clues detected for Patches board.",
            )

        for clue in clues:
            if clue.row < 0 or clue.row >= board_size or clue.col < 0 or clue.col >= board_size:
                return PatchesSolveResult(
                    solved=False,
                    regions=None,
                    iterations=0,
                    error=f"Clue cell ({clue.row}, {clue.col}) is out of bounds.",
                )

        clue_positions: dict[tuple[int, int], int] = {}
        for index, clue in enumerate(clues):
            key = (clue.row, clue.col)
            if key in clue_positions:
                return PatchesSolveResult(
                    solved=False,
                    regions=None,
                    iterations=0,
                    error=f"Multiple clues share cell ({clue.row}, {clue.col}).",
                )
            clue_positions[key] = index

        total_cells = board_size * board_size
        clue_count = len(clues)
        numbered_area_total = sum(int(clue.area or 0) for clue in clues if clue.area is not None)
        if numbered_area_total > total_cells:
            return PatchesSolveResult(
                solved=False,
                regions=None,
                iterations=0,
                error="Sum of numbered clue areas exceeds board size.",
            )

        candidates_by_clue: list[list[_CandidateRegion]] = []
        for index, clue in enumerate(clues):
            candidates = self._build_candidates_for_clue(
                clue_index=index,
                clue=clue,
                board_size=board_size,
                clue_positions=clue_positions,
            )
            if not candidates:
                clue_label = f"({clue.row}, {clue.col})"
                return PatchesSolveResult(
                    solved=False,
                    regions=None,
                    iterations=0,
                    error=f"No valid rectangles found for clue at {clue_label}.",
                )

            candidates_by_clue.append(candidates)

        all_mask = (1 << total_cells) - 1
        self._iterations = 0
        assigned: list[_CandidateRegion | None] = [None for _ in range(clue_count)]
        failed_states: set[tuple[int, tuple[int, ...]]] = set()
        solution_count = 0
        first_assignment: list[_CandidateRegion | None] | None = None

        def search(occupied_mask: int, remaining_indexes: tuple[int, ...]) -> bool:
            nonlocal solution_count, first_assignment
            self._iterations += 1

            state_key = (occupied_mask, remaining_indexes)
            if state_key in failed_states:
                return False

            if not remaining_indexes:
                if occupied_mask == all_mask:
                    solution_count += 1
                    if first_assignment is None:
                        first_assignment = list(assigned)
                return solution_count >= max_solutions

            remaining_cell_count = total_cells - occupied_mask.bit_count()

            best_index = -1
            best_candidates: list[_CandidateRegion] | None = None
            min_area_sum = 0
            max_area_sum = 0

            for clue_index in remaining_indexes:
                feasible = [
                    candidate
                    for candidate in candidates_by_clue[clue_index]
                    if (candidate.mask & occupied_mask) == 0
                ]

                if not feasible:
                    failed_states.add(state_key)
                    return False

                candidate_areas = [candidate.area for candidate in feasible]
                min_area_sum += min(candidate_areas)
                max_area_sum += max(candidate_areas)

                if best_candidates is None or len(feasible) < len(best_candidates):
                    best_index = clue_index
                    best_candidates = feasible

            if remaining_cell_count < min_area_sum or remaining_cell_count > max_area_sum:
                failed_states.add(state_key)
                return False

            if best_candidates is None or best_index < 0:
                failed_states.add(state_key)
                return False

            next_remaining = tuple(index for index in remaining_indexes if index != best_index)

            best_candidates.sort(
                key=lambda candidate: (
                    abs((candidate.width / max(1, candidate.height)) - 1.0),
                    -candidate.area,
                    candidate.top,
                    candidate.left,
                )
            )

            count_before = solution_count
            for candidate in best_candidates:
                assigned[best_index] = candidate
                if search(occupied_mask | candidate.mask, next_remaining):
                    return True
                assigned[best_index] = None

            # Only cache unsatisfiable states. Different earlier rectangle choices
            # can reach the same occupied mask and yield distinct valid tilings.
            if solution_count == count_before:
                failed_states.add(state_key)
            return False

        search_capped = search(occupied_mask=0, remaining_indexes=tuple(range(clue_count)))
        if first_assignment is None:
            return PatchesSolveResult(
                solved=False,
                regions=None,
                iterations=self._iterations,
                error="No valid rectangle tiling satisfies all clues.",
            )

        regions: list[PatchesRegion] = []
        for clue, candidate in zip(clues, first_assignment):
            if candidate is None:
                return PatchesSolveResult(
                    solved=False,
                    regions=None,
                    iterations=self._iterations,
                    error="Solver reached incomplete assignment state.",
                )

            regions.append(
                PatchesRegion(
                    top=int(candidate.top),
                    left=int(candidate.left),
                    height=int(candidate.height),
                    width=int(candidate.width),
                    clue_row=int(clue.row),
                    clue_col=int(clue.col),
                    area=int(candidate.area),
                )
            )

        return PatchesSolveResult(
            solved=True,
            regions=regions,
            iterations=self._iterations,
            error=None,
            solution_count=solution_count,
            solution_count_is_exact=not search_capped,
        )

    def _build_candidates_for_clue(
        self,
        clue_index: int,
        clue: PatchesClue,
        board_size: int,
        clue_positions: dict[tuple[int, int], int],
    ) -> list[_CandidateRegion]:
        area = clue.area
        shape = clue.shape

        dimensions: list[tuple[int, int]] = []

        if area is None:
            for height in range(1, board_size + 1):
                for width in range(1, board_size + 1):
                    if self._shape_accepts(shape, height, width):
                        dimensions.append((height, width))
        else:
            for height in range(1, board_size + 1):
                if area % height != 0:
                    continue
                width = area // height
                if width < 1 or width > board_size:
                    continue
                if self._shape_accepts(shape, height, width):
                    dimensions.append((height, width))

        if not dimensions:
            return []

        unique: dict[tuple[int, int, int, int], _CandidateRegion] = {}

        for height, width in dimensions:
            area_value = int(height * width)

            top_min = max(0, clue.row - height + 1)
            top_max = min(clue.row, board_size - height)
            left_min = max(0, clue.col - width + 1)
            left_max = min(clue.col, board_size - width)

            for top in range(top_min, top_max + 1):
                for left in range(left_min, left_max + 1):
                    if self._contains_foreign_clue(
                        clue_index=clue_index,
                        top=top,
                        left=left,
                        height=height,
                        width=width,
                        clue_positions=clue_positions,
                    ):
                        continue

                    mask = self._rectangle_mask(top=top, left=left, height=height, width=width, board_size=board_size)
                    key = (top, left, height, width)
                    unique[key] = _CandidateRegion(
                        top=int(top),
                        left=int(left),
                        height=int(height),
                        width=int(width),
                        area=int(area_value),
                        mask=int(mask),
                    )

        return list(unique.values())

    def _normalize_clues(
        self,
        clues: Iterable[PatchesClue | PatchesClueInput],
    ) -> tuple[list[PatchesClue], str | None]:
        normalized: list[PatchesClue] = []

        for raw in clues:
            if isinstance(raw, PatchesClue):
                row = int(raw.row)
                col = int(raw.col)
                shape = str(raw.shape or "any").strip().lower()
                area = None if raw.area is None else int(raw.area)
            elif isinstance(raw, dict):
                row = int(raw.get("row"))
                col = int(raw.get("col"))
                shape = str(raw.get("shape") or "any").strip().lower()
                area_raw = raw.get("area")
                if area_raw is None and "value" in raw:
                    area_raw = raw.get("value")
                area = None if area_raw is None else int(area_raw)
            else:
                return [], "Unsupported clue payload type."

            if shape not in VALID_SHAPES:
                shape = "any"

            if area is not None and area <= 0:
                area = None

            if shape == "square" and area is not None:
                side = isqrt(area)
                if side * side != area:
                    shape = "any"

            normalized.append(
                PatchesClue(
                    row=int(row),
                    col=int(col),
                    shape=shape,
                    area=area,
                )
            )

        return normalized, None

    @staticmethod
    def _shape_accepts(shape: str, height: int, width: int) -> bool:
        if shape == "square":
            return width == height
        if shape == "wide":
            return width > height
        if shape == "tall":
            return height > width
        return True

    @staticmethod
    def _rectangle_mask(top: int, left: int, height: int, width: int, board_size: int) -> int:
        mask = 0
        for row in range(top, top + height):
            base = row * board_size
            for col in range(left, left + width):
                mask |= 1 << (base + col)
        return mask

    @staticmethod
    def _contains_foreign_clue(
        clue_index: int,
        top: int,
        left: int,
        height: int,
        width: int,
        clue_positions: dict[tuple[int, int], int],
    ) -> bool:
        for row in range(top, top + height):
            for col in range(left, left + width):
                occupant = clue_positions.get((row, col))
                if occupant is not None and occupant != clue_index:
                    return True
        return False
