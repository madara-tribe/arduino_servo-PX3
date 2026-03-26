#!/usr/bin/env python3
"""
PIR Sensor Validation Script (Standalone, no ROS2)

For initial hardware validation before ROS2 integration.
Works with pir_sensor_px.ino (JSON protocol).

Usage:
  python pir_sensor_validate.py              # Auto-detect port
  python pir_sensor_validate.py /dev/ttyUSB0 # Specify port
"""

import json
import sys
import time
from datetime import datetime
from typing import Optional

import serial
from serial.tools import list_ports


class PIRValidator:
    """Standalone PIR sensor validator."""
    
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self.port = port or self._auto_detect_port()
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None
        
        # Statistics
        self.detection_count = 0
        self.total_duration_ms = 0
        self.start_time = datetime.now()
        self.last_detect_time: Optional[datetime] = None
    
    def _auto_detect_port(self) -> str:
        """Auto-detect Arduino port."""
        ports = list(list_ports.comports())
        
        print("Available ports:")
        for i, p in enumerate(ports):
            print(f"  [{i}] {p.device}  {p.description}")
        
        if not ports:
            print("ERROR: No serial ports found!")
            sys.exit(1)
        
        # Auto-select Arduino
        for p in ports:
            desc = p.description.lower()
            if 'arduino' in desc or 'ch340' in desc:
                print(f"\nAuto-selected: {p.device}")
                return p.device
        
        # Manual selection
        idx = int(input("\nSelect port index: ").strip())
        return ports[idx].device
    
    def connect(self) -> bool:
        """Connect to serial port."""
        try:
            print(f"\nConnecting to {self.port} @ {self.baudrate} baud...")
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino reset
            print("Connected!\n")
            return True
        except serial.SerialException as e:
            print(f"ERROR: {e}")
            return False
    
    def run(self):
        """Main validation loop."""
        if not self.connect():
            return
        
        print("=" * 60)
        print("PIR Sensor Validation - Press Ctrl+C to stop")
        print("=" * 60)
        print("Waiting for sensor events...\n")
        
        try:
            while True:
                line = self.serial.readline().decode(errors='replace').strip()
                if not line:
                    continue
                
                now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                
                try:
                    data = json.loads(line)
                    self._process_event(data, now)
                except json.JSONDecodeError:
                    # Legacy format
                    print(f"[{now}] RAW: {line}")
                    
        except KeyboardInterrupt:
            print("\n\n" + "=" * 60)
            self._print_summary()
        finally:
            if self.serial:
                self.serial.close()
    
    def _process_event(self, data: dict, timestamp: str):
        """Process JSON event."""
        event = data.get('event', '?')
        state = data.get('state', 0)
        duration = data.get('dur', 0)
        sensor_ts = data.get('ts', 0)
        
        if event == 'init':
            print(f"[{timestamp}] ✓ Sensor initialized (Arduino ts: {sensor_ts}ms)")
            
        elif event == 'detect_start':
            self.detection_count += 1
            self.last_detect_time = datetime.now()
            print(f"[{timestamp}] 🔴 DETECTED (#{self.detection_count})")
            
        elif event == 'detect_end':
            self.total_duration_ms += duration
            dur_sec = duration / 1000.0
            print(f"[{timestamp}] ⚪ CLEARED  (duration: {dur_sec:.2f}s)")
            
        elif event == 'heartbeat':
            state_str = "ACTIVE" if state else "idle"
            print(f"[{timestamp}] ♥ heartbeat ({state_str}, dur: {duration}ms)")
    
    def _print_summary(self):
        """Print validation summary."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        avg_dur = (self.total_duration_ms / self.detection_count / 1000.0) if self.detection_count else 0
        
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


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else None
    validator = PIRValidator(port=port)
    validator.run()


if __name__ == '__main__':
    main()
