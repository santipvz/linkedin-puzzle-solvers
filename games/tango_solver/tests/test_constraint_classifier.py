import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from constraint_classifier import ConstraintClassifier


def test_constraint_classifier_robustness():
    """
    Test: Verify constraint classifier robustness.
    """
    print("🧪 Test: Constraint classifier robustness")
    print("-" * 50)

    try:
        classifier = ConstraintClassifier()

        # Test with empty image
        empty_img = np.zeros((50, 50, 3), dtype=np.uint8)
        result = classifier.classify_constraint(empty_img)
        print(f"✅ Empty image: {result} (expected: None)")

        # Test with noise image
        noise_img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        result = classifier.classify_constraint(noise_img)
        print(f"✅ Noise image: {result}")

        # Test with very small image
        tiny_img = np.ones((5, 5, 3), dtype=np.uint8) * 255
        result = classifier.classify_constraint(tiny_img)
        print(f"✅ Small image: {result}")

        # Test with horizontal symbol (should be '=')
        horizontal_img = np.ones((30, 60, 3), dtype=np.uint8) * 255
        horizontal_img[12:15, 10:50] = [140, 114, 76]  # Horizontal line
        horizontal_img[18:21, 10:50] = [140, 114, 76]  # Another line
        result = classifier.classify_constraint(horizontal_img)
        assert result == 'equals'

        # Test with diagonal symbol (should be 'x')
        diagonal_img = np.ones((40, 40, 3), dtype=np.uint8) * 255
        for i in range(20):
            if 10+i < 40 and 10+i < 40:
                diagonal_img[10+i, 10+i] = [140, 114, 76]  # Diagonal \
            if 10+i < 40 and 30-i >= 0:
                diagonal_img[10+i, 30-i] = [140, 114, 76]  # Diagonal /
        result = classifier.classify_constraint(diagonal_img)
        assert result == 'not_equals'

        print("✅ Classifier handles edge cases correctly")
        return True

    except Exception as e:
        print(f"❌ Error in classifier: {e}")
        return False


if __name__ == "__main__":
    print("🎯 CONSTRAINT CLASSIFIER TESTS")
    print("=" * 50)

    # Run test
    success = test_constraint_classifier_robustness()

    print(f"\n📊 Results: {'PASSED' if success else 'FAILED'}")

    sys.exit(0 if success else 1)
