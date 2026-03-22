import sys
from pathlib import Path
import cv2

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from image_parser import TangoImageParser


def test_grid_detection(image_path):
    """
    Test: Verify that 6x6 grid detection works correctly.
    """
    print("🧪 Test: 6x6 Grid detection")
    print("-" * 50)

    try:
        parser = TangoImageParser()
        img = cv2.imread(image_path)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Use grid detector
        grid_coords = parser.grid_detector.detect_grid(img_rgb)

        # Verify it returns a 6x6 grid
        if len(grid_coords) != 6:
            print(f"❌ Error: Expected 6 rows, found {len(grid_coords)}")
            return False

        for i, row in enumerate(grid_coords):
            if len(row) != 6:
                print(f"❌ Error: Row {i} has {len(row)} columns, expected 6")
                return False

        print("✅ 6x6 grid detected correctly")

        # Verify coordinates are valid
        img_height, img_width = img_rgb.shape[:2]
        valid_coords = True

        for row in range(6):
            for col in range(6):
                x, y, w, h = grid_coords[row][col]
                if x < 0 or y < 0 or x + w > img_width or y + h > img_height:
                    print(f"❌ Invalid coordinates at ({row},{col}): x={x}, y={y}, w={w}, h={h}")
                    valid_coords = False

        if valid_coords:
            print("✅ All cell coordinates are valid")

        return valid_coords

    except Exception as e:
        print(f"❌ Error in grid detection: {e}")
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
            print("Usage: python3 -m tests.test_grid_detection [image_path]")
            sys.exit(1)

    print("🎯 GRID DETECTION TESTS")
    print("=" * 50)

    # Run test
    success = test_grid_detection(image_path)

    print(f"\n📊 Results: {'PASSED' if success else 'FAILED'}")

    sys.exit(0 if success else 1)
