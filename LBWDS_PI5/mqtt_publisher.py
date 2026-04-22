# mqtt_publisher.py
# Publishes detection events and captured images to HiveMQ Cloud broker.
#
# Topics used:
#   lbwds/events          – JSON metadata for every detection
#   lbwds/images/<id>     – Base64-encoded JPEG for each event
#   lbwds/status          – Periodic heartbeat / connection status

import json
import base64
import time
import threading
import os
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

# Load credentials from .env (see .env.example)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can also be set externally

# ── Broker credentials (from .env) ────────────────────────────────────────────
BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "")
BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", 8883))   # TLS port
MQTT_USER   = os.environ.get("MQTT_USERNAME", "")
MQTT_PASS   = os.environ.get("MQTT_PASSWORD", "")
MQTT_USE_TLS = os.environ.get("MQTT_USE_TLS", "true").lower() in ("1", "true", "yes")

# ── Topic definitions ─────────────────────────────────────────────────────────
TOPIC_EVENTS  = os.environ.get("MQTT_TOPIC_EVENTS", "lbwds/events")
TOPIC_IMAGES  = os.environ.get("MQTT_TOPIC_IMAGES", "lbwds/images")
TOPIC_STATUS  = os.environ.get("MQTT_TOPIC_STATUS", "lbwds/status")

# ── Client ID ─────────────────────────────────────────────────────────────────
MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", "lbwds_node1_pi5")

# ── QoS levels ────────────────────────────────────────────────────────────────
QOS_EVENTS = 1   # at-least-once  – important metadata
QOS_IMAGES = 1   # at-least-once  – image payloads
QOS_STATUS = 0   # fire-and-forget – heartbeat

# ── Heartbeat interval (seconds) ─────────────────────────────────────────────
HEARTBEAT_INTERVAL = 30


class MQTTPublisher:
    """
    Thread-safe MQTT client that connects once at startup, keeps the
    connection alive with a heartbeat, and publishes detection events
    (metadata JSON + Base64 image) whenever called.
    """

    def __init__(self):
        self._client = mqtt.Client(
            client_id=MQTT_CLIENT_ID,
            protocol=mqtt.MQTTv5,
        )
        self._client.username_pw_set(MQTT_USER, MQTT_PASS)
        if MQTT_USE_TLS:
            self._client.tls_set()          # uses system CA bundle – works on Pi OS

        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_publish    = self._on_publish

        self._connected = False
        self._lock      = threading.Lock()

        self._connect()
        self._start_heartbeat()

    # ── Internal callbacks ────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self._connected = True
            print("[MQTT] Connected to HiveMQ Cloud broker")
            self._publish_status("online")
        else:
            print(f"[MQTT] Connection failed – rc={rc}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        self._connected = False
        print(f"[MQTT] Disconnected – rc={rc}. Will auto-reconnect.")

    def _on_publish(self, client, userdata, mid):
        print(f"[MQTT] Message mid={mid} acknowledged by broker")

    # ── Connection management ─────────────────────────────────────────────────

    def _connect(self):
        try:
            self._client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
            self._client.loop_start()       # background network thread
        except Exception as exc:
            print(f"[MQTT] Initial connect error: {exc}")

    def _start_heartbeat(self):
        def _beat():
            while True:
                time.sleep(HEARTBEAT_INTERVAL)
                self._publish_status("online")
        t = threading.Thread(target=_beat, daemon=True, name="mqtt-heartbeat")
        t.start()

    # ── Public helpers ────────────────────────────────────────────────────────

    def _publish_status(self, state: str):
        payload = json.dumps({
            "state"    : state,
            "node"     : "PI5_Node1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        with self._lock:
            self._client.publish(TOPIC_STATUS, payload, qos=QOS_STATUS, retain=True)

    # ── Main public API ───────────────────────────────────────────────────────

    def publish_event(
        self,
        event_id  : str,
        result    : str,
        distance  : float | None,
        action    : str,
        lora_data : str,
        img_path  : str | None,
    ) -> bool:
        """
        Publish one complete detection event.

        Parameters
        ----------
        event_id  : unique ID for this event (timestamp-based)
        result    : classification label – "Human", "Animal", "Unknown"
        distance  : estimated distance in cm (None if unavailable)
        action    : human-readable description of what Node 1 did
        lora_data : raw LoRa payload received from Node 2
        img_path  : absolute path to the captured JPEG (None if capture failed)

        Returns True if both publishes were queued without error.
        """
        if not self._connected:
            print("[MQTT] Not connected – skipping publish")
            return False

        now = datetime.now(timezone.utc).isoformat()

        # ── 1. Metadata event JSON ────────────────────────────────────────────
        event_payload = {
            "event_id"    : event_id,
            "timestamp"   : now,
            "node"        : "PI5_Node1",
            "result"      : result,
            "distance_cm" : round(distance, 2) if distance is not None else None,
            "action_taken": action,
            "lora_raw"    : lora_data,
            "image_topic" : f"{TOPIC_IMAGES}/{event_id}" if img_path else None,
        }

        with self._lock:
            info = self._client.publish(
                TOPIC_EVENTS,
                json.dumps(event_payload),
                qos=QOS_EVENTS,
            )

        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[MQTT] Event publish failed – rc={info.rc}")
            return False

        print(f"[MQTT] Event published → {TOPIC_EVENTS} | result={result} | action={action}")

        # ── 2. Image payload (Base64 JPEG) ────────────────────────────────────
        if img_path and os.path.exists(img_path):
            try:
                with open(img_path, "rb") as fh:
                    b64_image = base64.b64encode(fh.read()).decode("ascii")

                image_payload = json.dumps({
                    "event_id"  : event_id,
                    "timestamp" : now,
                    "filename"  : os.path.basename(img_path),
                    "encoding"  : "base64/jpeg",
                    "data"      : b64_image,
                })

                img_topic = f"{TOPIC_IMAGES}/{event_id}"
                with self._lock:
                    img_info = self._client.publish(
                        img_topic,
                        image_payload,
                        qos=QOS_IMAGES,
                    )

                if img_info.rc != mqtt.MQTT_ERR_SUCCESS:
                    print(f"[MQTT] Image publish failed – rc={img_info.rc}")
                    return False

                print(f"[MQTT] Image published → {img_topic} ({len(b64_image)//1024} KB base64)")

            except Exception as exc:
                print(f"[MQTT] Image publish error: {exc}")
                return False

        return True

    def disconnect(self):
        """Graceful shutdown – publish 'offline' LWT then disconnect."""
        self._publish_status("offline")
        time.sleep(0.5)
        self._client.loop_stop()
        self._client.disconnect()
        print("[MQTT] Disconnected gracefully")
