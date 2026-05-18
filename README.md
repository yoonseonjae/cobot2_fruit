# cobot2_fruit — 음성 제어 과일 피킹 로봇 시스템

ROS2 (Humble) 기반의 음성 제어 픽앤플레이스 로봇 시스템입니다.  
Doosan M0609 협동로봇, RealSense 깊이 카메라, YOLO 객체 인식, Whisper STT, GPT-4o를 사용하여  
사용자가 음성으로 과일 이름을 말하면 로봇이 해당 과일을 집어 지정 위치에 옮깁니다.

---

## 지원 과일 목록

| 클래스 ID | 과일 |
|-----------|------|
| 0 | Apple (사과) |
| 1 | Banana (바나나) |
| 2 | Kiwi (키위) |
| 3 | Orange (오렌지) |
| 4 | Pear (배) |

---

## 시스템 구성

```
[사용자 음성]
     ↓
voice_processing/get_keyword   (Wake word 감지 → Whisper STT → GPT-4o 키워드 추출)
     ↓  /get_keyword (Trigger srv)
robot_control/robot_control    (과일별 루프: 위치 요청 → 픽앤플레이스 → 홈 복귀)
     ↓  /get_3d_position (SrvDepthPosition srv)
object_detection/object_detection  (YOLO 인식 + RealSense 깊이 → 3D 좌표 반환)
```

---

## 사전 요구사항

### 하드웨어
- Doosan M0609 협동로봇
- Intel RealSense 깊이 카메라
- OnRobot RG2 그리퍼 (IP: `192.168.1.1`, Port: `502`)
- 마이크

### 소프트웨어
- Ubuntu 22.04
- ROS2 Humble
- Docker (객체 인식 패키지 실행용)
- Python 패키지: `ultralytics`, `pyaudio`, `langchain-openai`, `python-dotenv`, `scipy`, `pymodbus`
- OpenAI API 키

---

## Git 클론 후 수동으로 추가해야 할 파일

`.gitignore`에 의해 저장소에 포함되지 않는 파일들입니다. 클론 후 직접 준비해야 합니다.

| 파일 | 경로 | 설명 |
|------|------|------|
| `.env` | `src/voice_processing/resource/.env` | OpenAI API 키 설정 파일 |
| `best.pt` | `src/object_detection/resource/best.pt` | YOLO 과일 인식 학습 모델 |
| `T_gripper2camera.npy` | `src/object_detection/resource/T_gripper2camera.npy` | 핸드-아이 캘리브레이션 행렬 |

### `.env` 파일 생성

```bash
echo "OPENAI_API_KEY=여기에_본인의_API_키_입력" > src/voice_processing/resource/.env
```

### `best.pt` 모델 배치

YOLO 학습 모델 파일(`best.pt`)을 별도로 전달받아 아래 경로에 복사하세요.

```bash
cp best.pt src/object_detection/resource/best.pt
```

### `T_gripper2camera.npy` 배치

핸드-아이 캘리브레이션을 수행하여 생성된 `.npy` 파일을 아래 경로에 복사하세요.  
카메라 위치가 바뀔 때마다 재캘리브레이션이 필요합니다.

```bash
cp T_gripper2camera.npy src/object_detection/resource/T_gripper2camera.npy
```

---

## 설치 방법

### 1. 저장소 클론

```bash
git clone https://github.com/yoonseonjae/cobot2_fruit.git ~/ros2_ws
cd ~/ros2_ws
```

### 2. Python 의존성 설치

```bash
pip install ultralytics langchain-openai python-dotenv pyaudio scipy pymodbus
```

### 3. 누락 파일 준비

위의 **"Git 클론 후 수동으로 추가해야 할 파일"** 섹션을 참고하여 `.env`, `best.pt`, `T_gripper2camera.npy`를 배치하세요.

### 4. ROS2 패키지 빌드

```bash
cd ~/ros2_ws
colcon build
source install/setup.bash
```

> **주의:** Python 파일 수정 후에는 반드시 `colcon build` 및 `source install/setup.bash`를 다시 실행하세요.

---

## 실행 방법

모든 터미널에서 **`ROS_DOMAIN_ID=60`** 을 설정해야 합니다.

### 터미널 1 — 로봇 브링업 (호스트)

