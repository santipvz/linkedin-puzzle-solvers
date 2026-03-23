"""Advanced region extraction using color clustering and validation."""

from typing import Dict, List, Tuple

import numpy as np

from src.core.interfaces import RegionExtractor
from src.core.models import Region


class ColorBasedRegionExtractor(RegionExtractor):
    """Extract regions based on color similarity with advanced validation."""

    def __init__(self, color_tolerance: int = 40):
        self.color_tolerance = color_tolerance
        self.tolerance_range = [25, 30, 35, 40, 45, 50, 60, 70]

    def extract_regions(self, image: np.ndarray, grid_lines: Tuple[List[int], List[int]],
                       board_size: int) -> Dict[int, Region]:
        """Extract colored regions with improved validation."""
        h_lines, v_lines = grid_lines

        # Extract cell colors
        cell_colors, cell_positions = self._extract_cell_colors(image, h_lines, v_lines, board_size)
        color_grid = self._build_color_grid(cell_colors, cell_positions, board_size)

        # Try multiple tolerances to find best grouping
        best_regions = self._find_best_color_grouping(cell_colors, cell_positions, color_grid, board_size)

        # Convert to Region objects
        regions = {}
        for region_id, positions in best_regions.items():
            # Calculate average color for this region
            region_colors = [cell_colors[cell_positions.index(pos)] for pos in positions]
            avg_color = np.mean(region_colors, axis=0)

            regions[region_id] = Region(
                id=region_id,
                positions=positions,
                color=avg_color,
                size=len(positions),
            )

        return regions

    def _build_color_grid(self, cell_colors: List[np.ndarray], cell_positions: List[Tuple[int, int]],
                         board_size: int) -> np.ndarray:
        """Build board-sized color matrix from flattened cell color list."""
        color_grid = np.zeros((board_size, board_size, 3), dtype=float)

        for index, (row, col) in enumerate(cell_positions):
            if index < len(cell_colors):
                color_grid[row, col] = cell_colors[index]

        return color_grid

    def _extract_cell_colors(self, image: np.ndarray, h_lines: List[int], v_lines: List[int],
                           board_size: int) -> Tuple[List[np.ndarray], List[Tuple[int, int]]]:
        """Extract average color from each cell."""
        cell_colors = []
        cell_positions = []

        for r in range(board_size):
            for c in range(board_size):
                raw_y1 = h_lines[r]
                raw_y2 = h_lines[r + 1]
                raw_x1 = v_lines[c]
                raw_x2 = v_lines[c + 1]

                cell_height = max(1, raw_y2 - raw_y1)
                cell_width = max(1, raw_x2 - raw_x1)

                # Dynamic inner margin to avoid grid lines while keeping enough border pixels
                margin = max(3, min(cell_height, cell_width) // 8)

                y1 = raw_y1 + margin
                y2 = raw_y2 - margin
                x1 = raw_x1 + margin
                x2 = raw_x2 - margin

                # Ensure within image bounds
                y1 = max(0, min(y1, image.shape[0] - 1))
                y2 = max(y1 + 1, min(y2, image.shape[0]))
                x1 = max(0, min(x1, image.shape[1] - 1))
                x2 = max(x1 + 1, min(x2, image.shape[1]))

                if y2 > y1 and x2 > x1:
                    cell_region = image[y1:y2, x1:x2]

                    # Use border-biased sampling so symbols placed in the center
                    # (queens, marks) do not distort region color estimation.
                    avg_color = self._extract_robust_cell_color(cell_region)

                    cell_colors.append(avg_color)
                    cell_positions.append((r, c))

        return cell_colors, cell_positions

    def _extract_robust_cell_color(self, cell_region: np.ndarray) -> np.ndarray:
        """Estimate cell color robustly against center overlays/icons."""
        if cell_region.size == 0:
            return np.array([0.0, 0.0, 0.0])

        height, width = cell_region.shape[:2]
        band = max(2, min(height, width) // 6)

        top = cell_region[:band, :, :]
        bottom = cell_region[-band:, :, :]
        left = cell_region[:, :band, :]
        right = cell_region[:, -band:, :]

        sampled_pixels = np.concatenate(
            [
                top.reshape(-1, 3),
                bottom.reshape(-1, 3),
                left.reshape(-1, 3),
                right.reshape(-1, 3),
            ],
            axis=0,
        )

        if sampled_pixels.size == 0:
            sampled_pixels = cell_region.reshape(-1, 3)

        brightness = np.mean(sampled_pixels, axis=1)
        low = np.percentile(brightness, 10)
        high = np.percentile(brightness, 95)

        filtered = sampled_pixels[(brightness >= low) & (brightness <= high)]
        if filtered.size == 0:
            filtered = sampled_pixels

        return np.median(filtered, axis=0)

    def _find_best_color_grouping(self, cell_colors: List[np.ndarray],
                                cell_positions: List[Tuple[int, int]],
                                color_grid: np.ndarray,
                                board_size: int) -> Dict[int, List[Tuple[int, int]]]:
        """Find the best color grouping using multiple tolerances."""
        best_regions = None
        best_score = float("inf")

        for tolerance in self.tolerance_range:
            regions = self._cluster_colors_connected(color_grid, board_size, tolerance)
            score = self._evaluate_region_quality(regions, board_size)

            if abs(len(regions) - board_size) <= 2 and score < best_score:
                best_regions = regions
                best_score = score

        if best_regions is None:
            best_regions = self._cluster_colors_global(cell_colors, cell_positions, self.color_tolerance)

        # Adjust region count if necessary - but only for major discrepancies
        if abs(len(best_regions) - board_size) > 2:
            best_regions = self._adjust_regions_count(best_regions, board_size)

        return best_regions

    def _cluster_colors_connected(self, color_grid: np.ndarray, board_size: int,
                                 tolerance: int) -> Dict[int, List[Tuple[int, int]]]:
        """Cluster cells by color using 4-neighbor connectivity constraints."""
        regions: Dict[int, List[Tuple[int, int]]] = {}
        assigned = np.zeros((board_size, board_size), dtype=bool)
        region_id = 0
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        for row in range(board_size):
            for col in range(board_size):
                if assigned[row, col]:
                    continue

                region_positions: List[Tuple[int, int]] = []
                stack = [(row, col)]
                assigned[row, col] = True

                while stack:
                    current_row, current_col = stack.pop()
                    region_positions.append((current_row, current_col))

                    for dr, dc in directions:
                        next_row = current_row + dr
                        next_col = current_col + dc

                        if not (0 <= next_row < board_size and 0 <= next_col < board_size):
                            continue

                        if assigned[next_row, next_col]:
                            continue

                        current_color = color_grid[current_row, current_col]
                        next_color = color_grid[next_row, next_col]
                        distance = np.linalg.norm(current_color - next_color)

                        if distance <= tolerance:
                            assigned[next_row, next_col] = True
                            stack.append((next_row, next_col))

                regions[region_id] = region_positions
                region_id += 1

        return regions

    def _cluster_colors_global(self, colors: List[np.ndarray], positions: List[Tuple[int, int]],
                              tolerance: int) -> Dict[int, List[Tuple[int, int]]]:
        """Group colors into regions based on similarity."""
        if not colors:
            return {}

        colors_array = np.array(colors)
        regions = {}
        region_id = 0
        assigned = [False] * len(colors_array)

        for i, color in enumerate(colors_array):
            if assigned[i]:
                continue

            # Start new region
            current_region = [positions[i]]
            assigned[i] = True

            # Find similar colors
            for j, other_color in enumerate(colors_array):
                if assigned[j]:
                    continue

                # Calculate Euclidean distance in BGR space
                distance = float(np.linalg.norm(color - other_color))

                if distance <= tolerance:
                    current_region.append(positions[j])
                    assigned[j] = True

            regions[region_id] = current_region
            region_id += 1

        return regions

    def _evaluate_region_quality(self, regions: Dict[int, List[Tuple[int, int]]],
                                expected_count: int) -> float:
        """Evaluate the quality of region grouping."""
        if not regions:
            return float("inf")

        # Penalize difference in region count
        count_penalty = abs(len(regions) - expected_count) * 10

        # Penalize very small or very large regions moderately
        size_penalty = 0
        sizes = [len(positions) for positions in regions.values()]
        avg_size = sum(sizes) / len(sizes)

        for size in sizes:
            if size > avg_size * 4:  # Only penalize extremely large regions
                size_penalty += 10

        # Penalize high variance in sizes
        variance_penalty = float(np.var(sizes) / 10) if len(sizes) > 1 else 0.0

        return float(count_penalty + size_penalty + variance_penalty)

    def _adjust_regions_count(self, regions: Dict[int, List[Tuple[int, int]]],
                            target_count: int) -> Dict[int, List[Tuple[int, int]]]:
        """Adjust the number of regions to target count."""
        current_count = len(regions)

        if current_count == target_count:
            return regions

        if current_count > target_count:
            return self._merge_regions(regions, target_count)
        return self._split_regions(regions, target_count)

    def _merge_regions(self, regions: Dict[int, List[Tuple[int, int]]],
                      target_count: int) -> Dict[int, List[Tuple[int, int]]]:
        """Merge smallest regions to reach target count."""
        sorted_regions = sorted(regions.items(), key=lambda x: len(x[1]))
        merged_regions = {}
        region_id = 0

        # Keep largest regions
        large_regions = sorted_regions[-(target_count - 1):]
        for _, positions in large_regions:
            merged_regions[region_id] = positions
            region_id += 1

        # Merge smallest regions
        small_positions = []
        for i in range(len(sorted_regions) - target_count + 1):
            small_positions.extend(sorted_regions[i][1])

        if small_positions:
            merged_regions[region_id] = small_positions

        return merged_regions

    def _split_regions(self, regions: Dict[int, List[Tuple[int, int]]],
                      target_count: int) -> Dict[int, List[Tuple[int, int]]]:
        """Split regions to reach target count."""
        all_positions = []
        for positions in regions.values():
            all_positions.extend(positions)

        new_regions = {}
        positions_per_region = len(all_positions) // target_count

        region_id = 0
        current_positions = []

        for pos in all_positions:
            current_positions.append(pos)

            if len(current_positions) >= positions_per_region and region_id < target_count - 1:
                new_regions[region_id] = current_positions.copy()
                current_positions = []
                region_id += 1

        # Add remaining positions to last region
        if current_positions:
            if region_id in new_regions:
                new_regions[region_id].extend(current_positions)
            else:
                new_regions[region_id] = current_positions

        return new_regions
