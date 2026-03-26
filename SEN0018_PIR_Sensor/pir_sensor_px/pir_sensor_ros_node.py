#!/usr/bin/env python3
"""
PIR Sensor ROS2 Node for PX System (SeamlessTrack-PX4.2)

Publishes:
  - /pir/detection (std_msgs/Bool): Current detection state
  - /pir/event (std_msgs/String): JSON event details
  
Parameters:
  - port: Serial port (default: auto-detect)
  - baudrate: Serial baudrate (default: 115200)
  
Usage:
  ros2 run px_sensors pir_sensor_node
  ros2 run px_sensors pir_sensor_node --ros-args -p port:=/dev/ttyUSB0
"""

import json
import sys
import threading
from datetime import datetime
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import Bool, String

import serial
from serial.tools import list_ports


class PIRSensorNode(Node):
    """ROS2 node for PIR sensor (SB612B) communication."""
    
    def __init__(self):
        super().__init__('pir_sensor_node')
        
        # Declare parameters
        self.declare_parameter('port', '')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('auto_reconnect', True)
        self.declare_parameter('reconnect_interval', 5.0)
        
        # Get parameters
        port = self.get_parameter('port').value
        self.baudrate = self.get_parameter('baudrate').value
        self.auto_reconnect = self.get_parameter('auto_reconnect').value
        self.reconnect_interval = self.get_parameter('reconnect_interval').value
        
        # QoS profile for reliable detection messages
        qos_reliable = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            depth=10
        )
        
        # Publishers
        self.pub_detection = self.create_publisher(Bool, '/pir/detection', qos_reliable)
        self.pub_event = self.create_publisher(String, '/pir/event', 10)
        
        # Serial connection
        self.serial: Optional[serial.Serial] = None
        self.running = True
        self.connected = False
        
        # State tracking
        self.current_state = False
        self.last_heartbeat = datetime.now()
        self.detection_count = 0
        
        # Auto-detect or use specified port
        if port:
            self.port = port
        else:
            self.port = self._auto_detect_port()
        
        # Connect and start reading thread
        self._connect()
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        
        # Watchdog timer for connection health
        self.watchdog_timer = self.create_timer(10.0, self._watchdog_callback)
        
        self.get_logger().info(f'PIR Sensor Node initialized (port: {self.port})')
    
    def _auto_detect_port(self) -> str:
        """Auto-detect Arduino serial port."""
        ports = list(list_ports.comports())
        
        # Look for Arduino
        for p in ports:
            desc_lower = p.description.lower()
            if 'arduino' in desc_lower or 'ch340' in desc_lower or 'usb' in desc_lower:
                self.get_logger().info(f'Auto-detected port: {p.device} ({p.description})')
                return p.device
        
        if ports:
            self.get_logger().warn(f'No Arduino found, using first port: {ports[0].device}')
            return ports[0].device
        
        self.get_logger().error('No serial ports found!')
        return '/dev/ttyUSB0'  # Default fallback
    
    def _connect(self) -> bool:
        """Establish serial connection."""
        try:
            if self.serial and self.serial.is_open:
                self.serial.close()
            
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            self.connected = True
            self.get_logger().info(f'Connected to {self.port}')
            return True
            
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to connect: {e}')
            self.connected = False
            return False
    
    def _read_loop(self):
        """Background thread for reading serial data."""
        while self.running:
            if not self.connected:
                if self.auto_reconnect:
                    self.get_logger().info('Attempting reconnect...')
                    if self._connect():
                        continue
                    import time
                    time.sleep(self.reconnect_interval)
                continue
            
            try:
                if self.serial and self.serial.in_waiting:
                    line = self.serial.readline().decode(errors='replace').strip()
                    if line:
                        self._process_line(line)
                        
            except serial.SerialException as e:
                self.get_logger().error(f'Serial error: {e}')
                self.connected = False
                
            except Exception as e:
                self.get_logger().warn(f'Read error: {e}')
    
    def _process_line(self, line: str):
        """Process incoming JSON line from Arduino."""
        try:
            data = json.loads(line)
            event_type = data.get('event', '')
            state = data.get('state', 0)
            timestamp = data.get('ts', 0)
            duration = data.get('dur', 0)
            sensor_id = data.get('sensor_id', 1)
            
            # Update heartbeat time
            self.last_heartbeat = datetime.now()
            
            # Process by event type
            if event_type == 'init':
                self.get_logger().info(f'Sensor {sensor_id} initialized')
                
            elif event_type == 'detect_start':
                self.current_state = True
                self.detection_count += 1
                self._publish_detection(True)
                self.get_logger().info(f'[DETECT] Motion detected (count: {self.detection_count})')
                
            elif event_type == 'detect_end':
                self.current_state = False
                self._publish_detection(False)
                self.get_logger().info(f'[CLEAR] Motion cleared (duration: {duration}ms)')
                
            elif event_type == 'heartbeat':
                # Heartbeat - update state if needed
                new_state = bool(state)
                if new_state != self.current_state:
                    self.current_state = new_state
                    self._publish_detection(new_state)
            
            # Publish raw event
            self._publish_event(data)
            
        except json.JSONDecodeError:
            # Legacy format or debug message
            self.get_logger().debug(f'Non-JSON: {line}')
    
    def _publish_detection(self, detected: bool):
        """Publish detection state."""
        msg = Bool()
        msg.data = detected
        self.pub_detection.publish(msg)
    
    def _publish_event(self, data: dict):
        """Publish raw event as JSON string."""
        # Add ROS timestamp
        data['ros_time'] = self.get_clock().now().nanoseconds
        
        msg = String()
        msg.data = json.dumps(data)
        self.pub_event.publish(msg)
    
    def _watchdog_callback(self):
        """Check connection health."""
        elapsed = (datetime.now() - self.last_heartbeat).total_seconds()
        
        if elapsed > 15.0 and self.connected:
            self.get_logger().warn(f'No heartbeat for {elapsed:.1f}s - connection may be lost')
    
    def destroy_node(self):
        """Cleanup on shutdown."""
        self.running = False
        if self.serial and self.serial.is_open:
            self.serial.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    
    node = PIRSensorNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
