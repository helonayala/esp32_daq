#!/usr/bin/env bash
# Builds and flashes the firmware (arduino-cli + esp32:esp32 core 3.x). Usage:  ./flash.sh <port>   (e.g. /dev/ttyUSB0)
# Alternative: open firmware/esp32_daq/esp32_daq.ino in the Arduino IDE (board "ESP32 Dev Module") and click Upload.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${1:?give the port (e.g. /dev/ttyUSB0 or /dev/cu.usbserial-0001)}"
FQBN="${FQBN:-esp32:esp32:esp32}"
SK="firmware/esp32_daq"
arduino-cli compile --fqbn "$FQBN" "$SK"
arduino-cli upload  --fqbn "$FQBN" -p "$PORT" "$SK"
