#!/usr/bin/env python3
import time, serial, rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Bool
from std_msgs.msg import Float32MultiArray

class AngleForwarder(Node):
    def __init__(self):
        super().__init__('px3')
        self.declare_parameter('serial_port', '/dev/ttyACM0')
        self.declare_parameter('baud', 9600)
        self.declare_parameter('min_interval_s', 0.10)

        port = self.get_parameter('serial_port').get_parameter_value().string_value
        baud = int(self.get_parameter('baud').get_parameter_value().integer_value)
        self.min_interval = float(self.get_parameter('min_interval_s').get_parameter_value().double_value)

        try:
            self.ser = serial.Serial(port, baudrate=baud, timeout=0.1)
            time.sleep(2.0)
            self.ser.write(b"90\n")
            self.get_logger().info(f'px3: opened {port} @ {baud}; centered 90°')
        except Exception as e:
            self.get_logger().error(f'px3: serial open failed: {e}')
            self.ser = None

        self.ready_pub = self.create_publisher(Bool, 'px3_ready', 10)
        self.ready_pub.publish(Bool(data=True))
        self.lat_pub = self.create_publisher(Float32MultiArray, 'px3_latency', 10)

        self.sub = self.create_subscription(Float32, 'abs_angle', self.on_angle, 10)

        self.last_send_t = time.perf_counter()
        self.last_servo = None
        self.baud = baud

    def on_angle(self, msg: Float32):
        servo = int(round(msg.data))
        now_s = time.perf_counter()
        if (now_s - self.last_send_t) < self.min_interval:
            return
        if self.last_servo is not None and (self.last_servo - 4 < servo < self.last_servo + 4):
            return

        recv_ns = time.perf_counter_ns()
        payload = f"{servo}\n".encode('ascii')
        try:
            write_start_ns = time.perf_counter_ns()
            if self.ser: 
                self.ser.write(payload)
                self.ser.flush()
            write_end_ns = time.perf_counter_ns()
        except Exception as e:
            self.get_logger().error(f'px3: serial write failed: {e}')
            return

        self.last_send_t = now_s
        self.last_servo = servo

        sub_to_write_ms = (write_end_ns - recv_ns)/1e6
        write_call_ms = (write_end_ns - write_start_ns)/1e6
        wire_ms = (len(payload)*10*1000.0)/float(self.baud) if self.baud>0 else 0.0
        dbg = Float32MultiArray(data=[sub_to_write_ms, write_call_ms, wire_ms])
        self.lat_pub.publish(dbg)
        self.get_logger().info(
            f'px3: lat sub->write={sub_to_write_ms:.2f} ms, write()={write_call_ms:.2f} ms, wire≈{wire_ms:.2f} ms'
        )

def main():
    rclpy.init()
    node = AngleForwarder()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if getattr(node, "ser", None) and node.ser.is_open:
            node.ser.close()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

