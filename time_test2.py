import time, glob, os
import lens

path = max(glob.glob("static/uploads/*"), key=os.path.getmtime)

t = time.time()
img = lens.prepare_image(path)
print("prepare image:", round(time.time() - t, 1), "seconds")

t = time.time()
try:
    data = lens.ask_gemini(img, "English")
    print(data)
except Exception as e:
    print("ERROR:", e)
print("ask gemini:", round(time.time() - t, 1), "seconds")