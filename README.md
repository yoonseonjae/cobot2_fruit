# cobot2-fruit-tutorial

A ROS2 (Humble) voice-controlled pick-and-place robot system using a **Doosan M0609** arm, **Intel RealSense** depth camera, **YOLO** object detection, and **Whisper + GPT-4o** voice commands.

The user speaks a wake word (`"Hello Rokey"`), names one or more fruits, and the robot picks each one sequentially and returns home after each pick.

---

## Detected Objects

| Class ID | Label |
|----------|-------|
| 0 | Apple |
| 1 | Banana |
| 2 | Kiwi |
| 3 | Orange |
| 4 | Pear |

---

## System Architecture

```
voice_processing/get_keyword  ──►  /get_keyword (std_srvs/Trigger)
                                          │
                                          ▼
robot_control/robot_control   calls /get_keyword, then /get_3d_position per fruit
                                          │
                                          ▼
object_detection/object_detection  ──►  /get_3d_position (od_msg/SrvDepthPosition)
                                          │
                                          ▼
                               returns [x, y, z] in camera frame
                                          │
                                          ▼
robot_control  transforms camera → base frame, runs pick-and-place, init_robot() between each fruit
```

### Data Flow

1. `robot_control` calls `/get_keyword` — blocks until user says wake word + fruit names
2. `get_keyword` uses **Whisper STT + GPT-4o** to extract fruit names as a space-separated string (e.g. `"apple banana"`)
3. `robot_control` splits into `target_list` and loops: for each fruit → `get_target_pos()` → `pick_and_place_target()` → `init_robot()`
4. `get_target_pos()` calls `/get_3d_position`, receives 3D position in camera frame, loads `T_gripper2camera.npy`, gets current robot pose, transforms to base frame
5. `object_detection` publishes `/detection_image` at ~10 Hz with bounding boxes drawn; `bbox_viewer` subscribes to display it

---

## ROS Interfaces

| Topic / Service | Type | Direction |
|---|---|---|
| `/get_keyword` | `std_srvs/Trigger` | voice_processing serves, robot_control calls |
| `/get_3d_position` | `od_msg/SrvDepthPosition` (string target → float64[] depth_position) | object_detection serves, robot_control calls |
| `/detection_image` | `sensor_msgs/Image` | object_detection publishes |
| `/camera/camera/color/image_raw` | `sensor_msgs/Image` | RealSense publishes |
| `/camera/camera/aligned_depth_to_color/image_raw` | `sensor_msgs/Image` | RealSense publishes |

---

## Package Structure

```
ros2_ws/src/
├── object_detection/       # YOLO inference + 3D position service + image publisher
│   ├── object_detection/
│   │   ├── detection.py    # /get_3d_position service + /detection_image publisher
│   │   ├── yolo.py         # Multi-frame aggregation with IoU grouping
│   │   ├── bbox_viewer.py  # Subscriber to display bounding boxes
│   │   └── visualize.py
│   └── resource/
│       ├── class_name_tool.json   # Class ID → label mapping
│       └── T_gripper2camera.npy  # Hand-eye calibration matrix
├── od_msg/                 # Custom service definition (SrvDepthPosition)
├── robot_control/          # All robot motion logic
│   └── robot_control/
│       ├── robot_control.py  # Pick-and-place controller
│       └── onrobot.py        # OnRobot RG2 gripper (Modbus TCP)
└── voice_processing/       # Wake word detection + Whisper STT
    └── voice_processing/
        ├── get_keyword.py
        ├── wakeup_word.py
        ├── stt.py
        └── MicController.py
```

---

## Prerequisites

- ROS2 Humble
- Doosan DSR ROS2 package (`dsr_launcher2`, `DSR_ROBOT2`)
- Intel RealSense ROS2 package (`realsense2_camera`)
- Docker container for object detection (with YOLO dependencies)
- OpenAI API key (for Whisper STT + GPT-4o)
- OnRobot RG2 gripper reachable at `192.168.1.1:502`

**`ROS_DOMAIN_ID=60` must be set in every terminal.**

---

## Build

```bash
cd ~/ros2_ws
colcon build
source install/setup.bash
```

To build a single package:

```bash
colcon build --packages-select <package_name>
source install/setup.bash
```

---

## Running the System

### Terminal 1 — Robot Bringup (Host)

```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 launch dsr_launcher2 dsr_moveit2_m0609.launch.py
```

### Terminal 2 — RealSense Camera (Host)

```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 launch realsense2_camera rs_launch.py
```

### Terminal 3 — Object Detection (Docker Container)

```bash
docker exec -it object_detection bash
```

Inside the container:

```bash
cd /home/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
export ROS_DOMAIN_ID=60
ros2 run object_detection object_detection
```

### Terminal 4 — Voice Recognition (Host)

```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 run voice_processing get_keyword
```

### Terminal 5 — Robot Controller (Host)

```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 run robot_control robot_control
```

### Terminal 6 — Bounding Box Viewer (Optional)

```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 run object_detection bbox_viewer
```

---

## Usage

1. Start all 5 terminals
2. Say **"Hello Rokey"** to activate the wake word
3. Say one or more fruit names — the robot picks each one and drops it at home position
4. Multiple fruits spoken at once are processed sequentially

**Example:**
- `"Apple"` → picks apple, returns home
- `"Apple and banana"` → picks apple first, then banana

---

## Configuration & Tuning

Key constants in [robot_control.py](src/robot_control/robot_control/robot_control.py):

| Constant | Description |
|---|---|
| `VELOCITY`, `ACC` | Robot velocity and acceleration (default: 60) |
| `JHOME_POS` | Home joint position `[0, -30, 90, 0, 90, 0]` |
| `PLACE_POS` | Place position in Cartesian space |
| `DEPTH_OFFSET` | Z-axis offset applied to detected position (mm) |
| `MIN_DEPTH` | Minimum valid depth reading (mm) |

Hand-eye calibration matrix: `object_detection/resource/T_gripper2camera.npy`
Recalibrate if the camera is moved relative to the gripper.

OpenAI API key: `voice_processing/resource/.env`

---

## Motion Pattern

- **`init_robot()`** — moves to `JHOME_POS` and opens gripper (the object drops at home pose)
- **`pick_and_place_target()`** — approach 80 mm above target → descend 30 mm below → close gripper → lift 80 mm → return → `init_robot()` drops object

---

## Gripper

OnRobot RG2 controlled via Modbus TCP ([onrobot.py](src/robot_control/robot_control/onrobot.py)).
Connection is established at module load time before the ROS node starts.

```python
gripper.open_gripper()
gripper.close_gripper()
```
