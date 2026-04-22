import Adafruit_DHT

SENSOR = Adafruit_DHT.DHT22
PIN = 4   # GPIO pin connected to DHT22 data pin

def read_temperature():
    humidity, temperature = Adafruit_DHT.read_retry(SENSOR, PIN)
    if temperature is not None:
        return round(temperature, 2)
    else:
        return None

