"""Queens Puzzle Solver - Main orchestrator class

This module provides the main QueensSolver class that coordinates all
components to solve Queens puzzles from images.
"""

import os
from typing import List, Optional

import cv2
import numpy as np

from src.core.models import BoardInfo, PuzzleState, SolverResult
from src.solver.queens_solver import BacktrackingQueensSolver
from src.solver.validator import QueensSolutionValidator
from src.utils.visualizer import QueensResultVisualizer
from src.vision.board_detector import EdgeDetectionBoardDetector
from src.vision.region_extractor import ColorBasedRegionExtractor


class QueensSolver:
    """Main orchestrator class for solving Queens puzzles from images.

    This class coordinates all components including board detection,
    region extraction, puzzle solving, validation, and visualization.
    """

    def __init__(self, verbose: bool = True):
        """Initialize the Queen Solver with all necessary components.

        Args:
            verbose: Whether to print detailed progress information

        """
        self.verbose = verbose

        # Initialize all components
        self.board_detector = EdgeDetectionBoardDetector()
        self.region_extractor = ColorBasedRegionExtractor()
        self.puzzle_solver = BacktrackingQueensSolver()
        self.solution_validator = QueensSolutionValidator()
        self.visualizer = QueensResultVisualizer()

        # State variables
        self.puzzle_state: Optional[PuzzleState] = None
        self.solver_result: Optional[SolverResult] = None

    def solve_from_image(self, image_path: str, output_dir: str = "output",
                        filename_prefix: Optional[str] = None,
                        generate_visualizations: bool = True,
                        quiet_mode: bool = False) -> bool:
        """Solve Queens puzzle from an image file.

        Args:
            image_path: Path to the board image
            output_dir: Directory to save results
            filename_prefix: Optional prefix for output filenames. If None, uses base name of image.
            generate_visualizations: Whether to generate and save visualization images
            quiet_mode: Whether to run in quiet mode (minimal output)

        Returns:
            True if puzzle was solved successfully, False otherwise

        """
        # Ensure output directory exists only if generating visualizations
        if generate_visualizations:
            os.makedirs(output_dir, exist_ok=True)

        # Generate filename prefix if not provided
        if filename_prefix is None:
            filename_prefix = os.path.splitext(os.path.basename(image_path))[0]

        try:
            # Show header only if not in quiet mode
            if not quiet_mode:
                print("👑 QUEENS PUZZLE SOLVER")
                print("=" * 25)

            if self.verbose:
                print("\n🖼️  STEP 1: Loading image...")

            # Step 1: Load and validate image
            image = self._load_image(image_path)
            if image is None:
                return False

            if self.verbose:
                print("\n🔧 STEP 2: Detecting board structure...")

            # Step 2: Detect board and grid
            if not self._detect_board_structure(image):
                return False

            if self.verbose:
                print("\n🎨 STEP 3: Extracting color regions...")

            # Step 3: Extract colored regions
            if not self._extract_regions(image):
                return False

            if self.verbose:
                print("\n🧩 STEP 4: Solving puzzle...")

            # Step 4: Solve the puzzle
            self._solve_puzzle()

            if self.verbose:
                print("\n📊 STEP 5: Validating solution...")

            # Step 5: Validate solution
            validation_errors = self._validate_solution()

            # Step 6: Generate results (conditional)
            if generate_visualizations:
                if self.verbose:
                    print("\n🖼️  STEP 6: Generating visualizations...")

                self._generate_results(image, output_dir, validation_errors, filename_prefix)

            # Step 7: Show results
            if self.verbose:
                print("\n📋 STEP 7: Results summary...")
                self._print_summary(validation_errors)
            elif not quiet_mode:
                self._print_simple_summary()
            else:
                # Quiet mode: only essential result
                self._print_quiet_summary()

            return self.solver_result.success and self.solver_result.validation_passed

        except Exception as e:
            if self.verbose:
                print(f"\n❌ Error during execution: {e}")
                import traceback
                traceback.print_exc()
            return False

    def _load_image(self, image_path: str) -> Optional[np.ndarray]:
        """Load and validate the input image."""
        if not os.path.exists(image_path):
            print(f"❌ Error: Image file not found: {image_path}")
            return None

        image = cv2.imread(image_path)
        if image is None:
            print(f"❌ Error: Could not load image: {image_path}")
            return None

        if self.verbose:
            print(f"✅ Image loaded successfully: {image.shape}")

        return image

    def _detect_board_structure(self, image: np.ndarray) -> bool:
        """Detect board size and grid structure."""
        try:
            # Detect board size
            board_size = self.board_detector.detect_board_size(image)

            # Check if board is valid for Queens puzzle
            if board_size == 0:
                print("❌ Invalid board detected: Non-square boards cannot be solved with Queens puzzle rules")
                return False

            if self.verbose:
                print(f"✅ Board size detected: {board_size}x{board_size}")

            # Detect grid lines
            h_lines, v_lines = self.board_detector.detect_grid(image, board_size)

            if self.verbose:
                print(f"✅ Grid detected: {len(h_lines)} horizontal, {len(v_lines)} vertical lines")

            # Create board info
            height, width = image.shape[:2]
            cell_height = height // board_size
            cell_width = width // board_size

            self.puzzle_state = PuzzleState(
                board_info=BoardInfo(
                    size=board_size,
                    image_shape=image.shape,
                    horizontal_lines=h_lines,
                    vertical_lines=v_lines,
                    cell_height=cell_height,
                    cell_width=cell_width,
                ),
                regions={},
            )

            return True

        except Exception as e:
            if self.verbose:
                print(f"❌ Error detecting board structure: {e}")
            return False

    def _extract_regions(self, image: np.ndarray) -> bool:
        """Extract colored regions from the board."""
        try:
            grid_lines = (
                self.puzzle_state.board_info.horizontal_lines,
                self.puzzle_state.board_info.vertical_lines,
            )

            regions = self.region_extractor.extract_regions(
                image, grid_lines, self.puzzle_state.board_info.size,
            )

            self.puzzle_state.regions = regions

            if self.verbose:
                print(f"✅ Regions extracted: {len(regions)} regions")
                for region in regions.values():
                    print(f"   Region {region.id}: {region.size} cells")

            # Validate regions
            if len(regions) != self.puzzle_state.board_info.size:
                self.puzzle_state.validation_errors.append(
                    f"Wrong number of regions: {len(regions)} (expected: {self.puzzle_state.board_info.size})",
                )
                self.puzzle_state.is_solvable = False
                if self.verbose:
                    print("⚠️  Warning: Region count mismatch may indicate detection issues")

            return True

        except Exception as e:
            if self.verbose:
                print(f"❌ Error extracting regions: {e}")
            return False

    def _solve_puzzle(self) -> None:
        """Solve the Queens puzzle."""
        try:
            self.solver_result = self.puzzle_solver.solve(
                self.puzzle_state.board_info.size,
                self.puzzle_state.regions,
            )

            self.puzzle_state.solution = self.solver_result.solution

            if self.verbose:
                if self.solver_result.success:
                    print(f"✅ Solution found in {self.solver_result.execution_time:.3f}s "
                          f"({self.solver_result.iterations:,} iterations)")
                else:
                    print(f"❌ No solution found after {self.solver_result.execution_time:.3f}s "
                          f"({self.solver_result.iterations:,} iterations)")
                    if self.solver_result.error_message:
                        print(f"   Reason: {self.solver_result.error_message}")

        except Exception as e:
            if self.verbose:
                print(f"❌ Error during solving: {e}")

            self.solver_result = SolverResult(
                success=False,
                solution=None,
                execution_time=0.0,
                iterations=0,
                validation_passed=False,
                error_message=str(e),
            )

    def _validate_solution(self) -> List[str]:
        """Validate the found solution."""
        validation_errors = []

        if self.puzzle_state.solution is not None:
            is_valid, errors = self.solution_validator.validate_with_details(
                self.puzzle_state.solution,
                self.puzzle_state.regions,
            )

            if not is_valid:
                validation_errors.extend(errors)
                if self.verbose:
                    print(f"❌ Solution validation failed with {len(errors)} errors")
                    for error in errors[:5]:  # Show first 5 errors
                        print(f"   • {error}")
                    if len(errors) > 5:
                        print(f"   ... and {len(errors) - 5} more errors")
            elif self.verbose:
                print("✅ Solution validation passed")
        else:
            validation_errors.append("No solution to validate")
            if self.verbose:
                print("⚠️  No solution to validate")

        return validation_errors

    def _generate_results(self, image: np.ndarray, output_dir: str,
                         validation_errors: List[str], filename_prefix: str) -> None:
        """Generate visualization and save results."""
        try:
            grid_lines = (
                self.puzzle_state.board_info.horizontal_lines,
                self.puzzle_state.board_info.vertical_lines,
            )

            # Create main visualization
            result_image = self.visualizer.visualize(
                image,
                self.puzzle_state.solution,
                grid_lines,
                self.puzzle_state.regions,
                output_dir,
                filename_prefix,
            )

            # Save main result with unique filename
            main_result_path = os.path.join(output_dir, f"{filename_prefix}_solution.png")
            cv2.imwrite(main_result_path, result_image)

            # Create detailed report
            self.visualizer.create_detailed_report(
                image,
                self.puzzle_state.solution,
                grid_lines,
                self.puzzle_state.regions,
                self.solver_result,
                validation_errors,
                output_dir,
                filename_prefix,
            )

            if self.verbose:
                print(f"✅ Results saved to {output_dir}/")
                print(f"   • {filename_prefix}_solution.png - Main result")
                print(f"   • {filename_prefix}_solution_analysis.png - Analysis overview")
                print(f"   • {filename_prefix}_detailed_report.png - Detailed report")

        except Exception as e:
            if self.verbose:
                print(f"⚠️  Error generating visualizations: {e}")

    def _print_simple_summary(self) -> None:
        """Print simple summary of results."""
        board_info = self.puzzle_state.board_info
        success = self.solver_result.success

        print(f"\n📋 Board: {board_info.size}x{board_info.size} with {len(self.puzzle_state.regions)} regions")

        if success:
            print(f"✅ Solution found in {self.solver_result.execution_time:.3f}s ({self.solver_result.iterations:,} iterations)")
            if self.solver_result.validation_passed:
                print("✅ Solution validation passed")
            else:
                print("⚠️  Solution validation failed")

            # Show solution board
            if self.puzzle_state.solution is not None:
                print("\n👑 Solution:")
                for r in range(board_info.size):
                    row_str = f"Row {r+1:2d}: "
                    for c in range(board_info.size):
                        if self.puzzle_state.solution[r, c] == 1:
                            row_str += "👑 "
                        else:
                            row_str += "·  "
                    print(row_str)
        else:
            print("❌ No solution found")

    def _print_quiet_summary(self) -> None:
        """Print minimal summary for quiet mode."""
        board_info = self.puzzle_state.board_info
        success = self.solver_result.success

        if success:
            print(f"✅ Solution found ({board_info.size}x{board_info.size}, {self.solver_result.execution_time:.3f}s)")
        else:
            print(f"❌ No solution ({board_info.size}x{board_info.size}, {self.solver_result.execution_time:.3f}s)")

    def _print_summary(self, validation_errors: List[str]) -> None:
        """Print summary of results."""
        print("\n" + "=" * 60)
        print("QUEENS PUZZLE SOLVER - RESULTS")
        print("=" * 60)

        # Basic information
        board_info = self.puzzle_state.board_info
        print(f"Board size: {board_info.size}x{board_info.size}")
        print(f"Image dimensions: {board_info.image_shape[1]}x{board_info.image_shape[0]}")
        print(f"Cell size: {board_info.cell_width}x{board_info.cell_height} pixels")
        print(f"Regions detected: {len(self.puzzle_state.regions)}")

        # Solver results
        print("\nSOLVER PERFORMANCE:")
        print(f"Success: {'Yes' if self.solver_result.success else 'No'}")
        print(f"Execution time: {self.solver_result.execution_time:.3f} seconds")
        print(f"Iterations: {self.solver_result.iterations:,}")
        print(f"Validation passed: {'Yes' if self.solver_result.validation_passed else 'No'}")

        if self.solver_result.error_message:
            print(f"Error message: {self.solver_result.error_message}")

        # Solution details
        if self.puzzle_state.solution is not None:
            print("\nSOLUTION DETAILS:")
            queens_count = int(np.sum(self.puzzle_state.solution))
            print(f"Queens placed: {queens_count}/{board_info.size}")

            # Show solution board
            print("\nBoard layout (👑 = Queen, · = Empty):")
            for r in range(board_info.size):
                row_str = f"Row {r+1:2d}: "
                for c in range(board_info.size):
                    if self.puzzle_state.solution[r, c] == 1:
                        row_str += "👑 "
                    else:
                        row_str += "·  "
                print(row_str)

        # Validation summary
        print("\nVALIDATION SUMMARY:")
        if not validation_errors:
            print("✅ All validation checks passed!")
            print("✅ Solution satisfies all Queens puzzle rules")
        else:
            print(f"❌ {len(validation_errors)} validation errors found:")
            for error in validation_errors[:10]:
                print(f"   • {error}")
            if len(validation_errors) > 10:
                print(f"   ... and {len(validation_errors) - 10} more errors")

        # Final verdict
        print("\nFINAL RESULT:")
        if self.solver_result.success and self.solver_result.validation_passed:
            print("🎉 PUZZLE SOLVED SUCCESSFULLY!")
        elif self.solver_result.success and not self.solver_result.validation_passed:
            print("⚠️  Solution found but validation failed")
        else:
            print("❌ NO VALID SOLUTION FOUND")
            if not self.puzzle_state.is_solvable:
                print("   The puzzle appears to be unsolvable due to region constraints")

        print("=" * 60)
