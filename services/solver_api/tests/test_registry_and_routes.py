from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.solver_api.app.main import _parse_cors_origins, app
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


if __name__ == "__main__":
    unittest.main()
