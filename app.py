import os
import io
import json
import time
import sqlite3
from datetime import datetime
import numpy as np
from PIL import Image
from flask import Flask, render_template, request, send_file, redirect, url_for
from werkzeug.utils import secure_filename
from gtts import gTTS

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:  # on your laptop we fall back to TensorFlow
    import tensorflow as tf
    Interpreter = tf.lite.Interpreter

app = Flask(__name__)

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

interpreter = Interpreter(model_path=os.path.join(BASE, "model", "plant_model.tflite"))
interpreter.allocate_tensors()
inp = interpreter.get_input_details()[0]
out = interpreter.get_output_details()[0]


# ---------- FINDING AND LOADING JSON FILES ----------
def find_file(name):
    skip = ("venv", ".git", "__pycache__", "uploads", "disease")
    for folder, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in skip]
        if name in files:
            if folder != BASE:
                print("NOTE:", name, "is in", folder, "- please move it to the main folder")
            return os.path.join(folder, name)
    return None


def load_json(name, default):
    path = find_file(name)
    if path is None:
        print("WARNING:", name, "not found - using default")
        return default
    return json.load(open(path, encoding="utf-8"))


class_names = json.load(open(os.path.join(BASE, "model", "class_names.json")))
advisory = load_json("advisory.json", {})

# hand-written translations first, then machine-translated crop/disease names
saved = load_json("translations.json", {})
for code, table in load_json("names_translations.json", {}).items():
    for k, v in table.items():
        saved.setdefault(code, {}).setdefault(k, v)

LANGS = {
    "en": "English",
    "kn": "ಕನ್ನಡ (Kannada)",
    "hi": "हिन्दी (Hindi)",
    "te": "తెలుగు (Telugu)",
    "ta": "தமிழ் (Tamil)",
}

LABELS = ["About", "Organic", "Chemical", "Prevention"]

