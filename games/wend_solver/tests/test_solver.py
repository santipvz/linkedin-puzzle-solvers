from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[3]
GAMES_ROOT = REPO_ROOT / "games"
if str(GAMES_ROOT) not in sys.path:
    sys.path.insert(0, str(GAMES_ROOT))

from wend_solver.src.dictionary import load_wend_dictionary
from wend_solver.src.image_parser import WendImageParser
from wend_solver.src.wend_solver import WendSolver


class WendSolverTests(unittest.TestCase):
    def test_solves_linkedin_example_board(self) -> None:
        board = [
            ["E", "R", "O", "R", "E", "T"],
            ["C", "A", "S", "A", "U", "S"],
            ["O", "T", None, None, "Q", "I"],
            ["N", "N", None, None, "S", "G"],
            ["I", "E", "G", "A", "M", "O"],
            ["H", "R", "B", "I", "O", "L"],
        ]
        dictionary = ["SQUARE", "MAGENTA", "BIOLOGIST", "RHINOCEROS"]

        solutions = WendSolver(dictionary).solve(board, [6, 7, 9, 10])

        self.assertEqual(1, len(solutions))
        self.assertEqual(
            {"SQUARE", "MAGENTA", "BIOLOGIST", "RHINOCEROS"},
            {candidate.word for candidate in solutions[0].words},
        )

    def test_rejects_diagonal_only_words(self) -> None:
        board = [
            ["A", "X"],
            ["X", "B"],
        ]

        candidates = WendSolver(["AB"]).find_candidates(board, [2])

        self.assertEqual([], candidates)

    def test_supports_duplicate_lengths(self) -> None:
        board = [
            ["A", "B"],
            ["C", "D"],
        ]

        solutions = WendSolver(["AB", "CD", "AC", "BD"]).solve(board, [2, 2])

        solution_word_sets = {frozenset(candidate.word for candidate in solution.words) for solution in solutions}
        self.assertIn(frozenset({"AB", "CD"}), solution_word_sets)
        self.assertIn(frozenset({"AC", "BD"}), solution_word_sets)

    def test_uses_ocr_alternatives_to_form_valid_words(self) -> None:
        board = [
            ["C", "A"],
            ["E", "T"],
        ]
        letter_options = {(0, 0): [("C", 0.0), ("G", 0.02)]}

        solutions = WendSolver(["GATE"]).solve(board, [4], letter_options=letter_options)

        self.assertEqual(1, len(solutions))
        self.assertEqual("GATE", solutions[0].words[0].word)
        self.assertAlmostEqual(0.02, solutions[0].words[0].ocr_cost)


class WendParserTests(unittest.TestCase):
    def test_parses_synthetic_example_capture(self) -> None:
        board = [
            ["E", "R", "O", "R", "E", "T"],
            ["C", "A", "S", "A", "U", "S"],
            ["O", "T", None, None, "Q", "I"],
            ["N", "N", None, None, "S", "G"],
            ["I", "E", "G", "A", "M", "O"],
            ["H", "R", "B", "I", "O", "L"],
        ]
        image = Image.new("RGB", (520, 690), (245, 246, 248))
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        x0, y0, cell = 40, 30, 70
        draw.rectangle((x0, y0, x0 + cell * 6, y0 + cell * 6), outline=(45, 48, 52), width=5)
        for index in range(1, 6):
            x = x0 + index * cell
            y = y0 + index * cell
            draw.line((x, y0, x, y0 + cell * 6), fill=(220, 224, 228), width=1)
            draw.line((x0, y, x0 + cell * 6, y), fill=(220, 224, 228), width=1)

        for row_index, row in enumerate(board):
            for col_index, letter in enumerate(row):
                left = x0 + col_index * cell
                top = y0 + row_index * cell
                if letter is None:
                    draw.rectangle((left, top, left + cell, top + cell), fill=(175, 175, 175), outline=(65, 65, 65), width=2)
                    continue
                bbox = draw.textbbox((0, 0), letter, font=font)
                draw.text(
                    (left + (cell - (bbox[2] - bbox[0])) / 2 - bbox[0], top + (cell - (bbox[3] - bbox[1])) / 2 - bbox[1]),
                    letter,
                    font=font,
                    fill=(10, 10, 10),
                )

        slot_y = y0 + cell * 6 + 60
        for row_index, length in enumerate((6, 7, 9, 10)):
            for col in range(length):
                x = x0 + col * 26
                y = slot_y + row_index * 28
                draw.rounded_rectangle((x, y, x + 22, y + 22), radius=4, fill=(218, 218, 218))

        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            image.save(tmp.name)
            parsed = WendImageParser().parse_image(tmp.name)

        self.assertEqual([6, 7, 9, 10], parsed["lengths"])
        self.assertEqual(board, parsed["board"])

    def test_detects_variable_board_sizes_from_grid_lines(self) -> None:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        parser = WendImageParser()

        for board_size in (5, 8):
            side = 400
            cell = side / board_size
            image = Image.new("RGB", (side, side), (245, 246, 248))
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, side - 1, side - 1), outline=(45, 48, 52), width=5)
            for index in range(1, board_size):
                position = round(index * cell)
                draw.line((position, 0, position, side), fill=(210, 214, 218), width=2)
                draw.line((0, position, side, position), fill=(210, 214, 218), width=2)
            for row in range(board_size):
                for col in range(board_size):
                    letter = chr(ord("A") + (row * board_size + col) % 26)
                    bbox = draw.textbbox((0, 0), letter, font=font)
                    draw.text(
                        (
                            col * cell + (cell - (bbox[2] - bbox[0])) / 2 - bbox[0],
                            row * cell + (cell - (bbox[3] - bbox[1])) / 2 - bbox[1],
                        ),
                        letter,
                        font=font,
                        fill=(10, 10, 10),
                    )

            with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                image.save(tmp.name)
                parsed = parser.parse_image(tmp.name)

            with self.subTest(board_size=board_size):
                self.assertEqual(board_size, parsed["board_size"])
                self.assertEqual(board_size * board_size, parsed["visible_cells"])


