import os
import shutil
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


class BoardVisualizer:
    def __init__(self, board_size=6, cell_size=60, margin=20, top_margin=50):
        self.board_size = board_size
        self.cell_size = cell_size
        self.margin = margin
        self.top_margin = top_margin
        self.image_width = self.board_size * self.cell_size + 2 * self.margin
        self.image_height = self.board_size * self.cell_size + self.margin + self.top_margin

        # Colors
        self.colors = {
            0: (100, 150, 200),
            1: (255, 165, 0),
            None: (240, 240, 240),
            'grid': (60, 60, 60),
            'highlight': (255, 255, 0),
            'constraint_equal': (0, 255, 0),
            'constraint_diff': (255, 0, 0),
        }

        self.step_counter = 0
        self.frames_dir = "solver_frames"
        self._setup_frames_dir()

        # Load piece templates
        self._load_piece_templates()

    def _load_piece_templates(self):
        """Load moon and sun templates from templates directory."""
        templates_dir = Path(__file__).parent.parent / "templates"
        self.piece_templates = {}

        try:
            moon_path = templates_dir / "moon.png"
            sun_path = templates_dir / "sun.png"

            if moon_path.exists():
                self.piece_templates[0] = Image.open(moon_path).convert('RGBA')
            if sun_path.exists():
                self.piece_templates[1] = Image.open(sun_path).convert('RGBA')

        except Exception as e:
            print(f"Warning: Could not load piece templates: {e}")
            self.piece_templates = {}

    def _setup_frames_dir(self):
        if os.path.exists(self.frames_dir):
            shutil.rmtree(self.frames_dir)
        os.makedirs(self.frames_dir)

    def create_board_image(self, board, constraints=None, current_pos=None, step_info=""):
        img = Image.new('RGB', (self.image_width, self.image_height), 'white')
        draw = ImageDraw.Draw(img)

        if step_info:
            try:
                title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except Exception:
                title_font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), step_info, font=title_font)
            text_width = bbox[2] - bbox[0]
            text_x = (self.image_width - text_width) // 2
            text_y = 15

            padding = 5
            draw.rectangle([text_x - padding, text_y - padding,
                           text_x + text_width + padding, text_y + bbox[3] - bbox[1] + padding],
                          fill=(240, 240, 240), outline=(200, 200, 200))

            draw.text((text_x, text_y), step_info, fill='black', font=title_font)

        for row in range(self.board_size):
            for col in range(self.board_size):
                x1 = self.margin + col * self.cell_size
                y1 = self.top_margin + row * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                cell_value = board[row][col] if board[row] else None

                if (row, col) == current_pos:
                    color = self.colors['highlight']
                else:
                    color = self.colors.get(cell_value, self.colors[None])

                draw.rectangle([x1, y1, x2, y2], fill=color, outline=self.colors['grid'], width=2)

                if cell_value is not None:
                    # Use template images if available, otherwise fallback to text
                    if cell_value in self.piece_templates:
                        self._draw_piece_template(img, cell_value, x1, y1)
                    else:
                        # Fallback to text rendering
                        text_x = x1 + self.cell_size // 2
                        text_y = y1 + self.cell_size // 2

                        try:
                            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
                        except Exception:
                            font = ImageFont.load_default()

                        text = str(cell_value)
                        bbox = draw.textbbox((0, 0), text, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]

                        draw.text((text_x - text_width//2, text_y - text_height//2),
                                 text, fill='white', font=font)

        if constraints:
            self._draw_constraints(draw, constraints)

        return img

    def _draw_piece_template(self, img, piece_type, x1, y1):
        """Draw piece using template image."""
        template = self.piece_templates[piece_type]

        # Calculate size to fit in cell with some padding
        padding = 8
        target_size = self.cell_size - 2 * padding

        # Resize template to fit in cell
        template_resized = template.resize((target_size, target_size), Image.Resampling.LANCZOS)

        # Calculate position to center the template in the cell
        paste_x = x1 + padding
        paste_y = y1 + padding

        # Paste the template onto the board image
        img.paste(template_resized, (paste_x, paste_y), template_resized)

    def _draw_constraints(self, draw, constraints):
        constraint_size = 8

        for constraint_type, pos1, pos2 in constraints:
            r1, c1 = pos1
            r2, c2 = pos2

            x1 = self.margin + c1 * self.cell_size + self.cell_size // 2
            y1 = self.top_margin + r1 * self.cell_size + self.cell_size // 2  # Offset by top margin
            x2 = self.margin + c2 * self.cell_size + self.cell_size // 2
            y2 = self.top_margin + r2 * self.cell_size + self.cell_size // 2  # Offset by top margin

            color = self.colors['constraint_equal'] if constraint_type == '=' else self.colors['constraint_diff']

            draw.ellipse([x1-constraint_size, y1-constraint_size, x1+constraint_size, y1+constraint_size],
                        fill=color, outline='black', width=1)
            draw.ellipse([x2-constraint_size, y2-constraint_size, x2+constraint_size, y2+constraint_size],
                        fill=color, outline='black', width=1)

    def save_frame(self, board, constraints=None, current_pos=None, step_info=""):
        img = self.create_board_image(board, constraints, current_pos, step_info)
        filename = f"frame_{self.step_counter:06d}.png"
        filepath = os.path.join(self.frames_dir, filename)
        img.save(filepath)
        self.step_counter += 1
        return filepath

    def create_gif(self, output_path="solving_animation.gif", duration=200, cleanup_frames=True):
        if not os.path.exists(self.frames_dir):
            return None

        frame_files = [f for f in os.listdir(self.frames_dir) if f.startswith("frame_") and f.endswith(".png")]
        frame_files.sort()

        if not frame_files:
            return None

        images = []
        for frame_file in frame_files:
            frame_path = os.path.join(self.frames_dir, frame_file)
            img = Image.open(frame_path)
            images.append(img)

        if not images:
            return None

        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=duration,
            loop=0
        )

        if cleanup_frames:
            shutil.rmtree(self.frames_dir)

        return output_path

    def reset(self):
        self.step_counter = 0
        self._setup_frames_dir()
