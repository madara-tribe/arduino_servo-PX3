#!/usr/bin/env python3
"""
PIR Sensor Validation Script — Telemetrix edition
(Standalone, no ROS2)

Drop-in replacement for pir_sensor_validate.py that uses
Telemetrix4Arduino.ino instead of pir_sensor_px.ino.
Output format is identical to pir_sensor_validate.py.

Hardware : SB612B OUT -> Arduino D2
Firmware : Telemetrix4Arduino.ino (no modification needed)

Usage:
  python pir_telemetrix_validate.py              # default /dev/ttyACM0
  python pir_telemetrix_validate.py /dev/ttyUSB0 # specify port

NOTE on baud rate:
  pir_sensor_validate.py had baudrate=96000, which is a typo.
  Telemetrix4Arduino.ino uses 115200. Telemetrix handles this internally.
"""

import sys
import time
from datetime import datetime
from typing import Optional

from telemetrix import telemetrix
from serial.tools import list_ports


# -----------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------
PIR_PIN       = 2       # SB612B OUT -> Arduino D2
DEBOUNCE_S    = 0.05    # 50 ms software debounce (same as pir_sensor_px.ino)
HEARTBEAT_S   = 5.0     # Heartbeat print interval


# -----------------------------------------------------------------------
# PIRValidator  (mirrors pir_sensor_validate.py API)
# -----------------------------------------------------------------------
class PIRValidator:
    """Standalone PIR validator using Telemetrix."""

    def __init__(self, port: Optional[str] = None):
        self.port = port or self._auto_detect_port()
        self.board: Optional[telemetrix.Telemetrix] = None

        # Statistics (identical fields to pir_sensor_validate.py)
        self.detection_count    = 0
        self.total_duration_ms  = 0
        self.start_time         = datetime.now()
        self.last_detect_time: Optional[datetime] = None

        # Internal state
        self._detected        = False
        self._detect_start_t  = 0.0
        self._last_change_t   = 0.0      # for debounce
        self._last_hb_t       = time.monotonic()

    # ------------------------------------------------------------------
    # Port selection
    # ------------------------------------------------------------------
    def _auto_detect_port(self) -> str:
        ports = list(list_ports.comports())

        print("Available ports:")
        for i, p in enumerate(ports):
            print(f"  [{i}] {p.device}  {p.description}")

        if not ports:
            print("ERROR: No serial ports found!")
            sys.exit(1)

        for p in ports:
            desc = p.description.lower()
            if 'arduino' in desc or 'ch340' in desc or 'acm' in desc:
                print(f"\nAuto-selected: {p.device}")
                return p.device

        idx = int(input("\nSelect port index: ").strip())
        return ports[idx].device

    # ------------------------------------------------------------------
    # Telemetrix callback
    # data: [cb_type, pin, value, timestamp_ms]
    #   value 1 = HIGH (motion detected)
    #   value 0 = LOW  (cleared)
    # ------------------------------------------------------------------
    def _pir_callback(self, data):
        if not isinstance(data, (list, tuple)) or len(data) < 3:
            return

        pin   = data[1]
        value = data[2]
        now   = time.monotonic()

        # Software debounce (replaces Arduino-side debounce in pir_sensor_px.ino)
        if (now - self._last_change_t) < DEBOUNCE_S:
            return
        self._last_change_t = now

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        if value == 1 and not self._detected:
            # Rising edge — matches "detect_start" event in pir_sensor_px.ino
            self._detected        = True
            self._detect_start_t  = now
            self.detection_count += 1
            self.last_detect_time = datetime.now()
            print(f"[{timestamp}] 🔴 DETECTED (#{self.detection_count})")

        elif value == 0 and self._detected:
            # Falling edge — matches "detect_end" event
            self._detected = False
            duration_ms    = int((now - self._detect_start_t) * 1000)
            self.total_duration_ms += duration_ms
            dur_sec = duration_ms / 1000.0
            print(f"[{timestamp}] ⚪ CLEARED  (duration: {dur_sec:.2f}s)")

    # ------------------------------------------------------------------
    # Connect to Arduino via Telemetrix
    # ------------------------------------------------------------------
    def connect(self) -> bool:
        try:
            print(f"\nConnecting to {self.port} via Telemetrix...")
            self.board = telemetrix.Telemetrix(com_port=self.port)
            time.sleep(2)   # Wait for Arduino reset (same as pir_sensor_validate.py)
            print("Connected!\n")
            return True
        except Exception as e:
            print(f"ERROR: {e}")
            return False

    # ------------------------------------------------------------------
    # Main validation loop
    # ------------------------------------------------------------------
    def run(self):
        if not self.connect():
            return

        # Send init event (mirrors pir_sensor_px.ino "init" message)
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{ts}] ✓ Sensor initialized (Telemetrix4Arduino)")

        # Register PIR pin
        self.board.set_pin_mode_digital_input(PIR_PIN, callback=self._pir_callback)

        print("=" * 60)
        print("PIR Sensor Validation (Telemetrix) - Press Ctrl+C to stop")
        print("=" * 60)
        print("Waiting for sensor events...\n")

        try:
            while True:
                # Heartbeat (mirrors pir_sensor_px.ino heartbeat message)
                now = time.monotonic()
                if (now - self._last_hb_t) >= HEARTBEAT_S:
                    self._last_hb_t = now
                    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    if self._detected:
                        dur_ms = int((now - self._detect_start_t) * 1000)
                        print(f"[{ts}] ♥ heartbeat (ACTIVE, dur: {dur_ms}ms)")
                    else:
                        print(f"[{ts}] ♥ heartbeat (idle, dur: 0ms)")

                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\n" + "=" * 60)
            self._print_summary()
        finally:
            if self.board:
                try:
                    self.board.shutdown()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Summary (identical output to pir_sensor_validate.py)
    # ------------------------------------------------------------------
    def _print_summary(self):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        avg_dur = (
            self.total_duration_ms / self.detection_count / 1000.0
            if self.detection_count else 0
        )
        print("VALIDATION SUMMARY")
        print("=" * 60)
        print(f"  Total runtime:      {elapsed:.1f} seconds")
        print(f"  Detection count:    {self.detection_count}")
        print(f"  Average duration:   {avg_dur:.2f} seconds")
        print(f"  Total detect time:  {self.total_duration_ms / 1000.0:.2f} seconds")
        print("=" * 60)

        if self.detection_count > 0:
            print("\n✓ Sensor is working correctly!")
        else:
            print("\n⚠ No detections recorded. Check:")
            print("  - Sensor wiring (OUT -> D2, VCC -> 5V, GND -> GND)")
            print("  - Sensor warm-up time (~30 seconds)")
            print("  - Move in front of sensor")


# -----------------------------------------------------------------------
def main():
    port = sys.argv[1] if len(sys.argv) > 1 else None
    validator = PIRValidator(port=port)
    validator.run()


if __name__ == '__main__':
    main()
