# 🌙🟠 Tango Solver

Computer vision system for automatically solving Tango puzzles from images using OpenCV and constraint satisfaction algorithms.

## 🎯 What is Tango?

Tango is a LinkedIn logic puzzle where you fill a 6x6 grid with moon (🌙) and sun (🟠) pieces following constraints:
- **Fixed pieces**: Some cells have predetermined pieces
- **Equality constraints**: Connected cells must have the same piece type
- **Inequality constraints**: Connected cells must have different piece types
- **Balance rule**: Each row and column should have equal numbers of moons and suns

## ✨ Features
- Automatic grid and piece detection from images
- Constraint detection through visual pattern recognition with template matching
- Backtracking algorithm with constraint propagation
- Visual debugging and solution visualization
- GIF animation: Step-by-step visualization of the backtracking algorithm (⚠️ significantly slower execution)

## 🚀 Installation & Usage

1. **Install dependencies (from monorepo root):**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r games/tango_solver/requirements.txt
```

2. **Solve a puzzle:**
```bash
python3 games/tango_solver/main.py games/tango_solver/examples/sample1.png
```

**Use your own puzzle image:**
```bash
python3 games/tango_solver/main.py path/to/your/puzzle.png
```

### Options

```bash
python3 games/tango_solver/main.py games/tango_solver/examples/sample1.png --verbose   # Detailed output
python3 games/tango_solver/main.py games/tango_solver/examples/sample1.png --gif       # Generate GIF animation (⚠️ much slower)
python3 games/tango_solver/main.py games/tango_solver/examples/sample1.png --quiet     # Minimal output
```

**Example:**
```bash
python3 games/tango_solver/main.py games/tango_solver/examples/sample5.png --verbose
```
![TEST](assets/test.gif)

### GIF Animation

You can generate an animated GIF showing how the backtracking algorithm explores the solution space:

```bash
# Generate GIF with default settings (1 ms default speed)
python3 games/tango_solver/main.py games/tango_solver/examples/sample1.png --gif

# Custom GIF speed and output filename
python3 games/tango_solver/main.py games/tango_solver/examples/sample1.png --gif --speed 500 --output my_solution.gif
```

⚠️ **Warning**: Generating the GIF animation significantly slows down the solving process as it captures and saves each step of the backtracking algorithm.

The GIF visualization shows:
- Yellow highlights: current position being processed
- Green dots: equality constraints (=)
- Red dots: difference constraints (x)
- Blue cells: piece type 0
- Orange cells: piece type 1

### Tests & Debugging

Run these commands from `games/tango_solver`:

```bash
python3 -m tests.test_runner           # Run all tests
python3 -m tests.test_runner --visual  # With debug images (saves to tests/img/)

# Test with specific image and generate visualizations:
python3 -m tests.test_runner examples/sample5.png --visual

# Test with your own image:
python3 -m tests.test_runner path/to/your/puzzle.png --visual

# Test with GIF generation:
python3 -m tests.test_runner examples/sample1.png --gif
```

### Constraint Detection Debugging

Debug constraint detection on all samples:
```bash
python3 -m tests.test_constraint_debug
```

Debug constraint detection on a specific image with visual output:
```bash
python3 -m tests.test_constraint_debug examples/sample6.png
```

This will show you exactly how the system detects and classifies each constraint, with visual comparisons between the detected regions and the templates used for matching.

### Example Puzzle

![Sample Puzzle](examples/sample5.png)

*Example of a Tango puzzle - Initial board state with fixed pieces and constraints*

### Visual Debug Output

The system generates comprehensive debugging visualizations when running tests with the `--visual` flag:

```bash
python3 -m tests.test_runner examples/sample5.png --visual
```

This generates the following debug images in `tests/img/`:

![Grid Detection](assets/grid_detection_debug.png)

*Grid detection analysis - Shows detected pieces, constraints, and cell boundaries*

![Constraint Heatmap](assets/constraint_heatmap.png)

*Constraint density heatmap - Visualizes constraint distribution across the grid*

![Solved Board](assets/solved_board.png)

*Solution visualization - The final solved puzzle with constraints overlay*

![Comprehensive Debug](assets/comprehensive_visualization.png)

*Complete debug view - Combined analysis with statistics and legend*

![Solution Animation](assets/sample5_solution.gif)

*Animated representation of the backtracking algorithm in action*


## ⚠️ Important: Image Quality Requirements

**It is crucial that the puzzle image is cropped as tightly as possible to the board area.** The presence of irrelevant information around the board can cause errors in constraint and fixed piece detection.

### Comparative Example

The following shows the same board captured in two different ways:

#### ✅ Correct Image (Cropped to board)
![Right Image](assets/right.png)

```
🎯 TANGO SOLVER
========================================
🖼️  Parsing puzzle from: examples/sample6.png
✅ Found 10 fixed pieces
✅ Found 4 constraints
🔒 Fixed pieces:
   (0, 2): 🟠
   (0, 3): 🌙
   (2, 0): 🟠
   (2, 3): 🟠
   (2, 5): 🟠
   (3, 0): 🟠
   (3, 2): 🌙
   (3, 5): 🌙
   (5, 2): 🌙
   (5, 3): 🟠
🔗 Constraints:
   (1, 4) = (1, 5)
   (4, 0) x (4, 1)
   (0, 1) x (1, 1)
   (4, 4) x (5, 4)
✅ Puzzle solved!
📊 Steps: 96

