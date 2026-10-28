"""
video_engine.py - Complete video rendering pipeline for AI Property Video Generator.
Handles image preparation, Pillow text overlays, Ken Burns zoom, TTS audio sync,
crossfade transitions, and H.264 MP4 export without ImageMagick.
"""

import os
import tempfile
from typing import Dict, List, Tuple, Any, Optional, Callable
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from moviepy.editor import (
    VideoClip, AudioFileClip, CompositeVideoClip,
    CompositeAudioClip, concatenate_videoclips
)
from moviepy.audio.fx.all import audio_loop, volumex
from gtts import gTTS


# Target HD resolution
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
MAX_ZOOM_RATIO = 0.08  # Slow 1.0 -> 1.08 Ken Burns zoom
OVERSIZED_WIDTH = int(TARGET_WIDTH * (1.0 + MAX_ZOOM_RATIO))   # 1382
OVERSIZED_HEIGHT = int(TARGET_HEIGHT * (1.0 + MAX_ZOOM_RATIO)) # 778
CROSSFADE_DURATION = 0.5


def get_font(size: int = 28, bold: bool = False) -> ImageFont.ImageFont:
    """
    Safely loads a TrueType font with cross-platform fallbacks.
    Tries DejaVuSans on Debian/Streamlit Cloud, Segoe UI / Arial on Windows,
    and falls back to PIL default font so it never crashes.
    """
    font_candidates = [
        # Debian / Ubuntu / Streamlit Cloud paths (from packages.txt fonts-dejavu-core)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        # Windows system paths
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/tahomabd.ttf" if bold else "C:/Windows/Fonts/tahoma.ttf",
        # Local or font name lookups
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "arial.ttf"
    ]
    
    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass

    # Graceful fallback to default font
    return ImageFont.load_default()


def _get_text_dimensions(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    """Helper to get text width and height across PIL versions."""
    try:
        bbox = font.getbbox(text)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])
    except Exception:
        try:
            return draw.textsize(text, font=font)
        except Exception:
            return (len(text) * 10, 20)


def prepare_base_image(img: Image.Image) -> Image.Image:
    """
    Prepares raw image for Ken Burns rendering:
    1. Fixes EXIF rotation.
    2. Converts to RGB.
    3. Downscales extreme sizes (>4K) for performance.
    4. Scales & center-crops to oversized dimensions (1382x778).
    """
    # 1. EXIF rotation fix
    img = ImageOps.exif_transpose(img)
    
    # 2. Ensure RGB
    if img.mode != "RGB":
        img = img.convert("RGB")
        
    # 3. Downscale if very large (> 3840x2160)
    if img.width > 3840 or img.height > 2160:
        img.thumbnail((2560, 1440), Image.Resampling.LANCZOS)
        
    # 4. Crop & fit to oversized viewport preserving 16:9 aspect ratio
    fitted = ImageOps.fit(img, (OVERSIZED_WIDTH, OVERSIZED_HEIGHT), method=Image.Resampling.LANCZOS)
    return fitted


