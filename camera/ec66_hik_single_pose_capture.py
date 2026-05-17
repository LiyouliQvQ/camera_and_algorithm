import os
import sys
import json
import time
import socket
import select
from datetime import datetime
from ctypes import *

import cv2
import numpy as np


# =========================
# 运行前请先改这里
# =========================
ROBOT_IP = "192.168.1.200"
ROBOT_PORT = 8055

# 目标关节位姿（单位：度）
TARGET_POSE = [0.0, -20.0, 90.0, 0.0, 90.0, 0.0]
MOVE_SPEED = 20.0
MOVE_ACC = 10.0
MOVE_DEC = 10.0

# 图像保存目录
SAVE_DIR = r"./captures"
IMAGE_PREFIX = "pose_capture"

# 相机参数（按需改）
USE_AUTO_EXPOSURE = False
EXPOSURE_US = 5000.0
USE_AUTO_GAIN = False
GAIN_DB = 0.0

# 如果 MVS 运行库不在系统 PATH，可取消注释并改成你自己的路径
# os.add_dll_directory(r"C:\Program Files\MVS\Runtime\Win64_x64")


# =========================
# 导入海康相机 SDK
# 约定：MvImport 文件夹与本脚本同级
# =========================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MVIMPORT_DIR = os.path.join(CURRENT_DIR, "MvImport")
if MVIMPORT_DIR not in sys.path:
    sys.path.append(MVIMPORT_DIR)

try:
    from MvCameraControl_class import *
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        "未找到 MvCameraControl_class。请把 MvImport 文件夹放到本脚本同级目录。"
    )


class EliteEC66Client:
    """基于你提供的 JSON-RPC 控制方式整理的最小机械臂客户端。"""

    def __init__(self, ip: str, port: int = 8055, timeout: float = 10.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.connected = False

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.ip, self.port))
        self.connected = True
        return True

    def disconnect(self):
        self.connected = False
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None

    def send_cmd(self, method: str, params=None):
        if not self.connected or self.sock is None:
            raise RuntimeError("机械臂未连接")

        if params is None:
            params = []

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        send_str = json.dumps(payload, ensure_ascii=False) + "\n"

        # 参考你给的代码：先清底层缓存，再发命令
        while True:
            r, _, _ = select.select([self.sock], [], [], 0.0)
            if r:
                self.sock.recv(4096)
            else:
                break

        self.sock.sendall(send_str.encode("utf-8"))
        raw_data = self.sock.recv(4096).decode("utf-8")
        if not raw_data:
            return None

        for line in raw_data.strip().split("\n"):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                return json.loads(line)
        return None

    def enable_servo(self):
        return self.send_cmd("set_servo_status", {"status": 1})

    def get_robot_pos(self):
        res = self.send_cmd("getRobotPos")
        if not res or "result" not in res:
            return None
        data = res["result"]
        if isinstance(data, str):
            data = json.loads(data)
        return data

    def get_robot_state(self):
        res = self.send_cmd("getRobotState")
        if not res:
            return None
        return res.get("result")

    def move_by_joint(self, target_pose, speed=20.0, acc=10.0, dec=10.0):
        if len(target_pose) < 6:
            raise ValueError("target_pose 至少需要 6 个关节值")

        current = self.get_robot_pos()
        if current and len(current) >= 6:
            diff = sum(abs(a - b) for a, b in zip(current[:6], target_pose[:6]))
            if diff < 0.1:
                raise ValueError("目标位姿与当前位姿几乎相同，已拦截本次运动。")

        final_target = list(target_pose[:6])
        while len(final_target) < 8:
            final_target.append(0.0)

        move_params = {
            "targetPos": final_target,
            "speed": float(speed),
            "acc": float(acc),
            "dec": float(dec),
        }
        return self.send_cmd("moveByJoint", move_params)

    def wait_until_idle(self, poll_interval=0.5, timeout=120.0):
        start = time.time()
        while True:
            state = self.get_robot_state()
            if str(state) == "0":
                return True
            if time.time() - start > timeout:
                raise TimeoutError("等待机械臂运动结束超时")
            time.sleep(poll_interval)


