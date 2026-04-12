from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PATCHES_ROOT = REPO_ROOT / "games" / "patches_solver"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(PATCHES_ROOT) not in sys.path:
    sys.path.insert(0, str(PATCHES_ROOT))

from services.solver_api.app.workers.solve_patches_worker import solve as solve_patches_worker
from src.image_parser import PatchesImageParser
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


class PatchesParserIntegrationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
