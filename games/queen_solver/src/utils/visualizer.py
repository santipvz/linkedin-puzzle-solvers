"""Advanced visualization for Queens puzzle solutions."""

import os
from typing import Dict, List, Optional, Tuple

import cv2
import matplotlib.pyplot as plt
import numpy as np

from src.core.interfaces import ResultVisualizer
from src.core.models import Region


class QueensResultVisualizer(ResultVisualizer):
    """Advanced visualizer for Queens puzzle results."""

    def __init__(self):
        self.region_colors = [
            (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255),
            (0, 255, 255), (128, 0, 0), (0, 128, 0), (0, 0, 128), (128, 128, 0),
            (128, 0, 128), (0, 128, 128), (255, 128, 0), (128, 255, 0), (0, 255, 128),
        ]
        # Load queen image once and cache it
        self.queen_image = self._load_queen_image()

    def _load_queen_image(self) -> Optional[np.ndarray]:
        """Load the queen PNG image."""
        try:
            # Path to queen image - adjust if needed
            queen_path = os.path.join("assets", "queen.png")
            if not os.path.exists(queen_path):
                # Try alternative path if running from different directory
                queen_path = os.path.join("..", "assets", "queen.png")

            if os.path.exists(queen_path):
                queen_img = cv2.imread(queen_path, cv2.IMREAD_UNCHANGED)
                if queen_img is not None:
                    return queen_img
            return None
        except Exception as e:
            print(f"Warning: Could not load queen image: {e}")
            return None

    def visualize(self, original_image: np.ndarray, solution: Optional[np.ndarray],
                 grid_lines: Tuple[List[int], List[int]],
                 regions: Dict[int, Region], output_dir: str = "output",
                 filename_prefix: str = "board") -> np.ndarray:
        """Create visualization of the solution."""
        fig, axes = plt.subplots(2, 2, figsize=(16, 16))

        # 1. Original image
        axes[0, 0].imshow(cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB))
        axes[0, 0].set_title("Original Board Image", fontsize=14, fontweight="bold")
        axes[0, 0].axis("off")

        # 2. Grid detection
        grid_img = self._create_grid_image(original_image, grid_lines)
        axes[0, 1].imshow(cv2.cvtColor(grid_img, cv2.COLOR_BGR2RGB))

        h_lines, v_lines = grid_lines
        board_size = len(h_lines) - 1
        axes[0, 1].set_title(f"Detected Grid ({board_size}x{board_size})", fontsize=14, fontweight="bold")
        axes[0, 1].axis("off")

        # 3. Regions visualization
        regions_img = self._create_regions_image(original_image, grid_lines, regions)
        axes[1, 0].imshow(cv2.cvtColor(regions_img, cv2.COLOR_BGR2RGB))
        axes[1, 0].set_title(f"Color Regions ({len(regions)} detected)", fontsize=14, fontweight="bold")
        axes[1, 0].axis("off")

        # 4. Solution or error message
        if solution is not None:
            solution_img = self._create_solution_image(original_image, solution, grid_lines)
            axes[1, 1].imshow(cv2.cvtColor(solution_img, cv2.COLOR_BGR2RGB))
            axes[1, 1].set_title("Solution with Queens", fontsize=14, fontweight="bold")
        else:
            axes[1, 1].text(0.5, 0.5, "NO SOLUTION\nFOUND",
                           ha="center", va="center", fontsize=20, fontweight="bold",
                           color="red", transform=axes[1, 1].transAxes)
            axes[1, 1].set_title("No Valid Solution", fontsize=14, fontweight="bold")
        axes[1, 1].axis("off")

        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f"{filename_prefix}_solution_analysis.png"),
                   dpi=150, bbox_inches="tight")
        plt.close()

        # Return the final result image
        if solution is not None:
            return self._create_solution_image(original_image, solution, grid_lines)
        return self._create_no_solution_image(original_image, grid_lines, regions)

    def create_detailed_report(self, original_image: np.ndarray, solution: Optional[np.ndarray],
                             grid_lines: Tuple[List[int], List[int]], regions: Dict[int, Region],
                             solver_result, validation_errors: List[str] = None,
                             output_dir: str = "output", filename_prefix: str = "queens") -> None:
        """Create a detailed analysis report."""
        fig = plt.figure(figsize=(20, 12))

        # Create a more complex layout
        gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)

        # Original image (top-left)
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.imshow(cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB))
        ax1.set_title("Original Image", fontweight="bold")
        ax1.axis("off")

        # Grid detection (top-center-left)
        ax2 = fig.add_subplot(gs[0, 1])
        grid_img = self._create_grid_image(original_image, grid_lines)
        ax2.imshow(cv2.cvtColor(grid_img, cv2.COLOR_BGR2RGB))
        ax2.set_title("Grid Detection", fontweight="bold")
        ax2.axis("off")

        # Regions (top-center-right)
        ax3 = fig.add_subplot(gs[0, 2])
        regions_img = self._create_regions_image(original_image, grid_lines, regions)
        ax3.imshow(cv2.cvtColor(regions_img, cv2.COLOR_BGR2RGB))
        ax3.set_title("Color Regions", fontweight="bold")
        ax3.axis("off")

        # Solution or error (top-right)
        ax4 = fig.add_subplot(gs[0, 3])
        if solution is not None:
            solution_img = self._create_solution_image(original_image, solution, grid_lines)
            ax4.imshow(cv2.cvtColor(solution_img, cv2.COLOR_BGR2RGB))
            ax4.set_title("Final Solution", fontweight="bold")
        else:
            ax4.text(0.5, 0.5, "NO SOLUTION", ha="center", va="center",
                    fontsize=16, fontweight="bold", color="red")
            ax4.set_title("Result", fontweight="bold")
        ax4.axis("off")

        # Statistics and info (middle row)
        ax5 = fig.add_subplot(gs[1, :2])
        self._add_statistics_text(ax5, original_image, grid_lines, regions, solver_result)

        # Validation results (middle-right)
        ax6 = fig.add_subplot(gs[1, 2:])
        self._add_validation_text(ax6, validation_errors, solution, regions)

        # Solution board representation (bottom)
        ax7 = fig.add_subplot(gs[2, :])
        if solution is not None:
            self._add_solution_board_text(ax7, solution)
        else:
            ax7.text(0.5, 0.5, "No solution to display", ha="center", va="center",
                    fontsize=14, fontweight="bold")

        plt.savefig(os.path.join(output_dir, f"{filename_prefix}_detailed_report.png"),
                   dpi=150, bbox_inches="tight")
        plt.close()

    def _create_grid_image(self, image: np.ndarray, grid_lines: Tuple[List[int], List[int]]) -> np.ndarray:
        """Create image showing detected grid."""
        result = image.copy()
        h_lines, v_lines = grid_lines

        # Draw horizontal lines
        for y in h_lines:
            cv2.line(result, (0, y), (result.shape[1], y), (0, 255, 0), 2)

        # Draw vertical lines
        for x in v_lines:
            cv2.line(result, (x, 0), (x, result.shape[0]), (0, 0, 255), 2)

        return result

    def _create_regions_image(self, image: np.ndarray, grid_lines: Tuple[List[int], List[int]],
                            regions: Dict[int, Region]) -> np.ndarray:
        """Create image showing detected regions."""
        result = image.copy()
        h_lines, v_lines = grid_lines

        for region in regions.values():
            color = self.region_colors[region.id % len(self.region_colors)]

            for r, c in region.positions:
                if r < len(h_lines) - 1 and c < len(v_lines) - 1:
                    y1, y2 = h_lines[r], h_lines[r + 1]
                    x1, x2 = v_lines[c], v_lines[c + 1]

                    # Draw region border
                    cv2.rectangle(result, (x1, y1), (x2, y2), color, 3)

                    # Add region number
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2
                    cv2.putText(result, str(region.id),
                              (center_x - 10, center_y + 5),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

        return result

    def _create_solution_image(self, image: np.ndarray, solution: np.ndarray,
                             grid_lines: Tuple[List[int], List[int]]) -> np.ndarray:
        """Create image showing solution with queens."""
        result = image.copy()
        h_lines, v_lines = grid_lines
        board_size = solution.shape[0]

        for r in range(board_size):
            for c in range(board_size):
                if solution[r, c] == 1:
                    # Cell coordinates
                    y1, y2 = h_lines[r], h_lines[r + 1]
                    x1, x2 = v_lines[c], v_lines[c + 1]

                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2

                    # Cell size for scaling
                    cell_width = x2 - x1
                    cell_height = y2 - y1
                    cell_size = min(cell_width, cell_height)

                    if self.queen_image is not None:
                        # Use the queen PNG image
                        self._draw_queen_image(result, center_x, center_y, cell_size)
                    else:
                        # Fallback to drawn queen if image not available
                        self._draw_queen_fallback(result, center_x, center_y, cell_size)

        return result

    def _draw_queen_image(self, image: np.ndarray, center_x: int, center_y: int, cell_size: int):
        """Draw the queen PNG image at the specified position."""
        try:
            # Calculate desired size (55% of cell size for better fit)
            queen_size = int(cell_size * 0.55)

            # Resize queen image to fit cell
            queen_resized = cv2.resize(self.queen_image, (queen_size, queen_size))

            # Calculate position to center the queen
            start_x = center_x - queen_size // 2
            start_y = center_y - queen_size // 2

            # Ensure we don't go out of bounds
            start_x = max(0, min(start_x, image.shape[1] - queen_size))
            start_y = max(0, min(start_y, image.shape[0] - queen_size))

            end_x = start_x + queen_size
            end_y = start_y + queen_size

            # Handle both RGBA and RGB queen images
            if queen_resized.shape[2] == 4:  # RGBA
                # Use alpha channel for blending
                queen_rgb = queen_resized[:, :, :3]
                alpha = queen_resized[:, :, 3] / 255.0

                # Blend with background
                for c in range(3):
                    image[start_y:end_y, start_x:end_x, c] = (
                        alpha * queen_rgb[:, :, c] +
                        (1 - alpha) * image[start_y:end_y, start_x:end_x, c]
                    )
            else:  # RGB
                # Simple overlay for RGB images
                image[start_y:end_y, start_x:end_x] = queen_resized

        except Exception as e:
            print(f"Warning: Could not draw queen image: {e}")
            # Fallback to drawn queen
            self._draw_queen_fallback(image, center_x, center_y, cell_size)

    def _draw_queen_fallback(self, image: np.ndarray, center_x: int, center_y: int, cell_size: int):
        """Fallback method to draw queen using shapes and text."""
        # Queen crown size based on cell size
        radius = max(cell_size // 4, 15)

        # Draw golden crown
        cv2.circle(image, (center_x, center_y), radius, (0, 215, 255), -1)
        cv2.circle(image, (center_x, center_y), radius, (0, 0, 0), 3)

        # Queen symbol
        font_scale = max(0.8, cell_size / 80.0)
        thickness = max(2, int(font_scale * 3))

        cv2.putText(image, "♛",
                  (center_x - int(radius * 0.7),
                   center_y + int(radius * 0.4)),
                  cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                  (0, 0, 0), thickness)

    def _create_no_solution_image(self, image: np.ndarray, grid_lines: Tuple[List[int], List[int]],
                                regions: Dict[int, Region]) -> np.ndarray:
        """Create image indicating no solution."""
        result = self._create_regions_image(image, grid_lines, regions)

        # Add "NO SOLUTION" overlay
        height, width = result.shape[:2]
        overlay = result.copy()

        # Semi-transparent red overlay
        cv2.rectangle(overlay, (0, 0), (width, height), (0, 0, 255), -1)
        result = cv2.addWeighted(result, 0.7, overlay, 0.3, 0)

        # Add text
        font_scale = min(width, height) / 300
        thickness = max(2, int(font_scale * 3))

        text = "NO SOLUTION"
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
        text_x = (width - text_size[0]) // 2
        text_y = (height + text_size[1]) // 2

        # Text with outline
        cv2.putText(result, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX,
                   font_scale, (0, 0, 0), thickness + 2)
        cv2.putText(result, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX,
                   font_scale, (255, 255, 255), thickness)

        return result

    def _add_statistics_text(self, ax, image, grid_lines, regions, solver_result):
        """Add statistics information to the plot."""
        h_lines, v_lines = grid_lines
        board_size = len(h_lines) - 1

        stats_text = f"""
BOARD ANALYSIS:
• Image size: {image.shape[1]} × {image.shape[0]} pixels
• Board size: {board_size} × {board_size}
• Total cells: {board_size * board_size}
• Regions detected: {len(regions)}

SOLVER STATISTICS:
• Success: {'Yes' if solver_result.success else 'No'}
• Execution time: {solver_result.execution_time:.3f} seconds
• Iterations: {solver_result.iterations:,}
• Validation passed: {'Yes' if solver_result.validation_passed else 'No'}
"""

        ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=10,
               verticalalignment="top", fontfamily="monospace")
        ax.set_title("Statistics", fontweight="bold")
        ax.axis("off")

    def _add_validation_text(self, ax, validation_errors, solution, regions):
        """Add validation results to the plot."""
        if solution is not None and not validation_errors:
            validation_text = """
VALIDATION RESULTS:
✓ All rules satisfied
✓ Exactly 1 queen per row
✓ Exactly 1 queen per column
✓ Exactly 1 queen per region
✓ No adjacent queens
✓ Solution is valid!
"""
            color = "green"
        elif validation_errors:
            validation_text = "VALIDATION ERRORS:\n"
            for error in validation_errors[:10]:  # Show first 10 errors
                validation_text += f"✗ {error}\n"
            if len(validation_errors) > 10:
                validation_text += f"... and {len(validation_errors) - 10} more errors"
            color = "red"
        else:
            validation_text = "NO SOLUTION TO VALIDATE"
            color = "orange"

        ax.text(0.05, 0.95, validation_text, transform=ax.transAxes, fontsize=10,
               verticalalignment="top", fontfamily="monospace", color=color)
        ax.set_title("Validation", fontweight="bold")
        ax.axis("off")

    def _add_solution_board_text(self, ax, solution):
        """Add text representation of the solution board."""
        board_size = solution.shape[0]

        board_text = "SOLUTION BOARD:\n\n"
        board_text += "   " + " ".join([f"{i+1:2d}" for i in range(board_size)]) + "\n"

        for r in range(board_size):
            row_text = f"{r+1:2d} "
            for c in range(board_size):
                if solution[r, c] == 1:
                    row_text += " ♛"
                else:
                    row_text += " ·"
            board_text += row_text + "\n"

        ax.text(0.5, 0.5, board_text, transform=ax.transAxes, fontsize=12,
               ha="center", va="center", fontfamily="monospace")
        ax.set_title("Solution Layout", fontweight="bold")
        ax.axis("off")
