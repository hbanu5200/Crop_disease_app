import os
import io
import json
import time
import sqlite3
from collections import defaultdict, deque

from flask import Blueprint, request, jsonify, redirect, url_for
from PIL import Image

lens_bp = Blueprint("lens", __name__)

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "history.db")
UPLOADS = os.path.join(BASE, "static", "uploads")

LANG_NAMES = {"en": "English", "kn": "Kannada", "hi": "Hindi", "te": "Telugu", "ta": "Tamil"}

TEXTS = {
    "en": {
        "ai_title": "AI expert (Leaf Lens)", "working": "AI is looking at your leaf...",
        "plant": "Plant", "confidence": "Confidence", "organic": "Organic treatment",
        "chemical": "Chemical treatment", "prevention": "Prevention", "tips": "More advice",
        "listen": "Listen", "stop": "Stop", "retry": "Try again",
        "notice": "AI advice can be wrong. Please confirm with a local agriculture officer before spraying anything. Your photo is sent to Google's AI service.",
        "busy": "The AI expert is busy right now. Please try again in a minute.",
        "fail": "Could not read the result. Please try a clear photo of one leaf.",
        "notplant": "This does not look like a plant. Please try another photo.",
        "sev_none": "None", "sev_mild": "Mild", "sev_moderate": "Moderate", "sev_severe": "Severe",
    },
    "kn": {
        "ai_title": "AI ತಜ್ಞ (ಎಲೆ ಲೆನ್ಸ್)", "working": "AI ನಿಮ್ಮ ಎಲೆಯನ್ನು ನೋಡುತ್ತಿದೆ...",
        "plant": "ಗಿಡ", "confidence": "ವಿಶ್ವಾಸಾರ್ಹತೆ", "organic": "ಸಾವಯವ ಚಿಕಿತ್ಸೆ",
        "chemical": "ರಾಸಾಯನಿಕ ಚಿಕಿತ್ಸೆ", "prevention": "ತಡೆಗಟ್ಟುವಿಕೆ", "tips": "ಹೆಚ್ಚಿನ ಸಲಹೆ",
        "listen": "ಕೇಳಿ", "stop": "ನಿಲ್ಲಿಸಿ", "retry": "ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ",
        "notice": "AI ಸಲಹೆ ತಪ್ಪಾಗಿರಬಹುದು. ಏನನ್ನಾದರೂ ಸಿಂಪಡಿಸುವ ಮೊದಲು ಸ್ಥಳೀಯ ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು ಕೇಳಿ. ನಿಮ್ಮ ಫೋಟೋ Google ನ AI ಸೇವೆಗೆ ಕಳುಹಿಸಲಾಗುತ್ತದೆ.",
        "busy": "AI ತಜ್ಞರು ಈಗ ಬ್ಯುಸಿಯಾಗಿದ್ದಾರೆ. ಒಂದು ನಿಮಿಷದ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        "fail": "ಫಲಿತಾಂಶ ಓದಲು ಆಗಲಿಲ್ಲ. ಒಂದೇ ಎಲೆಯ ಸ್ಪಷ್ಟ ಫೋಟೋ ಪ್ರಯತ್ನಿಸಿ.",
        "notplant": "ಇದು ಗಿಡದಂತೆ ಕಾಣುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಬೇರೆ ಫೋಟೋ ಪ್ರಯತ್ನಿಸಿ.",
        "sev_none": "ಇಲ್ಲ", "sev_mild": "ಸೌಮ್ಯ", "sev_moderate": "ಮಧ್ಯಮ", "sev_severe": "ತೀವ್ರ",
    },
    "hi": {
        "ai_title": "AI विशेषज्ञ (लीफ लेंस)", "working": "AI आपकी पत्ती देख रहा है...",
        "plant": "पौधा", "confidence": "विश्वसनीयता", "organic": "जैविक उपचार",
        "chemical": "रासायनिक उपचार", "prevention": "रोकथाम", "tips": "और सलाह",
        "listen": "सुनें", "stop": "रोकें", "retry": "फिर कोशिश करें",
        "notice": "AI की सलाह गलत हो सकती है। कुछ भी छिड़कने से पहले अपने स्थानीय कृषि अधिकारी से पुष्टि करें। आपकी फोटो Google की AI सेवा को भेजी जाती है।",
        "busy": "AI विशेषज्ञ अभी व्यस्त है। कृपया एक मिनट बाद फिर कोशिश करें।",
        "fail": "परिणाम पढ़ा नहीं जा सका। कृपया एक पत्ती की साफ़ फोटो आज़माएं।",
        "notplant": "यह पौधा नहीं लगता। कृपया दूसरी फोटो आज़माएं।",
        "sev_none": "कोई नहीं", "sev_mild": "हल्की", "sev_moderate": "मध्यम", "sev_severe": "गंभीर",
    },
    "te": {
        "ai_title": "AI నిపుణుడు (లీఫ్ లెన్స్)", "working": "AI మీ ఆకును చూస్తోంది...",
        "plant": "మొక్క", "confidence": "నమ్మకం", "organic": "సేంద్రీయ చికిత్స",
        "chemical": "రసాయన చికిత్స", "prevention": "నివారణ", "tips": "మరిన్ని సలహాలు",
        "listen": "వినండి", "stop": "ఆపండి", "retry": "మళ్లీ ప్రయత్నించండి",
        "notice": "AI సలహా తప్పు కావచ్చు. ఏదైనా పిచికారీ చేసే ముందు మీ స్థానిక వ్యవసాయ అధికారిని అడగండి. మీ ఫోటో Google AI సేవకు పంపబడుతుంది.",
        "busy": "AI నిపుణుడు ఇప్పుడు బిజీగా ఉన్నారు. దయచేసి ఒక నిమిషం తర్వాత మళ్లీ ప్రయత్నించండి.",
        "fail": "ఫలితం చదవలేకపోయాం. దయచేసి ఒక ఆకు స్పష్టమైన ఫోటోను ప్రయత్నించండి.",
        "notplant": "ఇది మొక్కలా కనిపించడం లేదు. దయచేసి మరో ఫోటో ప్రయత్నించండి.",
        "sev_none": "లేదు", "sev_mild": "తేలికపాటి", "sev_moderate": "మధ్యస్థ", "sev_severe": "తీవ్రమైన",
    },
    "ta": {
        "ai_title": "AI நிபுணர் (லீஃப் லென்ஸ்)", "working": "AI உங்கள் இலையைப் பார்க்கிறது...",
        "plant": "செடி", "confidence": "நம்பகத்தன்மை", "organic": "இயற்கை சிகிச்சை",
        "chemical": "ரசாயன சிகிச்சை", "prevention": "தடுப்பு", "tips": "மேலும் ஆலோசனை",
        "listen": "கேளுங்கள்", "stop": "நிறுத்து", "retry": "மீண்டும் முயலவும்",
        "notice": "AI ஆலோசனை தவறாக இருக்கலாம். எதையும் தெளிப்பதற்கு முன் உங்கள் உள்ளூர் வேளாண் அலுவலரிடம் உறுதிசெய்யுங்கள். உங்கள் புகைப்படம் Google AI சேவைக்கு அனுப்பப்படுகிறது.",
        "busy": "AI நிபுணர் இப்போது பிஸியாக உள்ளார். ஒரு நிமிடம் கழித்து மீண்டும் முயலவும்.",
        "fail": "முடிவைப் படிக்க முடியவில்லை. ஒரு இலையின் தெளிவான புகைப்படத்தை முயலவும்.",
        "notplant": "இது செடி போலத் தெரியவில்லை. வேறு புகைப்படத்தை முயலவும்.",
        "sev_none": "இல்லை", "sev_mild": "லேசானது", "sev_moderate": "மிதமானது", "sev_severe": "கடுமையானது",
    },
}


