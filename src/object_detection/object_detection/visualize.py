import rclpy
import cv2
import json
import os
from ament_index_python.packages import get_package_share_directory
from ultralytics import YOLO
from object_detection.realsense import ImgNode

PACKAGE_PATH = get_package_share_directory("pick_and_place_text")
YOLO_MODEL_PATH = os.path.join(PACKAGE_PATH, "resource", "yolov8n_tools_0122.pt")
YOLO_JSON_PATH = os.path.join(get_package_share_directory("object_detection"), "resource", "class_name_tool.json")


def main():
    rclpy.init()
    node = ImgNode()

    with open(YOLO_JSON_PATH, "r") as f:
        class_dict = json.load(f)  # {0: "drill", 1: "hammer", ...}

    model = YOLO(YOLO_MODEL_PATH)

    print("Press 'q' to quit.")

    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.1)
        frame = node.get_color_frame()
        if frame is None:
            continue

        results = model(frame, verbose=False)
        for box, score, label in zip(
            results[0].boxes.xyxy.tolist(),
            results[0].boxes.conf.tolist(),
            results[0].boxes.cls.tolist(),
        ):
            if score < 0.5:
                continue
            x1, y1, x2, y2 = map(int, box)
            name = class_dict.get(str(int(label)), str(int(label)))
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{name} {score:.2f}", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.imshow("YOLO Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    node.destroy_node()
    rclpy.shutdown()
