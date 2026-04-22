import RPi.GPIO as GPIO
import smbus2
import spidev

# --- MLX90614 (I²C temperature sensor) ---
bus = smbus2.SMBus(1)
MLX_ADDR = 0x5A

def read_temp(reg):
    data = bus.read_word_data(MLX_ADDR, reg)
    data = ((data << 8) & 0xFF00) + (data >> 8)
    return data * 0.02 - 273.15

def ambient_temp():
    return read_temp(0x06)

def object_temp():
    return read_temp(0x07)

# --- SW420 vibration sensor ---
SW420_PIN = 27   # adjust to your wiring
GPIO.setmode(GPIO.BCM)
GPIO.setup(SW420_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def sw420_triggered():
    return GPIO.input(SW420_PIN) == GPIO.LOW

# --- MAX9814 microphone module ---
MAX9814_PIN = 23   # adjust to your wiring
GPIO.setup(MAX9814_PIN, GPIO.IN)

def max9814_triggered():
    return GPIO.input(MAX9814_PIN) == GPIO.LOW

# --- Buzzer ---
BUZZER_PIN = 22
GPIO.setup(BUZZER_PIN, GPIO.OUT)

def buzzer_on():
    GPIO.output(BUZZER_PIN, GPIO.HIGH)

def buzzer_off():
    GPIO.output(BUZZER_PIN, GPIO.LOW)

# --- LoRa (SPI communication) ---
spi = spidev.SpiDev()
spi.open(0, 0)   # bus 0, device 0
spi.max_speed_hz = 50000

def send_lora_message(msg: str):
    spi.xfer2([ord(c) for c in msg])

def receive_lora_message():
    resp = spi.xfer2([0x00])
    return resp

