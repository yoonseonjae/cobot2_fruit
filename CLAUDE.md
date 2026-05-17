# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A ROS2 (Humble) pick-and-place robot system using a Doosan M0609 arm, RealSense depth camera, YOLO object detection, and voice commands. The user speaks a wake word ("Hello Rokey"), names one or more tools, and the robot picks each one sequentially and returns to home.

**ROS_DOMAIN_ID=60** must be set in every terminal.

## Build

```bash
cd ~/ros2_ws
colcon build --packages-select <package_name>
# or build all
colcon build
source install/setup.bash
```

After editing any Python entry point or adding new files, rebuild and re-source before running.

## Running the System (5 terminals)

**Terminal 1 — Robot bringup (Host)**
```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 launch dsr_launcher2 dsr_moveit2_m0609.launch.py
```

**Terminal 2 — RealSense camera (Host)**
```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 launch realsense2_camera rs_launch.py
```

**Terminal 3 — Object detection (Docker container — start from a blank terminal inside the container)**
```bash
cd /home/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
export ROS_DOMAIN_ID=60
ros2 run object_detection object_detection
```

**Terminal 4 — Wake word / STT (Host)**
```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 run voice_processing get_keyword
```

**Terminal 5 — Robot controller (Host)**
```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 run robot_control robot_control
```

**Optional — Bounding box viewer (any terminal)**
```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 run object_detection bbox_viewer
```

## Architecture

```
voice_processing/get_keyword  →  /get_keyword (Trigger srv)
                                        ↓
robot_control/robot_control  calls /get_keyword, then /get_3d_position per tool
                                        ↓
object_detection/object_detection  →  /get_3d_position (SrvDepthPosition srv)
                                        ↓
                              returns [x,y,z] in camera frame
                                        ↓
robot_control  transforms camera→base coords, runs pick-and-place, init_robot() between each tool
```

### Data flow detail

1. `robot_control` calls `/get_keyword` → blocks until user says wake word + tool names
2. `get_keyword` uses Whisper STT + GPT-4o to extract tool names as a space-separated string (e.g. `"hammer wrench"`)
3. `robot_control` splits the string into `target_list` and loops: for each tool → `get_target_pos()` → `pick_and_place_target()` → `init_robot()` (home + gripper open = place)
4. `get_target_pos()` calls `/get_3d_position`, receives depth position in camera frame, loads `T_gripper2camera.npy`, gets current robot pose, transforms to base frame
5. `object_detection` publishes `/detection_image` (Image) at ~10 Hz with bounding boxes drawn; `bbox_viewer` subscribes to display it

### Key files

- `robot_control/robot_control/robot_control.py` — all robot motion logic; `PLACE_POS`, `DEPTH_OFFSET`, `MIN_DEPTH`, `VELOCITY/ACC` are tuning constants at the top
- `object_detection/object_detection/detection.py` — YOLO inference + `/get_3d_position` service + `/detection_image` publisher
- `object_detection/object_detection/yolo.py` — multi-frame aggregation with IoU grouping for stable detections
- `object_detection/resource/T_gripper2camera.npy` — hand-eye calibration matrix (gripper→camera transform); must be recalibrated if camera is moved
- `object_detection/resource/class_name_tool.json` — YOLO class id→name mapping: `{0:drill, 1:hammer, 2:pliers, 3:screwdriver, 4:wrench}`
- `voice_processing/resource/.env` — contains `OPENAI_API_KEY`

### ROS interfaces

| Topic/Service | Type | Direction |
|---|---|---|
| `/get_keyword` | `std_srvs/Trigger` | voice_processing serves, robot_control calls |
| `/get_3d_position` | `od_msg/SrvDepthPosition` (string target → float64[] depth_position) | object_detection serves, robot_control calls |
| `/detection_image` | `sensor_msgs/Image` | object_detection publishes |
| `/camera/camera/color/image_raw` | `sensor_msgs/Image` | realsense publishes |
| `/camera/camera/aligned_depth_to_color/image_raw` | `sensor_msgs/Image` | realsense publishes |

### Gripper

`robot_control/robot_control/onrobot.py` — Modbus TCP to OnRobot RG2 gripper at `192.168.1.1:502`. `gripper.open_gripper()` / `gripper.close_gripper()`. Called at module load time (not inside the Node), so the connection is established before the node starts.

### Motion pattern

`init_robot()`: movej to JReady `[0,0,90,0,90,0]` + open gripper (this is the "place" step — object drops at home pose).  
`pick_and_place_target()`: approach 80mm above → descend 30mm below target → close gripper → lift 80mm → return to caller → `init_robot()` drops object.
