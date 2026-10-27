from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[3]
GAMES_ROOT = REPO_ROOT / "games"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from games.wend_solver.src.dictionary import load_wend_dictionary
from games.wend_solver.src.image_parser import WendImageParser, _LetterOcr
from games.wend_solver.src.wend_solver import WendSolver
from services.solver_api.app.workers import solve_wend_worker as wend_worker
from services.solver_api.app.workers.solve_wend_worker import solve as solve_wend_worker


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

        solutions = WendSolver(dictionary).solve(board, [6, 7, 9, 10]).solutions

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

        solutions = WendSolver(["AB", "CD", "AC", "BD"]).solve(board, [2, 2]).solutions

        solution_word_sets = {frozenset(candidate.word for candidate in solution.words) for solution in solutions}
        self.assertIn(frozenset({"AB", "CD"}), solution_word_sets)
        self.assertIn(frozenset({"AC", "BD"}), solution_word_sets)

    def test_uses_ocr_alternatives_to_form_valid_words(self) -> None:
        board = [
            ["C", "A"],
            ["E", "T"],
        ]
        letter_options = {(0, 0): [("C", 0.0), ("G", 0.02)]}

        solutions = WendSolver(["GATE"]).solve(board, [4], letter_options=letter_options).solutions

        self.assertEqual(1, len(solutions))
        self.assertEqual("GATE", solutions[0].words[0].word)
        self.assertAlmostEqual(0.02, solutions[0].words[0].ocr_cost)

    def test_validates_public_solver_inputs(self) -> None:
        solver = WendSolver(["WORD"])

        with self.assertRaises(ValueError):
            solver.solve([["W"]], [1], max_solutions=0)
        with self.assertRaises(ValueError):
            solver.solve([["AB"]], [1])
        with self.assertRaises(ValueError):
            solver.solve([["W"]], [True])
        with self.assertRaises(ValueError):
            solver.solve([["W"]], [1], letter_options={(0, 0): [("W", float("nan"))]})
        with self.assertRaises(ValueError):
            solver.solve([["W"]], [1], letter_options={(1, 0): [("W", 0.0)]})

    def test_reports_when_solution_count_is_capped(self) -> None:
        board = [["A", "B"], ["C", "D"]]

        result = WendSolver(["AB", "CD", "AC", "BD"]).solve(board, [2, 2], max_solutions=1)

        self.assertEqual(1, len(result.solutions))
        self.assertEqual(1, len(result))
        self.assertTrue(result)
        self.assertEqual(result.solutions[0], result[0])
        self.assertFalse(result.solution_count_is_exact)


