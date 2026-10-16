import json
import numpy as np
import tensorflow as tf
from PIL import Image

interpreter = tf.lite.Interpreter(model_path="model/plant_model.tflite")
interpreter.allocate_tensors()
inp = interpreter.get_input_details()[0]
out = interpreter.get_output_details()[0]

class_names = json.load(open("model/class_names.json"))

img = Image.open("static/uploads/leaf.jpeg").convert("RGB").resize((160, 160))
x = np.expand_dims(np.array(img, dtype=np.float32), axis=0)

interpreter.set_tensor(inp["index"], x)
interpreter.invoke()
probs = interpreter.get_tensor(out["index"])[0]

best = int(np.argmax(probs))
print(class_names[best], round(float(probs[best]) * 100, 1), "%")