🎉 Final solved board:
🌙 🟠 🟠 🌙 🟠 🌙
🌙 🌙 🟠 🌙 🟠 🟠
🟠 🌙 🌙 🟠 🌙 🟠
🟠 🟠 🌙 🟠 🌙 🌙
🌙 🟠 🟠 🌙 🟠 🌙
🟠 🌙 🌙 🟠 🌙 🟠
```

#### ❌ Incorrect Image (With irrelevant information)
![Wrong Image](assets/wrong.png)

```
🎯 TANGO SOLVER
========================================
🖼️  Parsing puzzle from: assets/wrong.png
✅ Found 11 fixed pieces
✅ Found 1 constraints
🔒 Fixed pieces:
   (0, 2): 🟠
   (2, 0): 🟠
   (2, 1): 🟠
   (2, 3): 🟠
   (2, 4): 🟠
   (2, 5): 🟠
   (3, 0): 🟠
   (3, 1): 🟠
   (3, 2): 🌙
   (5, 2): 🌙
   (5, 3): 🟠
🔗 Constraints:
   (4, 4) x (5, 4)
❌ No solution found
Final board state:
⬜ ⬜ 🟠 ⬜ ⬜ ⬜
⬜ ⬜ ⬜ ⬜ ⬜ ⬜
🟠 🟠 ⬜ 🟠 🟠 🟠
🟠 🟠 🌙 ⬜ ⬜ ⬜
⬜ ⬜ ⬜ ⬜ ⬜ ⬜
⬜ ⬜ 🌙 🟠 ⬜ ⬜
```

As can be observed:
- **Correct image**: Detected 10 fixed pieces and 4 constraints.
- **Incorrect image**: Detected 11 fixed pieces and only 1 constraint → **❌ No solution found**

The difference in constraint detection (4 vs 1) is critical and causes the same board to be unsolvable when the image contains irrelevant information.


## 🛠️ Architecture

- **`main.py`**: Command-line interface
- **`src/image_parser.py`**: Image processing and feature extraction
- **`src/tango_solver.py`**: Constraint satisfaction solver with optional GIF generation
- **`src/visualizer.py`**: Board visualization and GIF animation creation
- **`tests/`**: Comprehensive test suite with visual debugging

```mermaid
classDiagram
direction TB
    class TangoCLI {
        +main()
        +parse_args()
        +setup_logging()
    }

    class TangoImageParser {
        -grid_detector: GridDetector
        -piece_detector: PieceDetector
        -constraint_classifier: TemplateConstraintClassifier
        +parse_image(image_path: str) Dict
        -_extract_board_contents(img, grid_coords) Dict
        -_detect_edge_constraints(img, grid_coords) List
        -_analyze_border_for_constraint(border_img, is_horizontal) str
    }

    class TangoSolver {
        -board: List~List~int~~
        -constraints: List~Dict~
        -fixed_pieces: Dict
        -visualizer: BoardVisualizer
        +add_constraint(pos1, pos2, constraint_type)
        +add_fixed_piece(row, col, piece_type)
        +solve(create_gif: bool) bool
        +print_board()
        -_is_valid_placement(row, col, piece_type) bool
        -_backtrack(create_gif) bool
        -_check_row_col_balance() bool
    }

    class BoardVisualizer {
        -board_size: int
        -cell_size: int
        -frames: List
        +create_board_image(board, constraints, current_pos) Image
        +save_frame(board, constraints, current_pos)
        +create_gif(output_path, speed_ms)
        +visualize_solution(board, constraints)
    }

    class GridDetector {
        +detect_grid(img: ndarray) List~List~Tuple~~
        -_detect_grid_lines(img) Tuple
        -_extract_cell_coords(lines) List
    }

    class PieceDetector {
        +detect_piece(cell_img: ndarray) Dict
        -_analyze_colors(img) Dict
        -_classify_piece_type(colors) int
    }

    class TemplateConstraintClassifier {
        -templates_dir: Path
        -templates: Dict
        +classify_constraint(image: ndarray, is_horizontal: bool) str
        +_load_templates() Dict
        +_extract_constraint_from_template(template, name) ndarray
        +_preprocess_image(image) ndarray
        +_match_template(image, template) float
        +_fallback_classify(image) str
    }

    class ConstraintClassifier {
        <<fallback>>
        +classify_constraint(image: ndarray) str
        -_count_horizontal_connections(mask) int
        -_count_diagonal_connections(mask) int
    }

    %% Notes for key components
    note for TangoImageParser "Main image processing pipeline<br/>Coordinates all detection components<br/>Handles both horizontal and vertical constraints"
    note for TangoSolver "Constraint satisfaction solver<br/>Backtracking with pruning<br/>Optional step-by-step visualization"
    note for TemplateConstraintClassifier "Advanced template-based matching<br/>High accuracy constraint detection<br/>Fallback to heuristic classifier"
    note for BoardVisualizer "Visual output generation<br/>GIF animation support<br/>Debug visualizations"

    %% Relationships
    TangoCLI --> TangoImageParser : uses
    TangoCLI --> TangoSolver : uses
    TangoSolver --> BoardVisualizer : contains
    TangoImageParser --> GridDetector : contains
    TangoImageParser --> PieceDetector : contains
    TangoImageParser --> TemplateConstraintClassifier : contains
    TemplateConstraintClassifier --> ConstraintClassifier : fallback to
    TangoImageParser ..> TangoSolver : provides data
```
## 📋 Requirements

- Python 3.8+
- OpenCV 4.0+
- NumPy, Pillow, Matplotlib
