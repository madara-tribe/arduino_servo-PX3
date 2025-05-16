# arduino servo control for HW (PX3)

this repository belong to ROS2 Python package. you can control an Arduino-connected servo motor via serial communication. 

This package enables both hardware-level actuation and software-based calibration of servo angles 

# Features
- Serial communication with Arduino
Easily send servo angle commands to an Arduino 

- Hardware control via software
Integrate servo actuation into automated software pipelines for physical control tasks.

- Interactive angle calibration (GUI)
with Tkinter GUI, you can adjust the servo angle during setup or test phase.

# How to use

```
# adjust angle with GUI
$ python3 gui_calibrate.py

# run as test
python3 main.py

# if you need to use ros2 subscriber or publisher, modify main.py and run
$ ros2 run hw_px3 hw_px3
```
