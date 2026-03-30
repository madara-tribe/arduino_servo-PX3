#!/usr/bin/env python3
"""
PIR Watch Node — Telemetrix edition
SeamlessTrack-PX / px_pir package

Hardware : SB612B OUT -> Arduino D2
Firmware : Telemetrix4Arduino.ino (no modification needed)

Topics published:
  /pir/state   std_msgs/Bool   True=human detected, False=cleared
  /pir/event   std_msgs/String JSON {"event":"detect_start"|"detect_end"|
                                      "heartbeat","pin":<n>,"dur_ms":<ms>}

Parameters:
  com_port  (string, default "/dev/ttyACM0")
  pir_pin   (int,    default 2)
  heartbeat_sec (float, default 5.0)
"""

import json
import threading
import time
from datetime import datetime

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from telemetrix import telemetrix


class PIRWatchNode(Node):

    def __init__(self):
        super().__init__('pir_watch_node')

        # ---- Parameters ----
        self.declare_parameter('com_port',      '/dev/ttyACM0')
        self.declare_parameter('pir_pin',       2)
        self.declare_parameter('heartbeat_sec', 5.0)

        self._port          = self.get_parameter('com_port').value
        self._pir_pin       = self.get_parameter('pir_pin').value
        self._hb_sec        = self.get_parameter('heartbeat_sec').value

        # ---- Publishers ----
        self._state_pub = self.create_publisher(Bool,   '/pir/state', 10)
        self._event_pub = self.create_publisher(String, '/pir/event', 10)

        # ---- Internal state ----
        self._detected        = False
        self._detect_start_t  = 0.0
        self._detection_count = 0
        self._lock            = threading.Lock()

        # ---- Heartbeat timer (ROS timer, runs in executor thread) ----
        self._hb_timer = self.create_timer(self._hb_sec, self._heartbeat_cb)

        # ---- Connect to Arduino via Telemetrix ----
        self.get_logger().info(f'Connecting to Arduino on {self._port} ...')
        try:
            self._board = telemetrix.Telemetrix(com_port=self._port)
        except Exception as e:
            self.get_logger().error(f'Telemetrix connect failed: {e}')
            raise RuntimeError(f'Telemetrix connect failed: {e}')

        # Register PIR pin as digital input with callback
        self._board.set_pin_mode_digital_input(
            self._pir_pin,
            callback=self._pir_callback
        )

        self.get_logger().info(
            f'PIR watch node ready. pin=D{self._pir_pin}, '
            f'port={self._port}, heartbeat={self._hb_sec}s'
        )

    # ------------------------------------------------------------------
    # Telemetrix callback  (runs in Telemetrix internal reader thread)
    # data format: [cb_type, pin, value, timestamp]
    #   cb_type: 2 = digital input
    # ------------------------------------------------------------------
    def _pir_callback(self, data):
        # Validate callback data format
        if not isinstance(data, (list, tuple)) or len(data) < 3:
            self.get_logger().warn(f'Unexpected callback format: {data}')
            return

        pin   = data[1]
        value = data[2]   # 1 = HIGH (detected), 0 = LOW (cleared)

        now_str = datetime.now().strftime('%H:%M:%S.%f')[:-3]

        with self._lock:
            if value == 1 and not self._detected:
                # --- Rising edge: detection start ---
                self._detected       = True
                self._detect_start_t = time.monotonic()
                self._detection_count += 1
                count = self._detection_count

                self.get_logger().info(
                    f'[{now_str}] PIR DETECTED  '
                    f'(#{count}, pin=D{pin})'
                )

                self._publish_state(True)
                self._publish_event('detect_start', pin, dur_ms=0)

            elif value == 0 and self._detected:
                # --- Falling edge: detection end ---
                self._detected = False
                dur_ms = int((time.monotonic() - self._detect_start_t) * 1000)

                self.get_logger().info(
                    f'[{now_str}] PIR CLEARED   '
                    f'(duration: {dur_ms/1000:.2f}s, pin=D{pin})'
                )

                self._publish_state(False)
                self._publish_event('detect_end', pin, dur_ms=dur_ms)

    # ------------------------------------------------------------------
    # Heartbeat (called by ROS timer — executor thread)
    # ------------------------------------------------------------------
    def _heartbeat_cb(self):
        with self._lock:
            detected = self._detected
            if detected:
                dur_ms = int((time.monotonic() - self._detect_start_t) * 1000)
            else:
                dur_ms = 0

        state_str = 'ACTIVE' if detected else 'idle'
        self.get_logger().info(
            f'PIR heartbeat ({state_str}, dur={dur_ms}ms, '
            f'count={self._detection_count})'
        )
        self._publish_event('heartbeat', self._pir_pin, dur_ms=dur_ms)

    # ------------------------------------------------------------------
    # Publish helpers
    # ------------------------------------------------------------------
    def _publish_state(self, detected: bool):
        msg = Bool()
        msg.data = detected
        self._state_pub.publish(msg)

    def _publish_event(self, event: str, pin: int, dur_ms: int):
        payload = {
            'event':  event,
            'pin':    pin,
            'dur_ms': dur_ms,
        }
        msg = String()
        msg.data = json.dumps(payload)
        self._event_pub.publish(msg)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def destroy_node(self):
        self.get_logger().info('Shutting down PIR watch node...')
        try:
            self._board.shutdown()
        except Exception as e:
            self.get_logger().warn(f'Telemetrix shutdown warning: {e}')
        super().destroy_node()


# ----------------------------------------------------------------------
def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = PIRWatchNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except RuntimeError as e:
        if rclpy.ok():
            rclpy.get_logger('pir_watch_node').error(str(e))
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
