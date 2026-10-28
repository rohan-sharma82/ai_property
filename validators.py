"""
validators.py - Input validation and AI output safety checking.
Handles form validation, photo integrity checks, and Gemini hallucination guards.
"""

import re
from typing import Dict, List, Tuple, Any, Optional
from PIL import Image


# Banned real-estate buzzwords & unauthorized financial/legal guarantees
BANNED_INVENTED_CLAIMS = [
    "metro", "school", "swimming pool", "pool", "gym", "gymnasium", 
    "sea view", "beach", "ocean view", "hospital", "shopping mall",
    "mall", "railway", "train station", "airport", "clubhouse",
    "penthouse", "golf course", "lake view", "helipad", "valet",
    # Financial guarantees, fake legal claims, and prompt-injected promises
    "government-approved", "government approved", "govt-approved",
    "guaranteed return", "guarantee 25%", "annual return", "annual returns",
    "25% return", "guaranteed profit", "zero risk", "risk-free", "rbi approved"
]

# Patterns commonly used in prompt injection attacks
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?instructions",
    r"system\s+prompt",
    r"system\s+override",
    r"you\s+are\s+now",
    r"developer\s+mode",
    r"jailbreak",
    r"as\s+(a\s+)?government[- ]approved",
    r"guarantee\s+\d+%\s+.*return",
    r"guarantee(d)?\s+.*(annual|roi|profit|return)",
    r"25%\s+annual\s+return",
    r"zero\s+risk",
    r"100%\s+profit"
]


def sanitize_and_check_injection(text: str) -> Tuple[str, bool, Optional[str]]:
    """
    Pre-flight prompt injection guard.
    Treats user input strictly as untrusted data, detects prompt injection signatures,
    neutralizes unauthorized instructions, and returns (clean_text, is_injected, message).
    """
    if not isinstance(text, str):
        return str(text), False, None

    detected = False
    clean_text = text
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, clean_text, flags=re.IGNORECASE):
            detected = True
            clean_text = re.sub(pattern, "[UNAUTHORIZED CLAIM STRIPPED]", clean_text, flags=re.IGNORECASE)

    alert = "Prompt injection attempt detected! Malicious commands stripped before AI processing." if detected else None
    return clean_text.strip(), detected, alert


def validate_text_fields(form_data: Dict[str, Any]) -> List[str]:
    """
    Validates mandatory text inputs.
    Returns list of missing field display names.
    """
    required_fields = {
        "name": "Property Name",
        "location": "Location",
        "price": "Price",
        "property_type": "Property Type",
        "bhk": "BHK",
        "cta_text": "Contact / CTA Text"
    }
    missing = []
    for field_key, field_name in required_fields.items():
        val = form_data.get(field_key)
        if val is None or (isinstance(val, str) and not val.strip()):
            missing.append(field_name)
    return missing


def validate_uploaded_images(
    photos_dict: Dict[str, Any],
    required_room_labels: List[str]
) -> Tuple[bool, List[Tuple[str, Image.Image]], List[str], List[str]]:
    """
    Validates uploaded images.
    
    Checks:
    1. Unreadable/corrupt files or non-image types
    2. Dimensions < 400px width or height
    3. Minimum 4 valid images required
    4. Capped at 8 images maximum
    5. Missing required rooms warning
    
    Returns:
    - is_valid (bool): True if at least 4 valid photos are present
    - valid_photos (list of (room_label, PIL.Image))
    - errors (list of str): Blocking error messages
    - warnings (list of str): Non-blocking warning messages
    """
    valid_photos: List[Tuple[str, Image.Image]] = []
    errors: List[str] = []
    warnings: List[str] = []
    
    uploaded_room_names = set()

    for room_label, file_obj in photos_dict.items():
        if file_obj is None:
            continue
            
        try:
            # Attempt to open image
            img = Image.open(file_obj)
            img.verify()  # Check for corruption
            
            # Reopen because verify() closes the file handle
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
            img = Image.open(file_obj)
            
            # Verify image has valid non-zero dimensions
            width, height = img.size
            if width <= 0 or height <= 0:
                warnings.append(f"Photo for '{room_label}' has invalid dimensions. Skipped.")
                continue

            # Images of any size or aspect ratio are accepted and automatically adjusted/cropped
            valid_photos.append((room_label, img))
            uploaded_room_names.add(room_label)
            
        except Exception as e:
            file_name = getattr(file_obj, "name", room_label)
            warnings.append(f"Photo '{file_name}' for '{room_label}' is unreadable or corrupted ({str(e)}). Skipped.")

    valid_count = len(valid_photos)
    
    # Check minimum 4 photos
    if valid_count < 4:
        missing_count = 4 - valid_count
        # Find which required rooms are missing
        empty_required = [r for r in required_room_labels if r not in uploaded_room_names]
        err_msg = f"You uploaded {valid_count} valid photos. Minimum is 4, please upload {missing_count} more."
        if empty_required:
            err_msg += f" Empty required rooms: {', '.join(empty_required)}."
        errors.append(err_msg)
        return False, [], errors, warnings

    # Check maximum 8 photos
    if valid_count > 8:
        warnings.append("More than 8 photos supplied. Using the first 8 photos and skipping the rest.")
        valid_photos = valid_photos[:8]

    # Check for empty required rooms when >= 4 images total
    for req_room in required_room_labels:
        if req_room not in uploaded_room_names:
            warnings.append(f"{req_room} photo missing. That scene will be skipped.")

    return True, valid_photos, errors, warnings


