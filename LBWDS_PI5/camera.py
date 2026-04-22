# camera.py - Raspberry Pi 5 camera wrapper using Picamera2
import os
from picamera2 import Picamera2
from datetime import datetime

class Camera:
    def __init__(self, width=1280, height=720, save_dir="/home/pi/Desktop/captured_images"):
        self.picam2 = Picamera2()
        self.picam2.configure(
            self.picam2.create_still_configuration(main={"size": (width, height)})
        )
        self.picam2.start()
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)

    def capture(self, result="Unknown", distance=None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dist_str = f"{round(distance,2)}cm" if distance is not None else "NA"
        filename = f"{result}_{dist_str}_{timestamp}.jpg"
        filepath = os.path.join(self.save_dir, filename)
        self.picam2.capture_file(filepath)
        print(f"Captured image saved as {filepath}")
        return filepath

    def stop(self):
        self.picam2.stop()
        print("Camera stopped")