def load_env():
    path = os.path.join(BASE, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


load_env()

HITS = defaultdict(deque)
CACHE = {}


def too_many(ip):
    now = time.time()
    q = HITS[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= 5:
        return True
    q.append(now)
    return False


def get_lang():
    code = request.cookies.get("lang", "en")
    return code if code in LANG_NAMES else "en"


def prepare_image(path):
    img = Image.open(path).convert("RGB")
    img.thumbnail((768, 768))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def build_prompt(lang_name):
    return (
        "You are an experienced plant pathologist helping farmers. "
        "Look carefully at the photo and answer ONLY with a JSON object, with no extra text. "
        "Write every text value in " + lang_name + ". "
        "Keep the JSON keys and the severity_level value in English. "
        "Keys: "
        "is_plant (true or false), "
        "plant_name (common name of the plant or crop), "
        "plant_part (for example leaf, fruit or stem), "
        "condition (name of the disease, pest or deficiency, or Healthy), "
        "confidence (whole number 0 to 100: how sure you are), "
        "severity_level (one of: none, mild, moderate, severe), "
        "what_i_see (one short sentence), "
        "organic_treatment (list of 2 short steps, max 12 words each), "
        "chemical_treatment (list of 1 or 2 short steps, max 12 words each; always say to follow the product label), "
        "prevention (list of 2 short tips, max 12 words each), "
        "extra_advice (list of 1 short tip about when to ask an agriculture officer). "
        "Be honest: if the photo is unclear or you are unsure, lower the confidence and say so. "
        "Never invent a disease. If the photo is not a plant, set is_plant to false and leave the rest empty."
    )


def ask_gemini(image_bytes, lang_name):
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(timeout=30000),
    )
    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        build_prompt(lang_name),
    ]
    try:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_level="minimal"),
        )
        response = client.models.generate_content(
            model=os.environ["GEMINI_MODEL"], contents=contents, config=config
        )
    except Exception as e:
        if "thinking" not in str(e).lower():
            raise
        config = types.GenerateContentConfig(response_mime_type="application/json")
        response = client.models.generate_content(
            model=os.environ["GEMINI_MODEL"], contents=contents, config=config
        )
    text = (response.text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text)


