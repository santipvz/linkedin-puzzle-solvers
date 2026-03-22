import sys
import os
from pathlib import Path
import time
import subprocess

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

img_dir = Path(__file__).parent / "img"
if not img_dir.exists():
    img_dir.mkdir(parents=True, exist_ok=True)

def run_test_file(test_file, image_path=None, create_gif=False):
    """
    Run a test file and return (success, output).
    """
    try:
        cmd = [sys.executable, test_file]
        if image_path and ("image_parser" in test_file or "grid_detection" in test_file or
                          "piece_detection" in test_file or "constraint_detection" in test_file or
                          "solver_integration" in test_file or "visual_debug" in test_file):
            cmd.append(image_path)

        if create_gif and "solver_integration" in test_file:
            cmd.append("--gif")

        project_root = Path(__file__).parent.parent
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def run_all_tests(image_path=None, include_visual=False, create_gif=False):
    """
    Run all test suites and generate comprehensive report.
    """
    print("🎯 TANGO SOLVER - TEST")
    print("=" * 70)
    print("Running all test modules")
    if create_gif:
        print("🎬 GIF animation will be created for solver tests")
    print()

    # Test files to run
    test_files = [
        ("Image Parser", "test_image_parser.py"),
        ("Grid Detection", "test_grid_detection.py"),
        ("Piece Detection", "test_piece_detection.py"),
        ("Constraint Detection", "test_constraint_detection.py"),
        ("Constraint Classifier", "test_constraint_classifier.py"),
        ("Solver Integration", "test_solver_integration.py"),
    ]

    # Visual debug tests
    visual_tests = [
        ("Visual Debug", "test_visual_debug.py"),
        ("Constraint Debug", "test_constraint_debug.py"),
    ]

    results = []

    print("📋 Running standard tests...")
    print()

    for test_name, test_file in test_files:
        print(f"🔄 Running {test_name} tests...")

        test_path = Path(__file__).parent / test_file
        if not test_path.exists():
            print(f"❌ Test file not found: {test_file}")
            results.append((test_name, False, f"File not found: {test_file}"))
            continue

        success, stdout, stderr = run_test_file(str(test_path), image_path, create_gif)

        if success:
            print(f"✅ {test_name}: PASSED")
        else:
            print(f"❌ {test_name}: FAILED")
            if stderr:
                print(f"   Error: {stderr.strip()}")

        results.append((test_name, success, stderr if stderr else ""))
        print()

    # Run visual tests if requested
    if include_visual and image_path:
        print("🎨 Running visual debugging tests...")
        print()

        for test_name, test_file in visual_tests:
            print(f"🔄 Running {test_name} tests...")

            test_path = Path(__file__).parent / test_file
            if not test_path.exists():
                print(f"❌ Test file not found: {test_file}")
                results.append((test_name, False, f"File not found: {test_file}"))
                continue

            success, stdout, stderr = run_test_file(str(test_path), image_path, create_gif)

            if success:
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
                if stderr:
                    print(f"   Error: {stderr.strip()}")

            results.append((test_name, success, stderr if stderr else ""))
            print()

        # Run constraint debug specifically with visual output
        print("🔍 Running constraint detection debug with visual output...")
        try:
            # Import and run the constraint debug function directly
            sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
            sys.path.insert(0, str(Path(__file__).parent))
            from test_constraint_debug import debug_constraint_detection

            # Save to tests/img/ directory
            img_dir = Path(__file__).parent / "img"
            img_dir.mkdir(exist_ok=True)

            # Convert relative path to absolute path from the main directory
            if not Path(image_path).is_absolute():
                image_path = str(Path(__file__).parent.parent / image_path)

            # Change to the output directory temporarily
            original_dir = os.getcwd()
            os.chdir(str(img_dir))

            try:
                debug_constraint_detection(image_path, save_debug=True)

                # Check if the image was actually saved
                expected_filename = f"constraint_debug_{Path(image_path).stem}.png"
                saved_path = img_dir / expected_filename
                if saved_path.exists():
                    print(f"✅ Constraint debug visualization saved to: {saved_path}")
                else:
                    print(f"✅ Constraint debug completed (check {img_dir} for output)")
            finally:
                os.chdir(original_dir)

        except Exception as e:
            print(f"❌ Failed to run constraint debug: {e}")
            results.append(("Constraint Debug Visual", False, str(e)))
    elif image_path:
        print("🎨 Visual debugging tests available!")
        print("   These generate PNG visualizations of grid detection and constraints.")
        print("   Run with --visual flag to include visual tests")
        print("   Or run manually: python3 tests/test_visual_debug.py [image_path]")
        print()

    # Generate final report
    print("📊 FINAL TEST REPORT")
    print("=" * 60)
    print(f"Image analyzed: {image_path if image_path else 'N/A'}")
    print(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    for test_name, success, error in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status:12} {test_name}")
        if error and not success:
            print(f"             Error: {error.strip()}")



if __name__ == "__main__":

    if "--help" in sys.argv:
        print("Usage: python3 -m tests.test_runner [image_path] [--visual] [--gif]")
        print("  --visual: Include visual debugging tests (generates PNG files)")
        print("  --gif: Create GIF animation for solver tests")
        sys.exit(0)

    include_visual = "--visual" in sys.argv
    create_gif = "--gif" in sys.argv

    if include_visual:
        sys.argv.remove("--visual")
    if create_gif:
        sys.argv.remove("--gif")

    # Determine image to use
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        image_path = None
        if not image_path:
            print("❌ No image found. Please provide image path as argument.")
            print("Usage: python3 -m tests.test_runner [image_path] [--visual] [--gif]")
            print("  --visual: Include visual debugging tests (generates PNG files)")
            print("  --gif: Create GIF animation for solver tests")
            sys.exit(1)

    # Run all tests
    success = run_all_tests(image_path, include_visual, create_gif)
    sys.exit(0 if success else 1)
