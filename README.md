# AI Property Video Generator 🏠🎬

A simple, robust, production-ready Streamlit web prototype that transforms real estate listing details and room-wise photos into a polished 20-40 second promotional MP4 slideshow video.

Designed specifically for real estate sales teams, the app runs locally and deploys seamlessly on **Streamlit Community Cloud** with **zero paid API dependencies** and **no ImageMagick installation required**.

---

## 🌟 Key Features

- **Dynamic Room Slots**: Automatically configures required photo slots based on property type and BHK count (e.g. Living Room, Kitchen, Bathroom, Bedroom 1..N) plus optional and custom room slots.
- **AI-Powered Narration (Gemini Free Tier)**: Writes concise, engaging promotional scripts using `gemini-2.5-flash` with strict anti-hallucination guardrails.
- **Deterministic Template Fallback**: Automatically falls back to a deterministic f-string script if no API key is provided, if rate limits are hit, or if AI validation fails.
- **Natural Voice Narration (gTTS)**: Generates synchronized audio narration per scene in English or Hindi.
- **Pillow-Based Video Overlay**: Renders all high-definition text overlays, badges, and caption bars using Pillow. **Does not require ImageMagick**, ensuring 100% compatibility with Streamlit Community Cloud.
- **Ken Burns Slow Zoom**: Smooth frame-by-frame subtle zoom-in (1.0 -> 1.08) on property photos.
- **Audio-Video Synchronization**: Dynamically calculates scene durations based on speech length (`scene_duration = max(3.0, audio_dur + 0.5)`), clamped strictly between 20 and 40 seconds total.
- **Crossfade Transitions & Ambient Music**: 0.5s smooth crossfades between scenes and royalty-free ambient background music mixed at ~12% volume under the narration.
- **Instant Sample Testing**: A single click on "Load Sample 2BHK Data" populates the form with synthetic data and placeholder images for instant testing without uploading files.
- **Standalone CLI Generator**: Includes `generate_sample.py` to render sample videos from the terminal without launching the web UI.

---

## 🏗️ Architecture & Technology Stack

| Component | Library / Service | Purpose |
| :--- | :--- | :--- |
| **User Interface** | `Streamlit` (>=1.35.0) | Interactive web interface with real-time progress, dynamic upload slots, and video player |
| **Script Generation** | `google-genai` SDK (`gemini-2.5-flash`) | Writes concise scene captions (max 8 words) and voiceovers (max 20 words) |
| **Voice Narration** | `gTTS` (Google Text-to-Speech) | Converts written scene script to spoken MP3 narration |
| **Video Assembly** | `MoviePy==1.0.3` | Concatenates video clips, applies crossfades, and composites audio |
| **FFmpeg Backend** | `imageio-ffmpeg` | Bundles platform-specific static FFmpeg binaries for fast video encoding |
| **Image & Text Prep** | `Pillow` (PIL) | Downscaling, EXIF rotation fix, center cropping, and font/overlay drawing |
| **Array Processing** | `numpy` | Fast in-memory frame transformations for Ken Burns zoom |

---

## 📁 Repository Structure

```
property-video-generator/
│
├── app.py                            # Streamlit web application
├── script_generator.py               # Gemini API caller + deterministic template fallback
├── validators.py                     # Form validation + strict 5-step AI safety checks
├── video_engine.py                   # Image prep, Pillow overlays, Ken Burns zoom, TTS, export
├── generate_sample.py                # Standalone CLI sample video generator
├── requirements.txt                  # Pinned Python package dependencies
├── packages.txt                      # Linux packages (fonts-dejavu-core, ffmpeg) for Cloud
├── .gitignore                        # Git exclusion rules (secrets, venv, temporary files)
│
├── .streamlit/
│   └── secrets.toml.example          # Example secrets configuration for Gemini API key
│
├── assets/
│   ├── music.mp3                     # Royalty-free ambient background music
│   └── README.md                     # Music format guidelines and volume mixing notes
│
├── sample_data/
│   └── sample_input.json             # Synthetic 2BHK flat listing data
│
└── sample_output/
    ├── sample_video.mp4              # Pre-generated sample promotional MP4 video
    └── README.md                     # Video specifications and format details
```

---

## 🚀 Quick Start & Local Setup

### 1. Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13
- Git

### 2. Clone and Setup Virtual Environment
```bash
git clone https://github.com/your-username/property-video-generator.git
cd property-video-generator

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
.\venv\Scripts\activate.bat
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Gemini API Key (Optional)
The application works **100% offline and without any API key** using the built-in deterministic template fallback.

To enable Gemini AI copywriting:
1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
2. Replace `"your-key-here"` with your free Google Gemini API key:
   ```toml
   GEMINI_API_KEY = "AIzaSy..."
   ```
*(Alternatively, set the environment variable: `export GEMINI_API_KEY="AIzaSy..."` or `$env:GEMINI_API_KEY="AIzaSy..."`)*

### 4. Run the Web App
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### 5. Run via Standalone CLI (Without Web UI)
To render a promotional video directly from the terminal using synthetic data:
```bash
python generate_sample.py
```
The resulting video will be saved to `sample_output/sample_video.mp4`.

---

## ☁️ Deployment on Streamlit Community Cloud

Deploying to Streamlit Community Cloud is 100% free and takes under 3 minutes:

1. **Push your repository to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of AI Property Video Generator"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/property-video-generator.git
   git push -u origin main
   ```
