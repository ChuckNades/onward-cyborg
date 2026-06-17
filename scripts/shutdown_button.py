from __future__ import annotations

import subprocess
import time

GPIO_PIN = 17
POLL_SECONDS = 0.1
HOLD_SECONDS = 1.5

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None


def shutdown() -> None:
    subprocess.run(["/sbin/shutdown", "-h", "now"], check=False)


def monitor_button(pin: int = GPIO_PIN) -> None:
    if GPIO is None:
        raise RuntimeError("RPi.GPIO is not installed")

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    pressed_since = None
    try:
        while True:
            if GPIO.input(pin) == GPIO.LOW:
                if pressed_since is None:
                    pressed_since = time.monotonic()
                elif time.monotonic() - pressed_since >= HOLD_SECONDS:
                    shutdown()
                    return
            else:
                pressed_since = None
            time.sleep(POLL_SECONDS)
    finally:
        GPIO.cleanup(pin)


if __name__ == "__main__":
    monitor_button()
