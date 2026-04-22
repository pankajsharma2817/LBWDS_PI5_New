# sensor_pi5.py
from gpiozero import OutputDevice, Device
from gpiozero.pins.lgpio import LGPIOFactory
import time

# Force Pi 5 to use LGPIO backend
Device.pin_factory = LGPIOFactory()

# GPIO pin for buzzer relay control
buzzer = OutputDevice(21, active_high=True, initial_value=False)

def activate_buzzer(duration=2):
    """
    Turn buzzer ON for 'duration' seconds, then OFF.
    """
    buzzer.on()
    print("Buzzer ON")
    time.sleep(duration)
    buzzer.off()
    print("Buzzer OFF")
