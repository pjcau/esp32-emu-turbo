#!/usr/bin/env python3
"""Generate PNG renders and animated GIF from PCB SVG files.

Creates:
- pcb-top.png, pcb-bottom.png — static renders
- pcb-animation.gif — animated flip between top/bottom with transition
"""

import io
import math
import os
import sys

import cairosvg
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = "website/static/img/pcb"
GIF_FRAMES = 60
GIF_DELAY = 80  # ms per frame
PAUSE_FRAMES = 20  # hold on each view
WIDTH = 800


def svg_to_png(svg_path, png_path, width=WIDTH):
    """Convert SVG to PNG using cairosvg."""
    cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=width)
    print(f"  PNG: {png_path}")


def svg_to_pil(svg_path, width=WIDTH):
    """Convert SVG to PIL Image."""
    png_data = cairosvg.svg2png(url=svg_path, output_width=width)
    return Image.open(io.BytesIO(png_data)).convert("RGBA")


def create_flip_frame(top_img, bot_img, progress, frame_w, frame_h):
    """Create a single frame of the flip animation.

    progress: 0.0 = full top view, 1.0 = full bottom view
    Uses a pseudo-3D perspective flip effect.
    """
    frame = Image.new("RGBA", (frame_w, frame_h), (13, 17, 35, 255))

    # Determine which image to show and scale factor
    if progress <= 0.5:
        # Showing top, shrinking horizontally
        img = top_img
        scale_x = math.cos(progress * math.pi)
    else:
        # Showing bottom, growing horizontally
        img = bot_img
        scale_x = -math.cos(progress * math.pi)

    if scale_x < 0.02:
        scale_x = 0.02

    # Scale the image
    new_w = max(1, int(img.width * scale_x))
    new_h = img.height

    # Add slight vertical perspective (narrower at the "back")
    scaled = img.resize((new_w, new_h), Image.LANCZOS)

    # Center it
    x_off = (frame_w - new_w) // 2
    y_off = (frame_h - new_h) // 2

    frame.paste(scaled, (x_off, y_off), scaled)
    return frame.convert("RGB")


def create_animated_gif(top_path, bot_path, gif_path):
    """Create animated GIF with flip transition between top and bottom."""
    top_img = svg_to_pil(top_path)
    bot_img = svg_to_pil(bot_path)

    frame_w = max(top_img.width, bot_img.width)
    frame_h = max(top_img.height, bot_img.height) + 40

    # Resize both to same dimensions
    top_img = top_img.resize((frame_w, frame_h - 40), Image.LANCZOS)
    bot_img = bot_img.resize((frame_w, frame_h - 40), Image.LANCZOS)

    frames = []

    # Phase 1: Hold on top view
    top_frame = create_flip_frame(top_img, bot_img, 0.0, frame_w, frame_h)
    for _ in range(PAUSE_FRAMES):
        frames.append(top_frame.copy())

    # Phase 2: Flip top → bottom
    flip_frames = 15
    for i in range(flip_frames):
        progress = i / (flip_frames - 1)
        f = create_flip_frame(top_img, bot_img, progress, frame_w, frame_h)
        frames.append(f)

    # Phase 3: Hold on bottom view
    bot_frame = create_flip_frame(top_img, bot_img, 1.0, frame_w, frame_h)
    for _ in range(PAUSE_FRAMES):
        frames.append(bot_frame.copy())

    # Phase 4: Flip bottom → top
    for i in range(flip_frames):
        progress = 1.0 - i / (flip_frames - 1)
        f = create_flip_frame(top_img, bot_img, progress, frame_w, frame_h)
        frames.append(f)

    # Save GIF
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=GIF_DELAY,
        loop=0,
        optimize=True,
    )
    size_kb = os.path.getsize(gif_path) / 1024
    print(f"  GIF: {gif_path} ({len(frames)} frames, {size_kb:.0f} KB)")


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    top_svg = os.path.join(output_dir, "pcb-top.svg")
    bot_svg = os.path.join(output_dir, "pcb-bottom.svg")

    if not os.path.exists(top_svg):
        print("ERROR: Run render_pcb_svg.py first to generate SVGs")
        sys.exit(1)

    # Static PNGs
    svg_to_png(top_svg, os.path.join(output_dir, "pcb-top.png"))
    svg_to_png(bot_svg, os.path.join(output_dir, "pcb-bottom.png"))

    # Combined PNG
    combined_svg = os.path.join(output_dir, "pcb-combined.svg")
    if os.path.exists(combined_svg):
        svg_to_png(combined_svg, os.path.join(output_dir, "pcb-combined.png"),
                   width=1600)

    # Animated GIF
    create_animated_gif(top_svg, bot_svg,
                        os.path.join(output_dir, "pcb-animation.gif"))

    print(f"\nGenerated PNG + GIF in {output_dir}/")


if __name__ == "__main__":
    main()
