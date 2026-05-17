# 🤖 ROS2 음성 제어 로봇 픽앤플레이스 시스템

음성 명령으로 도구를 인식하고 집어서 홈 위치에 가져다 놓는 ROS2 기반 로봇 자동화 시스템입니다.  
Doosan M0609 로봇 암, RealSense 깊이 카메라, YOLOv8 객체 인식, Whisper STT, GPT-4o를 활용합니다.

---

## 시스템 구성

```
음성 입력 (웨이크워드 + 도구 이름)
        ↓
voice_processing — Whisper STT + GPT-4o로 도구 이름 추출
        ↓
robot_control — 도구별 순서대로 픽앤플레이스 반복
        ↓
object_detection — YOLOv8으로 도구 위치 탐지 (카메라 좌표 → 로봇 베이스 좌표 변환)
        ↓
Doosan M0609 + OnRobot RG2 그리퍼로 동작 실행
```

### 패키지 구조

| 패키지 | 역할 |
|---|---|
| `robot_control` | 로봇 모션 제어, 픽앤플레이스 로직 |
| `object_detection` | YOLOv8 추론, 3D 위치 서비스, 바운딩박스 시각화 |
| `voice_processing` | 웨이크워드 감지, STT, LLM 키워드 추출 |
| `od_msg` | 커스텀 ROS2 서비스 메시지 (`SrvDepthPosition`) |

### 인식 가능한 도구

`drill`, `hammer`, `pliers`, `screwdriver`, `wrench`

---

## 실행 방법

> 모든 터미널에서 `export ROS_DOMAIN_ID=60` 필수

### 터미널 1 — 로봇 bringup (Host)

```bash
cd ~/ros2_ws && source install/setup.bash
export ROS_DOMAIN_ID=60
ros2 launch dsr_launcher2 dsr_moveit2_m0609.launch.py
```

### 터미널 2 — RealSense 카메라 (Host)

```bash
cd ~/ros2_ws && source install/setup.bash
export ROS_DOMAIN_ID=60
ros2 launch realsense2_camera rs_launch.py
```

### 터미널 3 — 객체 인식 (Docker 컨테이너 내부 — 빈 터미널에서 시작)

```bash
cd /home/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
export ROS_DOMAIN_ID=60
ros2 run object_detection object_detection
```

### 터미널 4 — 웨이크워드 / STT (Host)

```bash
cd ~/ros2_ws && source install/setup.bash
export ROS_DOMAIN_ID=60
ros2 run voice_processing get_keyword
```

### 터미널 5 — 로봇 컨트롤러 (Host)

```bash
cd ~/ros2_ws && source install/setup.bash
export ROS_DOMAIN_ID=60
ros2 run robot_control robot_control
```

### (선택) 바운딩박스 뷰어

현재 카메라에서 인식 중인 바운딩박스를 실시간으로 확인합니다.

```bash
cd ~/ros2_ws && source install/setup.bash
export ROS_DOMAIN_ID=60
ros2 run object_detection bbox_viewer
```

---

## 사용 방법

1. 5개 터미널 모두 실행
2. **"Hello Rokey"** 라고 말해서 웨이크워드 활성화
3. 도구 이름을 말하면 로봇이 자동으로 집어서 홈 위치에 내려놓음
4. 여러 도구를 한 번에 말하면 순서대로 처리

**예시 발화:**
- `"해머 가져와"` → hammer 1개 픽앤플레이스
- `"해머랑 랜치 가져와"` → hammer 먼저, 이후 wrench 순서대로 처리

---

## 빌드

```bash
cd ~/ros2_ws
colcon build --packages-select <패키지명>
source install/setup.bash
```

---

## 주요 설정값

| 항목 | 파일 | 상수명 |
|---|---|---|
| 로봇 속도/가속도 | `robot_control/robot_control.py` | `VELOCITY`, `ACC` |
| 깊이 오프셋 | `robot_control/robot_control.py` | `DEPTH_OFFSET` |
| 그리퍼 IP | `robot_control/robot_control.py` | `TOOLCHARGER_IP` |
| 핸드-아이 캘리브레이션 | `object_detection/resource/T_gripper2camera.npy` | — |
| OpenAI API 키 | `voice_processing/resource/.env` | `OPENAI_API_KEY` |

---

## ROS2 인터페이스

| 토픽 / 서비스 | 타입 | 설명 |
|---|---|---|
| `/get_keyword` | `std_srvs/Trigger` | 음성 키워드 요청 서비스 |
| `/get_3d_position` | `od_msg/SrvDepthPosition` | 도구 3D 좌표 요청 서비스 |
| `/detection_image` | `sensor_msgs/Image` | 바운딩박스 시각화 이미지 |

---

## 동작 시퀀스 (픽앤플레이스)

1. 타겟 상공 80mm 접근
2. 타겟 위치로 하강 (30mm 추가)
3. 그리퍼 닫기 (물건 파지)
4. 80mm 들어올리기
5. 홈 포즈(`[0,0,90,0,90,0]`)로 복귀 → 그리퍼 열기 (내려놓기)
6. 다음 도구가 있으면 반복