```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 launch dsr_launcher2 dsr_moveit2_m0609.launch.py
```

### 터미널 2 — RealSense 카메라 (호스트)

```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 launch realsense2_camera rs_launch.py
```

### 터미널 3 — 객체 인식 (Docker 컨테이너 내부)

Docker 컨테이너를 실행한 후 컨테이너 내부에서 아래 명령을 입력하세요.

```bash
cd /home/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
export ROS_DOMAIN_ID=60
ros2 run object_detection object_detection
```

### 터미널 4 — 음성 인식 (호스트)

```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 run voice_processing get_keyword
```

### 터미널 5 — 로봇 컨트롤러 (호스트)

```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 run robot_control robot_control
```

### 선택 — 바운딩 박스 뷰어

```bash
cd ~/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=60
ros2 run object_detection bbox_viewer
```

---

## 사용 방법

1. 5개의 터미널이 모두 실행되면 로봇이 홈 위치(`JReady`)로 이동합니다.
2. 마이크에 대고 **"헬로 로키"** (wake word)라고 말합니다.
3. Wake word가 감지되면 과일 이름과 목적지를 말합니다.
   - 예: `"사과랑 바나나 가져와"` → Apple, Banana 순서대로 픽앤플레이스
   - 예: `"오렌지를 pos1에 놓고 키위는 pos2에 놔"` → 각 위치로 이동
4. 로봇이 YOLO로 과일 위치를 파악한 뒤 순서대로 집어 지정 위치에 내려놓습니다.

---

## 주요 설정값 (튜닝)

[`src/robot_control/robot_control/robot_control.py`](src/robot_control/robot_control/robot_control.py) 상단에서 조정합니다.

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `VELOCITY`, `ACC` | `60, 60` | 로봇 속도/가속도 |
| `JHOME_POS` | `[0, -30, 90, 0, 90, 0]` | 홈 관절 각도 |
| `PLACE_POS` | `[501.58, -139.35, 396.03, ...]` | 물건 놓는 위치 (직교 좌표) |
| `DEPTH_OFFSET` | `-5.0` | 깊이 보정값 (mm) |
| `MIN_DEPTH` | `2.0` | 최소 유효 깊이 (m) |

---

## 파일 구조

```
ros2_ws/
├── src/
│   ├── object_detection/         # YOLO 인식 + /get_3d_position 서비스
│   │   ├── object_detection/
│   │   │   ├── detection.py      # 메인 인식 노드
│   │   │   ├── yolo.py           # YOLO 멀티프레임 집계
│   │   │   └── visualize.py      # 바운딩 박스 시각화
│   │   └── resource/
│   │       ├── best.pt           # YOLO 학습 모델
│   │       ├── class_name_tool.json  # 클래스 ID → 과일 이름 매핑
│   │       └── T_gripper2camera.npy  # 핸드-아이 캘리브레이션 행렬
│   ├── robot_control/            # 로봇 모션 제어
│   │   └── robot_control/
│   │       ├── robot_control.py  # 픽앤플레이스 메인 로직
│   │       └── onrobot.py        # RG2 그리퍼 Modbus TCP 제어
│   ├── voice_processing/         # Wake word + STT + GPT 키워드 추출
│   │   ├── voice_processing/
│   │   │   └── get_keyword.py
│   │   └── resource/
│   │       ├── .env              # OPENAI_API_KEY 설정 파일
│   │       └── hello_rokey_*.tflite  # Wake word 모델
│   └── od_msg/                   # 커스텀 ROS2 서비스 메시지
```

---

## 캘리브레이션 주의사항

카메라 위치를 변경한 경우 핸드-아이 캘리브레이션을 다시 수행하고  
`src/object_detection/resource/T_gripper2camera.npy` 파일을 교체해야 합니다.

---

## 마이크 설정

`get_keyword.py`의 `MicConfig` 에서 `device_index`를 본인 환경에 맞게 수정하세요.

```python
mic_config = MicConfig(
    ...
    device_index=10,   # 본인 마이크 장치 번호로 변경
    ...
)
```

장치 번호 확인:
```bash
python3 -c "import pyaudio; p=pyaudio.PyAudio(); [print(i, p.get_device_info_by_index(i)['name']) for i in range(p.get_device_count())]"
```