class WendParserTests(unittest.TestCase):
    def test_worker_solves_recent_captures_without_inventing_ocr_ambiguity(self) -> None:
        captures = {
            "sample3.png": {"TIE", "PEER", "UNIFORM", "ALIKE"},
            "sample4.png": {"ATOM", "BIOME", "HYBRID", "PHYSICS"},
            "sample5.png": {"AGILE", "CONTEST", "USE", "POSE"},
            "sample6.png": {"PUPPY", "PET", "PEPPER", "TYPO"},
        }
        for filename, expected in captures.items():
            with self.subTest(filename=filename):
                result = solve_wend_worker(GAMES_ROOT / "wend_solver" / "examples" / filename)
                self.assertTrue(result["solved"], result.get("error"))
                self.assertEqual(expected, {entry["word"] for entry in result["words"]})
                self.assertEqual("exact_letters_exact_cover", result["details"]["search_mode"])
                self.assertTrue(result["details"]["solution_count_is_exact"])
                self.assertEqual([0.0], result["details"]["solution_costs"])
                self.assertEqual([], result["details"]["ocr_corrections"])

    @staticmethod
    def _recovery_board() -> dict:
        board = [[None] * 5 for _ in range(5)]
        board[0][:2] = ["C", "A"]
        board[1][:2] = ["E", "T"]
        cells = [
            {"row": row, "col": col, "letter": letter, "confidence": 0.96,
             "candidates": [{"letter": letter, "confidence": 0.96}]}
            for row, entries in enumerate(board)
            for col, letter in enumerate(entries) if letter is not None
        ]
        cells[0]["candidates"].extend([
            {"letter": "G", "confidence": 0.94}, {"letter": "H", "confidence": 0.93},
        ])
        return {"board": board, "lengths": [4], "board_size": 5, "visible_cells": 4,
                "ocr": {"cells": cells, "min_confidence": 0.96, "avg_confidence": 0.96}}

    def test_worker_still_recovers_a_wrong_letter_when_exact_search_fails(self) -> None:
        with patch.object(WendImageParser, "parse_image", return_value=self._recovery_board()), \
                patch.object(wend_worker, "_get_solver", return_value=WendSolver(["GATE"])):
            result = solve_wend_worker("unused.png")
        self.assertTrue(result["solved"], result.get("error"))
        self.assertEqual("weighted_ocr_exact_cover", result["details"]["search_mode"])
        self.assertEqual([{"row": 0, "col": 0, "from": "C", "to": "G"}], result["details"]["ocr_corrections"])

    def test_worker_rejects_ambiguous_ocr_recovery(self) -> None:
        with patch.object(WendImageParser, "parse_image", return_value=self._recovery_board()), \
                patch.object(wend_worker, "_get_solver", return_value=WendSolver(["GATE", "HATE"])):
            result = solve_wend_worker("unused.png")
        self.assertFalse(result["solved"])
        self.assertEqual(2, result["details"]["solution_count"])
        self.assertEqual([], result["words"])

    def test_worker_rejects_ambiguity_in_exact_letters_without_trying_recovery(self) -> None:
        parsed = self._recovery_board()
        parsed["board"][0][:2] = ["A", "B"]
        parsed["board"][1][:2] = ["C", "D"]
        parsed["lengths"] = [2, 2]
        solver = WendSolver(["AB", "CD", "AC", "BD"])
        with patch.object(WendImageParser, "parse_image", return_value=parsed), \
                patch.object(wend_worker, "_get_solver", return_value=solver), \
                patch.object(solver, "solve", wraps=solver.solve) as solve:
            result = solve_wend_worker("unused.png")
        self.assertFalse(result["solved"])
        self.assertEqual(2, result["details"]["solution_count"])
        self.assertEqual(1, solve.call_count)

    def test_worker_solves_seven_by_seven_capture_with_correct_r(self) -> None:
        result = solve_wend_worker(GAMES_ROOT / "wend_solver" / "examples" / "sample2.png")
        self.assertTrue(result["solved"], result.get("error"))
        self.assertEqual(7, result["board_size"])
        self.assertEqual("R", result["details"]["parsed_board"][1][4])
        self.assertTrue(result["details"]["unique_solution"])
        self.assertEqual([], result["details"]["ocr_corrections"])
        self.assertEqual({"KNOT", "DWELL", "EQUINOX", "DRAWBACK", "ENDURANCE", "WORKSTATION"},
                         {entry["word"] for entry in result["words"]})
        paths = [(cell["row"], cell["col"]) for word in result["words"] for cell in word["path"]]
        self.assertEqual(44, len(paths))
        self.assertEqual(44, len(set(paths)))

    def test_template_cache_changes_with_the_available_fonts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.ttf"
            second = Path(tmp) / "second.ttf"
            first.write_bytes(b"font-one")
            second.write_bytes(b"font-two")
            original = _LetterOcr._template_cache_path([str(first)])
            self.assertNotEqual(original, _LetterOcr._template_cache_path([str(first), str(second)]))
            first.write_bytes(b"font-one-updated")
            self.assertNotEqual(original, _LetterOcr._template_cache_path([str(first)]))

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

    def test_worker_rejects_unique_solution_from_low_confidence_ocr(self) -> None:
        board = [
            ["E", "R", "O", "R", "E", "T"],
            ["C", "A", "S", "A", "U", "S"],
            ["O", "T", None, None, "Q", "I"],
            ["N", "N", None, None, "S", "G"],
            ["I", "E", "G", "A", "M", "O"],
            ["H", "R", "B", "I", "O", "L"],
        ]
        cells = [
            {
                "row": row,
                "col": col,
                "letter": letter,
                "confidence": 0.01,
                "candidates": [{"letter": letter, "confidence": 0.01}],
            }
            for row, board_row in enumerate(board)
            for col, letter in enumerate(board_row)
            if letter is not None
        ]
        parsed = {
            "board": board,
            "lengths": [6, 7, 9, 10],
            "board_size": 6,
            "visible_cells": 32,
            "board_bbox": {"x": 0, "y": 0, "width": 600, "height": 600},
            "ocr": {"cells": cells, "min_confidence": 0.01, "avg_confidence": 0.01},
        }

        with patch.object(WendImageParser, "parse_image", return_value=parsed):
            result = solve_wend_worker("unused.png")

        self.assertFalse(result["solved"])
        self.assertFalse(result["details"]["parse_reliable"])


class WendDictionaryTests(unittest.TestCase):
    def test_loads_repository_wordlist(self) -> None:
        words = set(load_wend_dictionary())

        self.assertIn("SQUARE", words)
        self.assertIn("MAGENTA", words)
        self.assertIn("BIOLOGIST", words)
        self.assertIn("RHINOCEROS", words)
        self.assertIn("BIOME", words)
        self.assertIn("BIOMES", words)

    def test_supports_additional_env_wordlist(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as tmp:
            tmp.write("customword\nnot-a-word\nAB\n")
            tmp.flush()

            with patch.dict("os.environ", {"WEND_WORDLIST_PATH": tmp.name}):
                words = set(load_wend_dictionary())

        self.assertIn("CUSTOMWORD", words)
        self.assertNotIn("NOT-A-WORD", words)
        self.assertNotIn("AB", words)

    def test_rejects_missing_configured_wordlist_and_invalid_bounds(self) -> None:
        with patch.dict("os.environ", {"WEND_WORDLIST_PATH": "/missing/wend-words.txt"}):
            with self.assertRaises(FileNotFoundError):
                load_wend_dictionary()
        with self.assertRaises(ValueError):
            load_wend_dictionary(min_length=10, max_length=5)


if __name__ == "__main__":
    unittest.main()
