# デフォルト（/dev/ttyACM0, D2）
ros2 run px_pir_cpp pir_watch_node

# ポート・ピン指定
ros2 run px_pir_cpp pir_watch_node \
  --ros-args -p com_port:=/dev/ttyUSB0 -p pir_pin:=2

# Topic 確認（別ターミナル）
ros2 topic echo /pir/state
ros2 topic echo /pir/event
