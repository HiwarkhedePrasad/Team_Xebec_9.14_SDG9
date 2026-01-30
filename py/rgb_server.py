from flask import Flask, request
import cv2
import numpy as np

app = Flask(__name__)

@app.route("/rgb", methods=["POST"])
def receive_rgb():
    data = request.data
    img_array = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if img is not None:
        cv2.imshow("RGB Camera", img)
        cv2.waitKey(1)

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
