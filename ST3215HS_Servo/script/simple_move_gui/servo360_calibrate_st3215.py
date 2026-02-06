#!/usr/bin/env python3
"""
servo360_calibrate_st3215.py

Tkinter GUI to move ST3215-HS (STS bus servo) via Arduino Nano ESP32 over USB serial.
Works with the paired Arduino sketch: simple_move_gui.ino

Install:
  pip install pyserial

Usage:
  python3 servo360_calibrate_st3215.py
"""

import time
import threading
import tkinter as tk
from tkinter import messagebox

import serial
import serial.tools.list_ports

# === Settings (edit here) ===
COM_PORT = "/dev/ttyACM0"     # e.g. "/dev/ttyACM0", "COM3", "/dev/cu.usbmodem*"
BAUDRATE = 115200

INVERT_DEG = False           # True if motion feels reversed
NEUTRAL_DEG = 180.0          # center position (0..360)

DEFAULT_SPEED = 500          # steps/s (0..2000)
DEFAULT_ACC = 0              # 0..255

ser = None
rx_thread = None
stop_rx = False

def list_ports():
    return [p.device for p in serial.tools.list_ports.comports()]

def safe_write_line(line: str):
    global ser
    if ser is None:
        return
    try:
        ser.write((line.strip() + "\n").encode("utf-8"))
        ser.flush()
    except Exception as e:
        append_log(f"[TX error] {e}")

def append_log(msg: str):
    log.configure(state="normal")
    log.insert("end", msg + "\n")
    log.see("end")
    log.configure(state="disabled")

def rx_loop():
    global ser, stop_rx
    buf = b""
    while not stop_rx and ser is not None:
        try:
            chunk = ser.read(ser.in_waiting or 1)
            if not chunk:
                time.sleep(0.01)
                continue
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                s = line.decode("utf-8", errors="replace").strip()
                if s:
                    root.after(0, append_log, s)
        except Exception as e:
            root.after(0, append_log, f"[RX error] {e}")
            time.sleep(0.2)

def open_serial():
    global ser, rx_thread, stop_rx
    if ser is not None:
        return
    port = port_entry.get().strip()
    if not port:
        messagebox.showerror("Port Error", "COM_PORT is empty.")
        return
    try:
        ser = serial.Serial(port, BAUDRATE, timeout=0.1)
        stop_rx = False
        rx_thread = threading.Thread(target=rx_loop, daemon=True)
        rx_thread.start()
        append_log(f"Connected: {port} @ {BAUDRATE}")
        # USB CDC may reset; give it a moment
        time.sleep(0.4)
        set_speed()
        set_acc()
        go_center()
    except Exception as e:
        ser = None
        messagebox.showerror("Connection Error", f"Could not open {port}:\n{e}")

def close_serial():
    global ser, stop_rx
    try:
        stop_rx = True
        time.sleep(0.1)
        if ser is not None:
            ser.close()
            ser = None
        append_log("Disconnected.")
    except Exception as e:
        append_log(f"[Close error] {e}")

def send_deg(deg: float):
    if INVERT_DEG:
        deg = 360.0 - float(deg)
    deg = max(0.0, min(360.0, float(deg)))
    safe_write_line(f"DEG {deg:.1f}")

def on_slider(value):
    try:
        send_deg(float(value))
    except ValueError:
        pass

def go_center():
    slider.set(NEUTRAL_DEG)
    send_deg(NEUTRAL_DEG)

def nudge(delta: float):
    cur = float(slider.get())
    newv = max(0.0, min(360.0, cur + delta))
    slider.set(newv)
    send_deg(newv)

def set_speed():
    try:
        v = int(speed_entry.get().strip())
    except Exception:
        v = DEFAULT_SPEED
        speed_entry.delete(0, "end")
        speed_entry.insert(0, str(v))
    v = max(0, min(2000, v))
    safe_write_line(f"SPEED {v}")

def set_acc():
    try:
        v = int(acc_entry.get().strip())
    except Exception:
        v = DEFAULT_ACC
        acc_entry.delete(0, "end")
        acc_entry.insert(0, str(v))
    v = max(0, min(255, v))
    safe_write_line(f"ACC {v}")

def send_help():
    safe_write_line("HELP")

def rescan():
    safe_write_line("RESCAN")

def refresh_ports():
    ports = list_ports()
    append_log("Ports: " + ", ".join(ports) if ports else "Ports: (none)")

def on_close():
    close_serial()
    root.destroy()

# === Tkinter GUI ===
root = tk.Tk()
root.title("ST3215-HS Servo GUI (ESP32 USB Serial)")
root.geometry("520x420")
root.protocol("WM_DELETE_WINDOW", on_close)

top = tk.Frame(root)
top.pack(fill="x", padx=12, pady=(10, 6))

tk.Label(top, text="Port").pack(side="left")
port_entry = tk.Entry(top, width=22)
port_entry.pack(side="left", padx=(6, 8))
port_entry.insert(0, COM_PORT)

tk.Button(top, text="Refresh", command=refresh_ports, width=8).pack(side="left", padx=4)
tk.Button(top, text="Connect", command=open_serial, width=8).pack(side="left", padx=4)
tk.Button(top, text="Disconnect", command=close_serial, width=10).pack(side="left", padx=4)

slider = tk.Scale(
    root, from_=0.0, to=360.0, resolution=1.0,
    orient="horizontal", command=on_slider, label="Angle (deg)"
)
slider.set(NEUTRAL_DEG)
slider.pack(fill="x", padx=16, pady=(6, 6))

btn_row = tk.Frame(root)
btn_row.pack(fill="x", padx=16, pady=(0, 6))

tk.Button(btn_row, text="◀ -1°", command=lambda: nudge(-1.0), width=8).pack(side="left", padx=4)
tk.Button(btn_row, text="Center", command=go_center, width=10).pack(side="left", padx=4)
tk.Button(btn_row, text="+1° ▶", command=lambda: nudge(+1.0), width=8).pack(side="left", padx=4)
tk.Button(btn_row, text="Rescan ID", command=rescan, width=10).pack(side="left", padx=4)
tk.Button(btn_row, text="Help", command=send_help, width=8).pack(side="left", padx=4)

cfg = tk.Frame(root)
cfg.pack(fill="x", padx=16, pady=(0, 8))

tk.Label(cfg, text="Speed(steps/s)").pack(side="left")
speed_entry = tk.Entry(cfg, width=6)
speed_entry.pack(side="left", padx=(6, 8))
speed_entry.insert(0, str(DEFAULT_SPEED))
tk.Button(cfg, text="Set", command=set_speed, width=6).pack(side="left", padx=4)

tk.Label(cfg, text="Acc").pack(side="left", padx=(12, 0))
acc_entry = tk.Entry(cfg, width=4)
acc_entry.pack(side="left", padx=(6, 8))
acc_entry.insert(0, str(DEFAULT_ACC))
tk.Button(cfg, text="Set", command=set_acc, width=6).pack(side="left", padx=4)

log = tk.Text(root, height=12, state="disabled")
log.pack(fill="both", expand=True, padx=16, pady=(0, 12))

append_log("1) Upload simple_move_gui.ino to Nano ESP32")
append_log("2) Set driver jumper to A (line1-line2 on both columns)")
append_log("3) Provide external 9-12.6V to driver board, common GND")
append_log("4) Click Connect, then move the slider")

root.mainloop()
