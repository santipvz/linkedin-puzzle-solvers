"""
Tango Solver - LinkedIn Tango game solver

Game rules:
1. 6x6 board with two types of pieces (0 and 1)
2. Each row and column must have exactly 3 of each type
3. No 3 consecutive pieces of the same type allowed (max 2 in a row)
4. "=" clues indicate adjacent cells must have the same type
5. "x" clues indicate adjacent cells must have different types
"""

try:
    from .visualizer import BoardVisualizer
except ImportError:
    from visualizer import BoardVisualizer


class TangoSolver:
    def __init__(self):
        self.size = 6
        self.board = [[None for _ in range(self.size)] for _ in range(self.size)]
        self.constraints = []
        self.fixed_pieces = []
        self.steps = 0
        self._constraints_by_cell = None

        # Visualization settings
        self._visualizer = None
        self._create_gif = False
        self._gif_speed = 400

    def add_constraint(self, constraint_type, pos1, pos2):
        self.constraints.append((constraint_type, pos1, pos2))
        self._constraints_by_cell = None

    def add_fixed_piece(self, row, col, piece_type):
        self.board[row][col] = piece_type
        self.fixed_pieces.append((row, col, piece_type))

        if self._create_gif and self._visualizer:
            self._visualizer.save_frame(
                self.board,
                self.constraints,
                (row, col),
                f"Fixed piece: {piece_type} at ({row}, {col})"
            )

    def is_valid_placement(self, row, col, piece_type):
        if not self._check_row_column_constraints(row, col, piece_type):
            return False

        if not self._check_no_three_consecutive(row, col, piece_type):
            return False

        if not self._check_equality_constraints(row, col, piece_type):
            return False

        return True

    def _check_row_column_constraints(self, row, col, piece_type):
        row_count = [0, 0]
        row_empty = 0
        for c in range(self.size):
            value = piece_type if c == col else self.board[row][c]
            if value is None:
                row_empty += 1
            else:
                row_count[value] += 1

        col_count = [0, 0]
        col_empty = 0
        for r in range(self.size):
            value = piece_type if r == row else self.board[r][col]
            if value is None:
                col_empty += 1
            else:
                col_count[value] += 1

        if any(count > 3 for count in row_count + col_count):
            return False

        return (
            row_count[0] + row_empty >= 3
            and row_count[1] + row_empty >= 3
            and col_count[0] + col_empty >= 3
            and col_count[1] + col_empty >= 3
        )

    def _cell_value_with_candidate(self, row, col, candidate_row, candidate_col, piece_type):
        if row == candidate_row and col == candidate_col:
            return piece_type
        return self.board[row][col]

    def _check_no_three_consecutive(self, row, col, piece_type):
        for start_col in range(max(0, col - 2), min(self.size - 2, col + 1)):
            if all(
                self._cell_value_with_candidate(row, start_col + i, row, col, piece_type) == piece_type
                for i in range(3)
            ):
                return False

        for start_row in range(max(0, row - 2), min(self.size - 2, row + 1)):
            if all(
                self._cell_value_with_candidate(start_row + i, col, row, col, piece_type) == piece_type
                for i in range(3)
            ):
                return False

        return True

    def _build_constraint_lookup(self):
        lookup = {(row, col): [] for row in range(self.size) for col in range(self.size)}
        for constraint_type, pos1, pos2 in self.constraints:
            lookup[pos1].append((constraint_type, pos1, pos2))
            lookup[pos2].append((constraint_type, pos1, pos2))
        self._constraints_by_cell = lookup

    def _check_equality_constraints(self, row, col, piece_type):
        if self._constraints_by_cell is None:
            self._build_constraint_lookup()

        for constraint_type, pos1, pos2 in self._constraints_by_cell.get((row, col), []):
            r1, c1 = pos1
            r2, c2 = pos2
            value1 = self._cell_value_with_candidate(r1, c1, row, col, piece_type)
            value2 = self._cell_value_with_candidate(r2, c2, row, col, piece_type)

            if value1 is not None and value2 is not None:
                if constraint_type == '=':
                    if value1 != value2:
                        return False
                elif constraint_type == 'x':
                    if value1 == value2:
                        return False

        return True

    def is_complete(self):
        for row in self.board:
            if None in row:
                return False

        for i in range(self.size):
            row_count = [0, 0]
            col_count = [0, 0]

            for j in range(self.size):
                row_count[self.board[i][j]] += 1
                col_count[self.board[j][i]] += 1

            if row_count != [3, 3] or col_count != [3, 3]:
                return False

        return True

    def solve(self, create_gif=False, gif_speed=400, gif_output="solving_animation.gif"):

        if create_gif:
            self._enable_gif_creation(gif_speed)

        result = self._backtrack()

        if create_gif and self._visualizer:
            self._finalize_gif(result, gif_output)

        return result

    def _enable_gif_creation(self, gif_speed=400):
        self._create_gif = True
        self._gif_speed = gif_speed
        self._visualizer = BoardVisualizer()
        self._visualizer.save_frame(
            self.board,
            self.constraints,
            None,
            f"Step {self.steps}: Initial board"
        )

    def _finalize_gif(self, solved, output_path):
        """Create final GIF"""
        status = "SOLVED" if solved else "NO SOLUTION"
        self._visualizer.save_frame(
            self.board,
            self.constraints,
            None,
            f"Step {self.steps}: {status}"
        )

        gif_path = self._visualizer.create_gif(
            output_path=output_path,
            duration=self._gif_speed,
            cleanup_frames=True
        )

        return gif_path

    def _backtrack(self):
        best_cell = None
        best_candidates = None

        for row in range(self.size):
            for col in range(self.size):
                if self.board[row][col] is not None:
                    continue

                candidates = [piece_type for piece_type in (0, 1) if self.is_valid_placement(row, col, piece_type)]
                if not candidates:
                    return False

                if best_candidates is None or len(candidates) < len(best_candidates):
                    best_cell = (row, col)
                    best_candidates = candidates
                    if len(best_candidates) == 1:
                        break
            if best_candidates is not None and len(best_candidates) == 1:
                break

        if best_cell is None or best_candidates is None:
            return self.is_complete()

        row, col = best_cell
        row_counts = [sum(1 for value in self.board[row] if value == piece_type) for piece_type in (0, 1)]
        col_counts = [sum(1 for r in range(self.size) if self.board[r][col] == piece_type) for piece_type in (0, 1)]
        ordered_candidates = sorted(best_candidates, key=lambda piece_type: (row_counts[piece_type] + col_counts[piece_type], piece_type))

        for piece_type in ordered_candidates:
            self.steps += 1

            if self._create_gif and self._visualizer:
                self._visualizer.save_frame(
                    self.board,
                    self.constraints,
                    (row, col),
                    f"Step {self.steps}: Trying {piece_type} at ({row}, {col})"
                )

            self.board[row][col] = piece_type

            if self._create_gif and self._visualizer:
                self._visualizer.save_frame(
                    self.board,
                    self.constraints,
                    (row, col),
                    f"Step {self.steps}: Placed {piece_type} at ({row}, {col})"
                )

            if self._backtrack():
                return True

            self.board[row][col] = None

            if self._create_gif and self._visualizer:
                self._visualizer.save_frame(
                    self.board,
                    self.constraints,
                    (row, col),
                    f"Step {self.steps}: Backtracking from ({row}, {col})"
                )

        return False

    def print_board_with_constraints(self):
        constraint_map = {}

        for constraint_type, pos1, pos2 in self.constraints:
            if constraint_type == '=':
                constraint_map[pos1] = '🟢'
                constraint_map[pos2] = '🟢'
            elif constraint_type == 'x':
                constraint_map[pos1] = '🔴'
                constraint_map[pos2] = '🔴'

        symbols = {0: '🌙', 1: '🟠', None: '⬜'}

        print("Board with constraints (🟢 = equals, 🔴 = not-equals):")
        for row_idx, row in enumerate(self.board):
            row_str = ""
            for col_idx, cell in enumerate(row):
                pos = (row_idx, col_idx)

                if cell is not None:
                    row_str += symbols[cell] + " "
                elif pos in constraint_map:
                    row_str += constraint_map[pos] + " "
                else:
                    row_str += symbols[None] + " "

            print(row_str.strip())
        print()

    def print_board(self):
        symbols = {0: '🌙', 1: '🟠', None: '⬜'}

        for row in self.board:
            print(' '.join(symbols[cell] for cell in row))
        print()

    def print_board_simple(self):
        """Print the board in simple format (for debugging)"""
        for row in self.board:
            print(' '.join(str(cell) if cell is not None else '.' for cell in row))
        print()

    def get_steps(self):
        return self.steps