def create_title_overlay(form_data: Dict[str, Any]) -> Image.Image:
    """
    Builds the title card overlay with property name, type, location, and price.
    Returns RGBA Image with transparent background.
    """
    overlay = Image.new("RGBA", (TARGET_WIDTH, TARGET_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Center card dimensions
    card_x1, card_y1 = 140, 110
    card_x2, card_y2 = 1140, 610
    
    # Elegant dark semi-transparent card with subtle border
    draw.rounded_rectangle(
        [(card_x1, card_y1), (card_x2, card_y2)],
        radius=20,
        fill=(15, 23, 42, 220),       # Slate 900 at ~86% opacity
        outline=(59, 130, 246, 160),  # Subtle blue border
        width=2
    )

    # 1. Top Pill Badge: e.g. "2 BHK FLAT FOR SALE"
    bhk = form_data.get("bhk", 2)
    prop_type = str(form_data.get("property_type", "Flat")).upper()
    badge_text = f"{bhk} BHK {prop_type} FOR SALE"
    badge_font = get_font(20, bold=True)
    bw, bh = _get_text_dimensions(draw, badge_text, badge_font)
    
    pill_cx = TARGET_WIDTH // 2
    pill_y = 155
    pill_w = bw + 36
    pill_h = bh + 14
    draw.rounded_rectangle(
        [(pill_cx - pill_w // 2, pill_y), (pill_cx + pill_w // 2, pill_y + pill_h)],
        radius=12,
        fill=(37, 99, 235, 220)  # Primary blue
    )
    draw.text((pill_cx - bw // 2, pill_y + 6), badge_text, font=badge_font, fill=(255, 255, 255, 255))

    # 2. Main Property Title
    title_text = str(form_data.get("name", "Featured Property"))
    title_font = get_font(46, bold=True)
    tw, th = _get_text_dimensions(draw, title_text, title_font)
    draw.text(((TARGET_WIDTH - tw) // 2, 230), title_text, font=title_font, fill=(255, 255, 255, 255))

    # 3. Location with optional landmark
    landmark = str(form_data.get("landmark", "")).strip()
    loc_base = str(form_data.get("location", "Prime Area")).strip()
    loc_text = f"Location: {loc_base} • {landmark}" if landmark else f"Location: {loc_base}"
    loc_font = get_font(24 if len(loc_text) > 40 else 26, bold=False)
    lw, lh = _get_text_dimensions(draw, loc_text, loc_font)
    draw.text(((TARGET_WIDTH - lw) // 2, 310), loc_text, font=loc_font, fill=(203, 213, 225, 240))

    # 4. Subtle separator line
    draw.line([(card_x1 + 80, 375), (card_x2 - 80, 375)], fill=(71, 85, 105, 140), width=1)

    # 5. Price Highlight Pill
    price_val = str(form_data.get("price", "Price on Request"))
    price_label = f"Price: {price_val}"
    price_font = get_font(36, bold=True)
    pw, ph = _get_text_dimensions(draw, price_label, price_font)
    
    p_box_w = pw + 48
    p_box_h = ph + 20
    p_box_y = 415
    draw.rounded_rectangle(
        [(pill_cx - p_box_w // 2, p_box_y), (pill_cx + p_box_w // 2, p_box_y + p_box_h)],
        radius=14,
        fill=(16, 185, 129, 230)  # Vibrant Emerald green
    )
    draw.text((pill_cx - pw // 2, p_box_y + 8), price_label, font=price_font, fill=(255, 255, 255, 255))

    # 6. Bottom subtitle invitation
    sub_text = "Exclusive Walkthrough Preview"
    sub_font = get_font(22, bold=False)
    sw, _ = _get_text_dimensions(draw, sub_text, sub_font)
    draw.text(((TARGET_WIDTH - sw) // 2, 530), sub_text, font=sub_font, fill=(148, 163, 184, 220))

    return overlay


def create_room_overlay(room_label: str, caption: str) -> Image.Image:
    """
    Builds the room scene overlay with a modern bottom bar and room label.
    Returns RGBA Image with transparent background.
    """
    overlay = Image.new("RGBA", (TARGET_WIDTH, TARGET_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Bottom bar background
    bar_top = 560
    draw.rectangle([(0, bar_top), (TARGET_WIDTH, TARGET_HEIGHT)], fill=(15, 23, 42, 225))
    
    # Top accent line on bar
    draw.line([(0, bar_top), (TARGET_WIDTH, bar_top)], fill=(59, 130, 246, 200), width=3)

    # Room Label Badge (e.g. "LIVING ROOM")
    badge_text = room_label.upper()
    badge_font = get_font(18, bold=True)
    bw, bh = _get_text_dimensions(draw, badge_text, badge_font)
    
    badge_x = 60
    badge_y = bar_top + 22
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + bw + 24, badge_y + bh + 10)],
        radius=8,
        fill=(37, 99, 235, 240)
    )
    draw.text((badge_x + 12, badge_y + 4), badge_text, font=badge_font, fill=(255, 255, 255, 255))

    # Caption Text (Max 8 words, bold, large, readable)
    caption_font = get_font(30, bold=True)
    draw.text((badge_x, bar_top + 70), caption, font=caption_font, fill=(255, 255, 255, 255))

    return overlay


def create_cta_overlay(form_data: Dict[str, Any], cta_caption: str) -> Image.Image:
    """
    Builds the final enquiry / CTA scene overlay.
    Returns RGBA Image with transparent background.
    """
    overlay = Image.new("RGBA", (TARGET_WIDTH, TARGET_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    card_x1, card_y1 = 140, 110
    card_x2, card_y2 = 1140, 610
    
    # Dark card
    draw.rounded_rectangle(
        [(card_x1, card_y1), (card_x2, card_y2)],
        radius=20,
        fill=(15, 23, 42, 230),
        outline=(245, 158, 11, 160),  # Amber accent border
        width=2
    )

    cx = TARGET_WIDTH // 2

    # Top Heading
    header_text = "READY TO MAKE THIS YOUR HOME?"
    h_font = get_font(24, bold=True)
    hw, _ = _get_text_dimensions(draw, header_text, h_font)
    draw.text((cx - hw // 2, 160), header_text, font=h_font, fill=(245, 158, 11, 255))

    # Main CTA Box
    cta_display = cta_caption.strip() if cta_caption else form_data.get("cta_text", "Call to Book a Visit")
    cta_font = get_font(36, bold=True)
    cw, ch = _get_text_dimensions(draw, cta_display, cta_font)
    
    cta_box_w = min(cw + 60, 940)
    cta_box_h = ch + 26
    cta_box_y = 230
    draw.rounded_rectangle(
        [(cx - cta_box_w // 2, cta_box_y), (cx + cta_box_w // 2, cta_box_y + cta_box_h)],
        radius=14,
        fill=(217, 119, 6, 240)  # Rich Amber
    )
    draw.text((cx - cw // 2, cta_box_y + 11), cta_display, font=cta_font, fill=(255, 255, 255, 255))

    # Property info reminder
    prop_line = f"{form_data.get('name', 'Property')} • {form_data.get('bhk', 2)} BHK {form_data.get('property_type', 'Flat')}"
    p_font = get_font(26, bold=False)
    pw, _ = _get_text_dimensions(draw, prop_line, p_font)
    draw.text((cx - pw // 2, 330), prop_line, font=p_font, fill=(226, 232, 240, 240))

    # Location reminder with optional landmark
    landmark = str(form_data.get("landmark", "")).strip()
    loc_base = str(form_data.get("location", "")).strip()
    loc_line = f"📍 {loc_base} ({landmark})" if landmark else f"📍 {loc_base}"
    lw, _ = _get_text_dimensions(draw, loc_line, p_font)
    draw.text((cx - lw // 2, 380), loc_line, font=p_font, fill=(148, 163, 184, 220))

    # Price pill
    price_text = f"Priced at {form_data.get('price', 'Contact for Price')}"
    price_font = get_font(30, bold=True)
    prw, prh = _get_text_dimensions(draw, price_text, price_font)
    draw.rounded_rectangle(
        [(cx - prw // 2 - 20, 440), (cx + prw // 2 + 20, 440 + prh + 16)],
        radius=10,
        fill=(16, 185, 129, 220)
    )
    draw.text((cx - prw // 2, 446), price_text, font=price_font, fill=(255, 255, 255, 255))

    # Closing prompt
    closing_text = "Schedule your site visit or request a full brochure"
    cl_font = get_font(20, bold=False)
    clw, _ = _get_text_dimensions(draw, closing_text, cl_font)
    draw.text((cx - clw // 2, 530), closing_text, font=cl_font, fill=(148, 163, 184, 200))

    return overlay


def build_ken_burns_clip(
    base_oversized_img: Image.Image,
    overlay_img: Image.Image,
    duration: float,
    is_blurred_bg: bool = False
) -> VideoClip:
    """
    Creates a VideoClip with a smooth Ken Burns slow zoom (1.0 -> 1.08).
    Text overlay is static and crisp on top of the zooming background.
    """
    if is_blurred_bg:
        # Subtle blur for title or CTA scene
        base_img = base_oversized_img.filter(ImageFilter.GaussianBlur(radius=6))
    else:
        base_img = base_oversized_img

    base_w, base_h = base_img.size
    dw = base_w - TARGET_WIDTH
    dh = base_h - TARGET_HEIGHT

    def make_frame(t):
        # Progress 0.0 -> 1.0
        progress = min(max(t / max(duration, 0.1), 0.0), 1.0)
        curr_w = int(base_w - dw * progress)
        curr_h = int(base_h - dh * progress)
        left = (base_w - curr_w) // 2
        top = (base_h - curr_h) // 2

        # Crop and resize to exact 1280x720
        cropped = base_img.crop((left, top, left + curr_w, top + curr_h))
        frame = cropped.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.BILINEAR)

        # Composite static text overlay
        frame_rgba = frame.convert("RGBA")
        frame_rgba.alpha_composite(overlay_img)
        return np.array(frame_rgba.convert("RGB"))

    return VideoClip(make_frame, duration=duration)


def generate_tts_file(text: str, lang: str, out_path: str) -> bool:
    """
    Generates TTS speech audio via gTTS.
    Returns True on success, False if network/library error occurs.
    """
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(out_path)
        return True
    except Exception:
        return False


def build_property_video(
    form_data: Dict[str, Any],
    valid_photos: List[Tuple[str, Image.Image]],
    script_data: Dict[str, Any],
    output_path: str,
    voice_lang: str = "en",
    enable_music: bool = True,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Tuple[str, List[str]]:
    """
    Master video assembly pipeline:
    1. Prepares images and text overlays.
    2. Generates TTS speech audio per scene and measures duration.
    3. Calculates sync durations (clamped to 20-40 seconds total).
    4. Applies Ken Burns zoom + crossfade transitions.
    5. Loops and mixes royalty-free background music if available.
    6. Exports 1280x720 H.264 MP4.
    
    Returns:
    - output_path (str)
    - warnings (list of str)
    """
    warnings: List[str] = []
    
    def report(pct: float, msg: str):
        if progress_callback:
            progress_callback(pct, msg)

    report(0.05, "Preparing scene images and overlays...")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        # Prepare scenes data
        # Scene 0: Title Scene
        # Scenes 1..N: One per room photo
        # Scene N+1: CTA Scene
        
        # 1. Base oversized images
        primary_photo = valid_photos[0][1]
        last_photo = valid_photos[-1][1]

        title_base = prepare_base_image(primary_photo)
        title_overlay = create_title_overlay(form_data)

        room_bases = [prepare_base_image(img) for _, img in valid_photos]
        room_scenes = script_data.get("scenes", [])
        room_overlays = []
        for i, (room_label, _) in enumerate(valid_photos):
            caption = room_scenes[i]["caption"] if i < len(room_scenes) else room_label
            room_overlays.append(create_room_overlay(room_label, caption))

        cta_base = prepare_base_image(last_photo)
        cta_caption = script_data.get("cta", {}).get("caption", form_data.get("cta_text", "Contact Us"))
        cta_overlay = create_cta_overlay(form_data, cta_caption)

        # 2. Generate Audio Narration
        report(0.20, "Generating narration voiceover with gTTS...")
        
        # Prepare voiceover texts
        name = form_data.get("name", "Modern Home")
        bhk = form_data.get("bhk", 2)
        prop_type = form_data.get("property_type", "Flat")
        location = form_data.get("location", "Prime Area")
        landmark = str(form_data.get("landmark", "")).strip()

        if landmark:
            title_text = f"Welcome to {name}, a {bhk} BHK {prop_type} in {location}, {landmark}."
        else:
            title_text = f"Welcome to {name}, a {bhk} BHK {prop_type} in {location}."
        room_texts = [
            room_scenes[i]["voiceover"] if i < len(room_scenes) else f"Here is the {room_label}."
            for i, (room_label, _) in enumerate(valid_photos)
        ]
        cta_text = script_data.get("cta", {}).get("voiceover", f"Contact us to book your visit for {name}.")

        all_texts = [title_text] + room_texts + [cta_text]
        num_scenes = len(all_texts)

        audio_paths: List[Optional[str]] = []
        audio_durations: List[float] = []

        gtts_failed = False
        for idx, text in enumerate(all_texts):
            out_file = os.path.join(temp_dir, f"scene_{idx}.mp3")
            success = generate_tts_file(text, lang=voice_lang, out_path=out_file)
            if success and os.path.exists(out_file):
                try:
                    ac = AudioFileClip(out_file)
                    dur = float(ac.duration)
                    ac.close()
                    audio_paths.append(out_file)
                    audio_durations.append(dur)
                except Exception:
                    audio_paths.append(None)
                    audio_durations.append(0.0)
            else:
                gtts_failed = True
                audio_paths.append(None)
                audio_durations.append(0.0)

        if gtts_failed:
            warnings.append("Voiceover service was unavailable. Video rendered with fixed scene timing.")

        # 3. Synchronize Scene Durations (Target around 45 seconds total with 0.4s sentence gap)
        report(0.40, "Synchronizing scene timing and audio...")
        # Rule: add 0.4 sec of clean silence after speech before crossfade begins
        # Speech starts at +0.15s, finishes at +0.15s + dur.
        # Next scene transition starts at scene_dur - CROSSFADE_DURATION (0.5s).
        # To guarantee at least 0.4s silence after speech: scene_dur = max(3.5, dur + 0.15 + 0.40 + 0.50)
        scene_durations = [min(7.5, max(3.5, dur + 1.05)) for dur in audio_durations]
        
        # Crossfade overlap is CROSSFADE_DURATION (0.5s) between consecutive scenes
        # Total video duration with crossfade:
        raw_total = sum(scene_durations) - (num_scenes - 1) * CROSSFADE_DURATION

        # Clamp total duration strictly around 45.0 seconds (max 45.0s)
        if raw_total > 45.0:
            scale = 45.0 / raw_total
            scene_durations = [max(3.5, dur * scale) for dur in scene_durations]
        elif raw_total < 25.0:
            scale = 42.0 / raw_total
            scene_durations = [dur * scale for dur in scene_durations]

        # 4. Build Ken Burns Video Clips
        report(0.55, "Rendering slow zoom frames and scene transitions...")
        clips: List[VideoClip] = []

        # Title clip
        c_title = build_ken_burns_clip(title_base, title_overlay, scene_durations[0], is_blurred_bg=True)
        clips.append(c_title)

        # Room clips
        for idx in range(len(valid_photos)):
            c_room = build_ken_burns_clip(
                room_bases[idx],
                room_overlays[idx],
                scene_durations[idx + 1],
                is_blurred_bg=False
            )
            # Add crossfade in
            c_room = c_room.crossfadein(CROSSFADE_DURATION)
            clips.append(c_room)

        # CTA clip
        c_cta = build_ken_burns_clip(
            cta_base,
            cta_overlay,
            scene_durations[-1],
            is_blurred_bg=True
        ).crossfadein(CROSSFADE_DURATION)
        clips.append(c_cta)

        # Concatenate video clips with 0.5s crossfade padding
        final_video = concatenate_videoclips(clips, method="compose", padding=-CROSSFADE_DURATION)
        # Fix exact duration to end of last clip
        final_video.duration = max(c.end for c in final_video.clips)

        # 5. Assemble Synchronized Audio Tracks
        report(0.70, "Mixing narration voiceover and ambient music...")
        voice_clips = []
        opened_audio_clips = []

        for idx, (a_path, v_clip) in enumerate(zip(audio_paths, final_video.clips)):
            if a_path and os.path.exists(a_path):
                try:
                    ac = AudioFileClip(a_path)
                    opened_audio_clips.append(ac)
                    # Align narration with 0.15s initial padding to prevent word-cut
                    ac_timed = ac.set_start(v_clip.start + 0.15)
                    voice_clips.append(ac_timed)
                except Exception:
                    pass

        # Background music handling
        music_path = os.path.join("assets", "music.mp3")
        bg_clip = None
        if enable_music:
            if os.path.exists(music_path):
                try:
                    raw_bg = AudioFileClip(music_path)
                    opened_audio_clips.append(raw_bg)
                    
                    # Loop or trim to total video duration
                    if raw_bg.duration < final_video.duration:
                        looped_bg = audio_loop(raw_bg, duration=final_video.duration)
                    else:
                        looped_bg = raw_bg.subclip(0, final_video.duration)
                        
                    # Lower volume to ~12% (-18 dB) under speech
                    bg_clip = volumex(looped_bg, 0.12)
                except Exception as e:
                    warnings.append(f"Could not load background music ({str(e)}). Skipped.")
            else:
                warnings.append("Background music file 'assets/music.mp3' not found. Video rendered without music.")

        # Composite audio mixing
        audio_layers = []
        if voice_clips:
            voice_composite = CompositeAudioClip(voice_clips)
            audio_layers.append(voice_composite)
        if bg_clip:
            audio_layers.append(bg_clip)

        if audio_layers:
            final_audio = CompositeAudioClip(audio_layers).set_duration(final_video.duration)
            final_video = final_video.set_audio(final_audio)

        # 6. Export Final Video
        report(0.85, "Encoding H.264 MP4 with ultrafast preset...")
        
        final_video.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            threads=2,
            logger=None
        )

        # Close all opened clips to free file handles on Windows
        try:
            for ac in opened_audio_clips:
                ac.close()
            final_video.close()
            for c in clips:
                c.close()
        except Exception:
            pass

        report(1.0, "Video generation complete!")

    return output_path, warnings
