import os, time, subprocess, threading, lgpio, spidev, re
from datetime import datetime, timezone
from SX127x.LoRa import LoRa, MODE
from SX127x.board_config_pi5 import BOARD
import lora_params as params
from detection import classify_image
from emailer import send_email_alert
from logger import log_incident
from mqtt_publisher import MQTTPublisher
import re
import pandas as pd
import face_recognition
import requests
from datetime import datetime, timezone

# Load credentials from .env (see .env.example)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can also be set externally

# --- SMS API Config ---
ACCOUNT_KEY = os.environ.get("SMS_ACCOUNT_KEY", "")
sender      = os.environ.get("SMS_SENDER", "")   # SIM number of your phone
# --- Normalize mobile numbers ---
def normalize_mobile(mobile: str) -> str:
    mobile = str(mobile).strip()
    if mobile.startswith("+91"):
        return mobile
    elif mobile.startswith("91"):
        return "+" + mobile
    else:
        return "+91" + mobile
 
# --- Local Gateway Config ---
PHONE_IP   = os.environ.get("SMS_PHONE_IP", "")     # your phone's IP
LOCAL_PORT = os.environ.get("SMS_LOCAL_PORT", "8080")

# --- Cloud Gateway Config ---
CLOUD_SERVER = os.environ.get("SMS_CLOUD_SERVER", "https://api.sms-gate.app:443")
USERNAME     = os.environ.get("SMS_USERNAME", "")
PASSWORD     = os.environ.get("SMS_PASSWORD", "")
DEVICE_ID    = os.environ.get("SMS_DEVICE_ID", "")

# Admin recipient for alert CC
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")

# --- Local SMS ---
def send_sms_local(mobile, message):
    url = f"http://{PHONE_IP}:{LOCAL_PORT}/sms"
    payload = {"from": sender, "to": mobile, "content": message}
    try:
        r = requests.post(url, json=payload, timeout=5)
        print("[LOCAL SMS] Response:", r.text)
        return r.status_code == 200
    except Exception as e:
        print("[ERROR] Local SMS failed:", e)
        return False

