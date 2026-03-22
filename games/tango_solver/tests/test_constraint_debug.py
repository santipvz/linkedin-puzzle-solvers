import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from template_constraint_classifier import TemplateConstraintClassifier
from image_parser import TangoImageParser

def debug_constraint_detection(image_path: str, save_debug: bool = True):
    print(f"🔍 Debugging constraint detection for: {image_path}")

    parser = TangoImageParser()
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ Could not load image: {image_path}")
        return

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    grid_coords = parser.grid_detector.detect_grid(img_rgb)
    print(f"✅ Grid detected with {len(grid_coords)}x{len(grid_coords[0])} cells")

    height, width = img_rgb.shape[:2]
    constraint_regions = []

    for row in range(6):
        for col in range(5):
            x1, y1, w1, h1 = grid_coords[row][col]

            border_x = x1 + w1 - 10
            border_y = y1
            border_w = 20
            border_h = h1

            if border_x >= 0 and border_x + border_w < width:
                border_img = img_rgb[border_y:border_y+border_h, border_x:border_x+border_w]

                target_color = np.array([140, 114, 76])
                color_diff = np.sqrt(np.sum((border_img - target_color) ** 2, axis=2))
                constraint_pixels = np.sum(color_diff < 30)

                if constraint_pixels > 8:
                    print(f"🎯 Found horizontal constraint candidate at ({row},{col})-({row},{col+1})")
                    constraint_regions.append({
                        'image': border_img,
                        'mask': (color_diff < 30).astype(np.uint8) * 255,
                        'position': f"({row},{col})-({row},{col+1})",
                        'orientation': 'horizontal',
                        'is_horizontal': True
                    })

    for row in range(5):
        for col in range(6):
            x1, y1, w1, h1 = grid_coords[row][col]

            border_x = x1
            border_y = y1 + h1 - 10
            border_w = w1
            border_h = 20

            if border_y >= 0 and border_y + border_h < height:
                border_img = img_rgb[border_y:border_y+border_h, border_x:border_x+border_w]

                target_color = np.array([140, 114, 76])
                color_diff = np.sqrt(np.sum((border_img - target_color) ** 2, axis=2))
                constraint_pixels = np.sum(color_diff < 30)

                if constraint_pixels > 8:
                    print(f"🎯 Found vertical constraint candidate at ({row},{col})-({row+1},{col})")
                    constraint_regions.append({
                        'image': border_img,
                        'mask': (color_diff < 30).astype(np.uint8) * 255,
                        'position': f"({row},{col})-({row+1},{col})",
                        'orientation': 'vertical',
                        'is_horizontal': False
                    })

    if not constraint_regions:
        print("❌ No constraint regions found")
        return

    print(f"✅ Found {len(constraint_regions)} constraint regions")

    classifier = TemplateConstraintClassifier()

    if save_debug:
        num_regions = len(constraint_regions)
        fig, axes = plt.subplots(num_regions, 4, figsize=(16, 4*num_regions))
        if num_regions == 1:
            axes = axes.reshape(1, -1)

        for i, region in enumerate(constraint_regions):
            print(f"\n🔍 Analyzing {region['orientation']} constraint at {region['position']}")

            axes[i, 0].imshow(region['image'])
            axes[i, 0].set_title(f"Original\n{region['position']}")
            axes[i, 0].axis('off')

            axes[i, 1].imshow(region['mask'], cmap='gray')
            axes[i, 1].set_title(f"Mask\n{region['orientation']}")
            axes[i, 1].axis('off')

            result = classifier.classify_constraint(region['mask'], region['is_horizontal'])
            print(f"   Template result: {result}")

            if len(region['image'].shape) == 3:
                gray_image = cv2.cvtColor(region['image'], cv2.COLOR_RGB2GRAY)
            else:
                gray_image = region['image'].copy()
            processed = classifier._preprocess_image(gray_image)

            axes[i, 2].imshow(processed, cmap='gray')
            axes[i, 2].set_title(f"Processed\nResult: {result}")
            axes[i, 2].axis('off')

            template_key = f"{'eq' if result == 'equals' else 'x'}_{'horizontal' if region['is_horizontal'] else 'vertical'}"
            if template_key in classifier.templates:
                template = classifier.templates[template_key]
                template_processed = classifier._preprocess_image(template)
                axes[i, 3].imshow(template_processed, cmap='gray')
                axes[i, 3].set_title(f"Template\n{template_key}")
            else:
                axes[i, 3].text(0.5, 0.5, 'No template', ha='center', va='center')
                axes[i, 3].set_title("No template")
            axes[i, 3].axis('off')

        plt.tight_layout()

        debug_path = "constraint_debug.png"
        plt.savefig(debug_path, dpi=150, bbox_inches='tight')
        print(f"💾 Debug visualization saved to: {debug_path}")

    else:
        for region in constraint_regions:
            result = classifier.classify_constraint(region['mask'], region['is_horizontal'])
            print(f"🎯 {region['position']} ({region['orientation']}): {result}")

def test_all_samples():
    examples_dir = Path(__file__).parent.parent / "examples"

    for sample_file in sorted(examples_dir.glob("sample*.png")):
        print(f"\n{'='*50}")
        debug_constraint_detection(str(sample_file), save_debug=False)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        test_all_samples()
    elif len(sys.argv) == 2:
        debug_constraint_detection(sys.argv[1])
    else:
        print("Usage:")
        print("  python test_constraint_debug.py                    # Test all samples")
        print("  python test_constraint_debug.py <image_path>       # Debug specific image")
        sys.exit(1)