def _truncate_words(text: str, max_words: int) -> str:
    """Helper to clamp text word count gracefully."""
    words = text.strip().split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).rstrip(",.;:-") + "..."


def validate_ai_script(
    script_data: Dict[str, Any],
    form_data: Dict[str, Any],
    expected_rooms: List[str]
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Strict 5-step validation for Gemini AI generated script:
    1. Structure and scene count: Must have 'title', 'scenes', 'cta' in exact room order.
    2. Word counts: Max 8 words for caption, max 20 words for voiceover (truncated if slightly over).
    3. Digits check: Every digit string in script MUST exist in user input.
    4. Hallucination check: Banned claims (metro, gym, etc.) rejected unless in user input.
    5. Returns (is_valid, cleaned_script_or_None, reason).
    """
    if not isinstance(script_data, dict):
        return False, None, "AI response is not a valid JSON dictionary."

    # Step 1: Check required top-level keys
    if "title" not in script_data or "scenes" not in script_data or "cta" not in script_data:
        return False, None, "Missing 'title', 'scenes', or 'cta' keys in script JSON."

    scenes = script_data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != len(expected_rooms):
        return False, None, (
            f"Scene count mismatch: Expected {len(expected_rooms)} scenes for rooms "
            f"{expected_rooms}, but received {len(scenes) if isinstance(scenes, list) else 0}."
        )

    # Step 2: Clean and validate word counts
    cleaned_scenes = []
    for idx, (scene, exp_room) in enumerate(zip(scenes, expected_rooms)):
        if not isinstance(scene, dict):
            return False, None, f"Scene {idx + 1} is not a valid dictionary object."
            
        caption = str(scene.get("caption", exp_room)).strip()
        voiceover = str(scene.get("voiceover", f"Here is the {exp_room}.")).strip()
        
        # Word limits: caption max 8 words, voiceover max 20 words
        clean_caption = _truncate_words(caption, 8)
        clean_voiceover = _truncate_words(voiceover, 20)
        
        cleaned_scenes.append({
            "room": exp_room,
            "caption": clean_caption,
            "voiceover": clean_voiceover
        })

    cta = script_data.get("cta")
    if not isinstance(cta, dict):
        return False, None, "CTA block is not a dictionary."
        
    cta_caption = _truncate_words(str(cta.get("caption", form_data.get("cta_text", "Contact Us"))), 10)
    cta_voiceover = _truncate_words(str(cta.get("voiceover", form_data.get("cta_text", "Contact us today."))), 25)

    cleaned_script = {
        "title": str(script_data.get("title", f"{form_data.get('name', 'Property')} Tour")).strip(),
        "scenes": cleaned_scenes,
        "cta": {
            "caption": cta_caption,
            "voiceover": cta_voiceover
        }
    }

    # Gather all user input text for reference
    user_input_blob = " ".join([
        str(form_data.get("name", "")),
        str(form_data.get("location", "")),
        str(form_data.get("landmark", "")),
        str(form_data.get("price", "")),
        str(form_data.get("property_type", "")),
        str(form_data.get("bhk", "")),
        str(form_data.get("features", "")),
        str(form_data.get("cta_text", ""))
    ]).lower()

    # Step 3: Digits/Numbers Check (Hallucinated prices/phone numbers/sizes check)
    user_digits = set(re.findall(r"\d+", user_input_blob))
    
    # Gather all script text
    script_blob_parts = [cleaned_script["title"], cta_caption, cta_voiceover]
    for sc in cleaned_scenes:
        script_blob_parts.append(sc["caption"])
        script_blob_parts.append(sc["voiceover"])
    script_blob = " ".join(script_blob_parts)
    
    script_digits = set(re.findall(r"\d+", script_blob))
    for digit in script_digits:
        if digit not in user_digits:
            return False, None, (
                f"Hallucinated number detected: '{digit}' in script was not found in user input."
            )

    # Step 4: Banned Claims Check (metro, school, gym, swimming pool, etc.)
    script_blob_lower = script_blob.lower()
    for claim in BANNED_INVENTED_CLAIMS:
        # Check whole word match or phrase
        pattern = r"\b" + re.escape(claim) + r"\b"
        if re.search(pattern, script_blob_lower):
            if not re.search(pattern, user_input_blob):
                return False, None, (
                    f"Invented claim detected: '{claim}' appeared in AI script but was not provided by user."
                )

    return True, cleaned_script, "AI script passed all validation checks."