class HikCamera:
    def __init__(self):
        self.cam = None
        self.device_info = None
        self.opened = False

    @staticmethod
    def _check_ret(ret, msg):
        if ret != 0:
            raise RuntimeError(f"{msg} 失败, ret=0x{ret:x}")

    def open_first_camera(self):
        device_list = MV_CC_DEVICE_INFO_LIST()
        tlayer_type = MV_GIGE_DEVICE | MV_USB_DEVICE
        ret = MvCamera.MV_CC_EnumDevices(tlayer_type, device_list)
        self._check_ret(ret, "枚举设备")

        if device_list.nDeviceNum == 0:
            raise RuntimeError("没有找到相机")

        self.cam = MvCamera()
        self.device_info = cast(device_list.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents

        ret = self.cam.MV_CC_CreateHandle(self.device_info)
        self._check_ret(ret, "创建句柄")

        ret = self.cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        self._check_ret(ret, "打开相机")
        self.opened = True

        # GigE 尝试设最优包大小
        if self.device_info.nTLayerType == MV_GIGE_DEVICE:
            packet_size = self.cam.MV_CC_GetOptimalPacketSize()
            if int(packet_size) > 0:
                self.cam.MV_CC_SetIntValue("GevSCPSPacketSize", packet_size)

    def close(self):
        if self.cam is not None:
            try:
                if self.opened:
                    self.cam.MV_CC_CloseDevice()
            except Exception:
                pass
            try:
                self.cam.MV_CC_DestroyHandle()
            except Exception:
                pass
        self.cam = None
        self.opened = False

    def set_camera_params(self, auto_exposure=False, exposure_us=5000.0,
                          auto_gain=False, gain_db=0.0):
        if not self.opened:
            raise RuntimeError("相机未打开")

        # 关闭触发，直接抓一帧。这样最稳，适合“到位后拍一张”。
        ret = self.cam.MV_CC_SetEnumValue("TriggerMode", 0)  # Off
        self._check_ret(ret, "设置 TriggerMode=Off")

        # 曝光
        if auto_exposure:
            ret = self.cam.MV_CC_SetEnumValue("ExposureAuto", 2)  # Continuous
            self._check_ret(ret, "设置自动曝光")
        else:
            ret = self.cam.MV_CC_SetEnumValue("ExposureAuto", 0)  # Off
            self._check_ret(ret, "关闭自动曝光")
            ret = self.cam.MV_CC_SetFloatValue("ExposureTime", float(exposure_us))
            self._check_ret(ret, "设置曝光时间")

        # 增益
        if auto_gain:
            ret = self.cam.MV_CC_SetEnumValue("GainAuto", 2)  # Continuous
            self._check_ret(ret, "设置自动增益")
        else:
            ret = self.cam.MV_CC_SetEnumValue("GainAuto", 0)  # Off
            self._check_ret(ret, "关闭自动增益")
            ret = self.cam.MV_CC_SetFloatValue("Gain", float(gain_db))
            self._check_ret(ret, "设置增益")

    def capture_one_frame(self, save_path: str, timeout_ms: int = 3000):
        if not self.opened:
            raise RuntimeError("相机未打开")

        ret = self.cam.MV_CC_StartGrabbing()
        self._check_ret(ret, "开始取流")

        st_out_frame = MV_FRAME_OUT()
        memset(byref(st_out_frame), 0, sizeof(st_out_frame))

        try:
            ret = self.cam.MV_CC_GetImageBuffer(st_out_frame, timeout_ms)
            self._check_ret(ret, "获取图像")

            width = st_out_frame.stFrameInfo.nWidth
            height = st_out_frame.stFrameInfo.nHeight
            frame_len = st_out_frame.stFrameInfo.nFrameLen

            buf_ptr = cast(st_out_frame.pBufAddr, POINTER(c_ubyte * frame_len))
            raw = np.frombuffer(buf_ptr.contents, dtype=np.uint8)

            # 常见情况 1：单色 Mono8
            if frame_len == width * height:
                img = raw.reshape((height, width)).copy()

            # 常见情况 2：RGB/BGR 8bit 三通道
            elif frame_len == width * height * 3:
                img = raw.reshape((height, width, 3)).copy()

            else:
                raise RuntimeError(
                    f"当前像素格式暂未自动适配: width={width}, height={height}, frame_len={frame_len}"
                )

            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            ok = cv2.imwrite(save_path, img)
            if not ok:
                raise RuntimeError(f"保存图像失败: {save_path}")
            return img, width, height

        finally:
            try:
                self.cam.MV_CC_FreeImageBuffer(st_out_frame)
            except Exception:
                pass
            try:
                self.cam.MV_CC_StopGrabbing()
            except Exception:
                pass


def build_save_path(save_dir: str, prefix: str = "pose_capture") -> str:
    os.makedirs(save_dir, exist_ok=True)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(save_dir, f"{prefix}_{now}.png")


def run_one_pose_one_capture():
    robot = EliteEC66Client(ROBOT_IP, ROBOT_PORT, timeout=10.0)
    camera = HikCamera()

    try:
        print("[1/5] 连接机械臂...")
        robot.connect()
        robot.enable_servo()
        print("机械臂已连接")

        print("[2/5] 连接相机...")
        camera.open_first_camera()
        camera.set_camera_params(
            auto_exposure=USE_AUTO_EXPOSURE,
            exposure_us=EXPOSURE_US,
            auto_gain=USE_AUTO_GAIN,
            gain_db=GAIN_DB,
        )
        print("相机已连接")

        print(f"[3/5] 机械臂运动到目标位姿: {TARGET_POSE}")
        move_res = robot.move_by_joint(TARGET_POSE, speed=MOVE_SPEED, acc=MOVE_ACC, dec=MOVE_DEC)
        if not move_res:
            raise RuntimeError("机械臂未返回有效响应")
        result_val = move_res.get("result")
        if not (result_val is True or str(result_val).lower() == "true"):
            raise RuntimeError(f"机械臂拒绝执行运动命令: {move_res}")

        robot.wait_until_idle(timeout=120.0)
        print("机械臂已到位")

        # 可选：到位后给一点稳定时间，减少抖动
        time.sleep(0.3)

        print("[4/5] 拍照并保存...")
        save_path = build_save_path(SAVE_DIR, IMAGE_PREFIX)
        _, w, h = camera.capture_one_frame(save_path)
        print(f"图像已保存: {save_path} ({w}x{h})")

        print("[5/5] 完成")
        return save_path

    finally:
        try:
            camera.close()
        finally:
            robot.disconnect()


if __name__ == "__main__":
    try:
        saved = run_one_pose_one_capture()
        print(f"\n最终输出文件: {saved}")
    except Exception as e:
        print(f"\n执行失败: {e}")
        raise
