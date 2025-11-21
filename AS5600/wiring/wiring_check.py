#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AS5600 Wiring Checker (simplified, Telemetrix)
- Probes I2C port (--i2c first, then the other) and address 0x36 (AS5600).
- Optional: also tries 0x40-0x43 for AS5600L (--try-l).
- Prints STATUS/AGC once, then streams RAW_ANGLE in degrees.

Prereqs (on your PC):
  pip install telemetrix pyserial

How to run:
  Linux:  python3 wiring_check.py --serial /dev/ttyACM0 --i2c 1
  Win  :  python  wiring_check.py --serial COM3         --i2c 0
  Try AS5600L: add --try-l

Wiring (Arduino side):
  AS5600 VCC→5V (or 3.3V per module), GND→GND, SDA→SDA, SCL→SCL.
  Keep grounds common when using a separate 5V servo supply.
"""

import time, argparse
from telemetrix import telemetrix

# AS5600 registers
REG_STATUS       = 0x0B
REG_AGC          = 0x1A
REG_RAW_ANGLE_H  = 0x0C  # read two bytes: 0x0C (high), 0x0D (low)

ADDR_PRIMARY     = 0x36
ADDR_L_RANGE     = (0x40, 0x41, 0x42, 0x43)

def i2c_init(board, port):
    board.set_pin_mode_i2c(i2c_port=port)
    time.sleep(0.08)

def i2c_read(board, addr, reg, n, i2c_port, timeout=1.0):
    """Read n bytes from (addr, reg) via callback and return bytes list or None."""
    box = {"data": None}
    def cb(data):
        if data:
            # keep last n bytes as unsigned 8-bit
            tail = [int(round(x)) & 0xFF for x in data[-n:]]
            box["data"] = tail
    board.i2c_read(addr, reg, n, cb, i2c_port=i2c_port)
    t0 = time.time()
    while time.time() - t0 < timeout:
        if box["data"] is not None:
            return box["data"]
        time.sleep(0.005)
    return None

def probe(board, port, addr):
    """Return (status, agc) or None if not responding."""
    i2c_init(board, port)
    b = i2c_read(board, addr, REG_STATUS, 1, i2c_port=port, timeout=1.0)
    if not b: 
        return None
    agc = i2c_read(board, addr, REG_AGC, 1, i2c_port=port, timeout=1.0)
    return (b[0], agc[0] if agc else None)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default="/dev/ttyACM0", help="Arduino serial port (e.g., /dev/ttyACM0 or COM3)")
    ap.add_argument("--i2c", type=int, default=1, help="I2C port number to try first (0 or 1)")
    ap.add_argument("--addr", type=lambda x:int(x,0), default=ADDR_PRIMARY, help="Primary I2C address (e.g., 0x36)")
    ap.add_argument("--try-l", action="store_true", help="Also try 0x40-0x43 (AS5600L) o. In our scripts, --try-l means “also try AS5600L** addresses**. The normal AS5600 uses I²C address 0x36. The AS5600L variant’s default address is 0x40 (some boards let you change it). The option --try-l makes the checker probe 0x40–0x43 in addition to 0x36.")
    ap.add_argument("--hz", type=float, default=20.0, help="Print rate (Hz)")
    args = ap.parse_args()

    print("[INFO] Connecting Telemetrix ...", flush=True)
    board = telemetrix.Telemetrix(com_port=args.serial)

    # build candidate lists
    ports = [args.i2c] if args.i2c in (0,1) else [1]
    if ports[0] == 1: ports.append(0)
    else:             ports.append(1)
    addrs = [args.addr] + ([a for a in ADDR_L_RANGE if a != args.addr] if args.try_l else [])

    picked_port, picked_addr, status, agc = None, None, None, None
    try:
        for p in ports:
            for a in addrs:
                print(f"[INFO] Trying I2C port={p}, addr=0x{a:02X} ...", flush=True)
                res = probe(board, p, a)
                if res is None: 
                    continue
                status, agc = res
                picked_port, picked_addr = p, a
                md = (status >> 5) & 1
                ml = (status >> 4) & 1
                mh = (status >> 3) & 1
                print(f"[OK]  Found AS5600 on port={p}, addr=0x{a:02X}")
                print(f"     STATUS=0x{status:02X} (MD={md} ML={ml} MH={mh}), AGC={agc}")
                if not md:
                    print("     WARN: magnet not detected (MD=0)")
                elif ml:
                    print("     WARN: magnetic field too LOW (ML=1)")
                elif mh:
                    print("     WARN: magnetic field too HIGH (MH=1)")
                break
            if picked_port is not None:
                break

        if picked_port is None:
            print("[ERROR] No response on I2C port 1 or 0 (0x36, and 0x40-0x43 if tried).")
            print("        Check wiring, ground, pull-ups, and module address.")
            return

        print("\n[INFO] Streaming RAW_ANGLE (Ctrl+C to stop)", flush=True)
        period = 1.0 / max(args.hz, 1.0)
        while True:
            b = i2c_read(board, picked_addr, REG_RAW_ANGLE_H, 2, i2c_port=picked_port, timeout=1.0)
            if b and len(b) == 2:
                raw12 = ((b[0] << 8) | b[1]) & 0x0FFF
                deg = raw12 * (360.0 / 4096.0)
                print(f"{time.time():.3f}, RAW={raw12:4d}, {deg:8.3f} deg", flush=True)
            else:
                print(f"{time.time():.3f}, READ_FAIL", flush=True)
            time.sleep(period)

    except KeyboardInterrupt:
        pass
    finally:
        try:
            board.shutdown()
        except Exception:
            pass
        print("[INFO] Bye.")

if __name__ == "__main__":
    main()

