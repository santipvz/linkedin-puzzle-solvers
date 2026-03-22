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

        # Try multiple tolerances to find best grouping
        best_regions = self._find_best_color_grouping(cell_colors, cell_positions, board_size)

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

    def _extract_cell_colors(self, image: np.ndarray, h_lines: List[int], v_lines: List[int],
                           board_size: int) -> Tuple[List[np.ndarray], List[Tuple[int, int]]]:
        """Extract average color from each cell."""
        cell_colors = []
        cell_positions = []

        for r in range(board_size):
            for c in range(board_size):
                # Cell coordinates with larger margins to avoid grid lines
                y1 = h_lines[r] + 8
                y2 = h_lines[r + 1] - 8
                x1 = v_lines[c] + 8
                x2 = v_lines[c + 1] - 8

                # Ensure within image bounds
                y1 = max(0, min(y1, image.shape[0] - 1))
                y2 = max(y1 + 1, min(y2, image.shape[0]))
                x1 = max(0, min(x1, image.shape[1] - 1))
                x2 = max(x1 + 1, min(x2, image.shape[1]))

                if y2 > y1 and x2 > x1:
                    cell_region = image[y1:y2, x1:x2]

                    # Use smaller central region for better precision
                    h_margin = max(3, (y2 - y1) // 3)
                    w_margin = max(3, (x2 - x1) // 3)

                    if cell_region.shape[0] > 2 * h_margin and cell_region.shape[1] > 2 * w_margin:
                        center_region = cell_region[h_margin:-h_margin, w_margin:-w_margin]
                        avg_color = np.mean(center_region.reshape(-1, 3), axis=0)
                    else:
                        avg_color = np.mean(cell_region.reshape(-1, 3), axis=0)

                    cell_colors.append(avg_color)
                    cell_positions.append((r, c))

        return cell_colors, cell_positions

    def _find_best_color_grouping(self, cell_colors: List[np.ndarray],
                                cell_positions: List[Tuple[int, int]],
                                board_size: int) -> Dict[int, List[Tuple[int, int]]]:
        """Find the best color grouping using multiple tolerances."""
        best_regions = None
        best_score = float("inf")

        for tolerance in self.tolerance_range:
            regions = self._cluster_colors(cell_colors, cell_positions, tolerance)
            score = self._evaluate_region_quality(regions, board_size)

            if abs(len(regions) - board_size) <= 1 and score < best_score:
                best_regions = regions
                best_score = score

        if best_regions is None:
            # Use default tolerance if no good grouping found
            best_regions = self._cluster_colors(cell_colors, cell_positions, self.color_tolerance)

        # Adjust region count if necessary - but only for major discrepancies
        if abs(len(best_regions) - board_size) > 2:
            best_regions = self._adjust_regions_count(best_regions, board_size)

        return best_regions

    def _cluster_colors(self, colors: List[np.ndarray], positions: List[Tuple[int, int]],
                       tolerance: int) -> Dict[int, List[Tuple[int, int]]]:
        """Group colors into regions based on similarity."""
        if not colors:
            return {}

        colors = np.array(colors)
        regions = {}
        region_id = 0
        assigned = [False] * len(colors)

        for i, color in enumerate(colors):
            if assigned[i]:
                continue

            # Start new region
            current_region = [positions[i]]
            assigned[i] = True

            # Find similar colors
            for j, other_color in enumerate(colors):
                if assigned[j]:
                    continue

                # Calculate Euclidean distance in BGR space
                distance = np.linalg.norm(color - other_color)

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
        variance_penalty = np.var(sizes) / 10 if len(sizes) > 1 else 0

        return count_penalty + size_penalty + variance_penalty

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
