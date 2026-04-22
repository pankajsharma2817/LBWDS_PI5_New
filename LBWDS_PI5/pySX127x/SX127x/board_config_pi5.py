import lgpio
import time

class BOARD:
    # Adjust these to match your wiring
    RESET = 17   # GPIO pin for LoRa RESET
    DIO0  = 4    # GPIO pin for LoRa DIO0
    LED   = 27   # optional LED pin

    chip = None

    @staticmethod
    def setup():
        BOARD.chip = lgpio.gpiochip_open(0)

        # Claim pins
        lgpio.gpio_claim_output(BOARD.chip, BOARD.RESET)
        lgpio.gpio_claim_output(BOARD.chip, BOARD.LED)
        lgpio.gpio_claim_input(BOARD.chip, BOARD.DIO0)

        # Reset LoRa module
        lgpio.gpio_write(BOARD.chip, BOARD.RESET, 0)
        time.sleep(0.1)
        lgpio.gpio_write(BOARD.chip, BOARD.RESET, 1)

    @staticmethod
    def led_on():
        lgpio.gpio_write(BOARD.chip, BOARD.LED, 1)

    @staticmethod
    def led_off():
        lgpio.gpio_write(BOARD.chip, BOARD.LED, 0)

    @staticmethod
    def close():
        if BOARD.chip is not None:
            lgpio.gpiochip_close(BOARD.chip)
