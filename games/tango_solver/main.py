import sys
import os
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.image_parser import TangoImageParser
from src.tango_solver import TangoSolver


def solve_puzzle(image_path, create_gif=False, gif_speed=1, gif_output=None, verbose=False, show_details=False):

    if show_details:
        print(f"🖼️  Parsing puzzle from: {image_path}")

    # Parse image
    parser = TangoImageParser()
    board_state = parser.parse_image(image_path)

    if not board_state:
        print("❌ Failed to parse image")
        return False

    if show_details:
        print(f"✅ Found {len(board_state['fixed_pieces'])} fixed pieces")
        print(f"✅ Found {len(board_state['constraints'])} constraints")

    solver = TangoSolver()

    for piece in board_state['fixed_pieces']:
        solver.add_fixed_piece(piece['row'], piece['col'], piece['piece_type'])

    for constraint in board_state['constraints']:
        solver.add_constraint(constraint['type'], constraint['pos1'], constraint['pos2'])

    if show_details and board_state['fixed_pieces']:
        print("🔒 Fixed pieces:")
        for piece in board_state['fixed_pieces']:
            piece_emoji = "🌙" if piece['piece_type'] == 0 else "🟠"
            print(f"   ({piece['row']}, {piece['col']}): {piece_emoji}")

    if show_details and board_state['constraints']:
        print("🔗 Constraints:")
        for constraint in board_state['constraints']:
            print(f"   {constraint['pos1']} {constraint['type']} {constraint['pos2']}")

    if create_gif:
        if not gif_output:
            gif_output = f"{Path(image_path).stem}_solution.gif"

        success = solver.solve(create_gif=True, gif_speed=gif_speed, gif_output=gif_output)

        if success and show_details:
            print(f"✅ GIF saved: {gif_output}")
    else:
        success = solver.solve()

    if success:
        if show_details:
            print("✅ Puzzle solved!")
            print(f"📊 Steps: {solver.get_steps()}")

        if verbose:
            if show_details:
                print("\n🎉 Final solved board:")
            solver.print_board()

        return True
    else:
        print("❌ No solution found")
        if verbose:
            print("Final board state:")
            solver.print_board()
        return False


def main():

    parser = argparse.ArgumentParser(
        description="Solve LinkedIn Tango puzzles from images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 tango_cli.py examples/sample1.png
  python3 tango_cli.py examples/sample1.png --gif
  python3 tango_cli.py examples/sample1.png --gif --speed 500 --output my_solution.gif
        """
    )

    parser.add_argument("image", help="Path to puzzle image")
    parser.add_argument("--gif", action="store_true", help="Create GIF animation")
    parser.add_argument("--speed", type=int, default=1, help="GIF speed in ms (default: 1)")
    parser.add_argument("--output", help="Output GIF filename")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")

    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"❌ Image not found: {args.image}")
        return 1

    verbose = not args.quiet
    show_details = args.verbose and not args.quiet

    if not args.quiet:
        print("🎯 TANGO SOLVER")
        if args.gif:
            print("⚠️  GIF Selected: This may take a while for complex puzzles...")
            print("=" * 40)
        else:
            print("=" * 40)
    success = solve_puzzle(
        args.image,
        create_gif=args.gif,
        gif_speed=args.speed,
        gif_output=args.output,
        verbose=verbose,
        show_details=show_details
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