2. **Open Streamlit Community Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io) and log in with your GitHub account.
   - Click **"New app"**.
3. **Select Repository Settings**:
   - **Repository**: `YOUR_USERNAME/property-video-generator`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. **Configure Secrets**:
   - Expand **"Advanced settings..."** -> **"Secrets"**.
   - Paste your Gemini API key:
     ```toml
     GEMINI_API_KEY = "your-gemini-api-key"
     ```
5. **Click "Deploy!"**:
   - Streamlit Cloud automatically reads `packages.txt` to install `fonts-dejavu-core` and `ffmpeg`, and `requirements.txt` to install Python packages.
   - Within 1-2 minutes, your web application will be live at a public URL!

---

## 🛡️ Input Validation & Safety Checks

The app is built to **never crash** under edge cases:

1. **Mandatory Text Inputs**: Validates Property Name, Location, Price, Type, BHK, and CTA. Missing items trigger a clean `st.error` listing the exact missing fields.
2. **Photo Integrity & Bounds**:
   - Skips corrupt, unreadable, or non-image files with a non-blocking warning.
   - Rejects images smaller than 400x400 pixels.
   - Fixes EXIF orientation automatically using `ImageOps.exif_transpose`.
   - Downscales oversized images (>4K) to prevent memory exhaustion.
   - Minimum 4 valid photos required; blocks generation with `You uploaded X photos. Minimum is 4, please upload Y more.` and lists missing required rooms.
   - Caps total photos at 8 (uses first 8 and issues a warning).
   - If a required room is missing but total valid photos >= 4, alerts the user that the room will be skipped and proceeds safely.
3. **Strict 5-Step AI Output Safety Checks**:
   - **Step 1: Structure & Order**: JSON must contain `title`, `scenes`, and `cta` with scenes matching the room input order.
   - **Step 2: Word Limits**: Captions clamped to max 8 words; voiceover clamped to max 20 words.
   - **Step 3: Number/Price Hallucination Guard**: Every digit string in the script must exist in the user's input data. Unrecognized numbers cause immediate rejection.
   - **Step 4: Invented Claims Guard**: Rejects scripts with banned real estate buzzwords ("metro", "school", "swimming pool", "gym", "sea view") unless explicitly provided by the user.
   - **Step 5: Retry & Deterministic Fallback**: On any AI validation failure or API timeout/quota error, retries once with Gemini, then falls back seamlessly to the deterministic template generator.
4. **TTS Failure Recovery**: If gTTS is unavailable (e.g. offline), the video renders cleanly with synchronized fixed scene timings and a polite notification.
5. **Missing Music Asset**: If `assets/music.mp3` is missing, music mixing is skipped silently without errors.

---

## 📊 Example Inputs & Outputs

### Input Details:
```json
{
  "name": "Greenwood Heights",
  "location": "Whitefield, Bangalore",
  "price": "Rs 75 Lakh",
  "property_type": "Flat",
  "bhk": 2,
  "features": "Spacious sunlit balcony, Modular kitchen with chimney, Dedicated covered parking, 24x7 gated security",
  "cta_text": "Call 9800000000 to book a private tour"
}
```

### Video Output:
- **Format**: MP4 (H.264 video, AAC audio)
- **Resolution**: 1280x720 (720p HD, 16:9 widescreen)
- **Frame Rate**: 24 fps
- **Duration**: ~37 seconds
- **Visuals**:
  1. Opening Title Card (blurred primary photo, BHK badge, price highlight, location)
  2. Living Room (Ken Burns slow zoom + bottom caption bar)
  3. Kitchen (Ken Burns slow zoom + feature callout)
  4. Bathroom (Ken Burns slow zoom + caption)
  5. Bedroom 1 (Ken Burns slow zoom + caption)
  6. Bedroom 2 (Ken Burns slow zoom + caption)
  7. Closing CTA Card (prominent contact box, price reminder, action prompt)

---

## ⚠️ Known Limitations

1. **gTTS Network Dependency**: Google Text-to-Speech requires an internet connection. If offline, the video renders without narration using fixed slide timings.
2. **Gemini Free-Tier Rate Limits**: The free tier of Gemini allows 15 requests per minute. The app handles rate limit spikes by falling back to the deterministic template script.
3. **Synthetic Speech Cadence**: gTTS uses standard Google TTS voices which are clear and intelligible, but lack emotional inflection compared to paid APIs like ElevenLabs.
4. **Cloud CPU Rendering Time**: On Streamlit Community Cloud (shared 1 vCPU), video encoding takes approximately 30-45 seconds for a 30-second 720p video.
5. **Slideshow Motion**: Uses Ken Burns slow zoom (frame cropping) rather than AI video diffusion models (e.g. Sora, Runway, Luma), ensuring zero compute cost, instant turnaround, and no distorted architectural hallucinations.

---

## 🔮 Future Improvements

- [ ] **Voice Selection**: Add pitch and speed controls or neural voice models (e.g. Edge-TTS).
- [ ] **Custom Branding**: Support agency logo watermarks and brand color palette picker.
- [ ] **Vertical 9:16 Aspect Ratio**: Add Instagram Reels / YouTube Shorts export toggle.
- [ ] **Audio Waveform / Subtitles**: Optional animated word-by-word captions on screen.
- [ ] **Multi-Property Batch Processing**: CSV upload to generate videos for 50 listings automatically.