# ---------- PAGE TEXTS (built in, so no file can go missing) ----------
EXTRA = {
    "en": {
        "brand": "Crop Doctor", "namaste": "Namaste!",
        "stat_diseases": "Diseases", "stat_languages": "Languages", "stat_accuracy": "Test accuracy",
        "lib_search": "Search diseases...", "lib_healthy": "Healthy leaf", "lib_disease": "Disease",
        "lib_advice_ready": "Advice ready", "back": "Back", "no_results": "No diseases found.",
        "hist_empty": "No scans yet. Tap the camera button to scan your first leaf.",
        "hist_clear": "Clear history", "hist_confirm": "Delete all history?",
        "hero_title": "Know your crop's health in seconds", "example": "Example result",
        "how_title": "How it works",
        "step1_t": "Scan", "step1_d": "Take or upload a photo of one leaf.",
        "step2_t": "Detect", "step2_d": "The AI model finds the disease in seconds.",
        "step3_t": "Act", "step3_d": "Get treatment and prevention advice, read aloud in your language.",
        "scan_sub": "Add a clear photo of one leaf to check its health.",
        "drop_hint": "Drag and drop a photo here, or tap to choose",
        "guide_title": "Photo guide", "supported": "Works with these crops",
    },
    "kn": {
        "brand": "ಕ್ರಾಪ್ ಡಾಕ್ಟರ್", "namaste": "ನಮಸ್ಕಾರ!",
        "stat_diseases": "ರೋಗಗಳು", "stat_languages": "ಭಾಷೆಗಳು", "stat_accuracy": "ಪರೀಕ್ಷಾ ನಿಖರತೆ",
        "lib_search": "ರೋಗ ಹುಡುಕಿ...", "lib_healthy": "ಆರೋಗ್ಯಕರ ಎಲೆ", "lib_disease": "ರೋಗ",
        "lib_advice_ready": "ಸಲಹೆ ಲಭ್ಯ", "back": "ಹಿಂದೆ", "no_results": "ಯಾವುದೇ ರೋಗ ಕಂಡುಬಂದಿಲ್ಲ.",
        "hist_empty": "ಇನ್ನೂ ಸ್ಕ್ಯಾನ್ ಇಲ್ಲ. ಮೊದಲ ಎಲೆಯನ್ನು ಸ್ಕ್ಯಾನ್ ಮಾಡಲು ಕ್ಯಾಮೆರಾ ಬಟನ್ ಒತ್ತಿ.",
        "hist_clear": "ಇತಿಹಾಸ ಅಳಿಸಿ", "hist_confirm": "ಎಲ್ಲಾ ಇತಿಹಾಸ ಅಳಿಸಬೇಕೆ?",
        "hero_title": "ನಿಮ್ಮ ಬೆಳೆಯ ಆರೋಗ್ಯವನ್ನು ಕ್ಷಣಗಳಲ್ಲಿ ತಿಳಿಯಿರಿ", "example": "ಉದಾಹರಣೆ ಫಲಿತಾಂಶ",
        "how_title": "ಇದು ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ",
        "step1_t": "ಸ್ಕ್ಯಾನ್", "step1_d": "ಒಂದು ಎಲೆಯ ಫೋಟೋ ತೆಗೆಯಿರಿ ಅಥವಾ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.",
        "step2_t": "ಪತ್ತೆ", "step2_d": "AI ಮಾದರಿ ಕೆಲವೇ ಕ್ಷಣಗಳಲ್ಲಿ ರೋಗವನ್ನು ಗುರುತಿಸುತ್ತದೆ.",
        "step3_t": "ಕ್ರಮ", "step3_d": "ಚಿಕಿತ್ಸೆ ಮತ್ತು ತಡೆಗಟ್ಟುವ ಸಲಹೆಯನ್ನು ನಿಮ್ಮ ಭಾಷೆಯಲ್ಲಿ ಕೇಳಿ.",
        "scan_sub": "ಆರೋಗ್ಯ ಪರೀಕ್ಷಿಸಲು ಒಂದು ಎಲೆಯ ಸ್ಪಷ್ಟ ಫೋಟೋ ಸೇರಿಸಿ.",
        "drop_hint": "ಫೋಟೋವನ್ನು ಇಲ್ಲಿ ಎಳೆದು ಬಿಡಿ, ಅಥವಾ ಆಯ್ಕೆ ಮಾಡಲು ಟ್ಯಾಪ್ ಮಾಡಿ",
        "guide_title": "ಫೋಟೋ ಮಾರ್ಗದರ್ಶಿ", "supported": "ಈ ಬೆಳೆಗಳಿಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ",
    },
    "hi": {
        "brand": "क्रॉप डॉक्टर", "namaste": "नमस्ते!",
        "stat_diseases": "रोग", "stat_languages": "भाषाएं", "stat_accuracy": "परीक्षण सटीकता",
        "lib_search": "रोग खोजें...", "lib_healthy": "स्वस्थ पत्ती", "lib_disease": "रोग",
        "lib_advice_ready": "सलाह उपलब्ध", "back": "वापस", "no_results": "कोई रोग नहीं मिला।",
        "hist_empty": "अभी तक कोई स्कैन नहीं। पहली पत्ती स्कैन करने के लिए कैमरा बटन दबाएं।",
        "hist_clear": "इतिहास मिटाएं", "hist_confirm": "सारा इतिहास मिटाएं?",
        "hero_title": "अपनी फसल की सेहत सेकंडों में जानें", "example": "उदाहरण परिणाम",
        "how_title": "यह कैसे काम करता है",
        "step1_t": "स्कैन", "step1_d": "एक पत्ती की फोटो लें या अपलोड करें।",
        "step2_t": "पहचान", "step2_d": "AI मॉडल कुछ ही सेकंड में रोग पहचानता है।",
        "step3_t": "उपाय", "step3_d": "उपचार और रोकथाम की सलाह अपनी भाषा में सुनें।",
        "scan_sub": "सेहत जांचने के लिए एक पत्ती की साफ़ फोटो जोड़ें।",
        "drop_hint": "फोटो यहां खींचकर छोड़ें, या चुनने के लिए टैप करें",
        "guide_title": "फोटो गाइड", "supported": "इन फसलों के लिए काम करता है",
    },
    "te": {
        "brand": "క్రాప్ డాక్టర్", "namaste": "నమస్కారం!",
        "stat_diseases": "వ్యాధులు", "stat_languages": "భాషలు", "stat_accuracy": "పరీక్ష ఖచ్చితత్వం",
        "lib_search": "వ్యాధులను వెతకండి...", "lib_healthy": "ఆరోగ్యకరమైన ఆకు", "lib_disease": "వ్యాధి",
        "lib_advice_ready": "సలహా సిద్ధం", "back": "వెనుకకు", "no_results": "వ్యాధులు కనుగొనబడలేదు.",
        "hist_empty": "ఇంకా స్కాన్‌లు లేవు. మొదటి ఆకును స్కాన్ చేయడానికి కెమెరా బటన్‌ను నొక్కండి.",
        "hist_clear": "చరిత్రను తొలగించండి", "hist_confirm": "మొత్తం చరిత్రను తొలగించాలా?",
        "hero_title": "మీ పంట ఆరోగ్యాన్ని క్షణాల్లో తెలుసుకోండి", "example": "ఉదాహరణ ఫలితం",
        "how_title": "ఇది ఎలా పనిచేస్తుంది",
        "step1_t": "స్కాన్", "step1_d": "ఒక ఆకు ఫోటో తీయండి లేదా అప్‌లోడ్ చేయండి.",
        "step2_t": "గుర్తింపు", "step2_d": "AI మోడల్ కొన్ని సెకన్లలో వ్యాధిని గుర్తిస్తుంది.",
        "step3_t": "చర్య", "step3_d": "చికిత్స మరియు నివారణ సలహాను మీ భాషలో వినండి.",
        "scan_sub": "ఆరోగ్యాన్ని తనిఖీ చేయడానికి ఒక ఆకు స్పష్టమైన ఫోటోను జోడించండి.",
        "drop_hint": "ఫోటోను ఇక్కడ లాగి వదలండి, లేదా ఎంచుకోవడానికి నొక్కండి",
        "guide_title": "ఫోటో గైడ్", "supported": "ఈ పంటలకు పనిచేస్తుంది",
    },
    "ta": {
        "brand": "கிராப் டாக்டர்", "namaste": "வணக்கம்!",
        "stat_diseases": "நோய்கள்", "stat_languages": "மொழிகள்", "stat_accuracy": "சோதனை துல்லியம்",
        "lib_search": "நோய்களைத் தேடுங்கள்...", "lib_healthy": "ஆரோக்கியமான இலை", "lib_disease": "நோய்",
        "lib_advice_ready": "ஆலோசனை தயார்", "back": "பின்", "no_results": "நோய்கள் எதுவும் இல்லை.",
        "hist_empty": "இன்னும் ஸ்கேன் இல்லை. முதல் இலையை ஸ்கேன் செய்ய கேமரா பொத்தானை அழுத்தவும்.",
        "hist_clear": "வரலாற்றை அழிக்கவும்", "hist_confirm": "அனைத்து வரலாற்றையும் அழிக்கவா?",
        "hero_title": "உங்கள் பயிரின் ஆரோக்கியத்தை சில நொடிகளில் அறியுங்கள்", "example": "எடுத்துக்காட்டு முடிவு",
        "how_title": "இது எப்படி வேலை செய்கிறது",
        "step1_t": "ஸ்கேன்", "step1_d": "ஒரு இலையின் புகைப்படம் எடுக்கவும் அல்லது பதிவேற்றவும்.",
        "step2_t": "கண்டறிதல்", "step2_d": "AI மாதிரி சில விநாடிகளில் நோயைக் கண்டறியும்.",
        "step3_t": "நடவடிக்கை", "step3_d": "சிகிச்சை மற்றும் தடுப்பு ஆலோசனையை உங்கள் மொழியில் கேளுங்கள்.",
        "scan_sub": "ஆரோக்கியத்தைச் சரிபார்க்க ஒரு இலையின் தெளிவான புகைப்படத்தைச் சேர்க்கவும்.",
        "drop_hint": "புகைப்படத்தை இங்கே இழுத்து விடுங்கள், அல்லது தேர்ந்தெடுக்கத் தட்டவும்",
        "guide_title": "புகைப்பட வழிகாட்டி", "supported": "இந்தப் பயிர்களுக்கு வேலை செய்யும்",
    },
}

