from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[3]
PATCHES_ROOT = REPO_ROOT / "games" / "patches_solver"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.solver_api.app.workers.common import activate_game_import_context

activate_game_import_context(PATCHES_ROOT)

from services.solver_api.app.workers.solve_patches_worker import solve as solve_patches_worker
from src.image_parser import PatchesImageParser, _get_ocr
from src.patches_solver import PatchesClue, PatchesSolver


class PatchesSolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.solver = PatchesSolver()

    def test_solves_basic_manual_board(self) -> None:
        result = self.solver.solve(
            board_size=2,
            clues=[
                PatchesClue(row=0, col=0, shape="wide", area=2),
                PatchesClue(row=1, col=1, shape="wide", area=2),
            ],
        )

        self.assertTrue(result.solved)
        self.assertIsNotNone(result.regions)
        self.assertEqual(2, len(result.regions or []))
        self.assertEqual([2, 2], sorted(region.area for region in (result.regions or [])))

    def test_proves_a_unique_tiling_when_counting_two_solutions(self) -> None:
        result = self.solver.solve(2, [PatchesClue(0, 0, "wide", 2), PatchesClue(1, 1, "wide", 2)], max_solutions=2)
        self.assertTrue(result.solved)
        self.assertEqual(1, result.solution_count)
        self.assertTrue(result.solution_count_is_exact)

    def test_multiple_tilings_are_not_reported_as_unique(self) -> None:
        result = self.solver.solve(2, [PatchesClue(0, 0), PatchesClue(1, 1)], max_solutions=2)
        self.assertTrue(result.solved)
        self.assertEqual(2, result.solution_count)
        self.assertFalse(result.solution_count_is_exact)
        self.assertEqual(4, sum(region.area for region in result.regions or []))

    def test_rejects_invalid_solution_limits(self) -> None:
        for limit in (0, -1, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.solver.solve(2, [], max_solutions=limit)


class PatchesParserIntegrationTests(unittest.TestCase):
    def test_worker_solves_sparse_numbered_eight_by_eight_capture(self) -> None:
        payload = solve_patches_worker(PATCHES_ROOT / "examples" / "sample4.png")
        self.assertTrue(payload["solved"], payload.get("error"))
        self.assertEqual(8, payload["board_size"])
        self.assertEqual(14, payload["details"]["clue_count"])
        self.assertEqual(4, payload["details"]["numbered_clue_count"])
        self.assertTrue(payload["details"]["sparse_clues_verified"])
        self.assertTrue(payload["details"]["unique_solution"])
        self.assertFalse(payload["details"]["ocr_recovery_applied"])
        self.assertEqual(0, payload["details"]["relaxed_square_clues"])
        covered = set()
        for region in payload["regions"]:
            cells = {(r, c) for r in range(region["top"], region["top"] + region["height"])
                     for c in range(region["left"], region["left"] + region["width"])}
            self.assertFalse(covered & cells)
            covered.update(cells)
        self.assertEqual(64, len(covered))

    def test_current_translucent_cross_clues_keep_their_shape_and_numbers(self) -> None:
        payload = solve_patches_worker(Path(__file__).parent / "fixtures" / "linkedin-2026-10-28.jpg")
        self.assertTrue(payload["solved"], payload.get("error"))
        self.assertTrue(payload["details"]["unique_solution"])
        self.assertEqual(0, payload["details"]["relaxed_square_clues"])
        self.assertEqual(
            [(0, 2, "any", 5), (0, 3, "any", None), (2, 1, "tall", None),
             (2, 4, "tall", None), (3, 1, "square", None), (3, 4, "tall", None),
             (5, 2, "any", None), (5, 3, "any", 3)],
            [(c["row"], c["col"], c["shape"], c["value"]) for c in payload["clues"]],
        )

    def test_ocr_reads_white_digit_on_gray_badge(self) -> None:
        image = Image.new("RGB", (54, 54), (132, 150, 158))
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        left, top, right, bottom = draw.textbbox((0, 0), "3", font=font)
        draw.text(
            (((54 - (right - left)) // 2) - left, ((54 - (bottom - top)) // 2) - top),
            "3",
            font=font,
            fill=(255, 255, 255),
        )

        roi = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        prediction = _get_ocr().predict(roi, max_value=49)

        self.assertIsNotNone(prediction)
        self.assertEqual(3, prediction.value if prediction is not None else None)

    def test_parser_detects_clues_on_sample(self) -> None:
        parser = PatchesImageParser(board_size=6)
        sample_path = PATCHES_ROOT / "examples" / "sample1.png"
        parsed = parser.parse_image(sample_path)

        self.assertEqual(6, int(parsed["board_size"]))
        self.assertGreater(len(parsed["clues"]), 0)

    def test_worker_solves_all_samples(self) -> None:
        sample_paths = [
            PATCHES_ROOT / "examples" / "sample1.png",
            PATCHES_ROOT / "examples" / "sample2.png",
            PATCHES_ROOT / "examples" / "sample3.png",
        ]

        for sample_path in sample_paths:
            with self.subTest(sample=str(sample_path.name)):
                self.assertTrue(sample_path.exists(), f"Missing sample image: {sample_path}")
                payload = solve_patches_worker(sample_path)

                self.assertTrue(payload.get("solved"), payload.get("error"))
                self.assertEqual(6, int(payload.get("board_size") or 0))
                self.assertGreater(len(payload.get("regions") or []), 0)



PAGE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "linkedin-2026-11-20.json"
# LinkedIn's own answer for the 2026-11-20 puzzle, as the cells of each region.
OFFICIAL_2026_11_20 = [
    [0, 7, 14, 21, 28], [1, 2, 8, 9], [3, 4, 5], [6, 13], [10, 11], [12, 19, 26], [15, 16, 17, 18], [20, 27],
    [22, 23, 29, 30], [24, 25, 31, 32], [33, 34], [35, 36], [37, 38, 39, 40, 41], [42, 43, 44, 45, 46], [47, 48],
]


class PatchesPageBoardTests(unittest.TestCase):
    def test_worker_solves_a_page_board_without_the_image(self) -> None:
        board = json.loads(PAGE_FIXTURE.read_text())
        response = solve_patches_worker(Path("unused.png"), parsed_board=board)

        self.assertTrue(response["solved"], response["error"])
        self.assertEqual(response["details"]["input_source"], "page")
        self.assertTrue(response["details"]["unique_solution"])
        regions = sorted(
            sorted(row * 7 + col for row in range(r["top"], r["top"] + r["height"]) for col in range(r["left"], r["left"] + r["width"]))
            for r in response["regions"]
        )
        self.assertEqual(regions, sorted(OFFICIAL_2026_11_20))

    def test_page_shapes_are_not_relaxed(self) -> None:
        # Rows 1-3 belong to the 12-cell clue, so the square clue would need the 1x4 top row.
        # The OCR path relaxes square clues for misread shapes; page shapes are exact.
        board = {"size": 4, "clues": [[0, "square", None], [4, "any", 12]]}
        response = solve_patches_worker(Path("unused.png"), parsed_board=board)
        self.assertFalse(response["solved"])
        relaxed = {"size": 4, "clues": [[0, "any", None], [4, "any", 12]]}
        self.assertTrue(solve_patches_worker(Path("unused.png"), parsed_board=relaxed)["solved"])

    def test_invalid_page_boards_are_rejected(self) -> None:
        from services.solver_api.app.domain.errors import InvalidBoard
        from services.solver_api.app.domain.patches_board import validate_patches_board

        for payload in (
            None, {}, {"size": 6},
            {"size": 3, "clues": [[0, "any", None]]},
            {"size": 6, "clues": []},
            {"size": 6, "clues": [[36, "any", None]]},
            {"size": 6, "clues": [[0, "round", None]]},
            {"size": 6, "clues": [[0, "any", 0]]},
            {"size": 6, "clues": [[0, "any", None], [0, "square", 4]]},
            {"size": 6, "clues": [[0, "any", None]], "solution": []},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(InvalidBoard):
                    validate_patches_board(payload)
                if isinstance(payload, dict):
                    self.assertFalse(solve_patches_worker(Path("unused.png"), parsed_board=payload)["solved"])

if __name__ == "__main__":
    unittest.main()
