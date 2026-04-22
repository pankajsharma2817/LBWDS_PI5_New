# logger.py - log detections into a CSV file
import csv
import os
from datetime import datetime

LOG_FILE = "/home/pi/Desktop/captured_images/detections_log.csv"
serial_number = 1  # global counter

def log_incident(message: str, result="Unknown", distance=None, filename="NA"):
    """
    Append a detection/incident entry to the CSV log file.
    message: free text description
    result: classification result (e.g. 'person', 'dog')
    distance: optional distance in cm
    filename: image filename
    """
    global serial_number
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    # Create file with header if it doesn?t exist
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    try:
        with open(LOG_FILE, "x", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["S.N", "Date", "Time", "Message", "Image", "Detection", "Distance"])
    except FileExistsError:
        pass

    # Append new detection
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([serial_number, date_str, time_str, message, filename, result, distance])

    print(f"Logged: {serial_number}, {date_str}, {time_str}, {filename}, {result}, {distance}")
    serial_number += 1
