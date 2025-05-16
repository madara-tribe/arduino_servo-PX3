#!/bin/bash
# Find Arduino device (typically ttyACM)
ARDUINO_DEV=$(ls /dev/ttyACM* 2>/dev/null | head -n 1)

if [ -z "$ARDUINO_DEV" ]; then
  echo "Error: No Arduino device found (ttyACM*)"
  exit 1
fi

echo "Using Arduino device: $ARDUINO_DEV"

docker run -it --rm \
  --net=host \
  --privileged \
  --device=$ARDUINO_DEV \
  --group-add video \
  -v /home/hagi/Downloads/ggg/workspace/:/ros2_ws \
  test:latest


#sudo chmod 777 $ARDUINO_DEV
# v4l2-ctl --list-devices