class WendDictionaryTests(unittest.TestCase):
    def test_loads_repository_wordlist(self) -> None:
        words = set(load_wend_dictionary())

        self.assertIn("SQUARE", words)
        self.assertIn("MAGENTA", words)
        self.assertIn("BIOLOGIST", words)
        self.assertIn("RHINOCEROS", words)

    def test_supports_env_wordlist_override(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as tmp:
            tmp.write("customword\nnot-a-word\nAB\n")
            tmp.flush()

            with patch.dict("os.environ", {"WEND_WORDLIST_PATH": tmp.name}):
                words = set(load_wend_dictionary())

        self.assertIn("CUSTOMWORD", words)
        self.assertNotIn("NOT-A-WORD", words)
        self.assertNotIn("AB", words)


class WendHistoricalRegressionTests(unittest.TestCase):
    CASES = (
        ("2026-07-03/088d4971a2053645a99c74705d41c9d426f5c46ce2f67852d766d7ccc852ddd8.png", 6, 32),
        ("2026-07-03/9f02d7fb1d728be02f0bce79b51af60166cd9b945aa84c3158efa673a559e20f.png", 6, 32),
        ("2026-07-04/f590d330baed974e0c050a19cbed10d7802fc7c2c2ee330d5ec75983b0c9cc73.png", 7, 41),
        ("2026-07-05/3a7bc21cf9e85f77c261b489c5fa81ffd6b4cf37268126dc5c582bd9b558cba8.png", 8, 50),
        ("2026-07-06/296ed74a8c92fe5b69f9961660947f934570ccd5b914d636cb5bc27c2524855e.png", 5, 18),
        ("2026-07-06/a98793859a34b129be32409eab232a250045fc8f61670f31b7357219a34e618a.png", 5, 18),
        ("2026-07-09/8b7ae6991d346794de20c243dc25ee40396c3472af740a0c1abcfda537699b35.png", 6, 30),
        ("2026-07-23/077d8c0ff27040697a9f118049320cf566276f1a7946b7efdd369b26708bc4c3.png", 6, 26),
    )

    def test_detects_historical_board_sizes_and_open_cells(self) -> None:
        dataset_root = REPO_ROOT / "datasets" / "wend"
        if not dataset_root.exists():
            self.skipTest("Local Wend capture dataset is not available.")

        parser = WendImageParser()
        for relative_path, expected_size, expected_visible in self.CASES:
            image_path = dataset_root / relative_path
            if not image_path.exists():
                self.skipTest(f"Missing local Wend capture: {relative_path}")
            with self.subTest(capture=relative_path):
                parsed = parser.parse_image(image_path)
                self.assertEqual(expected_size, parsed["board_size"])
                self.assertEqual(expected_visible, parsed["visible_cells"])


if __name__ == "__main__":
    unittest.main()
