#!/usr/bin/env python3
"""Main entry point for the Queens Puzzle Solver application."""

import sys
import os
import argparse

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.queens_solver import QueensSolver


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Solve Queens puzzle from board images using computer vision",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py board.png                          # Show board solution
  python main.py board.png --verbose                # Detailed progress
  python main.py board.png --quiet                  # One-line result
  python main.py board.png --output results         # Custom output directory
        """
    )

    parser.add_argument(
        'image_path',
        help='Path to the board image file'
    )

    parser.add_argument(
        '--output', '-o',
        default='output',
        help='Output directory for results (default: output)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output (show detailed progress)'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Run in quiet mode (minimal one-line output)'
    )

    args = parser.parse_args()

    # Handle conflicting arguments
    if args.quiet and args.verbose:
        print("Error: Cannot use both --quiet and --verbose at the same time")
        return 1

    # Validate input file
    if not os.path.exists(args.image_path):
        print(f"Error: Image file not found: {args.image_path}")
        return 1

    # Create solver
    # Default behavior: show basic output with board
    # --verbose: show detailed output
    # --quiet: minimal output only
    verbose_mode = args.verbose
    solver = QueensSolver(verbose=verbose_mode)

    # Solve puzzle
    success = solver.solve_from_image(args.image_path, args.output, quiet_mode=args.quiet)

    # Handle output messages based on mode
    if not args.quiet:
        if success:
            print(f"\n✅ Results saved to: {args.output}/")
        else:
            print("\n❌ Failed to solve puzzle")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
