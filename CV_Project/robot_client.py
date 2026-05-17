from robot import Robot
import time


class RobotArmClient:
    def __init__(self, ip):
        self.robot = Robot(ip)

    def connect(self):
        ok, msg = self.robot.connect()
        if not ok:
            raise Exception(f"连接失败: {msg}")
        print("[Robot] 已连接")

    def init(self):
        print("[Robot] 初始化...")
        self.robot.execute("power_on()")
        time.sleep(1)
        self.robot.execute("enable_robot()")
        time.sleep(1)

    def movej(self, joints):
        cmd = f"movej({joints})"
        ok, res = self.robot.execute(cmd)
        print("[Robot] movej:", ok, res)

    def movel(self, pose):
        cmd = f"movel({pose})"
        ok, res = self.robot.execute(cmd)
        print("[Robot] movel:", ok, res)

    def stop(self):
        self.robot.execute("stopj()")

    def disconnect(self):
        self.robot.disconnect()
        print("[Robot] 断开连接")