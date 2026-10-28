"""
app.py - Streamlit Web UI for AI Property Video Generator.
Simple, robust, beginner-readable, designed for Streamlit Community Cloud and local execution.
"""

import os
import io
import tempfile
import traceback
from typing import Dict, Any, List
import streamlit as st
from PIL import Image

import importlib
import validators
import script_generator
import video_engine
from generate_sample import create_synthetic_room_image

# Force reload sub-modules so code changes take effect immediately without restarting Streamlit
importlib.reload(validators)
importlib.reload(script_generator)
importlib.reload(video_engine)

from validators import validate_text_fields, validate_uploaded_images
from script_generator import generate_property_script, get_gemini_api_key, GEMINI_MODEL_NAME
from video_engine import build_property_video


# Page configuration
st.set_page_config(
    page_title="AI Property Video Generator",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)


# --- Custom Styling for Premium Feel ---
st.markdown("""
<style>
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #38BDF8 0%, #818CF8 50%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        color: #38BDF8;
        margin-bottom: 0.25rem;
        display: inline-block;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #94A3B8;
        margin-bottom: 1.5rem;
    }
    .status-badge-ai {
        background-color: #DCFCE7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    .status-badge-tpl {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initializes session state defaults."""
    if "extra_room_slots" not in st.session_state:
        st.session_state.extra_room_slots = []
    if "sample_mode" not in st.session_state:
        st.session_state.sample_mode = False
    if "show_demo_modal" not in st.session_state:
        st.session_state.show_demo_modal = False
    if "sample_images" not in st.session_state:
        st.session_state.sample_images = {}
    if "form_defaults" not in st.session_state:
        st.session_state.form_defaults = {
            "name": "",
            "location": "",
            "landmark": "",
            "price": "",
            "property_type": "Flat",
            "bhk": 2,
            "features": "",
            "cta_text": ""
        }


init_session_state()


def populate_sample_data():
    """Populates form with synthetic sample data and placeholder images."""
    st.session_state.form_defaults = {
        "name": "Homeland Heights",
        "location": "Mohali",
        "landmark": "Opposite to Sohana Sahib",
        "price": "Rs 89 Lakh",
        "property_type": "Flat",
        "bhk": 2,
        "features": "Spacious sunlit balcony, Modular kitchen with chimney, Dedicated covered parking, 24x7 gated security",
        "cta_text": "Call 9800000000 to book a private tour"
    }
    # Pre-generate 5 synthetic room images
    st.session_state.sample_images = {
        "Living Room": create_synthetic_room_image("Living Room", (45, 55, 72), (28, 35, 51)),
        "Kitchen": create_synthetic_room_image("Kitchen", (70, 50, 45), (45, 30, 28)),
        "Bathroom": create_synthetic_room_image("Bathroom", (40, 65, 75), (25, 42, 50)),
        "Bedroom 1": create_synthetic_room_image("Bedroom 1", (55, 45, 65), (38, 28, 45)),
        "Bedroom 2": create_synthetic_room_image("Bedroom 2", (45, 65, 55), (28, 45, 38))
    }
    st.session_state.sample_mode = True


# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Gemini API Key (Hidden & Secure)
    detected_key = get_gemini_api_key()
    with st.expander("🔑 Gemini AI Setup (Secure)", expanded=False):
        if detected_key:
            st.success("✓ Gemini API Key configured: `••••••••••••`")
            st.caption(f"Model: `{GEMINI_MODEL_NAME}` (Key is securely masked)")
        else:
            st.info("ℹ️ Running in deterministic **Template Fallback** mode (No key needed).")
        
        manual_key = st.text_input(
            "Enter / Update Gemini Key:",
            type="password",
            placeholder="Paste key here (hidden)...",
            help="Your key is password-masked and never displayed in plaintext."
        )
        if manual_key.strip():
            os.environ["GEMINI_API_KEY"] = manual_key.strip()
            st.success("✓ Key saved securely for this session!")
            st.rerun()

    st.markdown("---")
    st.header("⚡ Quick Start")
    if st.button("✨ Load Sample 2BHK Data", use_container_width=True):
        populate_sample_data()
        st.success("Sample data & placeholder photos loaded!")
        st.rerun()

    if st.session_state.sample_mode:
        if st.button("Clear Sample Data", use_container_width=True):
            st.session_state.sample_mode = False
            st.session_state.sample_images = {}
            st.session_state.form_defaults = {
                "name": "", "location": "", "price": "", "property_type": "Flat",
                "bhk": 2, "features": "", "cta_text": ""
            }
            st.rerun()

    st.markdown("---")
    st.header("🎵 Audio Settings")
    voice_lang = st.selectbox(
        "Narration Language (gTTS)",
        options=["en", "hi"],
        format_func=lambda x: "English (en)" if x == "en" else "Hindi (hi)"
    )
    
    has_music_asset = os.path.exists(os.path.join("assets", "music.mp3"))
    enable_music = st.toggle("Include Background Music", value=True)
    if enable_music and not has_music_asset:
        st.caption("Note: `assets/music.mp3` not found. Will render without music.")

    st.markdown("---")
    st.header("🎬 Result Demo Video")
    demo_video_path = os.path.join("sample_output", "sample_video.mp4")
    if os.path.exists(demo_video_path):
        if st.button("▶️ View Demo Video on Screen", use_container_width=True, type="secondary"):
            st.session_state.show_demo_modal = True
            st.rerun()
        with st.expander("🎥 Quick Sidebar Player", expanded=False):
            st.video(demo_video_path)
    else:
        st.caption("Demo video will appear here after generation.")

    st.markdown("---")
    st.caption("AI Property Video Generator • 720p HD MP4 (H.264/AAC)")


# --- MAIN HEADER ---
st.markdown('<div class="main-title">AI Property Video Generator 🎬</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Generate elegant 20-40s slideshow promotional videos with slow zoom, '
    'narration voiceover, and modern overlays for real estate listings.</div>',
    unsafe_allow_html=True
)

if st.session_state.sample_mode:
    st.info("💡 **Sample Mode Active**: Form is filled with sample data & placeholder photos. Click **Generate Video** below to test immediately!")

# --- DEMO VIDEO POP-UP CONTAINER ---
if st.session_state.get("show_demo_modal", False):
    demo_video_path = os.path.join("sample_output", "sample_video.mp4")
    if os.path.exists(demo_video_path):
        st.markdown("---")
        d_col1, d_col2 = st.columns([4, 1])
        with d_col1:
            st.markdown("### 🎬 Result Demo Video")
            st.caption("Here is a pre-rendered promotional tour video showing Ken Burns slow zoom, voiceover narration, and caption overlays.")
        with d_col2:
            st.write("")
            if st.button("❌ Close Demo", use_container_width=True):
                st.session_state.show_demo_modal = False
                st.rerun()

        st.video(demo_video_path)
        st.markdown("---")

# --- PROPERTY DETAILS FORM ---
st.subheader("1. Property Details")
defaults = st.session_state.form_defaults

# Row 1: Name, Type, BHK
col1, col2, col3 = st.columns([2, 2, 1.5])
with col1:
    prop_name = st.text_input(
        "Property Name *",
        value=defaults.get("name", ""),
        placeholder="e.g. Homeland Heights"
    )

with col2:
    prop_type = st.selectbox(
        "Property Type *",
        options=["Flat", "House", "Villa"],
        index=["Flat", "House", "Villa"].index(defaults.get("property_type", "Flat"))
    )

with col3:
    bhk = st.selectbox(
        "BHK *",
        options=[1, 2, 3, 4],
        index=[1, 2, 3, 4].index(defaults.get("bhk", 2))
    )

# Row 2: Location, Landmark, Price
col_loc, col_lm, col_pr = st.columns([2, 2, 1.5])
with col_loc:
    location = st.text_input(
        "Location *",
        value=defaults.get("location", ""),
        placeholder="e.g. Mohali"
    )

with col_lm:
    landmark = st.text_input(
        "Landmark (Optional)",
        value=defaults.get("landmark", ""),
        placeholder="e.g. Opposite to Sohana Sahib"
    )

with col_pr:
    price = st.text_input(
        "Price *",
        value=defaults.get("price", ""),
        placeholder="e.g. Rs 89 Lakh"
    )

col_feat, col_cta = st.columns(2)
with col_feat:
    features = st.text_area(
        "Key Features (comma or line separated)",
        value=defaults.get("features", ""),
        placeholder="e.g. Spacious sunlit balcony, Modular kitchen, Covered parking, 24x7 security",
        height=100
    )

with col_cta:
    cta_text = st.text_area(
        "Contact / CTA Text *",
        value=defaults.get("cta_text", ""),
        placeholder="e.g. Call 9800000000 to book a private tour",
        height=100
    )


# --- ROOM-WISE PHOTO UPLOADS ---
st.markdown("---")
st.subheader("2. Room-wise Photos (Minimum 4, Maximum 8)")
st.info(
    "💡 **Image Framing & Sizing Note:** Please upload proper landscape images "
    "(recommended: **1280x720** px, 16:9 widescreen) for the best visual presentation. "
    "Photos of other dimensions, portrait orientation, or different sizes will be "
    "**automatically adjusted, scaled, and center-cropped** to fit the video frame."
)
st.caption("Upload photos for each room. The video engine applies Ken Burns slow zoom and crisp caption bars.")

# Dynamic required slots based on BHK
required_slots = ["Living Room", "Kitchen", "Bathroom"] + [f"Bedroom {i}" for i in range(1, bhk + 1)]
optional_slots = ["Storeroom", "Balcony", "Exterior / Front"]

uploaded_files_map: Dict[str, Any] = {}

st.markdown("##### Required Room Slots")
req_cols = st.columns(min(len(required_slots), 4))
for idx, room in enumerate(required_slots):
    col = req_cols[idx % len(req_cols)]
    with col:
        st.markdown(f"**{room}** *")
        # Check if sample image is available
        has_sample = room in st.session_state.sample_images
        file = st.file_uploader(
            f"Upload {room}",
            type=["jpg", "jpeg", "png"],
            key=f"req_{room}",
            label_visibility="collapsed"
        )
        if file:
            uploaded_files_map[room] = file
        elif has_sample and st.session_state.sample_mode:
            uploaded_files_map[room] = st.session_state.sample_images[room]
            st.caption("✓ Sample photo active")

st.markdown("##### Optional Room Slots")
opt_cols = st.columns(len(optional_slots))
for idx, room in enumerate(optional_slots):
    with opt_cols[idx]:
        st.markdown(f"**{room}** (Optional)")
        file = st.file_uploader(
            f"Upload {room}",
            type=["jpg", "jpeg", "png"],
            key=f"opt_{room}",
            label_visibility="collapsed"
        )
        if file:
            uploaded_files_map[room] = file

# Extra Custom Photo Slots
with st.expander("➕ Add Extra Room Photos"):
    st.caption("Add custom room labels (e.g. 'Second Kitchen', 'Study Room', 'Garden Terrace').")
    col_add_name, col_add_btn = st.columns([3, 1])
    with col_add_name:
        new_slot_name = st.text_input("New Room Label", placeholder="e.g. Study Room", key="new_slot_name")
    with col_add_btn:
        st.write("")
        st.write("")
        if st.button("Add Slot"):
            slot_clean = new_slot_name.strip()
            if slot_clean and slot_clean not in st.session_state.extra_room_slots:
                st.session_state.extra_room_slots.append(slot_clean)
                st.rerun()

    if st.session_state.extra_room_slots:
        for extra_room in st.session_state.extra_room_slots:
            ecol1, ecol2 = st.columns([4, 1])
            with ecol1:
                st.markdown(f"**{extra_room}**")
                file = st.file_uploader(
                    f"Upload {extra_room}",
                    type=["jpg", "jpeg", "png"],
                    key=f"extra_{extra_room}",
                    label_visibility="collapsed"
                )
                if file:
                    uploaded_files_map[extra_room] = file
            with ecol2:
                st.write("")
                st.write("")
                if st.button("Remove", key=f"remove_{extra_room}"):
                    st.session_state.extra_room_slots.remove(extra_room)
                    st.rerun()

total_uploaded_count = len(uploaded_files_map)
st.caption(f"Total photos selected: **{total_uploaded_count}** (Max 8 used in video)")


# --- GENERATE VIDEO ACTION ---
st.markdown("---")
generate_clicked = st.button("🎬 Generate Property Video", type="primary", use_container_width=True)

if generate_clicked:
    # 1. Validate Text Fields
    form_data = {
        "name": prop_name,
        "location": location,
        "landmark": landmark,
        "price": price,
        "property_type": prop_type,
        "bhk": bhk,
        "features": features,
        "cta_text": cta_text,
        "voice_lang": voice_lang
    }
    
    missing_fields = validate_text_fields(form_data)
    if missing_fields:
        st.error(f"Missing mandatory fields: {', '.join(missing_fields)}. Please complete all fields marked with *.")
        st.stop()

    # 2. Validate Photos
    is_img_valid, valid_photos, img_errors, img_warnings = validate_uploaded_images(
        photos_dict=uploaded_files_map,
        required_room_labels=required_slots
    )

    # Display warnings if any
    for w in img_warnings:
        st.warning(w)

    # Display blocking errors
    if not is_img_valid:
        for e in img_errors:
            st.error(e)
        st.stop()

    # 3. Execution Pipeline with Spinner & Progress
    progress_bar = st.progress(0, text="Initializing video generation pipeline...")
    
    try:
        room_labels_used = [label for label, _ in valid_photos]

        # Stage A: Script Generation
        progress_bar.progress(15, text="✍️ Stage 1/3: Generating promotional script...")
        script_data, is_ai, status_msg = generate_property_script(form_data, room_labels_used)
        
        if is_ai:
            st.toast(f"AI script generated via Gemini ({GEMINI_MODEL_NAME})", icon="✨")
        else:
            st.info(f"ℹ️ {status_msg}")

        # Stage B: Video Assembly & Audio Mixing
        def on_video_progress(pct: float, stage_msg: str):
            mapped_pct = int(20 + pct * 75)
            progress_bar.progress(mapped_pct, text=f"🎬 Stage 2/3: {stage_msg}")

        output_filename = f"property_tour_{bhk}bhk.mp4"
        with tempfile.TemporaryDirectory() as run_temp_dir:
            temp_output_path = os.path.join(run_temp_dir, output_filename)

            final_mp4, render_warnings = build_property_video(
                form_data=form_data,
                valid_photos=valid_photos,
                script_data=script_data,
                output_path=temp_output_path,
                voice_lang=voice_lang,
                enable_music=enable_music,
                progress_callback=on_video_progress
            )

            for rw in render_warnings:
                st.warning(rw)

            # Read video bytes for Streamlit playback and download
            with open(final_mp4, "rb") as vf:
                video_bytes = vf.read()

        progress_bar.progress(100, text="✅ Video successfully generated!")
        st.success("🎉 Your promotional property video is ready!")

        # Layout: Video Preview and Script Info
        col_vid, col_info = st.columns([3, 2])
        with col_vid:
            st.video(video_bytes)
            st.download_button(
                label="⬇️ Download Video (MP4)",
                data=video_bytes,
                file_name=f"{prop_name.replace(' ', '_').lower()}_tour.mp4",
                mime="video/mp4",
                type="primary",
                use_container_width=True
            )

        with col_info:
            st.markdown("### Generated Script Details")
            if is_ai:
                st.markdown(f'<span class="status-badge-ai">✨ AI-Generated (Gemini {GEMINI_MODEL_NAME})</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="status-badge-tpl">📋 Deterministic Template Fallback</span>', unsafe_allow_html=True)

            st.write(f"**Title**: {script_data.get('title')}")
            
            with st.expander("View Full Script JSON", expanded=True):
                st.json(script_data)

    except Exception as ex:
        progress_bar.empty()
        st.error(f"❌ Video generation encountered an unexpected error: {str(ex)}")
        with st.expander("Technical Traceback (for debugging)"):
            st.code(traceback.format_exc(), language="python")