def as_list(value):
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()][:2]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def clean_result(d):
    try:
        conf = int(float(d.get("confidence", 0)))
    except Exception:
        conf = 0
    conf = max(0, min(100, conf))
    sev = str(d.get("severity_level", "none")).lower()
    if sev not in ("none", "mild", "moderate", "severe"):
        sev = "none"
    return {
        "plant_name": str(d.get("plant_name", "")).strip(),
        "plant_part": str(d.get("plant_part", "")).strip(),
        "condition": str(d.get("condition", "")).strip(),
        "confidence": conf,
        "severity_level": sev,
        "what_i_see": str(d.get("what_i_see", "")).strip(),
        "organic_treatment": as_list(d.get("organic_treatment")),
        "chemical_treatment": as_list(d.get("chemical_treatment")),
        "prevention": as_list(d.get("prevention")),
        "extra_advice": as_list(d.get("extra_advice")),
    }


def save_ai(scan_id, r):
    """Save the AI answer on the scan, so History shows the same crop, disease and confidence."""
    healthy = 1 if r["severity_level"] == "none" else 0
    try:
        with sqlite3.connect(DB) as con:
            con.execute(
                "UPDATE scans SET crop = ?, disease = ?, confidence = ?, healthy = ? WHERE id = ?",
                (r["plant_name"], r["condition"], float(r["confidence"]), healthy, scan_id),
            )
    except Exception as e:
        print("LENS: could not save AI result:", e)


@lens_bp.app_context_processor
def inject_lens_texts():
    return {"lensx": TEXTS[get_lang()]}


@lens_bp.route("/lens")
def lens_page():
    return redirect(url_for("scan"))


@lens_bp.route("/history/delete/<int:scan_id>", methods=["POST"])
def delete_scan(scan_id):
    image = None
    left = 0
    try:
        with sqlite3.connect(DB) as con:
            row = con.execute("SELECT image FROM scans WHERE id = ?", (scan_id,)).fetchone()
            if row:
                image = row[0]
            con.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
            if image:
                left = con.execute("SELECT COUNT(*) FROM scans WHERE image = ?", (image,)).fetchone()[0]
    except Exception as e:
        print("LENS: delete failed:", e)
        return redirect(url_for("history"))

    if image and left == 0:
        try:
            os.remove(os.path.join(UPLOADS, os.path.basename(image)))
        except OSError:
            pass
    for k in [k for k in CACHE if k[0] == scan_id]:
        CACHE.pop(k, None)
    return redirect(url_for("history"))


@lens_bp.route("/lens/analyze/<int:scan_id>")
def lens_analyze(scan_id):
    started = time.time()
    lang = get_lang()
    t = TEXTS[lang]
    print("LENS: request for scan", scan_id, "language", lang)
    key = (scan_id, lang)
    if key in CACHE:
        print("LENS: sent from cache")
        return jsonify(CACHE[key])

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    if too_many(ip):
        print("LENS: too many requests, blocked")
        return jsonify({"error": t["busy"]}), 429

    with sqlite3.connect(DB) as con:
        row = con.execute("SELECT image FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if row is None:
        print("LENS: scan not found in database")
        return jsonify({"error": t["fail"]}), 404
    path = os.path.join(UPLOADS, os.path.basename(row[0]))
    if not os.path.exists(path):
        print("LENS: image file not found")
        return jsonify({"error": t["fail"]}), 404

    if not os.environ.get("GEMINI_API_KEY") or not os.environ.get("GEMINI_MODEL"):
        print("LENS: GEMINI_API_KEY or GEMINI_MODEL is missing")
        return jsonify({"error": t["busy"]}), 503

    try:
        image_bytes = prepare_image(path)
    except Exception:
        return jsonify({"error": t["fail"]}), 400

    print("LENS: calling Gemini after", round(time.time() - started, 1), "seconds")
    try:
        data = ask_gemini(image_bytes, LANG_NAMES[lang])
    except Exception as e:
        print("LENS ERROR after", round(time.time() - started, 1), "seconds:", e)
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            return jsonify({"error": t["busy"]}), 429
        return jsonify({"error": t["fail"]}), 502

    print("LENS: Gemini answered after", round(time.time() - started, 1), "seconds")
    if not isinstance(data, dict):
        return jsonify({"error": t["fail"]}), 502
    if data.get("is_plant") is False:
        return jsonify({"error": t["notplant"]}), 422

    result = clean_result(data)
    CACHE[key] = result
    save_ai(scan_id, result)
    return jsonify(result)