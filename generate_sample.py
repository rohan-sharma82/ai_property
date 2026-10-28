"""
generate_sample.py - Standalone CLI sample video generator.
Generates synthetic room images and renders a complete 720p MP4 without Streamlit UI.
"""

import os
import json
import sys
from PIL import Image, ImageDraw, ImageFont
from script_generator import generate_property_script
from video_engine import build_property_video, get_font


def create_synthetic_room_image(
    room_name: str,
    color_primary: tuple,
    color_secondary: tuple,
    width: int = 1280,
    height: int = 720
) -> Image.Image:
    """
    Creates an attractive synthetic room image using Pillow with architectural
    gradients and room markings. Fully synthetic with zero external assets needed.
    """
    # Create base gradient
    base = Image.new("RGB", (width, height), color_primary)
    draw = ImageDraw.Draw(base)

    # Architectural floor and ceiling perspective lines
    draw.polygon([(0, 480), (width, 480), (width, height), (0, height)], fill=color_secondary)
    draw.line([(0, 480), (width, 480)], fill=(255, 255, 255, 60), width=3)
    
    # Perspective wall lines
    draw.line([(0, 0), (220, 480)], fill=(255, 255, 255, 40), width=2)
    draw.line([(width, 0), (width - 220, 480)], fill=(255, 255, 255, 40), width=2)

    # Window / decor architectural box
    win_x1, win_y1, win_x2, win_y2 = 360, 100, 920, 400
    draw.rectangle([(win_x1, win_y1), (win_x2, win_y2)], fill=(220, 235, 250), outline=(255, 255, 255), width=4)
    # Window panes
    draw.line([(win_x1 + (win_x2 - win_x1)//2, win_y1), (win_x1 + (win_x2 - win_x1)//2, win_y2)], fill=(200, 215, 230), width=3)
    draw.line([(win_x1, win_y1 + (win_y2 - win_y1)//2), (win_x2, win_y1 + (win_y2 - win_y1)//2)], fill=(200, 215, 230), width=3)

    # Room title banner watermark
    font = get_font(42, bold=True)
    text = f"Sample: {room_name}"
    try:
        bbox = font.getbbox(text)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        tw, th = 300, 40

    # Draw centered badge in the window
    badge_x = (width - tw) // 2
    badge_y = 220
    draw.rounded_rectangle([(badge_x - 20, badge_y - 10), (badge_x + tw + 20, badge_y + th + 10)], radius=10, fill=(15, 23, 42))
    draw.text((badge_x, badge_y), text, font=font, fill=(255, 255, 255))

    return base


def run_cli_generator():
    """CLI orchestrator for sample generation."""
    print("=" * 60)
    print("   AI PROPERTY VIDEO GENERATOR - CLI SAMPLE BUILDER")
    print("=" * 60)

    # 1. Load sample JSON
    sample_json_path = os.path.join("sample_data", "sample_input.json")
    if not os.path.exists(sample_json_path):
        print(f"Error: Sample data file '{sample_json_path}' not found.")
        sys.exit(1)

    with open(sample_json_path, "r", encoding="utf-8") as f:
        form_data = json.load(f)

    print(f"\n[1/4] Loaded property data: {form_data.get('name')} ({form_data.get('location')})")

    # 2. Build synthetic room photos
    print("\n[2/4] Generating synthetic room photo assets...")
    room_specs = [
        ("Living Room", (45, 55, 72), (28, 35, 51)),
        ("Kitchen", (70, 50, 45), (45, 30, 28)),
        ("Bathroom", (40, 65, 75), (25, 42, 50)),
        ("Bedroom 1", (55, 45, 65), (38, 28, 45)),
        ("Bedroom 2", (45, 65, 55), (28, 45, 38))
    ]

    valid_photos = []
    room_labels = []
    for room_name, c_prim, c_sec in room_specs:
        img = create_synthetic_room_image(room_name, c_prim, c_sec)
        valid_photos.append((room_name, img))
        room_labels.append(room_name)
        print(f"  -> Created synthetic photo for '{room_name}' (1280x720)")

    # 3. Generate script
    print("\n[3/4] Generating promotional narration script...")
    script_data, is_ai, status_msg = generate_property_script(form_data, room_labels)
    engine_type = "Gemini AI" if is_ai else "Deterministic Template"
    print(f"  -> Script generated via: {engine_type}")
    print(f"  -> Status: {status_msg}")
    print(f"  -> Title: {script_data.get('title')}")
    print(f"  -> Scenes count: {len(script_data.get('scenes', []))}")

    # 4. Render video
    output_mp4 = os.path.join("sample_output", "sample_video.mp4")
    print(f"\n[4/4] Rendering video pipeline -> {output_mp4}")
    
    def on_progress(pct: float, msg: str):
        bar_len = 30
        filled = int(bar_len * pct)
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"\r  [{bar}] {int(pct * 100):3d}% | {msg}", end="", flush=True)

    out_file, warnings = build_property_video(
        form_data=form_data,
        valid_photos=valid_photos,
        script_data=script_data,
        output_path=output_mp4,
        voice_lang=form_data.get("voice_lang", "en"),
        enable_music=True,
        progress_callback=on_progress
    )

    print("\n\n" + "=" * 60)
    print("   GENERATION COMPLETE!")
    print("=" * 60)
    print(f"Output File: {os.path.abspath(out_file)}")
    print(f"File Size  : {os.path.getsize(out_file) / (1024 * 1024):.2f} MB")
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  * {w}")
    print("=" * 60)


if __name__ == "__main__":
    run_cli_generator()
