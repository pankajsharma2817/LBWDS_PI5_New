# LBWDS — LoRa-Based Wildlife Detection System (Raspberry Pi 5)

A Raspberry Pi 5 gateway node for a two-node LoRa-based intrusion / wildlife detection pipeline. When the remote node (Node 2) transmits a `MOTION_DETECTED` packet over LoRa, this node (Node 1) captures an image, runs YOLOv8 classification, performs face recognition against a known-person database, logs a sensor-fusion record, and sends email + SMS alerts.

---

## 🔐 Note on credentials

The earlier version of this code had API keys, a Gmail App Password, SMS gateway credentials, HiveMQ Cloud broker credentials, and personal email/phone details **hardcoded** inside `emailer.py`, `server_main3.py`, and `mqtt_publisher.py`. They have all been moved out of the source into environment variables loaded from a `.env` file.

- All secrets now live in `.env` (which is listed in `.gitignore` and is never committed).
- `.env.example` is the template — copy it to `.env` and fill in your real values.
- `emailer.py`, `server_main3.py`, and `mqtt_publisher.py` read the values via `os.environ.get(...)` and use `python-dotenv` to auto-load `.env` on startup.

**Rotate your old keys before using this repo.** Because the original credentials were committed locally at least once, treat them as exposed:

- Revoke the old Gmail App Password in your Google Account → Security → App passwords, and generate a fresh one.
- Revoke/rotate the old httpSMS account key from the httpSMS dashboard.
- Change the SMS-gateway username/password and device ID.
- Change the HiveMQ Cloud broker user password (or delete and recreate the credential).

After rotating, put the new values in `.env` only.

---

## Features

- **LoRa RX**: Listens on 433 MHz (SX1276/SX1278 module) via SPI for packets from the remote sensor node.
- **YOLOv8 classification**: Uses `yolov8n.pt` to classify captured images as Human / Animal / Unknown.
- **Distance estimation**: Simple focal-length pinhole model from detected bounding-box height.
- **Face recognition**: Matches captured faces against a local Excel-based database (`face_db/faces-1.xlsx`) using the `face_recognition` library.
- **Multi-channel alerting**:
  - Email (Gmail SMTP) with image attachment
  - SMS via local phone gateway (httpSMS) with cloud fallback
  - MQTT publish for downstream dashboards
- **Sensor fusion logging**: Writes PIR / vibration / ambient-temp / object-temp / classification to `sensor_fusion.csv`.
- **Buzzer output** on GPIO 16 for local audible alert.
- **Microphone sampling** via MCP3008 + MAX9814 for sound level reading.

## Hardware

| Component | Interface | Notes |
|---|---|---|
| Raspberry Pi 5 | — | Main gateway |
| SX1276/SX1278 LoRa module | SPI0 (CE0) | RESET → GPIO22, DIO0 → GPIO17 |
| Raspberry Pi Camera (libcamera/rpicam-still) | CSI | Still image capture |
| MCP3008 ADC | SPI | For MAX9814 mic |
| MAX9814 microphone | via MCP3008 ch 0 | Sound level sampling |
| MLX90614 IR temp sensor | I²C (addr 0x5A) | Ambient + object temp |
| SW420 vibration sensor | GPIO27 | Digital input |
| Buzzer / relay | GPIO16 | Local alert |
| DHT22 (optional) | GPIO4 | Ambient humidity + temp |

Note: The remote **Node 2** firmware (sending `MOTION_DETECTED` packets) is not included in this repository.

## Repository layout

```
.
├── server_main3.py         # Main gateway program (Node 1 entry point)
├── mqtt_publisher.py       # HiveMQ/Mosquitto MQTT client (events + base64 images + heartbeat)
├── detection.py            # YOLOv8 classifier + distance estimator
├── camera.py               # Picamera2 wrapper
├── emailer.py              # SMTP email alerts with image attachment
├── logger.py               # CSV detection log
├── lora.py                 # Simplified LoRa wrapper (stand-alone demo)
├── lora_params.py          # LoRa radio parameters (freq, BW, SF, CR, sync word)
├── sensor.py               # MLX90614 / SW420 / MAX9814 / buzzer / SPI helpers
├── sensor_pi5.py           # gpiozero + lgpio buzzer helper for Pi 5
├── temperature.py          # DHT22 helper
├── audio.py                # sounddevice recording helper
├── SX127x/                 # Pi-5-tuned fork of SX127x driver (with board_config_pi5.py)
├── pySX127x/               # Upstream pySX127x library (reference / examples)
├── face_db/                # Known-face Excel database + reference images
│   ├── faces-1.xlsx
│   └── ravi.jpg
├── yolov8n.pt              # YOLOv8 nano weights (~6.3 MB)
├── requirements.txt
├── .env.example            # Template for all secrets/config — copy to .env
├── .gitignore              # Ignores .env, __pycache__, captured_images, etc.
└── LICENSE
```

## Prerequisites

- Raspberry Pi 5 running Raspberry Pi OS (Bookworm or newer) — 64-bit recommended
- Python 3.11+
- Camera and SPI enabled (`sudo raspi-config` → Interface Options)

System packages (install via apt for best compatibility):

```bash
sudo apt update
sudo apt install -y \
    python3-pip python3-venv \
    python3-picamera2 python3-lgpio python3-rpi.gpio \
    python3-smbus python3-spidev \
    rpicam-apps \
    libatlas-base-dev libjpeg-dev
```

## Installation

```bash
git clone https://github.com/<your-username>/LBWDS_PI5.git
cd LBWDS_PI5

python3 -m venv --system-site-packages venv
source venv/bin/activate

pip install -r requirements.txt
```

> `--system-site-packages` is recommended so the venv can see the apt-installed `picamera2` and `lgpio` modules.

## Configuration

1. **Credentials & paths**: copy the example env file and edit it with your real values.
   ```bash
   cp .env.example .env
   nano .env
   ```
   All variables listed in `.env.example` are read by `server_main3.py` and `emailer.py` on startup — there is nothing left to edit inside the `.py` files for secrets or paths.

2. **Face database**: update `face_db/faces-1.xlsx` with rows containing at minimum `Name`, `Email`, `Mobile`, and `Image` (absolute path) columns. Point `FACE_DB_PATH` in `.env` at the correct location if you move the file.

3. **LoRa pins**: verify RESET / DIO0 pins in `SX127x/board_config_pi5.py` match your wiring.

4. **LoRa radio params**: adjust `lora_params.py` (frequency, spreading factor, coding rate, sync word) so both nodes match.

## Running

From the project root:

```bash
source venv/bin/activate
python3 server_main3.py
```

You should see:

```
Node1 (PI5) started – waiting for Node2 LoRa signals …
BOARD setup complete: RESET=22, DIO0=17
[DEBUG] Loaded N known faces from database
```

When Node 2 transmits `MOTION_DETECTED`, the pipeline runs automatically.

## Known limitations

- `server_main3.py` defines `main()` twice; Python uses the second definition. This is preserved as-is from the source.

## License

This project is released under the MIT License — see [LICENSE](LICENSE). The bundled `pySX127x/` and `SX127x/` drivers retain their original license (see `pySX127x/LICENSE`).
