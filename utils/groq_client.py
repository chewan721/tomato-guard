import os
import json
import logging
import requests
from PIL import Image, ImageStat
import numpy as np

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile" 

def _get_api_key():
    return os.environ.get("GROQ_API_KEY")

def _describe_image(filepath: str) -> str:
    """Lightweight visual description based on pixel analysis."""
    try:
        with Image.open(filepath).convert("RGB") as img:
            img = img.resize((224, 224))
            stat = ImageStat.Stat(img)
            r_mean, g_mean, b_mean = stat.mean[:3]
            r_std, g_std, b_std = stat.stddev[:3]
            brightness = (r_mean + g_mean + b_mean) / 3
            contrast = (r_std + g_std + b_std) / 3

            if g_mean > r_mean and g_mean > b_mean:
                tone = "predominantly green (mostly healthy tissue or green stalks)"
            elif r_mean > g_mean and r_mean > b_mean:
                tone = "reddish/brownish tones (sign of lesions, blight, or necrosis)"
            elif b_mean > r_mean and b_mean > g_mean:
                tone = "bluish/greyish tones (fungal or mould coverage)"
            else:
                tone = "mixed tones"

            brightness_desc = "well-lit" if brightness > 150 else "dimly lit" if brightness < 80 else "moderately lit"
            
            arr = np.array(img, dtype=np.float32)
            dark_pct = np.all(arr < 60, axis=2).mean() * 100
            yellow_pct = ((arr[:,:,0] > 150) & (arr[:,:,1] > 150) & (arr[:,:,2] < 80)).mean() * 100
            
            hints = []
            if dark_pct > 5: hints.append(f"~{dark_pct:.1f}% necrotic/dark pixels")
            if yellow_pct > 5: hints.append(f"~{yellow_pct:.1f}% yellowing pixels")
            lesion_str = "Visual hints: " + ", ".join(hints) if hints else "No strong lesion patterns in basic pixel test"
            
            return f"The image is {brightness_desc}. Color tone: {tone}. {lesion_str}."
    except Exception as exc:
        logger.warning("Image description failed: %s", exc)
        return "Visual metadata unavailable."

def _infer_severity(disease_label: str, confidence: float) -> str:
    label = (disease_label or "").lower()
    if "healthy" in label: return "None"
    if "late_blight" in label: return "High"
    if confidence >= 0.85: return "Moderate to High"
    return "Low to Moderate"

def _is_valid_url(url: str) -> bool:
    """Check if URL is reasonably valid."""
    if not url or not isinstance(url, str):
        return False
    url_lower = url.lower()
    # Reject placeholder/generic URLs or obviously invalid ones
    if any(x in url_lower for x in ["example", "placeholder", "test", "your-", "{"]):
        return False
    if not url_lower.startswith("http"):
        return False
    if len(url) < 10:
        return False
    return True

def get_ai_cure(disease_label: str, confidence: float, filepath: str = None) -> dict:
    """Generate AI-powered management recommendation using Groq API."""
    FALLBACK = {
        "summary": "AI recommendation unavailable. Follow general plant care.",
        "description": "We couldn't connect to our AI advisor right now.",
        "immediate_actions": ["Isolate affected plant", "Avoid overhead watering"],
        "fungicides": ["Consult local agricultural store"],
        "prevention": ["Maintain spacing", "Crop rotation"],
        "severity": _infer_severity(disease_label, confidence),
        "learn_more": "https://www.fao.org/plant-health-2020/en/"
    }

    api_key = _get_api_key()
    if not api_key:
        logger.warning("GROQ_API_KEY not found in environment.")
        return FALLBACK

    if confidence < 0.60 or disease_label in ("Unknown / Low Confidence", "Prediction error"):
        return FALLBACK

    image_meta = _describe_image(filepath) if filepath else "No image provided."
    severity = _infer_severity(disease_label, confidence)

    prompt = (
        f"Diagnosed Tomato Disease: {disease_label}\n"
        f"Confidence Score: {confidence*100:.1f}%\n"
        f"Image Analysis Context: {image_meta}\n"
        f"Assessed Severity: {severity}\n"
        f"Geographic Region: South Asia (Nepal)\n\n"
        "Provide a detailed organic and chemical management plan in JSON."
    )

    SYSTEM_PROMPT = (
        "You are TomatoGuard Expert, a specialist in plant pathology. "
        "Return ONLY a clean JSON object with these exact keys: "
        "summary, description, immediate_actions (list), fungicides (list), "
        "prevention (list), severity (string), learn_more (url)."
    )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }

        response = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=12)
        response.raise_for_status()
        
        content = response.json()["choices"][0]["message"]["content"]
        
        # Robust JSON extraction (removes markdown backticks or preambles)
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = json.loads(content)
        
        # Always LOG the AI-generated learn_more for debugging, but don't use it
        logger.warning(f"AI generated learn_more: {result.get('learn_more')} (will be ignored)")
        # This will be overridden by routes/disease.py with verified link
        
        return result

    except Exception as exc:
        if 'response' in locals() and hasattr(response, 'text'):
            logger.error("Groq AI API Error Details: %s", response.text)
        logger.error("Groq AI cure failed: %s", exc)
        return FALLBACK
