import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from image_parser import TangoImageParser


def test_constraint_detection_structure(image_path):
    """
    Test: Verify that constraint detection returns valid structure.
    """
    print("🧪 Test: Constraint detection structure")
    print("-" * 50)

    try:
        parser = TangoImageParser()
        board_state = parser.parse_image(image_path)

        constraints = board_state['constraints']
        print(f"✅ Constraints detected: {len(constraints)}")

        if len(constraints) == 0:
            print("⚠️  No constraints detected (may be valid)")
            return True

        # Verify constraint structure
        valid_constraints = True
        for i, constraint in enumerate(constraints):
            # Verify required keys
            if not all(key in constraint for key in ['type', 'pos1', 'pos2']):
                print(f"❌ Constraint {i} with invalid structure: {constraint}")
                valid_constraints = False
                continue

            # Verify constraint type
            if constraint['type'] not in ['=', 'x']:
                print(f"❌ Invalid constraint type: '{constraint['type']}'")
                valid_constraints = False

            # Verify positions
            pos1, pos2 = constraint['pos1'], constraint['pos2']
            for pos in [pos1, pos2]:
                if not (isinstance(pos, tuple) and len(pos) == 2):
                    print(f"❌ Position with invalid format: {pos}")
                    valid_constraints = False
                    continue

                if not (0 <= pos[0] <= 5 and 0 <= pos[1] <= 5):
                    print(f"❌ Position out of range: {pos}")
                    valid_constraints = False

            # Verify positions are adjacent
            if valid_constraints:
                row_diff = abs(pos1[0] - pos2[0])
                col_diff = abs(pos1[1] - pos2[1])

                if not ((row_diff == 1 and col_diff == 0) or (row_diff == 0 and col_diff == 1)):
                    print(f"❌ Constraint between non-adjacent positions: {pos1} ↔ {pos2}")
                    valid_constraints = False

        if valid_constraints:
            print("✅ All constraints have valid structure")

        # Show detected constraints for information
        if constraints:
            print("📋 Constraints found:")
            for constraint in constraints:
                type_emoji = "🟢" if constraint['type'] == '=' else "🔴"
                print(f"   {type_emoji} {constraint['type']} between {constraint['pos1']} ↔ {constraint['pos2']}")

        return valid_constraints

    except Exception as e:
        print(f"❌ Error in constraint structure: {e}")
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
            print("Usage: python3 -m tests.test_constraint_detection [image_path]")
            sys.exit(1)

    print("🎯 CONSTRAINT DETECTION TESTS")
    print("=" * 50)

    # Run test
    success = test_constraint_detection_structure(image_path)

    print(f"\n📊 Results: {'PASSED' if success else 'FAILED'}")

    sys.exit(0 if success else 1)
