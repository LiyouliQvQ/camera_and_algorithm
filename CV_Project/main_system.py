from robot_client import RobotArmClient
from vision_server_api import VisionServer
from config import Config
import time


def main():
    robot = RobotArmClient(Config.ROBOT_IP)
    vision = VisionServer()

    # ===== 1. 连接机器人 =====
    robot.connect()
    robot.init()

    try:
        while True:
            print("\n[System] 开始检测...")

            # ===== 2. 视觉检测 =====
            image_path = "datasets/differential_housing/test/bad/bad_04.png"

            has_defect, pose = vision.infer(image_path)

            # ===== 3. 控制机械臂 =====
            if has_defect:
                print("[System] 检测到缺陷 → 移动机械臂")

                robot.movej(Config.MOVE_JOINT)
                time.sleep(2)

                robot.movel(pose)
                time.sleep(2)

            else:
                print("[System] 无缺陷")

            time.sleep(3)

    except KeyboardInterrupt:
        print("\n[System] 手动停止")

    finally:
        robot.disconnect()


if __name__ == "__main__":
    main()