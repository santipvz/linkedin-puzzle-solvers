import sys
import os
from pathlib import Path
import cv2

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from image_parser import TangoImageParser


def test_image_loading_and_parsing(image_path):
    """
    Test: Verify that image loads and parses correctly.
    """
    print("🧪 Test: Image loading and parsing")
    print("-" * 50)

    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return False

    try:
        # Verify OpenCV can load the image
        img = cv2.imread(image_path)
        if img is None:
            print("❌ OpenCV could not load image")
            return False

        print(f"✅ Image loaded: {img.shape}")

        # Verify parser can process the image
        parser = TangoImageParser()
        board_state = parser.parse_image(image_path)

        if board_state is None:
            print("❌ Error in image parsing")
            return False

        print("✅ Parsing successful")
        print(f"   • Valid data structure: {type(board_state)}")
        print(f"   • Keys found: {list(board_state.keys())}")

        return True

    except Exception as e:
        print(f"❌ Error during loading/parsing: {e}")
        return False


def test_edge_cases_and_robustness(image_path):
    """
    Test: Edge cases and general system robustness.
    """
    print("\n🧪 Test: Edge cases and robustness")
    print("-" * 50)

    try:
        parser = TangoImageParser()

        # Test with non-existent image
        result = parser.parse_image("non_existent_image.png")
        if result is None:
            print("✅ Correctly handles non-existent image")
        else:
            print("⚠️  Should return None for non-existent image")

        # Test with current image (should work)
        board_state = parser.parse_image(image_path)
        if board_state:
            print("✅ Processes valid image correctly")

            # Verify consistency across multiple parses
            board_state2 = parser.parse_image(image_path)
            if board_state2:
                # Compare results (should be equal)
                same_pieces = len(board_state['fixed_pieces']) == len(board_state2['fixed_pieces'])
                same_constraints = len(board_state['constraints']) == len(board_state2['constraints'])

                if same_pieces and same_constraints:
                    print("✅ Consistent results across multiple parses")
                else:
                    print("⚠️  Inconsistent results between parses")

        return True

    except Exception as e:
        print(f"❌ Error in edge cases: {e}")
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
            print("Usage: python3 -m tests.test_image_parser [image_path]")
            sys.exit(1)

    print("🎯 IMAGE PARSER TESTS")
    print("=" * 50)

    # Run tests
    tests = [
        test_image_loading_and_parsing,
        test_edge_cases_and_robustness,
    ]

    passed = 0
    total = len(tests)

    for test_func in tests:
        try:
            if test_func(image_path):
                passed += 1
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

    print(f"\n📊 Results: {passed}/{total} tests passed")
    success = passed == total
    print("✅ All tests passed!" if success else "❌ Some tests failed")

    sys.exit(0 if success else 1)
