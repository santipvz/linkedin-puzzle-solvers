import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from image_parser import TangoImageParser


def test_piece_detection_structure(image_path):
    """
    Test: Verify that piece detection returns valid structure.
    """
    print("🧪 Test: Piece detection structure")
    print("-" * 50)

    try:
        parser = TangoImageParser()
        board_state = parser.parse_image(image_path)

        fixed_pieces = board_state['fixed_pieces']
        empty_cells = board_state['empty_cells']

        print(f"✅ Fixed pieces detected: {len(fixed_pieces)}")
        print(f"✅ Empty cells detected: {len(empty_cells)}")

        # Verify that sum of pieces + empty cells = 36
        total_cells = len(fixed_pieces) + len(empty_cells)
        if total_cells != 36:
            print(f"❌ Error: Total cells {total_cells} ≠ 36")
            return False

        print("✅ Correct total cells (36)")

        # Verify fixed pieces structure
        valid_pieces = True
        for piece in fixed_pieces:
            # Verify required keys
            if not all(key in piece for key in ['row', 'col', 'piece_type']):
                print(f"❌ Piece with invalid structure: {piece}")
                valid_pieces = False
                continue

            # Verify ranges
            if not (0 <= piece['row'] <= 5 and 0 <= piece['col'] <= 5):
                print(f"❌ Piece at invalid position: ({piece['row']}, {piece['col']})")
                valid_pieces = False

            if piece['piece_type'] not in [0, 1]:
                print(f"❌ Invalid piece type: {piece['piece_type']}")
                valid_pieces = False

        if valid_pieces:
            print("✅ All pieces have valid structure")

        # Verify no duplicate positions
        positions = set()
        duplicates = False
        for piece in fixed_pieces:
            pos = (piece['row'], piece['col'])
            if pos in positions:
                print(f"❌ Duplicate position in pieces: {pos}")
                duplicates = True
            positions.add(pos)

        for pos in empty_cells:
            if pos in positions:
                print(f"❌ Duplicate position between piece and empty cell: {pos}")
                duplicates = True
            positions.add(pos)

        if not duplicates:
            print("✅ No duplicate positions")

        return valid_pieces and not duplicates and total_cells == 36

    except Exception as e:
        print(f"❌ Error in piece structure: {e}")
        return False


if __name__ == "__main__":
    import sys

    # Determine image to use
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        image_path = None
        if not image_path:
            print("❌ No image found. Please provide image path as argument.")
            print("Usage: python3 -m tests.test_piece_detection [image_path]")
            sys.exit(1)

    print("🎯 PIECE DETECTION TESTS")
    print("=" * 50)

    # Run test
    success = test_piece_detection_structure(image_path)

    print(f"\n📊 Results: {'PASSED' if success else 'FAILED'}")

    sys.exit(0 if success else 1)
