from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.solver_api.app.main import _archive_board_capture, _cache_key_for_upload, _parse_cors_origins, app
from services.solver_api.app.puzzle_registry import PUZZLE_DEFINITIONS


class PuzzleRegistryTests(unittest.TestCase):
    def test_registry_keys_unique(self) -> None:
        keys = [definition.key for definition in PUZZLE_DEFINITIONS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_registry_entries_have_required_fields(self) -> None:
        for definition in PUZZLE_DEFINITIONS:
            with self.subTest(puzzle=definition.key):
                self.assertTrue(definition.key)
                self.assertTrue(definition.worker_filename.endswith(".py"))
                self.assertTrue(definition.sample_image)
                self.assertGreater(definition.expected_board_size, 0)
                self.assertGreater(definition.cache_revision, 0)

    def test_cache_revision_changes_upload_key(self) -> None:
        payload = b"same image"

        self.assertNotEqual(
            _cache_key_for_upload("wend", 1, payload),
            _cache_key_for_upload("wend", 2, payload),
        )


class ApiRouteRegistrationTests(unittest.TestCase):
    def test_all_registry_solve_routes_exist(self) -> None:
        route_paths = {route.path for route in app.routes if hasattr(route, "path")}

        for definition in PUZZLE_DEFINITIONS:
            with self.subTest(endpoint=definition.endpoint_path):
                self.assertIn(definition.endpoint_path, route_paths)


class CorsParsingTests(unittest.TestCase):
    def test_parse_cors_origins_defaults(self) -> None:
        self.assertEqual(["*"], _parse_cors_origins(""))
        self.assertEqual(["*"], _parse_cors_origins("*"))
        self.assertEqual(["*"], _parse_cors_origins("foo,*,bar"))

    def test_parse_cors_origins_list(self) -> None:
        parsed = _parse_cors_origins("https://a.example, https://b.example")
        self.assertEqual(["https://a.example", "https://b.example"], parsed)


class DatasetCaptureTests(unittest.TestCase):
    def test_capture_preserves_original_payload_and_solution_paths(self) -> None:
        sample_path = REPO_ROOT / "games" / "wend_solver" / "examples" / "sample1.png"
        payload = sample_path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        response = {
            "solved": True,
            "board_size": 5,
            "details": {"parse_reliable": True},
            "words": [{"word": "TEST", "path": []}],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            capture_root = Path(temp_dir)
            with patch("services.solver_api.app.main.CAPTURE_DATASET_DIR", capture_root):
                _archive_board_capture("wend", payload, response, from_cache=False)
            image_path = next(capture_root.glob("wend/*/*.png"))
            metadata_path = image_path.with_suffix(".json")
            captured_payload = image_path.read_bytes()
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(payload, captured_payload)
        self.assertEqual(".png", image_path.suffix)
        self.assertEqual(digest, metadata["original_sha256"])
        self.assertEqual(digest, metadata["artifact_sha256"])
        self.assertEqual(response["words"], metadata["words"])


class ExtensionRegressionTests(unittest.TestCase):
    def test_mini_sudoku_apply_keeps_ready_preflight(self) -> None:
        content_script = (REPO_ROOT / "extension" / "content.js").read_text(encoding="utf-8")

        self.assertIn("async function getReadySudokuSelectionCandidates", content_script)
        self.assertIn("scoreSudokuSelectionCandidate", content_script)
        self.assertIn(
            "const selectionCandidates = await getReadySudokuSelectionCandidates(selection, boardSize, actionableMoves);",
            content_script,
        )


if __name__ == "__main__":
    unittest.main()
