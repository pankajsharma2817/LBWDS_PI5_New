import cv2
from ultralytics import YOLO

model = YOLO("yolov8n.pt")

KNOWN_HEIGHT = 30
KNOWN_DISTANCE = 100
CALIB_PIXEL_HEIGHT = 150
FOCAL_LENGTH = (CALIB_PIXEL_HEIGHT * KNOWN_DISTANCE) / KNOWN_HEIGHT

def estimate_distance(known_height, pixel_height):
    if pixel_height <= 0:
        return None
    return (known_height * FOCAL_LENGTH) / pixel_height

def classify_image(img_path):
    results = model(img_path)
    labels = [results[0].names[int(c)] for c in results[0].boxes.cls.tolist()]
    print("YOLO labels:", labels)

    distance = None
    if len(results[0].boxes) > 0:
        box = results[0].boxes[0]
        xyxy = box.xyxy[0].cpu().numpy()
        pixel_height = xyxy[3] - xyxy[1]
        distance = estimate_distance(KNOWN_HEIGHT, pixel_height)

    if "person" in labels:
        return "Human", distance
    elif any(lbl in ["dog","cat","cow","elephant"] for lbl in labels):
        return "Animal", distance
    else:
        return "Unknown", distance
