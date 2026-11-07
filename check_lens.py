import os

print("Folder:", os.getcwd())
print(".env file found:", os.path.exists(".env"))

if os.path.exists(".env"):
    for line in open(".env", encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

key = os.environ.get("GEMINI_API_KEY", "")
model = os.environ.get("GEMINI_MODEL", "")
print("API key set:", bool(key), "(length", len(key), ")")
print("Model name:", model if model else "MISSING")

if not key or not model:
    print("STOP: fix the .env file first.")
else:
    from google import genai
    try:
        client = genai.Client(api_key=key)
        r = client.models.generate_content(model=model, contents="Say hello in one word.")
        print("SUCCESS. Gemini replied:", r.text)
    except Exception as e:
        print("FAILED:")
        print(str(e)[:600])