import lgpio
import spidev
import threading
import time

class BOARD:
    chip = None
    RESET = 22   # adjust if your LoRa RESET pin is wired differently
    DIO0  = 17   # LoRa DIO0 pin connected to GPIO17
    low_band = True   # <-- add this line
    
    @staticmethod
    def setup():
        if BOARD.chip is None:
            BOARD.chip = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_output(BOARD.chip, BOARD.RESET)
            lgpio.gpio_claim_input(BOARD.chip, BOARD.DIO0)
            print(f"BOARD setup complete: RESET={BOARD.RESET}, DIO0={BOARD.DIO0}")
    @staticmethod
    def reset_on():
        lgpio.gpio_write(BOARD.chip, BOARD.RESET, 0)

    @staticmethod
    def reset_off():
        lgpio.gpio_write(BOARD.chip, BOARD.RESET, 1)

    @staticmethod
    def add_event_detect(dio_number, callback):
        def poll():
            last_state = lgpio.gpio_read(BOARD.chip, dio_number)
            while True:
                state = lgpio.gpio_read(BOARD.chip, dio_number)
                if state == 1 and last_state == 0:  # rising edge
                    callback(dio_number)
                last_state = state
                time.sleep(0.001)
        t = threading.Thread(target=poll, daemon=True)
        t.start()

    @staticmethod
    def add_events(cb_dio0=None, cb_dio1=None, cb_dio2=None,
                   cb_dio3=None, cb_dio4=None, cb_dio5=None):
        if cb_dio0:
            BOARD.add_event_detect(BOARD.DIO0, cb_dio0)

    @staticmethod
    def SpiDev():
        spi = spidev.SpiDev()
        spi.open(0, 0)          # bus 0, device 0 (use 0,1 if wired to CE1)
        spi.max_speed_hz = 500000
        spi.mode = 0
        return spi

    @staticmethod
    def teardown():
        if BOARD.chip is not None:
            lgpio.gpiochip_close(BOARD.chip)
            BOARD.chip = None
            print("GPIO released.")
