from PIL import Image

img = Image.open("icon.png").convert("RGBA")
for size in (192, 512):
    img.resize((size, size)).save(f"static/icon-{size}.png")
print("done")