# --- Cloud SMS ---
def send_sms_cloud(mobile, message):
    url = "https://api.httpsms.com/v1/messages/send"
    payload = {
        "from": sender,       # SIM number
        "to": mobile,
        "content": message
    }
    headers = {
        "x-api-key": ACCOUNT_KEY,   # use your uk_... account key here
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        print("[CLOUD SMS] Response:", r.text)
        if r.status_code == 200:
            data = r.json()
            msg_id = data["data"]["id"]
            print(f"[CLOUD SMS] Queued ID: {msg_id}, Status: {data['data']['status']}")
            return True
        return False
    except Exception as e:
        print("[ERROR] Cloud SMS failed:", e)
        return False
# Directories & pins
IMG_DIR = os.environ.get("IMG_DIR", "/home/pi/Desktop/captured_images")
os.makedirs(IMG_DIR, exist_ok=True)

BUZZER_PIN = 16
chip = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(chip, BUZZER_PIN)

# MCP3008 / MAX9814 microphone
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1_350_000

# MQTT publisher
mqtt_pub = MQTTPublisher()

# Sensor fusion CSV
FUSION_LOG = os.environ.get("FUSION_LOG", "/home/pi/mqtt_bridge/sensor_fusion.csv")

def log_sensor_fusion(event_id, pir, vib, amb, obj, classification="Unknown"):
    os.makedirs(os.path.dirname(FUSION_LOG), exist_ok=True)
    if not os.path.exists(FUSION_LOG) or os.path.getsize(FUSION_LOG) == 0:
        with open(FUSION_LOG, "w") as f:
            f.write("EventID,PIR,Vibration,AmbientTemp,ObjectTemp,Classification,Timestamp\n")
    with open(FUSION_LOG, "a") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{event_id},{pir},{vib},{amb},{obj},{classification},{timestamp}\n")

# Helpers
def read_channel(channel: int) -> int:
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data

def trigger_buzzer():
    lgpio.gpio_write(chip, BUZZER_PIN, 1)
    time.sleep(1)
    lgpio.gpio_write(chip, BUZZER_PIN, 0)
    print("[DEBUG] Buzzer activated")

def mic_on() -> float:
    print("[DEBUG] Mic ON ? sampling sound")
    samples = [read_channel(0) for _ in range(20)]
    avg_level = sum(samples) / len(samples)
    print(f"[DEBUG] Mic average level: {avg_level:.1f}")
    return avg_level

def mic_off():
    print("[DEBUG] Mic OFF")

def capture_image() -> str | None:
    filename = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    filepath = os.path.join(IMG_DIR, filename)
    try:
        subprocess.run(["rpicam-still", "-n", "-o", filepath], check=True)
        print(f"[DEBUG] Image saved: {filepath}")
        return filepath
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Capture failed: {exc}")
        return None
            
# --- NEW FUNCTION: Unauthorized entry alert ---
def send_unauthorized_alert(name: str, email: str, mobile: str, img_path: str):
    subject = "[LBWDS] Unauthorized Entry Alert"
    body = (
        f"{name}, you are entered unauthorized area.\n\n"
        f"Image file : {os.path.basename(img_path)}\n"
        f"Timestamp  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    send_email_alert(subject, body, img_path, recipient=email)
    # Also send to admin
    if ADMIN_EMAIL:
        send_email_alert(subject, body, img_path, recipient=ADMIN_EMAIL)
    # Normalize mobile number before sending SMS
    mobile_norm = normalize_mobile(mobile)
    sms_message = f"Unauthorized entry detected for {name}. Image: {os.path.basename(img_path)}"
    if not send_sms_local(mobile_norm, sms_message):
        if not send_sms_cloud(mobile_norm, sms_message):
            print(f"[FAIL] SMS not sent to {mobile_norm}. Both local and cloud gateways failed.")
    # SMS alerts (try local first, then cloud)
    sms_message = f"Unauthorized entry detected for {name}. Image: {os.path.basename(img_path)}"
    if not send_sms_local(mobile, sms_message):
        if not send_sms_cloud(mobile, sms_message):
            print(f"[FAIL] SMS not sent to {mobile}. Both local and cloud gateways failed.")
   
    mqtt_pub.publish_event(
        event_id  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f"),
        result    = "Unauthorized Entry",
        distance  = None,
        action    = f"Alert sent to {email}",
        lora_data = "FACE_MATCH",
        img_path  = img_path,
    )
    print(f"[ALERT] Unauthorized entry email sent to {email}, {mobile}, and admin")

# Load known faces from Excel
DB_PATH = os.environ.get("FACE_DB_PATH", "/home/pi/Desktop/LBWDS/face_db/faces-1.xlsx")
df = pd.read_excel(DB_PATH)
known_encodings, known_names, known_emails, known_mobiles = [], [], [], []
for _, row in df.iterrows():
    img_path = str(row["Image"]).strip()
    if os.path.isfile(img_path):
        img = face_recognition.load_image_file(img_path)
        enc = face_recognition.face_encodings(img)
        if enc:
            known_encodings.append(enc[0])
            known_names.append(row["Name"])
            known_emails.append(row["Email"])
            known_mobiles.append(str(row["Mobile"]))
print(f"[DEBUG] Loaded {len(known_encodings)} known faces from database")
# LoRa receiver
class LoRaReceiver(LoRa):
    def __init__(self, verbose=False):
        super().__init__(verbose)
        self.set_mode(MODE.SLEEP)
        self.set_freq(params.FREQ)
        self.set_bw(params.BW)
        self.set_spreading_factor(params.SF)
        self.set_coding_rate(params.CR)
        self.set_sync_word(params.SYNC_WORD)
        self.set_dio_mapping([0, 0, 0, 0, 0, 0])

    def send_message(self, message: str):
        self.set_mode(MODE.STDBY)
        self.write_payload([ord(c) for c in message])
        self.set_mode(MODE.TX)
        print(f"[Node1 TX] {message}")
        time.sleep(1)
        self.reset_ptr_rx()
        self.set_mode(MODE.RXCONT)

    def on_rx_done(self, dio_number=None):
        self.clear_irq_flags(RxDone=1)
        payload = self.read_payload(nocheck=True)
        data = "".join([chr(c) for c in payload])
        print("RX <-", data)
        threading.Thread(target=handle_detection_event, args=(self, data), daemon=True).start()
        self.reset_ptr_rx()
        self.set_mode(MODE.RXCONT)

def handle_detection_event(lora: LoRaReceiver, data: str):
    if "MOTION_DETECTED" not in data:
        print(f"[INFO] No motion - camera stays OFF: {data}")
        return
    print("[INFO] MOTION_DETECTED - activating camera pipeline")
    event_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")

    # 1. Capture image
    img_path = capture_image()
    if not img_path:
        print("[ERROR] Image capture failed ? aborting detection pipeline")
        return

    # 2. Classify with YOLOv8
    result, distance = classify_image(img_path)
    print(f"[DEBUG] Classification: {result}, Distance: {distance}")
    log_incident("Detection event", result, distance, os.path.basename(img_path))

    # 3. Face recognition check
    captured_img = face_recognition.load_image_file(img_path)
    captured_enc = face_recognition.face_encodings(captured_img)
    if captured_enc:
        matches = face_recognition.compare_faces(known_encodings, captured_enc[0])
        if True in matches:
            idx = matches.index(True)
            name  = known_names[idx]
            email = known_emails[idx]
            mobile = known_mobiles[idx]
            print(f"[DEBUG] Face match: {name} ({email}, {mobile})")
            send_unauthorized_alert(name, email, mobile, img_path)
        else:
            print("[DEBUG] No face match found")
    # 4. Parse sensor values
    pir_match = re.search(r"PIR:(\d+)", data)
    vib_match = re.search(r"VIB:(\d+)", data)
    obj_match = re.search(r"Obj:(\d+\.\d+)C", data)
    amb_match = re.search(r"Amb:(\d+\.\d+)C", data)
    pir = int(pir_match.group(1)) if pir_match else 0
    vib = int(vib_match.group(1)) if vib_match else 0
    obj = float(obj_match.group(1)) if obj_match else 0.0
    amb = float(amb_match.group(1)) if amb_match else 0.0
    log_sensor_fusion(event_id, pir, vib, amb, obj, classification=result)

    # 5. Email alert
    subject = f"[LBWDS] Detection Alert: {result}"
    body = (
        f"Event ID   : {event_id}\n"
        f"Detection  : {result}\n"
        f"Distance   : {round(distance, 2)} cm\n" if distance else
        f"Event ID   : {event_id}\n"
        f"Detection  : {result}\n"
        f"Distance   : unknown\n"
    )
    body += f"Image file : {os.path.basename(img_path)}\n"
    body += f"Raw LoRa   : {data}\n"
    send_email_alert(subject, body, img_path)

    # 6. Actions (ensure action_taken is always defined)
    if result == "Human":
        trigger_buzzer()
        avg_level = mic_on()
        action_taken = (
            f"Buzzer triggered 1 s. Mic sampled ? avg level {avg_level:.1f}. "
            f"LoRa reply sent: ALERT Human at "
            f"{round(distance,2) if distance else 'unknown'} cm."
        )
        lora.send_message(
            f"ALERT: Human detected at "
            f"{round(distance,2) if distance else '?'} cm, sound {avg_level:.1f}"
        )

    elif result == "Animal":
        trigger_buzzer()
        mic_off()
        action_taken = "Buzzer triggered 1 s. LoRa reply sent: ALERT Animal."
        lora.send_message("ALERT: Animal detected")

    else:
        mic_off()
        action_taken = "No buzzer (Unknown classification). LoRa reply sent: ALERT Other."
        lora.send_message("ALERT: Other detected")

    print(f"[DEBUG] Action taken: {action_taken}")

    # 7. Publish to MQTT
    mqtt_pub.publish_event(
        event_id  = event_id,
        result    = result,
        distance  = float(distance) if distance is not None else None,
        action    = action_taken,
        lora_data = data,
        img_path  = img_path,
    )

# Entry point

def main():
    print("Node1 (PI5) started – waiting for Node2 LoRa signals …")
    BOARD.setup()
    lora = LoRaReceiver(verbose=True)
    lora.set_mode(MODE.STDBY)
    lora.set_pa_config(pa_select=1)
    BOARD.add_events(cb_dio0=lora.on_rx_done)

    try:
        lora.reset_ptr_rx()
        lora.set_mode(MODE.RXCONT)
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping Node1 …")

    finally:
        lora.set_mode(MODE.SLEEP)
        BOARD.teardown()
        lgpio.gpiochip_close(chip)
        spi.close()
        mqtt_pub.disconnect()   # graceful offline publish before exit
        print("Node1 shutdown complete.")

if __name__ == "__main__":
    main()


# Entry point
def main():
    print("Node1 (PI5) started ? waiting for Node2 LoRa signals ?")
    BOARD.setup()
    lora = LoRaReceiver(verbose=True)
    lora.set_mode(MODE.STDBY)
    lora.set_pa_config(pa_select=1)
    BOARD.add_events(cb_dio0=lora.on_rx_done)

    try:
        lora.reset_ptr_rx()
        lora.set_mode(MODE.RXCONT)
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping Node1 ?")

    finally:
        lora.set_mode(MODE.SLEEP)
        BOARD.teardown()
        lgpio.gpiochip_close(chip)
        spi.close()
        mqtt_pub.disconnect()   # graceful offline publish before exit
        print("Node1 shutdown complete.")


