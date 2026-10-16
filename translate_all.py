import json
import time
from deep_translator import GoogleTranslator

advisory = json.load(open("advisory.json", encoding="utf-8"))
LANGS = ["kn", "hi", "te", "ta"]

texts = set(["About", "Organic", "Chemical", "Prevention"])
for label, info in advisory.items():
    texts.update(info.values())
    if label != "default":
        texts.add(label.split("___")[-1].replace("_", " "))

try:
    out = json.load(open("translations.json", encoding="utf-8"))
except FileNotFoundError:
    out = {}

for lang in LANGS:
    out.setdefault(lang, {})
    for t in sorted(texts):
        if t in out[lang]:
            continue
        for attempt in range(6):
            try:
                out[lang][t] = GoogleTranslator(source="en", target=lang).translate(t)
                print(lang, "OK:", t[:30])
                time.sleep(1)
                break
            except Exception as e:
                print("blocked, waiting 20 seconds...", lang)
                time.sleep(20)
        json.dump(out, open("translations.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

print("DONE")