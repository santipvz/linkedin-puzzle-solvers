#!/usr/bin/env python3
"""
Automated test suite for the Queens Puzzle Solver.

This script tests both solvable and unsolvable boards to ensure
the solver correctly identifies and processes different puzzle types.
"""

import os
import sys
import time
import glob

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.queens_solver import QueensSolver


class TestQueensSolver:
    """Test class for the Queens Puzzle Solver."""

    def test_solvable_boards(self):
        """Test all boards in the solvable directory."""
        solvable_dir = os.path.join("tests", "boards", "solvable")
        if os.path.exists(solvable_dir):
            solvable_boards = glob.glob(os.path.join(solvable_dir, "*.png"))
            for board_path in solvable_boards:
                assert self._test_single_board(board_path, expected_solvable=True)

    def test_unsolvable_boards(self):
        """Test all boards in the unsolvable directory."""
        unsolvable_dir = os.path.join("tests", "boards", "unsolvable")
        if os.path.exists(unsolvable_dir):
            unsolvable_boards = glob.glob(os.path.join(unsolvable_dir, "*.png"))
            for board_path in unsolvable_boards:
                assert self._test_single_board(board_path, expected_solvable=False)

    def _test_single_board(self, board_path: str, expected_solvable: bool = True) -> bool:
        """
        Test a single board.

        Args:
            board_path: Path to the board image
            expected_solvable: Whether the board should be solvable

        Returns:
            True if test passed, False otherwise
        """
        print(f"\n{'='*60}")
        print(f"Testing: {os.path.basename(board_path)}")
        print(f"Expected: {'Solvable' if expected_solvable else 'Unsolvable'}")
        print(f"{'='*60}")

        if not os.path.exists(board_path):
            print(f"❌ Board file not found: {board_path}")
            return False

        solver = QueensSolver(verbose=False)  # Disable verbose for faster tests
        start_time = time.time()

        # Run solver without generating visualizations for speed
        success = solver.solve_from_image(board_path, "", "", generate_visualizations=False)

        end_time = time.time()
        total_time = end_time - start_time

        print(f"\n{'='*40}")
        print(f"TEST RESULT for {os.path.basename(board_path)}:")
        print(f"Expected: {'Solvable' if expected_solvable else 'Unsolvable'}")
        print(f"Actual: {'Solved' if success else 'Not solved'}")
        print(f"Total time: {total_time:.3f} seconds")

        if expected_solvable == success:
            print("✅ TEST PASSED")
            return True
        else:
            print("❌ TEST FAILED")
            return False


def discover_test_boards():
    """
    Discover all test boards in the organized directory structure.

    Returns:
        List of tuples (board_path, expected_solvable)
    """
    test_cases = []

    # Get solvable boards
    solvable_dir = "tests/boards/solvable"
    if os.path.exists(solvable_dir):
        solvable_boards = glob.glob(os.path.join(solvable_dir, "*.png"))
        solvable_boards.extend(glob.glob(os.path.join(solvable_dir, "*.jpg")))
        solvable_boards.extend(glob.glob(os.path.join(solvable_dir, "*.jpeg")))

        for board in sorted(solvable_boards):
            test_cases.append((board, True))

    # Get unsolvable boards
    unsolvable_dir = "tests/boards/unsolvable"
    if os.path.exists(unsolvable_dir):
        unsolvable_boards = glob.glob(os.path.join(unsolvable_dir, "*.png"))
        unsolvable_boards.extend(glob.glob(os.path.join(unsolvable_dir, "*.jpg")))
        unsolvable_boards.extend(glob.glob(os.path.join(unsolvable_dir, "*.jpeg")))

        for board in sorted(unsolvable_boards):
            test_cases.append((board, False))

    return test_cases


def run_all_tests():
    """Run all available tests - for manual execution."""
    print("👑 QUEENS PUZZLE SOLVER - AUTOMATED TESTING")
    print("="*60)

    # Discover test cases
    test_cases = discover_test_boards()

    if not test_cases:
        print("⚠️  No test boards found!")
        print("   Place solvable boards in: tests/boards/solvable/")
        print("   Place unsolvable boards in: tests/boards/unsolvable/")
        return False

    print(f"Found {len(test_cases)} test cases:")
    solvable_count = sum(1 for _, expected in test_cases if expected)
    unsolvable_count = len(test_cases) - solvable_count
    print(f"   • {solvable_count} solvable boards")
    print(f"   • {unsolvable_count} unsolvable boards")

    # Create test instance
    test_instance = TestQueensSolver()

    results = []
    total_start = time.time()

    for board_path, expected in test_cases:
        result = test_instance._test_single_board(board_path, expected)
        results.append((os.path.basename(board_path), result))

    total_end = time.time()
    total_time = total_end - total_start

    # Summary
    print(f"\n{'='*60}")
    print("TESTING SUMMARY")
    print(f"{'='*60}")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    print(f"\nOverall Results: {passed}/{total} tests passed")
    print(f"Total testing time: {total_time:.2f} seconds")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n❌ {total - passed} tests failed")
        return False


if __name__ == "__main__":
    run_all_tests()