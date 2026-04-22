#!/usr/bin/env python3

import sys
import time

from SX127x.LoRa import LoRa as SX127xLoRa
from SX127x.board_config_pi5 import BOARD
from SX127x.constants import MODE   # import MODE directly

# Make sure GPIO chip is opened before LoRa object is created
#BOARD.setup()

#class LoRaNode(LoRa):
#    def __init__(self, verbose=False):
#        super(LoRaNode, self).__init__(verbose)
#        self.set_mode(MODE.STDBY)   # start in standby
#        self.set_freq(433.0)        # set frequency (MHz)
class LoRa(SX127xLoRa):
    def __init__(self, verbose=False):
        super().__init__(verbose)
        self.set_mode(MODE.STDBY)
        self.set_freq(433.0)

    def send_message(self, message: str):
        """Send a string message over LoRa."""
        payload = [ord(c) for c in message]
        self.write_payload(payload)
        self.set_mode(MODE.TX)
        time.sleep(1)
        self.set_mode(MODE.RXCONT)
        print(f"[DEBUG] LoRa sent: {message}")

    def on_rx_done(self):
        payload = self.read_payload(nocheck=True)
        msg = bytes(payload).decode('utf-8', errors='ignore')
        print(f"[DEBUG] LoRa received: {msg}")
        self.clear_irq_flags_rx_done()

    def on_tx_done(self):
        print("[DEBUG] LoRa transmission complete")
        self.clear_irq_flags_tx_done()
        
#    def on_rx_done(self):
#        payload = self.read_payload(nocheck=True)
#        print("Received:", bytes(payload).decode('utf-8', errors='ignore'))
#        self.clear_irq_flags_rx_done()

#    def on_tx_done(self):
#        print("Transmission complete")
#        self.clear_irq_flags_tx_done()

def main():
    lora = LoRa(verbose=True)

    try:
        # Example: send a packet
        lora.write_payload([ord(c) for c in "Hello LoRa"])
        lora.set_mode(MODE.TX)   # transmit
        time.sleep(1)

        # Switch to RX mode (continuous receive)
        lora.set_mode(MODE.RXCONT)
        print("Listening for packets...")

        while True:
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("Stopping LoRa node")
        lora.set_mode(MODE.SLEEP)
        BOARD.close()

if __name__ == "__main__":
    main()