UI = load_json("ui_text.json", {})
for fname in ("ui_extra.json", "ui_extra4.json"):
    for code, words in load_json(fname, {}).items():
        UI.setdefault(code, {}).update(words)
for code, words in EXTRA.items():
    UI.setdefault(code, {}).update(words)


# ---------- LANGUAGE ----------
def get_lang():
    code = request.cookies.get("lang", "en")
    return code if code in LANGS else "en"


@app.context_processor
def inject_globals():
    return {"ui": UI, "lang": get_lang(), "langs": LANGS}


@app.before_request
def need_language():
    if request.endpoint in ("language", "set_language", "static"):
        return None
    if "lang" not in request.cookies:
        return redirect(url_for("language"))


# ---------- DATABASE ----------
DB = os.path.join(BASE, "history.db")


def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created TEXT,
            image TEXT,
            crop TEXT,
            disease TEXT,
            confidence REAL,
            healthy INTEGER)""")
        for col in ("label TEXT", "others TEXT"):
            try:
                con.execute("ALTER TABLE scans ADD COLUMN " + col)
            except sqlite3.OperationalError:
                pass


init_db()


# ---------- HELPERS ----------
def translate_many(texts, lang):
    if lang == "en":
        return texts
    table = saved.get(lang, {})
    return [table.get(t, t) for t in texts]


def predict(path):
    img = Image.open(path).convert("RGB").resize((160, 160))
    x = np.expand_dims(np.array(img, dtype=np.float32), axis=0)
    interpreter.set_tensor(inp["index"], x)
    interpreter.invoke()
    probs = interpreter.get_tensor(out["index"])[0]
    top3 = np.argsort(probs)[::-1][:3]
    return [(class_names[i], float(probs[i]) * 100) for i in top3]


def clean(name):
    if "___" in name:
        crop, disease = name.split("___", 1)
    else:
        crop, disease = "", name
    return crop.replace("_", " ").strip(), disease.replace("_", " ").strip()


def get_crops():
    return sorted({clean(n)[0] for n in class_names} - {""})


def disease_img(label):
    fn = "disease/" + label + ".jpg"
    if os.path.exists(os.path.join(BASE, "static", fn)):
        return url_for("static", filename=fn)
    return None


def crop_thumb(crop):
    labels = [n for n in class_names if clean(n)[0] == crop]
    labels.sort(key=lambda n: "healthy" not in n.lower())
    for n in labels:
        u = disease_img(n)
        if u:
            return u
    return None


def crop_chips(lang):
    return [
        {"en": c, "t": translate_many([c], lang)[0], "img": crop_thumb(c)}
        for c in get_crops()
    ]


# ---------- LANGUAGE ROUTES ----------
@app.route("/language")
def language():
    return render_template("language.html")


@app.route("/set-language/<code>")
def set_language(code):
    if code not in LANGS:
        code = "en"
    nxt = request.args.get("next", "/")
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/"
    resp = redirect(nxt)
    resp.set_cookie("lang", code, max_age=60 * 60 * 24 * 365)
    return resp


# ---------- PAGES ----------
@app.route("/")
def home():
    lang = get_lang()
    return render_template(
        "home.html",
        chips=crop_chips(lang),
        sample=disease_img("Tomato___Early_blight"),
        sample_name=translate_many(["Early blight"], lang)[0],
    )


@app.route("/scan")
def scan():
    return render_template("scan.html", chips=crop_chips(get_lang()))


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["leaf"]
    filename = str(int(time.time())) + "_" + secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    results = predict(path)
    label, confidence = results[0]
    crop, disease = clean(label)
    healthy = "healthy" in label.lower()
    others = json.dumps([[n, round(c, 1)] for n, c in results[1:]])

    with sqlite3.connect(DB) as con:
        cur = con.execute(
            "INSERT INTO scans (created, image, crop, disease, confidence, healthy, label, others) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().strftime("%d %b %Y, %I:%M %p"), filename, crop,
             disease, round(confidence, 1), int(healthy), label, others),
        )
        scan_id = cur.lastrowid

    return redirect(url_for("result", scan_id=scan_id))


@app.route("/result/<int:scan_id>")
def result(scan_id):
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if row is None:
        return redirect(url_for("history"))

    lang = get_lang()
    label = row["label"] or ""
    if label:
        crop, disease = clean(label)
    else:
        crop, disease = (row["crop"] or "").strip(), (row["disease"] or "").strip()
    healthy = bool(row["healthy"])
    confidence = row["confidence"]

    others = []
    if row["others"]:
        for name, c in json.loads(row["others"]):
            c_crop, c_disease = clean(name)
            others.append((c_crop + " - " + c_disease, c))

    info = advisory.get(label, advisory["default"])
    keys = ["about", "organic", "chemical", "prevention"]
    texts = [crop, disease] + [info[k] for k in keys]
    translated = translate_many(texts, lang)
    speech = " ".join(translated[1:])

    return render_template(
        "result.html",
        image=row["image"],
        crop=translated[0],
        disease=translated[1],
        confidence=confidence,
        healthy=healthy,
        others=others,
        low=confidence < 60,
        info=dict(zip(keys, translated[2:])),
        speech=speech,
        labels=translate_many(LABELS, lang),
    )


@app.route("/history")
def history():
    lang = get_lang()
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM scans ORDER BY id DESC LIMIT 50"
        ).fetchall()
    items = []
    for r in rows:
        crop_t, disease_t = translate_many(
            [(r["crop"] or "").strip(), (r["disease"] or "").strip()], lang)
        items.append({
            "id": r["id"],
            "image": r["image"],
            "crop": crop_t,
            "disease": disease_t,
            "confidence": r["confidence"],
            "created": r["created"],
            "healthy": bool(r["healthy"]),
        })
    return render_template("history.html", items=items)


@app.route("/history/clear", methods=["POST"])
def clear_history():
    with sqlite3.connect(DB) as con:
        con.execute("DELETE FROM scans")
    return redirect(url_for("history"))


@app.route("/library")
def library():
    lang = get_lang()
    crops = get_crops()
    crop = request.args.get("crop", "Tomato")
    if crop not in crops:
        crop = crops[0]
    items = []
    for n in class_names:
        c, d = clean(n)
        if c == crop:
            items.append({
                "label": n,
                "disease": translate_many([d], lang)[0],
                "healthy": "healthy" in n.lower(),
                "has_advice": n in advisory,
                "img": disease_img(n),
            })
    return render_template(
        "library.html",
        chips=crop_chips(lang),
        crop=crop,
        crop_t=translate_many([crop], lang)[0],
        items=items,
    )


@app.route("/disease/<label>")
def disease_page(label):
    if label not in class_names:
        return redirect(url_for("library"))
    lang = get_lang()
    crop, disease = clean(label)
    info = advisory.get(label, advisory["default"])
    keys = ["about", "organic", "chemical", "prevention"]
    translated = translate_many([crop, disease] + [info[k] for k in keys], lang)
    return render_template(
        "disease.html",
        crop=crop,
        crop_t=translated[0],
        disease=translated[1],
        info=dict(zip(keys, translated[2:])),
        healthy="healthy" in label.lower(),
        img=disease_img(label),
        labels=translate_many(LABELS, lang),
    )


@app.route("/speak", methods=["POST"])
def speak():
    data = request.get_json()
    buf = io.BytesIO()
    gTTS(text=data["text"], lang=data["lang"]).write_to_fp(buf)
    buf.seek(0)
    return send_file(buf, mimetype="audio/mpeg")


if __name__ == "__main__":
    app.run(debug=True)