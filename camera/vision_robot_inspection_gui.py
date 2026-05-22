import os
import sys
import time
import threading
import json
import socket
import subprocess
import csv
import shutil
from pathlib import Path
from ctypes import *

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# =========================
# 海康 SDK 导入设置 (保持原样)
# =========================
SDK_PYTHON_IMPORT_DIR = None  
THIS_DIR = Path(__file__).resolve().parent
LOCAL_MVIMPORT = THIS_DIR / "MvImport"

if SDK_PYTHON_IMPORT_DIR and Path(SDK_PYTHON_IMPORT_DIR).exists():
    sys.path.append(SDK_PYTHON_IMPORT_DIR)
elif LOCAL_MVIMPORT.exists():
    sys.path.append(str(LOCAL_MVIMPORT))

try:
    from MvCameraControl_class import *
except ModuleNotFoundError as e:
    print("⚠️ 找不到 MvCameraControl_class，部分相机功能可能受限。请确保 MvImport 存在。")

try:
    from PIL import Image, ImageTk
except ModuleNotFoundError as e:
    raise ModuleNotFoundError("缺少 Pillow。请先运行: pip install pillow") from e

# =========================
# 机械臂常量
# =========================
DATA_FILE = "saved_poses.json"
SEQ_FILE = "saved_sequences.json"


# ==========================================
# [组件 1]: 海康相机底层逻辑控制类 (原样保留)
# ==========================================
class CameraError(RuntimeError):
    pass

class HikCamera:
    def __init__(self):
        self.cam = None
        self.device_info = None
        self.is_open = False
        self.is_grabbing = False
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.latest_frame_gray = None
        self.latest_frame_ts = 0.0
        self.grab_thread = None
        self.stop_event = threading.Event()
        self.last_pixel_type = None

    @staticmethod
    def _check_ret(ret, msg):
        if ret != 0:
            raise CameraError(f"{msg} 失败, ret=0x{ret:x}")

    def enum_devices(self):
        device_list = MV_CC_DEVICE_INFO_LIST()
        tlayer_type = MV_GIGE_DEVICE | MV_USB_DEVICE
        ret = MvCamera.MV_CC_EnumDevices(tlayer_type, device_list)
        self._check_ret(ret, "枚举设备")

        results = []
        for i in range(device_list.nDeviceNum):
            dev = cast(device_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            desc = self._device_desc(dev, i)
            results.append((desc, dev))
        return results

    @staticmethod
    def _decode_char_array(arr):
        raw = bytes(arr)
        return raw.split(b"\x00", 1)[0].decode(errors="ignore")

    def _device_desc(self, dev, idx):
        layer = dev.nTLayerType
        if layer == MV_GIGE_DEVICE:
            model = self._decode_char_array(dev.SpecialInfo.stGigEInfo.chModelName)
            ip = dev.SpecialInfo.stGigEInfo.nCurrentIp
            ip_str = f"{(ip >> 24) & 0xff}.{(ip >> 16) & 0xff}.{(ip >> 8) & 0xff}.{ip & 0xff}"
            return f"[{idx}] GigE | {model} | {ip_str}"
        elif layer == MV_USB_DEVICE:
            model = self._decode_char_array(dev.SpecialInfo.stUsb3VInfo.chModelName)
            serial = self._decode_char_array(dev.SpecialInfo.stUsb3VInfo.chSerialNumber)
            return f"[{idx}] USB | {model} | SN:{serial}"
        return f"[{idx}] 未知设备"

    def open(self, device_info):
        self.close()
        self.cam = MvCamera()
        self.device_info = device_info
        ret = self.cam.MV_CC_CreateHandle(device_info)
        self._check_ret(ret, "创建句柄")

        try:
            ret = self.cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
            self._check_ret(ret, "打开设备")

            if device_info.nTLayerType == MV_GIGE_DEVICE:
                packet_size = self.cam.MV_CC_GetOptimalPacketSize()
                if int(packet_size) > 0:
                    self.cam.MV_CC_SetIntValue("GevSCPSPacketSize", packet_size)

            self.is_open = True
        except Exception:
            try: self.cam.MV_CC_DestroyHandle()
            except Exception: pass
            self.cam = None
            self.device_info = None
            self.is_open = False
            raise

    def close(self):
        self.stop_grabbing()
        if self.cam is not None:
            try: self.cam.MV_CC_CloseDevice()
            except Exception: pass
            try: self.cam.MV_CC_DestroyHandle()
            except Exception: pass
        self.cam = None
        self.device_info = None
        self.is_open = False
        with self.frame_lock:
            self.latest_frame = None
            self.latest_frame_gray = None
            self.latest_frame_ts = 0.0

    def set_enum(self, name, value):
        self._check_ret(self.cam.MV_CC_SetEnumValue(name, value), f"设置{name}")

    def set_float(self, name, value):
        self._check_ret(self.cam.MV_CC_SetFloatValue(name, float(value)), f"设置{name}")

    def set_int(self, name, value):
        self._check_ret(self.cam.MV_CC_SetIntValue(name, int(value)), f"设置{name}")

    def get_float(self, name):
        val = c_float()
        self._check_ret(self.cam.MV_CC_GetFloatValue(name, val), f"读取{name}")
        return float(val.value)

    def get_int(self, name):
        val = c_uint64()
        self._check_ret(self.cam.MV_CC_GetIntValue(name, val), f"读取{name}")
        return int(val.value)

    def apply_preview_defaults(self):
        self.set_enum("TriggerMode", MV_TRIGGER_MODE_OFF)
        try: self.set_enum("AcquisitionMode", 2)
        except Exception: pass

    def software_trigger_mode(self):
        self.set_enum("TriggerMode", MV_TRIGGER_MODE_ON)
        try: self.set_enum("TriggerSource", MV_TRIGGER_SOURCE_SOFTWARE)
        except Exception: pass

    def send_software_trigger(self):
        self._check_ret(self.cam.MV_CC_SetCommandValue("TriggerSoftware"), "软件触发")

    def start_grabbing(self):
        if self.is_grabbing: return
        self.stop_event.clear()
        self._check_ret(self.cam.MV_CC_StartGrabbing(), "开始取流")
        self.is_grabbing = True
        self.grab_thread = threading.Thread(target=self._grab_loop, daemon=True)
        self.grab_thread.start()

    def stop_grabbing(self):
        if not self.is_grabbing: return
        self.stop_event.set()
        if self.grab_thread is not None:
            self.grab_thread.join(timeout=1.5)
            self.grab_thread = None
        try: self.cam.MV_CC_StopGrabbing()
        except Exception: pass
        self.is_grabbing = False

    def _grab_loop(self):
        while not self.stop_event.is_set():
            st_out_frame = MV_FRAME_OUT()
            memset(byref(st_out_frame), 0, sizeof(st_out_frame))

            ret = self.cam.MV_CC_GetImageBuffer(st_out_frame, 1000)
            if ret != 0: continue

            try:
                width = st_out_frame.stFrameInfo.nWidth
                height = st_out_frame.stFrameInfo.nHeight
                frame_len = st_out_frame.stFrameInfo.nFrameLen
                self.last_pixel_type = int(st_out_frame.stFrameInfo.enPixelType)

                buf_ptr = cast(st_out_frame.pBufAddr, POINTER(c_ubyte * frame_len))
                raw = np.frombuffer(buf_ptr.contents, dtype=np.uint8).copy()

                frame_rgb = None
                frame_gray = None

                if frame_len == width * height:
                    frame_gray = raw.reshape((height, width))
                    frame_rgb = cv2.cvtColor(frame_gray, cv2.COLOR_GRAY2RGB)
                elif frame_len == width * height * 3:
                    frame_rgb = raw.reshape((height, width, 3))
                    frame_gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
                else:
                    size = width * height
                    if raw.size >= size:
                        frame_gray = raw[:size].reshape((height, width))
                        frame_rgb = cv2.cvtColor(frame_gray, cv2.COLOR_GRAY2RGB)
                    else: continue

                with self.frame_lock:
                    self.latest_frame = frame_rgb
                    self.latest_frame_gray = frame_gray
                    self.latest_frame_ts = time.time()
            finally:
                try: self.cam.MV_CC_FreeImageBuffer(st_out_frame)
                except Exception: pass

    def capture_once(self, timeout=3.0):
        """
        单次软件触发采图：用于“机械臂到位 -> 相机拍照 -> 算法检测”的自动流程。
        返回: frame_rgb, frame_gray, timestamp

        注意：
        1. 海康相机必须已经 open。
        2. 这里会切到软件触发模式。
        3. 如果你的相机/SDK不允许在取流中切换 TriggerMode，本函数会自动尝试停止取流后再切换。
        """
        if not self.is_open:
            raise CameraError("相机未打开，无法采图")

        # 切换到软件触发模式；部分设备需要停流后才能改触发模式
        try:
            self.software_trigger_mode()
        except Exception:
            was_grabbing = self.is_grabbing
            if was_grabbing:
                self.stop_grabbing()
            self.software_trigger_mode()
            if was_grabbing:
                self.start_grabbing()

        if not self.is_grabbing:
            self.start_grabbing()
            time.sleep(0.1)

        with self.frame_lock:
            old_ts = self.latest_frame_ts

        self.send_software_trigger()

        deadline = time.time() + float(timeout)
        while time.time() < deadline:
            frame_rgb, frame_gray, ts = self.get_latest_frame()
            if frame_rgb is not None and ts > old_ts:
                return frame_rgb, frame_gray, ts
            time.sleep(0.02)

        raise CameraError(f"软件触发采图超时：{timeout}s 内没有收到新图像")

    def get_latest_frame(self):
        with self.frame_lock:
            if self.latest_frame is None: return None, None, 0.0
            return self.latest_frame.copy(), self.latest_frame_gray.copy(), self.latest_frame_ts


# ==========================================
# [组件 2]: 相机 UI 面板控制逻辑
# ==========================================
class CameraUIController:
    def __init__(self, root, control_parent, preview_parent):
        self.root = root
        self.control_parent = control_parent
        self.preview_parent = preview_parent
        
        self.camera = HikCamera()
        self.photo = None
        self.preview_after_id = None
        self.last_frame_time = 0.0
        self.display_fps = 0.0
        self.last_save_path = str((THIS_DIR / "captures").resolve())
        Path(self.last_save_path).mkdir(parents=True, exist_ok=True)

        self._build_ui()
        self.refresh_device_list()
        self._schedule_preview()

    def _build_ui(self):
        # 1. 将原先的 left (控制区) 放入 control_parent
        left = ttk.Frame(self.control_parent)
        left.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 2. 将原先的 right (预览区) 放入 preview_parent
        right = ttk.Frame(self.preview_parent)
        right.pack(fill=tk.BOTH, expand=True)

        # ============ 控制区 (左侧/第一页) ============
        dev_group = ttk.LabelFrame(left, text="设备")
        dev_group.pack(fill=tk.X, pady=(0, 8))

        self.device_combo = ttk.Combobox(dev_group, state="readonly", width=42)
        self.device_combo.pack(fill=tk.X, padx=8, pady=8)

        row = ttk.Frame(dev_group)
        row.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(row, text="刷新设备", command=self.refresh_device_list).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        ttk.Button(row, text="打开相机", command=self.open_camera).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))

        row2 = ttk.Frame(dev_group)
        row2.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(row2, text="开始预览", command=self.start_preview).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        ttk.Button(row2, text="停止预览", command=self.stop_preview).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))

        ttk.Button(dev_group, text="关闭相机", command=self.close_camera).pack(fill=tk.X, padx=8, pady=(0, 8))

        param_group = ttk.LabelFrame(left, text="关键参数")
        param_group.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(param_group, text="曝光自动").pack(anchor=tk.W, padx=8, pady=(8, 0))
        self.exposure_auto = ttk.Combobox(param_group, state="readonly", values=["Off", "Continuous"], width=18)
        self.exposure_auto.set("Off")
        self.exposure_auto.pack(fill=tk.X, padx=8, pady=(2, 6))
        self.exposure_auto.bind("<<ComboboxSelected>>", lambda e: self.apply_exposure_auto())

        ttk.Label(param_group, text="曝光时间 (us)").pack(anchor=tk.W, padx=8)
        self.exposure_var = tk.DoubleVar(value=5000)
        self.exposure_scale = ttk.Scale(param_group, from_=50, to=50000, variable=self.exposure_var, command=self._on_exposure_slide)
        self.exposure_scale.pack(fill=tk.X, padx=8, pady=(2, 0))
        exp_row = ttk.Frame(param_group)
        exp_row.pack(fill=tk.X, padx=8, pady=(4, 6))
        self.exposure_entry = ttk.Entry(exp_row, width=12)
        self.exposure_entry.insert(0, "5000")
        self.exposure_entry.pack(side=tk.LEFT)
        ttk.Button(exp_row, text="应用", command=self.apply_exposure_time).pack(side=tk.LEFT, padx=6)

        ttk.Label(param_group, text="增益自动").pack(anchor=tk.W, padx=8)
        self.gain_auto = ttk.Combobox(param_group, state="readonly", values=["Off", "Continuous"], width=18)
        self.gain_auto.set("Off")
        self.gain_auto.pack(fill=tk.X, padx=8, pady=(2, 6))
        self.gain_auto.bind("<<ComboboxSelected>>", lambda e: self.apply_gain_auto())

        ttk.Label(param_group, text="增益 (dB)").pack(anchor=tk.W, padx=8)
        self.gain_var = tk.DoubleVar(value=0.0)
        self.gain_scale = ttk.Scale(param_group, from_=0, to=24, variable=self.gain_var, command=self._on_gain_slide)
        self.gain_scale.pack(fill=tk.X, padx=8, pady=(2, 0))
        gain_row = ttk.Frame(param_group)
        gain_row.pack(fill=tk.X, padx=8, pady=(4, 8))
        self.gain_entry = ttk.Entry(gain_row, width=12)
        self.gain_entry.insert(0, "0.0")
        self.gain_entry.pack(side=tk.LEFT)
        ttk.Button(gain_row, text="应用", command=self.apply_gain).pack(side=tk.LEFT, padx=6)

        trig_group = ttk.LabelFrame(left, text="触发")
        trig_group.pack(fill=tk.X, pady=(0, 8))
        self.trigger_mode = ttk.Combobox(trig_group, state="readonly", values=["预览模式(Trigger Off)", "软件触发模式"], width=22)
        self.trigger_mode.set("预览模式(Trigger Off)")
        self.trigger_mode.pack(fill=tk.X, padx=8, pady=(8, 6))
        ttk.Button(trig_group, text="应用触发模式", command=self.apply_trigger_mode).pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Button(trig_group, text="软件触发一次", command=self.software_trigger_once).pack(fill=tk.X, padx=8, pady=(0, 8))

        save_group = ttk.LabelFrame(left, text="保存图像")
        save_group.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(save_group, text="保存当前图像", command=self.save_current_frame).pack(fill=tk.X, padx=8, pady=(8, 6))
        ttk.Button(save_group, text="选择保存目录", command=self.choose_save_dir).pack(fill=tk.X, padx=8, pady=(0, 8))

        self.save_dir_label = ttk.Label(save_group, text=self.last_save_path, wraplength=310)
        self.save_dir_label.pack(anchor=tk.W, padx=8, pady=(0, 8))

        status_group = ttk.LabelFrame(left, text="状态")
        status_group.pack(fill=tk.X)
        self.status_text = tk.StringVar(value="未连接")
        self.frame_info_text = tk.StringVar(value="分辨率: - | 显示FPS: -")
        ttk.Label(status_group, textvariable=self.status_text, foreground="#0a5").pack(anchor=tk.W, padx=8, pady=(8, 4))
        ttk.Label(status_group, textvariable=self.frame_info_text, wraplength=320).pack(anchor=tk.W, padx=8, pady=(0, 8))

        # ============ 预览区 (始终在右侧) ============
        preview_group = ttk.LabelFrame(right, text="📷 实时视觉反馈")
        preview_group.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.preview_label = ttk.Label(preview_group)
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    # ... 以下均为原有交互逻辑，保持不变 ...
    def set_status(self, msg): self.status_text.set(msg)
    
    def refresh_device_list(self):
        try:
            self.devices = self.camera.enum_devices()
            names = [d[0] for d in self.devices]
            self.device_combo["values"] = names
            if names:
                self.device_combo.current(0)
                self.set_status(f"找到 {len(names)} 台设备")
            else:
                self.device_combo.set("")
                self.set_status("未找到设备")
        except Exception as e:
            messagebox.showerror("错误", str(e))
            self.set_status("刷新设备失败")

    def open_camera(self):
        try:
            idx = self.device_combo.current()
            if idx < 0 or not getattr(self, "devices", None): raise CameraError("请先选择设备")
            self.camera.open(self.devices[idx][1])
            self.camera.apply_preview_defaults()
            self.set_status("相机已打开")
        except Exception as e: messagebox.showerror("打开相机失败", str(e))

    def close_camera(self):
        try:
            self.camera.close()
            self.preview_label.configure(image="")
            self.photo = None
            self.frame_info_text.set("分辨率: - | 显示FPS: -")
            self.set_status("相机已关闭")
        except Exception as e: messagebox.showerror("关闭相机失败", str(e))

    def start_preview(self):
        try:
            if not self.camera.is_open: raise CameraError("请先打开相机")
            self.camera.apply_preview_defaults()
            self.camera.start_grabbing()
            self.set_status("预览中")
        except Exception as e: messagebox.showerror("开始预览失败", str(e))

    def stop_preview(self):
        try:
            self.camera.stop_grabbing()
            self.set_status("预览已停止")
        except Exception as e: messagebox.showerror("停止预览失败", str(e))

    def apply_exposure_auto(self):
        try:
            if not self.camera.is_open: return
            mode = self.exposure_auto.get()
            self.camera.set_enum("ExposureAuto", 0 if mode == "Off" else 2)
            self.set_status(f"曝光自动: {mode}")
        except Exception as e: messagebox.showerror("错误", str(e))

    def apply_exposure_time(self):
        try:
            if not self.camera.is_open: return
            val = float(self.exposure_entry.get())
            self.exposure_var.set(val)
            self.camera.set_float("ExposureTime", val)
            self.set_status(f"曝光时间已设为 {val:.0f} us")
        except Exception as e: messagebox.showerror("错误", str(e))

    def _on_exposure_slide(self, _):
        self.exposure_entry.delete(0, tk.END)
        self.exposure_entry.insert(0, f"{self.exposure_var.get():.0f}")

    def apply_gain_auto(self):
        try:
            if not self.camera.is_open: return
            mode = self.gain_auto.get()
            self.camera.set_enum("GainAuto", 0 if mode == "Off" else 2)
            self.set_status(f"增益自动: {mode}")
        except Exception as e: messagebox.showerror("错误", str(e))

    def apply_gain(self):
        try:
            if not self.camera.is_open: return
            val = float(self.gain_entry.get())
            self.gain_var.set(val)
            self.camera.set_float("Gain", val)
            self.set_status(f"增益已设为 {val:.1f} dB")
        except Exception as e: messagebox.showerror("错误", str(e))

    def _on_gain_slide(self, _):
        self.gain_entry.delete(0, tk.END)
        self.gain_entry.insert(0, f"{self.gain_var.get():.1f}")

    def apply_trigger_mode(self):
        try:
            if not self.camera.is_open: return
            if self.trigger_mode.get() == "预览模式(Trigger Off)":
                self.camera.apply_preview_defaults()
                self.set_status("已切换到预览模式")
            else:
                self.camera.software_trigger_mode()
                self.set_status("已切换到软件触发模式")
        except Exception as e: messagebox.showerror("错误", str(e))

    def software_trigger_once(self):
        try:
            if not self.camera.is_open: raise CameraError("请先打开相机")
            if not self.camera.is_grabbing: self.camera.start_grabbing()
            self.camera.software_trigger_mode()
            self.camera.send_software_trigger()
            self.set_status("已软件触发一次")
        except Exception as e: messagebox.showerror("错误", str(e))

    def choose_save_dir(self):
        path = filedialog.askdirectory(initialdir=self.last_save_path)
        if path:
            self.last_save_path = path
            self.save_dir_label.config(text=path)

    def save_current_frame(self):
        frame_rgb, frame_gray, ts = self.camera.get_latest_frame()
        if frame_gray is None and frame_rgb is None:
            messagebox.showwarning("提示", "当前没有可保存的图像")
            return
        Path(self.last_save_path).mkdir(parents=True, exist_ok=True)
        now = time.strftime("%Y%m%d_%H%M%S")
        ms = int((time.time() % 1) * 1000)
        path = Path(self.last_save_path) / f"capture_{now}_{ms:03d}.png"
        
        ok = cv2.imwrite(str(path), frame_gray) if frame_gray is not None else cv2.imwrite(str(path), cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
        if ok:
            self.set_status(f"已保存: {path.name}")
            messagebox.showinfo("保存成功", f"图像已保存到:\n{path}")
        else: messagebox.showerror("保存失败", "OpenCV 写文件失败")

    def _schedule_preview(self):
        self.preview_after_id = self.root.after(30, self._update_preview)

    def _update_preview(self):
        try:
            frame_rgb, frame_gray, ts = self.camera.get_latest_frame()
            if frame_rgb is not None:
                h, w = frame_rgb.shape[:2]
                label_w = max(self.preview_label.winfo_width(), 400)
                label_h = max(self.preview_label.winfo_height(), 300)
                scale = min(label_w / w, label_h / h)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                disp = cv2.resize(frame_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

                if ts != self.last_frame_time and self.last_frame_time > 0:
                    dt = ts - self.last_frame_time
                    if dt > 0: self.display_fps = 1.0 / dt
                self.last_frame_time = ts

                img = Image.fromarray(disp)
                self.photo = ImageTk.PhotoImage(img)
                self.preview_label.configure(image=self.photo)
                self.frame_info_text.set(f"分辨率: {w} x {h} | 显示FPS: {self.display_fps:.1f}")
        finally:
            self._schedule_preview()

    def save_image_windows_safe(self, path, image):
        """Save a PNG robustly on Windows paths and verify the output file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        shape = getattr(image, "shape", None)
        dtype = getattr(image, "dtype", None)
        try:
            ok, encoded = cv2.imencode(".png", image)
            if not ok:
                raise CameraError(f"PNG编码失败: path={path}, shape={shape}, dtype={dtype}")
            encoded.tofile(str(path))
        except Exception as exc:
            raise CameraError(f"保存检测图片失败: path={path}, shape={shape}, dtype={dtype}, error={exc}") from exc

        if not path.exists() or path.stat().st_size <= 0:
            raise CameraError(f"保存检测图片失败: 文件为空或不存在, path={path}, shape={shape}, dtype={dtype}")

    def capture_for_inspection(self, pose_name="pose", product_id="", save_dir=None, timeout=3.0):
        """
        自动检测流程专用采图函数。
        调用链建议：机械臂到位 -> capture_for_inspection() -> detector.detect()

        返回:
            image_path: 保存后的图片路径
            frame_rgb:  RGB图像，给界面显示/深度学习可用
            frame_gray: 灰度图，给传统视觉/缺陷检测可用
            ts:         图像时间戳
        """
        if not self.camera.is_open:
            raise CameraError("请先打开相机")

        base_dir = Path(save_dir or self.last_save_path)
        base_dir.mkdir(parents=True, exist_ok=True)

        frame_rgb, frame_gray, ts = self.camera.capture_once(timeout=timeout)

        def safe_name(s):
            s = str(s).strip() or "unknown"
            return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in s)

        now = time.strftime("%Y%m%d_%H%M%S", time.localtime(ts))
        ms = int((ts % 1) * 1000)
        pid = safe_name(product_id) if product_id else "part"
        pname = safe_name(pose_name)
        image_path = base_dir / f"{pid}_{pname}_{now}_{ms:03d}.png"

        # 缺陷检测通常保存灰度图更稳定；如果是彩色相机也可改成保存 BGR 彩图
        if frame_gray is not None:
            image_to_save = frame_gray
        else:
            image_to_save = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        self.save_image_windows_safe(image_path, image_to_save)

        self.root.after(0, lambda: self.set_status(f"检测采图完成: {image_path.name}"))
        return str(image_path), frame_rgb, frame_gray, ts

    def on_close(self):
        if self.preview_after_id is not None:
            self.root.after_cancel(self.preview_after_id)
        try: self.camera.close()
        except: pass


# ==========================================
# [组件 3]: 机械臂 UI 面板控制逻辑
# ==========================================
class RobotUIController:
    def __init__(self, root, parent_frame):
        self.root = root # 用于 .after() 
        self.parent = parent_frame # 用于将UI绘制到选项卡内
        
        self.connected = False
        self.sock = None
        self.sock_lock = threading.Lock() 
        self.current_pose = [0.0] * 6
        self.is_running_sequence = False
        self.stop_requested = False
        self.is_moving = False 
        
        self.saved_poses = {}
        self.saved_sequences = {}
        self.sequence_list = [] 
        
        self.load_poses_from_file()
        self.load_sequences_from_file()
        
        self.current_labels = []
        self.target_entries = []
        
        self.setup_ui()
        self.refresh_listbox()
        self.refresh_seq_combo()
        
        self.update_ui_loop()

    def setup_ui(self):
        # 替换所有的 self.root 为 self.parent，将其装入 Notebook Tab 中
        top_frame = tk.Frame(self.parent, padx=10, pady=5); top_frame.pack(fill=tk.X)
        tk.Label(top_frame, text="IP地址:").pack(side=tk.LEFT)
        self.ip_entry = tk.Entry(top_frame, width=15); self.ip_entry.insert(0, "192.168.1.200"); self.ip_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(top_frame, text="端口:").pack(side=tk.LEFT)
        self.port_entry = tk.Entry(top_frame, width=6); self.port_entry.insert(0, "8055"); self.port_entry.pack(side=tk.LEFT, padx=5)
        self.btn_connect = tk.Button(top_frame, text="🔌 连接机械臂", bg="lightblue", command=self.toggle_connection); self.btn_connect.pack(side=tk.LEFT, padx=10)
        self.status_label = tk.Label(top_frame, text="🔴 未连接", fg="red", font=("Arial", 10, "bold")); self.status_label.pack(side=tk.RIGHT, padx=10)

        main_frame = tk.Frame(self.parent); main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 为了在分屏下显示更佳，将原有的三个左右排列改为纵向滚动或自适应网格，这里保持左右但允许自适应
        left_frame = tk.LabelFrame(main_frame, text="1. 单点调试", padx=10, pady=10); left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        tk.Label(left_frame, text="轴号", font=("Arial", 9, "bold")).grid(row=0, column=0, pady=5)
        tk.Label(left_frame, text="当前位姿(度)").grid(row=0, column=1, padx=5)
        tk.Label(left_frame, text="目标位姿(度)").grid(row=0, column=2, padx=5)
        for i in range(6):
            tk.Label(left_frame, text=f"J{i+1}:").grid(row=i+1, column=0, pady=5)
            lbl = tk.Label(left_frame, text="0.00", width=8, bg="#eeeeee", relief="sunken"); lbl.grid(row=i+1, column=1, padx=5); self.current_labels.append(lbl)
            ent = tk.Entry(left_frame, width=10, justify="center"); ent.grid(row=i+1, column=2, padx=5); self.target_entries.append(ent)
        tk.Button(left_frame, text="⬇️ 提取当前位姿", command=self.copy_current_to_target).grid(row=7, column=0, columnspan=3, pady=10)
        self.btn_submit = tk.Button(left_frame, text="🚀 单点执行", bg="lightgreen", command=self.start_single_movement, state=tk.DISABLED)
        self.btn_submit.grid(row=8, column=0, columnspan=3, pady=5, sticky="we")

        mid_frame = tk.LabelFrame(main_frame, text="2. 示教点位库", padx=10, pady=10); mid_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        tk.Button(mid_frame, text="💾 保存当前位姿至库", bg="#e0e0ff", command=self.save_current_pose).pack(fill=tk.X, pady=5)
        list_frame = tk.Frame(mid_frame); list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        scroll_mid = tk.Scrollbar(list_frame); scroll_mid.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox = tk.Listbox(list_frame, yscrollcommand=scroll_mid.set, font=("Arial", 10)); self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_mid.config(command=self.listbox.yview)
        tk.Button(mid_frame, text="❌ 删除选定点位", command=self.delete_selected, fg="red").pack(fill=tk.X, pady=2)

        right_frame = tk.LabelFrame(main_frame, text="3. 轨迹编程与执行", padx=10, pady=10); right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        param_frame = tk.Frame(right_frame); param_frame.pack(fill=tk.X, pady=5)
        tk.Label(param_frame, text="速度:").grid(row=0, column=0, sticky="e"); self.speed_entry = tk.Entry(param_frame, width=5); self.speed_entry.insert(0, "20"); self.speed_entry.grid(row=0, column=1, padx=2)
        tk.Label(param_frame, text="停顿(s):").grid(row=0, column=2, sticky="e"); self.delay_entry = tk.Entry(param_frame, width=5); self.delay_entry.insert(0, "1.0"); self.delay_entry.grid(row=0, column=3, padx=2)
        tk.Button(param_frame, text="➕ 添加入当前序列", bg="lightyellow", command=self.add_to_sequence).grid(row=0, column=4, padx=5)
        tree_frame = tk.Frame(right_frame); tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        scroll_right = tk.Scrollbar(tree_frame); scroll_right.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = ttk.Treeview(tree_frame, columns=("name", "speed", "delay"), show="headings", yscrollcommand=scroll_right.set)
        self.tree.heading("name", text="目标点位"); self.tree.heading("speed", text="速度%"); self.tree.heading("delay", text="停顿(s)")
        self.tree.column("name", width=80); self.tree.column("speed", width=50, anchor="center"); self.tree.column("delay", width=50, anchor="center")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); scroll_right.config(command=self.tree.yview)
        seq_op_frame = tk.Frame(right_frame); seq_op_frame.pack(fill=tk.X, pady=2)
        tk.Button(seq_op_frame, text="清空面板", command=self.clear_sequence).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(seq_op_frame, text="移除选中", command=self.remove_from_sequence).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        seq_file_frame = tk.LabelFrame(right_frame, text="序列方案管理"); seq_file_frame.pack(fill=tk.X, pady=5)
        tk.Label(seq_file_frame, text="已有方案:").grid(row=0, column=0, padx=2, pady=5); self.combo_seq = ttk.Combobox(seq_file_frame, state="readonly", width=12); self.combo_seq.grid(row=0, column=1, padx=2, pady=5)
        tk.Button(seq_file_frame, text="📂 读取", command=self.load_sequence).grid(row=0, column=2, padx=2)
        tk.Button(seq_file_frame, text="💾 保存", command=self.save_sequence, bg="lightblue").grid(row=0, column=3, padx=2)
        tk.Button(seq_file_frame, text="❌", fg="red", command=self.delete_sequence).grid(row=0, column=4, padx=2)

        exec_frame = tk.Frame(right_frame); exec_frame.pack(fill=tk.X, pady=5)
        self.btn_run_seq = tk.Button(exec_frame, text="▶️ 开始执行当前序列", bg="#aaffaa", font=("Arial", 10, "bold"), command=self.start_sequence_thread, state=tk.DISABLED, height=2); self.btn_run_seq.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.btn_stop_seq = tk.Button(exec_frame, text="⏹️ 中断停止", bg="#ffaaaa", font=("Arial", 10, "bold"), command=self.request_stop, state=tk.DISABLED, height=2); self.btn_stop_seq.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

    # =============== 机械臂通信控制 ===============
    def send_cmd(self, method, params=None):
        if not self.connected or not self.sock: return None
        if params is None: params = []
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        send_str = json.dumps(payload) + "\n"
        with self.sock_lock:
            try:
                self.sock.sendall(send_str.encode('utf-8'))
                raw_data = self.sock.recv(4096).decode('utf-8')
                lines = raw_data.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith("{") and line.endswith("}"): return json.loads(line)
                return None
            except socket.timeout:
                print(f"⚠️ [{method}] 请求超时。")
                return None
            except Exception as e:
                print(f"⚠️ [{method}] 异常: {e}")
                return None

    def toggle_connection(self):
        if not self.connected:
            ip = self.ip_entry.get().strip()
            port = int(self.port_entry.get().strip())
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(3.0)
                self.sock.connect((ip, port))
                self.connected = True
                
                self.btn_connect.config(text="🔌 断开连接", bg="lightcoral")
                self.status_label.config(text="🟢 已连接", fg="green")
                self.btn_submit.config(state=tk.NORMAL)
                self.btn_run_seq.config(state=tk.NORMAL)
                
                self.send_cmd("set_servo_status", {"status": 1})
                threading.Thread(target=self.poll_robot_status, daemon=True).start()
            except Exception as e:
                messagebox.showerror("连接失败", f"无法连接: {e}")
                if self.sock: self.sock.close()
        else:
            self.disconnect()

    def disconnect(self):
        self.connected = False
        self.stop_requested = True
        self.is_moving = False
        if self.sock:
            try: self.sock.close()
            except: pass
        self.sock = None
        self.btn_connect.config(text="🔌 连接机械臂", bg="lightblue")
        self.status_label.config(text="🔴 未连接", fg="red")
        self.btn_submit.config(state=tk.DISABLED)
        self.btn_run_seq.config(state=tk.DISABLED)
        self.btn_stop_seq.config(state=tk.DISABLED)

    def poll_robot_status(self):
        while self.connected:
            if not self.is_moving and not self.is_running_sequence:
                res_pos = self.send_cmd("getRobotPos")
                if res_pos and "result" in res_pos:
                    try:
                        data = json.loads(res_pos["result"]) if isinstance(res_pos["result"], str) else res_pos["result"]
                        if len(data) >= 6: self.current_pose = data[:6]
                    except: pass
            time.sleep(1.0) 

    def update_ui_loop(self):
        for i in range(6):
            self.current_labels[i].config(text=f"{self.current_pose[i]:.2f}")
        self.root.after(100, self.update_ui_loop)

    def start_single_movement(self):
        try:
            target = [float(ent.get().strip()) for ent in self.target_entries]
            self.btn_submit.config(state=tk.DISABLED)
            threading.Thread(target=self.execute_movement, args=(target, 20), daemon=True).start()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字！")

    def execute_movement(self, target_pose, speed):
        self.is_moving = True 
        final_target = list(target_pose)
        while len(final_target) < 8: final_target.append(0.0) 
        move_params = {"targetPos": final_target, "speed": speed, "acc": 10, "dec": 10}
        res_move = self.send_cmd("moveByJoint", move_params)
        
        if res_move:
            result_val = res_move.get("result")
            if result_val is True or str(result_val).lower() == "true":
                while self.connected and not self.stop_requested:
                    time.sleep(0.5)
                    state_res = self.send_cmd("getRobotState")
                    if state_res and str(state_res.get("result")) == "0": break
            else:
                self.root.after(0, lambda: messagebox.showerror("拒绝", f"指令被拒绝: {res_move}"))
                
        self.is_moving = False 
        if not self.is_running_sequence: 
            self.root.after(0, lambda: self.btn_submit.config(state=tk.NORMAL))

    # ---------------- 数据持久化与逻辑 ----------------
    def load_sequences_from_file(self):
        if os.path.exists(SEQ_FILE):
            try:
                with open(SEQ_FILE, 'r', encoding='utf-8') as f: self.saved_sequences = json.load(f)
            except: pass
    def save_sequences_to_file(self):
        with open(SEQ_FILE, 'w', encoding='utf-8') as f: json.dump(self.saved_sequences, f, ensure_ascii=False, indent=4)
    def refresh_seq_combo(self):
        seq_names = list(self.saved_sequences.keys()); self.combo_seq['values'] = seq_names
        if seq_names: self.combo_seq.current(0)
        else: self.combo_seq.set('')
    def save_sequence(self):
        if not self.sequence_list: return messagebox.showwarning("提示", "当前面板为空！")
        name = simpledialog.askstring("保存方案", "请输入方案名称:")
        if name:
            self.saved_sequences[name] = [step.copy() for step in self.sequence_list]
            self.save_sequences_to_file(); self.refresh_seq_combo(); self.combo_seq.set(name)
    def load_sequence(self):
        name = self.combo_seq.get()
        if not name or name not in self.saved_sequences: return
        self.clear_sequence()
        for step in self.saved_sequences[name]:
            self.sequence_list.append(step.copy()); self.tree.insert("", tk.END, values=(step["name"], step["speed"], step["delay"]))
    def delete_sequence(self):
        name = self.combo_seq.get()
        if name and name in self.saved_sequences and messagebox.askyesno("删除", f"删除 '{name}' 吗？"):
            del self.saved_sequences[name]; self.save_sequences_to_file(); self.refresh_seq_combo()
    def add_to_sequence(self):
        sel = self.listbox.curselection()
        if not sel: return messagebox.showwarning("提示", "请选中点位！")
        name = self.listbox.get(sel[0])
        try:
            sp = int(self.speed_entry.get().strip()); dl = float(self.delay_entry.get().strip())
        except: return messagebox.showerror("错误", "速度和停顿需为数字")
        self.sequence_list.append({"name": name, "speed": sp, "delay": dl})
        self.tree.insert("", tk.END, values=(name, sp, dl))
    def clear_sequence(self):
        self.sequence_list.clear()
        for item in self.tree.get_children(): self.tree.delete(item)
    def remove_from_sequence(self):
        sel = self.tree.selection()
        if sel:
            idx = self.tree.index(sel[0]); self.sequence_list.pop(idx); self.tree.delete(sel[0])
    def request_stop(self):
        self.stop_requested = True; self.btn_stop_seq.config(text="正在停止...")
    def start_sequence_thread(self):
        if not self.sequence_list: return
        self.is_running_sequence = True; self.stop_requested = False
        self.btn_run_seq.config(state=tk.DISABLED, text="🚀 序列执行中..."); self.btn_stop_seq.config(state=tk.NORMAL, text="⏹️ 中断停止")
        self.btn_submit.config(state=tk.DISABLED)
        threading.Thread(target=self.run_sequence_logic, daemon=True).start()
    def run_sequence_logic(self):
        items = self.tree.get_children()
        for i, step in enumerate(self.sequence_list):
            if self.stop_requested or not self.connected: break
            self.root.after(0, lambda idx=i: self.highlight_tree_item(items, idx))
            if step["name"] in self.saved_poses: self.execute_movement(self.saved_poses[step["name"]], step["speed"])
            delay_passed = 0.0
            while delay_passed < step["delay"]:
                if self.stop_requested or not self.connected: break
                time.sleep(0.1); delay_passed += 0.1
        self.is_running_sequence = False; self.root.after(0, self.reset_sequence_ui)
    def highlight_tree_item(self, items, idx):
        self.tree.selection_remove(self.tree.selection()); self.tree.selection_set(items[idx]); self.tree.focus(items[idx])
    def reset_sequence_ui(self):
        if self.connected:
            self.btn_run_seq.config(state=tk.NORMAL, text="▶️ 开始执行当前序列"); self.btn_submit.config(state=tk.NORMAL)
        self.btn_stop_seq.config(state=tk.DISABLED, text="⏹️ 中断停止"); self.tree.selection_remove(self.tree.selection())
    def copy_current_to_target(self):
        for i in range(6):
            self.target_entries[i].delete(0, tk.END); self.target_entries[i].insert(0, f"{self.current_pose[i]:.2f}")
    def load_poses_from_file(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f: self.saved_poses = json.load(f)
            except: pass
    def save_poses_to_file(self):
        with open(DATA_FILE, 'w', encoding='utf-8') as f: json.dump(self.saved_poses, f, ensure_ascii=False, indent=4)
    def refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for name in self.saved_poses.keys(): self.listbox.insert(tk.END, name)
    def save_current_pose(self):
        name = simpledialog.askstring("保存点位", "请输入点位名称:")
        if name:
            name = name.strip()
            if not name:
                return
            if name in self.saved_poses:
                should_overwrite = messagebox.askyesno(
                    "确认覆盖点位",
                    f"点位名称 '{name}' 已存在，是否覆盖？\n\n"
                    "覆盖后 saved_poses.json 中该点位坐标会更新。\n"
                    "所有引用该点位名称的检测序列会使用新的坐标。\n"
                    "algorithm_config.json 中同名 pose_profiles 仍然会继续匹配该点位。"
                )
                if not should_overwrite:
                    return
            self.saved_poses[name] = list(self.current_pose); self.save_poses_to_file(); self.refresh_listbox()
    def delete_selected(self):
        sel = self.listbox.curselection()
        if sel and messagebox.askyesno("删除", f"删除 '{self.listbox.get(sel[0])}' 吗？"):
            del self.saved_poses[self.listbox.get(sel[0])]; self.save_poses_to_file(); self.refresh_listbox()
    def on_closing(self):
        self.disconnect()



# ==========================================
# [组件 4]: 缺陷识别算法预留接口
# ==========================================
class DefectDetector:
    """
    这里是“算法识别”的统一接口。
    后续你可以把 YOLO、OpenCV、Halcon、Paddle、PyTorch、ONNXRuntime 等检测逻辑放进来。

    约定返回格式:
        {
            "ok": True/False,          # True=OK, False=NG
            "label": "OK" / "NG",
            "score": 0.0~1.0,
            "defect_type": "裂纹/砂眼/毛刺/漏加工/...",
            "message": "说明",
            "boxes": [
                {"x1": 0, "y1": 0, "x2": 100, "y2": 80, "score": 0.92, "class": "crack"}
            ]
        }
    """
    def __init__(self, model_path=None):
        self.model_path = model_path
        self.model = None
        self.project_root = Path(__file__).resolve().parents[1]
        self.config = self.load_algorithm_config()
        self.load_model(model_path)

    def load_model(self, model_path=None):
        """
        TODO: 在这里加载你的真实模型。

        示例：
        1. YOLO:
            from ultralytics import YOLO
            self.model = YOLO(model_path)

        2. ONNXRuntime:
            import onnxruntime as ort
            self.model = ort.InferenceSession(model_path)

        3. Halcon:
            在这里初始化 Halcon 引擎或读取模板/分类器。

        4. OpenCV传统视觉:
            读取模板、阈值参数、ROI配置等。
        """
        self.model_path = model_path
        self.model = None

    def load_algorithm_config(self):
        """Load algorithm profile config, preferring local config over example config."""
        config_paths = [
            self.project_root / "algorithm_config.json",
            self.project_root / "algorithm_config.example.json",
        ]
        for config_path in config_paths:
            if not config_path.exists():
                continue
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                config["_config_path"] = str(config_path)
                return config
            except Exception as exc:
                print(f"算法配置读取失败，将回退到dummy默认逻辑: {config_path}: {exc}")
                break
        return {
            "_config_path": "",
            "active_profile": "dummy",
            "active_workpiece_type": "demo_default",
            "profiles": {
                "dummy": {
                    "mode": "python",
                    "script": "CV_Project/scripts/infer_one_dummy.py",
                    "timeout": 5,
                }
            },
        }

    def get_dummy_profile(self):
        """Return the built-in dummy profile used as the final safe fallback."""
        return {
            "mode": "python",
            "script": "CV_Project/scripts/infer_one_dummy.py",
            "timeout": 5,
        }

    def get_active_profile(self):
        """Return the active algorithm profile, falling back to dummy when invalid."""
        profiles = self.config.get("profiles", {}) if isinstance(self.config, dict) else {}
        active_name = self.config.get("active_profile", "dummy") if isinstance(self.config, dict) else "dummy"
        profile = profiles.get(active_name)
        if isinstance(profile, dict):
            return active_name, profile
        dummy_profile = profiles.get("dummy")
        if isinstance(dummy_profile, dict):
            return "dummy", dummy_profile
        return "dummy", self.get_dummy_profile()

    def get_workpiece_display_map(self):
        """Return GUI display text mapped to workpiece type keys."""
        workpieces = self.config.get("workpiece_models", {}) if isinstance(self.config, dict) else {}
        display_map = {}
        if isinstance(workpieces, dict):
            for key, item in workpieces.items():
                if not isinstance(item, dict):
                    continue
                display = str(item.get("display_name") or key)
                display_map[f"{display} ({key})"] = key
        if not display_map:
            display_map["demo_default"] = "demo_default"
        return display_map

    def get_active_workpiece_type(self):
        """Return configured active workpiece type or demo_default."""
        if isinstance(self.config, dict):
            return str(self.config.get("active_workpiece_type") or "demo_default")
        return "demo_default"

    def merge_profile(self, profile_name, overrides=None):
        """Merge a global profile with pose-specific overrides."""
        profiles = self.config.get("profiles", {}) if isinstance(self.config, dict) else {}
        base = profiles.get(profile_name)
        if not isinstance(base, dict):
            raise ValueError(f"算法profile不存在：{profile_name}")
        merged = dict(base)
        if isinstance(overrides, dict):
            for key, value in overrides.items():
                if key != "profile":
                    merged[key] = value
        return merged

    def resolve_algorithm_profile(self, workpiece_type="", pose_name=""):
        """Resolve profile by workpiece type and pose, then fall back safely."""
        workpiece_type = str(workpiece_type or "").strip()
        pose_name = str(pose_name or "").strip()
        workpieces = self.config.get("workpiece_models", {}) if isinstance(self.config, dict) else {}

        if isinstance(workpieces, dict) and workpiece_type in workpieces:
            workpiece = workpieces[workpiece_type]
            if not isinstance(workpiece, dict):
                raise ValueError(f"工件型号配置无效：{workpiece_type}")

            pose_profiles = workpiece.get("pose_profiles", {})
            if isinstance(pose_profiles, dict) and pose_name in pose_profiles:
                pose_config = pose_profiles[pose_name]
                if not isinstance(pose_config, dict):
                    raise ValueError(f"点位算法配置无效：{workpiece_type}/{pose_name}")
                profile_name = str(pose_config.get("profile") or workpiece.get("default_profile") or "")
                if not profile_name:
                    raise ValueError(f"点位算法配置缺少profile：{workpiece_type}/{pose_name}")
                return profile_name, self.merge_profile(profile_name, pose_config), "pose"

            default_profile = workpiece.get("default_profile")
            if isinstance(default_profile, dict):
                profile_name = str(default_profile.get("profile") or "")
                if not profile_name:
                    raise ValueError(f"工件默认算法配置缺少profile：{workpiece_type}")
                return profile_name, self.merge_profile(profile_name, default_profile), "workpiece_default"
            if default_profile:
                profile_name = str(default_profile)
                return profile_name, self.merge_profile(profile_name), "workpiece_default"
            raise ValueError(f"工件型号缺少default_profile：{workpiece_type}")

        profile_name, profile = self.get_active_profile()
        return profile_name, dict(profile), "active_profile"

    def resolve_project_path(self, path_value):
        """Resolve relative config paths from project root."""
        path = Path(str(path_value)).expanduser()
        if not path.is_absolute():
            path = self.project_root / path
        return path

    def build_algorithm_command(self, profile, image_path, pose_name, product_id):
        """Build subprocess command for python or conda algorithm profiles."""
        mode = str(profile.get("mode", "python")).lower()
        script = self.resolve_project_path(profile.get("script", "CV_Project/scripts/infer_one_dummy.py"))
        if not script.exists():
            raise FileNotFoundError(f"算法脚本不存在：{script}")

        if mode == "python":
            python_exe = str(profile.get("python_exe") or sys.executable)
            cmd = [python_exe, str(script)]
        elif mode == "conda":
            conda_env = str(profile.get("conda_env") or profile.get("env") or "").strip()
            if not conda_env:
                raise ValueError("conda算法配置缺少conda_env")
            cmd = ["conda", "run", "--no-capture-output", "-n", conda_env, "python", str(script)]
        else:
            raise ValueError(f"不支持的算法调用模式：{mode}")

        cmd.extend([
            "--image", str(image_path),
            "--pose", str(pose_name or ""),
            "--product-id", str(product_id or ""),
        ])

        if profile.get("model"):
            cmd.extend(["--model", str(self.resolve_project_path(profile["model"]))])
        if profile.get("threshold") is not None:
            cmd.extend(["--threshold", str(profile["threshold"])])

        timeout = int(profile.get("timeout", 5))
        return cmd, script, timeout

    def detect(self, frame_rgb, frame_gray=None, image_path=None, pose_name="", product_id="", workpiece_type=""):
        """
        自动检测主入口。
        你后续只需要改这个函数内部的 TODO 区域即可。
        """
        started_at = time.time()
        script_path = ""
        profile_name = ""
        profile_source = ""

        def error_result(message):
            return {
                "ok": False,
                "label": "ERROR",
                "score": 0.0,
                "threshold": 0.5,
                "defect_type": "error",
                "message": message,
                "image_path": image_path or "",
                "heatmap_path": "",
                "pose": pose_name or "",
                "product_id": product_id or "",
                "workpiece_type": workpiece_type or "",
                "algorithm_script": script_path,
                "algorithm_profile": profile_name,
                "algorithm_profile_source": profile_source,
                "elapsed_ms": int((time.time() - started_at) * 1000),
                "boxes": []
            }

        if not image_path:
            return error_result("算法调用失败：image_path为空")

        try:
            profile_name, profile, profile_source = self.resolve_algorithm_profile(
                workpiece_type=workpiece_type,
                pose_name=pose_name,
            )
            cmd, infer_script, timeout = self.build_algorithm_command(
                profile=profile,
                image_path=image_path,
                pose_name=pose_name,
                product_id=product_id,
            )
            script_path = str(infer_script)
        except Exception as e:
            return error_result(f"算法配置错误：{e}")

        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        try:
            completed = subprocess.run(
                cmd,
                timeout=timeout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=child_env,
                cwd=str(self.project_root),
            )
        except subprocess.TimeoutExpired:
            return error_result(f"算法调用超时：超过{timeout}秒")
        except Exception as e:
            return error_result(f"算法调用异常：{e}")

        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()[:300]
            return error_result(f"算法脚本执行失败：{stderr or completed.returncode}")

        try:
            result = json.loads((completed.stdout or "").strip())
        except Exception as e:
            stdout = (completed.stdout or "").strip()
            return error_result(f"算法JSON解析失败：{e}; stdout={stdout[:200]}")

        result.setdefault("ok", bool(result.get("label") == "OK"))
        result.setdefault("label", "OK" if result.get("ok") else "NG")
        result.setdefault("score", 0.0)
        result.setdefault("threshold", 0.5)
        result.setdefault("defect_type", "")
        result.setdefault("message", "")
        result.setdefault("image_path", image_path or "")
        result.setdefault("heatmap_path", "")
        result.setdefault("pose", pose_name or "")
        result.setdefault("product_id", product_id or "")
        result.setdefault("workpiece_type", workpiece_type or "")
        result.setdefault("algorithm_script", script_path)
        result.setdefault("algorithm_profile", profile_name)
        result.setdefault("algorithm_profile_source", profile_source)
        result.setdefault("elapsed_ms", int((time.time() - started_at) * 1000))
        result.setdefault("boxes", [])
        return result


# ==========================================
# [组件 5]: 自动检测流程控制面板
# 逻辑：机械臂移动到点位 -> 相机软件触发拍照 -> 调用 DefectDetector.detect()
# ==========================================
class AlarmLightController:
    """Mock alarm light and buzzer controller; does not touch real hardware."""
    def __init__(self, logger=None):
        self.logger = logger
        self.state = "idle"

    def _set_state(self, state):
        self.state = state
        message = f"三色灯/蜂鸣器预留状态: {state}"
        if self.logger:
            self.logger(message)
        else:
            print(message)
        # TODO: 后续可在这里替换为机械臂 DO 输出、USB-Relay 或真实 IO 板卡控制。

    def set_idle(self):
        self._set_state("idle")

    def set_running(self):
        self._set_state("running")

    def set_pass(self):
        self._set_state("pass")

    def set_fail(self):
        self._set_state("fail")

    def set_error(self):
        self._set_state("error")


class InspectionUIController:
    def __init__(self, root, parent_frame, camera_app, robot_app):
        self.root = root
        self.parent = parent_frame
        self.camera_app = camera_app
        self.robot_app = robot_app
        self.detector = DefectDetector()
        self.workpiece_display_map = self.detector.get_workpiece_display_map()
        self.workpiece_type_var = tk.StringVar()

        self.is_running = False
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.all_detection_results = []
        self.results = self.all_detection_results
        self.run_logs = []
        self.last_report_path = ""
        self.auto_product_prefix = "PART_"
        self.result_filter_var = tk.StringVar(value="ALL")
        self.statistics_var = tk.StringVar(value="已检测: 0    OK: 0    NG: 0    ERROR: 0    良率: 0.00%")
        self.final_status_var = tk.StringVar(value="WAIT")
        self.preview_window = None
        self.preview_photo = None
        self.alarm_controller = AlarmLightController(logger=lambda msg: self.append_log(msg))

        self.save_dir = str((THIS_DIR / "inspection_captures").resolve())
        Path(self.save_dir).mkdir(parents=True, exist_ok=True)
        self.dataset_root = str((THIS_DIR.parent / "CV_Project" / "datasets_collected").resolve())
        self.collection_enabled_var = tk.BooleanVar(value=False)
        self.collection_batch_var = tk.StringVar(value=time.strftime("BATCH_%Y%m%d_%H%M%S"))
        self.collection_type_var = tk.StringVar(value="train/good")
        self.robot_simulation_enabled_var = tk.BooleanVar(value=False)

        self._build_ui()

    def get_workpiece_display_for_key(self, key):
        """Return the combobox display text for a workpiece key."""
        for display, value in self.workpiece_display_map.items():
            if value == key:
                return display
        return next(iter(self.workpiece_display_map), "demo_default")

    def get_selected_workpiece_type(self):
        """Return the selected workpiece type key from the GUI combobox."""
        display = self.workpiece_type_var.get()
        return self.workpiece_display_map.get(display, display or "demo_default")

    def is_robot_ready_for_inspection(self):
        """Return True when inspection may proceed with real or simulated robot motion."""
        return self.robot_simulation_enabled_var.get() or self.robot_app.connected

    def _build_ui(self):
        top = ttk.LabelFrame(self.parent, text="自动检测流程")
        top.pack(fill=tk.X, padx=10, pady=10)

        row1 = ttk.Frame(top)
        row1.pack(fill=tk.X, padx=8, pady=6)

        ttk.Label(row1, text="工件编号:").pack(side=tk.LEFT)
        self.product_id_var = tk.StringVar(value=self.generate_product_id())
        self.product_id_entry = ttk.Entry(row1, textvariable=self.product_id_var, width=28)
        self.product_id_entry.pack(side=tk.LEFT, padx=(4, 6))
        self.product_id_entry.bind("<Return>", self.on_barcode_entered)
        ttk.Label(row1, text="工件型号:").pack(side=tk.LEFT, padx=(8, 0))
        self.workpiece_type_combo = ttk.Combobox(
            row1,
            textvariable=self.workpiece_type_var,
            values=list(self.workpiece_display_map.keys()),
            width=30,
            state="readonly"
        )
        active_workpiece = self.detector.get_active_workpiece_type()
        self.workpiece_type_var.set(self.get_workpiece_display_for_key(active_workpiece))
        self.workpiece_type_combo.pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(row1, text="扫码枪预留: 键盘输入后回车").pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(row1, text="采图超时(s):").pack(side=tk.LEFT)
        self.capture_timeout_var = tk.DoubleVar(value=3.0)
        ttk.Entry(row1, textvariable=self.capture_timeout_var, width=8).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Button(row1, text="选择图片保存目录", command=self.choose_save_dir).pack(side=tk.LEFT, padx=4)
        self.save_dir_label = ttk.Label(row1, text=self.save_dir, wraplength=560)
        self.save_dir_label.pack(side=tk.LEFT, padx=8)

        robot_sim_row = ttk.Frame(top)
        robot_sim_row.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Checkbutton(
            robot_sim_row,
            text="启用机械臂模拟模式",
            variable=self.robot_simulation_enabled_var
        ).pack(side=tk.LEFT)

        collection_group = ttk.LabelFrame(top, text="数据采集模式")
        collection_group.pack(fill=tk.X, padx=8, pady=(2, 6))

        collection_row1 = ttk.Frame(collection_group)
        collection_row1.pack(fill=tk.X, padx=8, pady=(8, 4))
        ttk.Checkbutton(
            collection_row1,
            text="启用数据采集模式",
            variable=self.collection_enabled_var
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(collection_row1, text="batch_id:").pack(side=tk.LEFT)
        ttk.Entry(collection_row1, textvariable=self.collection_batch_var, width=24).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(collection_row1, text="采集类型:").pack(side=tk.LEFT)
        self.collection_type_combo = ttk.Combobox(
            collection_row1,
            textvariable=self.collection_type_var,
            values=("train/good", "test/good", "test/defect", "raw/unlabeled"),
            width=16,
            state="readonly"
        )
        self.collection_type_combo.pack(side=tk.LEFT, padx=(4, 0))

        collection_row2 = ttk.Frame(collection_group)
        collection_row2.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(collection_row2, text="选择数据集目录", command=self.choose_dataset_root).pack(side=tk.LEFT, padx=(0, 8))
        self.dataset_root_label = ttk.Label(collection_row2, text=self.dataset_root, wraplength=720)
        self.dataset_root_label.pack(side=tk.LEFT, padx=4)

        row2 = ttk.Frame(top)
        row2.pack(fill=tk.X, padx=8, pady=6)

        self.btn_start = ttk.Button(row2, text="▶️ 开始：移动-拍照-识别", command=self.start_inspection)
        self.btn_start.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        self.btn_stop = ttk.Button(row2, text="⏹️ 停止检测", command=self.stop_inspection, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))

        self.btn_pause = ttk.Button(row2, text="暂停检测", command=self.pause_inspection, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=(8, 4))

        self.btn_resume = ttk.Button(row2, text="继续检测", command=self.resume_inspection, state=tk.DISABLED)
        self.btn_resume.pack(side=tk.LEFT, padx=(4, 0))

        self.status_var = tk.StringVar(value="等待开始。请先在“机械臂示教中心”里配置当前序列。")
        ttk.Label(top, textvariable=self.status_var, foreground="#075").pack(anchor=tk.W, padx=8, pady=(2, 8))

        summary_frame = ttk.Frame(self.parent)
        summary_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Label(summary_frame, textvariable=self.statistics_var).pack(side=tk.LEFT)
        self.final_status_label = tk.Label(
            summary_frame,
            textvariable=self.final_status_var,
            font=("Arial", 28, "bold"),
            fg="#666",
            width=10
        )
        self.final_status_label.pack(side=tk.RIGHT, padx=8)

        result_group = ttk.LabelFrame(self.parent, text="检测结果")
        result_group.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        filter_row = ttk.Frame(result_group)
        filter_row.pack(fill=tk.X, padx=8, pady=(8, 0))
        ttk.Label(filter_row, text="结果过滤:").pack(side=tk.LEFT)
        self.result_filter_combo = ttk.Combobox(
            filter_row,
            textvariable=self.result_filter_var,
            values=("ALL", "NG", "ERROR"),
            width=12,
            state="readonly"
        )
        self.result_filter_combo.pack(side=tk.LEFT, padx=(6, 0))
        self.result_filter_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_result_tree())

        columns = ("idx", "pose", "image", "result", "score", "threshold", "defect", "message")
        self.result_tree = ttk.Treeview(result_group, columns=columns, show="headings")
        self.result_tree.heading("idx", text="序号")
        self.result_tree.heading("pose", text="点位")
        self.result_tree.heading("image", text="图片")
        self.result_tree.heading("result", text="结果")
        self.result_tree.heading("score", text="置信度")
        self.result_tree.heading("threshold", text="阈值")
        self.result_tree.heading("defect", text="缺陷类型")
        self.result_tree.heading("message", text="说明")

        self.result_tree.column("idx", width=50, anchor="center")
        self.result_tree.column("pose", width=120)
        self.result_tree.column("image", width=260)
        self.result_tree.column("result", width=70, anchor="center")
        self.result_tree.column("score", width=80, anchor="center")
        self.result_tree.column("threshold", width=80, anchor="center")
        self.result_tree.column("defect", width=120)
        self.result_tree.column("message", width=420)

        scroll = ttk.Scrollbar(result_group, orient=tk.VERTICAL, command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=scroll.set)
        self.result_tree.bind("<<TreeviewSelect>>", self.on_result_tree_select)
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=8)

        bottom = ttk.Frame(self.parent)
        bottom.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(bottom, text="清空结果", command=self.clear_results).pack(side=tk.LEFT)
        ttk.Button(bottom, text="保存结果CSV", command=self.save_results_csv).pack(side=tk.LEFT, padx=8)
        ttk.Button(bottom, text="最近报告路径", command=self.show_last_report_path).pack(side=tk.LEFT, padx=8)

    def set_status(self, msg):
        self.status_var.set(msg)

    def generate_product_id(self):
        """Generate a unique automatic product id for a new workpiece."""
        now = time.time()
        ms = int((now - int(now)) * 1000)
        return f"{self.auto_product_prefix}{time.strftime('%Y%m%d_%H%M%S')}_{ms:03d}"

    def prepare_product_id_for_run(self):
        """Refresh auto ids for each run while preserving manual ids."""
        current = self.product_id_var.get().strip()
        if not current or current.startswith(self.auto_product_prefix):
            current = self.generate_product_id()
            self.product_id_var.set(current)
        return current

    def on_barcode_entered(self, _event=None):
        """Handle keyboard-enter barcode simulation without real scanner IO."""
        code = self.product_id_var.get().strip()
        self.product_id_var.set(code)
        self.append_log(f"扫码输入预留触发：{code or '<空>'}")
        # TODO: 后续如需接入串口扫码枪，可在这里增加 pyserial 读取逻辑。
        return "break"

    def pause_inspection(self):
        """Pause the workflow at safe checkpoints between hardware actions."""
        if not self.is_running:
            return
        self.pause_event.set()
        self.btn_pause.config(state=tk.DISABLED)
        self.btn_resume.config(state=tk.NORMAL)
        self.append_log("检测流程已暂停", level="WARN")
        self.set_status("已暂停")

    def resume_inspection(self):
        """Resume a paused workflow without clearing current results."""
        if not self.is_running:
            return
        self.pause_event.clear()
        self.btn_pause.config(state=tk.NORMAL)
        self.btn_resume.config(state=tk.DISABLED)
        self.append_log("检测流程继续执行")
        self.set_status("检测中")

    def wait_if_paused(self):
        """Block the worker thread while paused, but still allow stop."""
        while self.pause_event.is_set() and not self.stop_event.is_set():
            self.root.after(0, lambda: self.set_status("已暂停"))
            time.sleep(0.1)
        return not self.stop_event.is_set()

    def calculate_statistics(self):
        """Calculate current inspection counts and yield rate."""
        total = len(self.all_detection_results)
        labels = [str(item.get("label", item.get("result", ""))).upper() for item in self.all_detection_results]
        ok_count = sum(1 for label in labels if label == "OK")
        ng_count = sum(1 for label in labels if label == "NG")
        error_count = sum(1 for label in labels if label == "ERROR")
        yield_rate = (ok_count / total * 100.0) if total else 0.0
        return {
            "total": total,
            "ok_count": ok_count,
            "ng_count": ng_count,
            "error_count": error_count,
            "yield_rate": yield_rate,
        }

    def update_statistics(self):
        """Update the statistics bar from all stored detection results."""
        stats = self.calculate_statistics()
        self.statistics_var.set(
            f"已检测: {stats['total']}    OK: {stats['ok_count']}    "
            f"NG: {stats['ng_count']}    ERROR: {stats['error_count']}    "
            f"良率: {stats['yield_rate']:.2f}%"
        )
        return stats

    def reset_final_status(self):
        """Reset the large final status label for a new product."""
        self.final_status_var.set("WAIT")
        self.final_status_label.config(fg="#666")

    def update_final_status(self, final_label):
        """Show the final PASS, FAIL, or ERROR state prominently."""
        label = str(final_label or "").upper()
        if label == "OK":
            self.final_status_var.set("PASS")
            self.final_status_label.config(fg="#078a2f")
            self.alarm_controller.set_pass()
        elif label == "NG":
            self.final_status_var.set("FAIL")
            self.final_status_label.config(fg="#c00000")
            self.alarm_controller.set_fail()
        else:
            self.final_status_var.set("ERROR")
            self.final_status_label.config(fg="#e67e00")
            self.alarm_controller.set_error()

    def append_log(self, message, level="INFO"):
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": str(message)
        }
        self.run_logs.append(entry)
        self.root.after(0, lambda m=str(message): self.set_status(m))
        return entry

    @staticmethod
    def safe_dataset_name(value, fallback="unknown"):
        text = str(value or "").strip() or fallback
        safe = "".join(
            ch if ch.isascii() and (ch.isalnum() or ch in ("-", "_")) else "_"
            for ch in text
        )
        safe = "_".join(part for part in safe.split("_") if part)
        return safe or fallback

    def parse_collection_type(self, value):
        parts = str(value or "train/good").split("/", 1)
        if len(parts) != 2:
            return "train", "good"
        split = self.safe_dataset_name(parts[0], "train")
        label = self.safe_dataset_name(parts[1], "good")
        if (split, label) not in {
            ("train", "good"),
            ("test", "good"),
            ("test", "defect"),
            ("raw", "unlabeled"),
        }:
            return "train", "good"
        return split, label

    def ensure_unique_path(self, path):
        path = Path(path)
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        for index in range(1, 10000):
            candidate = path.with_name(f"{stem}_{index:03d}{suffix}")
            if not candidate.exists():
                return candidate
        raise RuntimeError(f"cannot create unique dataset image path: {path}")

    def build_dataset_target_path(self, source_image_path, workpiece_type, product_id, pose_name, split, label, ts):
        source_path = Path(source_image_path)
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(ts or time.time()))
        workpiece_safe = self.safe_dataset_name(workpiece_type, "demo_default")
        product_safe = self.safe_dataset_name(product_id, "part")
        pose_safe = self.safe_dataset_name(pose_name, "pose")
        original_safe = self.safe_dataset_name(source_path.stem, "image")
        suffix = source_path.suffix.lower() or ".png"

        target_dir = Path(self.dataset_root) / workpiece_safe / split / label / pose_safe
        target_name = f"{timestamp}_{product_safe}_{pose_safe}_{original_safe}{suffix}"
        return self.ensure_unique_path(target_dir / target_name)

    def append_dataset_manifest(self, row):
        manifest_path = Path(self.dataset_root) / "manifest.csv"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "timestamp",
            "workpiece_type",
            "product_id",
            "pose_name",
            "split",
            "label",
            "batch_id",
            "source_image_path",
            "target_image_path",
        ]
        write_header = not manifest_path.exists() or manifest_path.stat().st_size == 0
        with open(manifest_path, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    def archive_dataset_image(self, image_path, product_id, workpiece_type, pose_name, ts):
        if not self.collection_enabled_var.get():
            return None

        try:
            split, label = self.parse_collection_type(self.collection_type_var.get())
            batch_id = self.safe_dataset_name(
                self.collection_batch_var.get(),
                time.strftime("BATCH_%Y%m%d_%H%M%S")
            )
            source_path = Path(image_path)
            if not source_path.exists():
                raise FileNotFoundError(f"source image does not exist: {source_path}")

            target_path = self.build_dataset_target_path(
                source_image_path=source_path,
                workpiece_type=workpiece_type,
                product_id=product_id,
                pose_name=pose_name,
                split=split,
                label=label,
                ts=ts,
            )
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source_path), str(target_path))

            capture_time = ts or time.time()
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(capture_time))
            ms = int((capture_time % 1) * 1000)
            self.append_dataset_manifest({
                "timestamp": f"{timestamp}.{ms:03d}",
                "workpiece_type": workpiece_type,
                "product_id": product_id,
                "pose_name": pose_name,
                "split": split,
                "label": label,
                "batch_id": batch_id,
                "source_image_path": str(source_path.resolve()),
                "target_image_path": str(target_path.resolve()),
            })
            self.append_log(f"数据采集归档完成: {target_path.name}")
            return str(target_path)
        except Exception as exc:
            self.append_log(f"数据采集归档失败: {exc}", level="ERROR")
            return None

    def normalize_detection_result(self, result, idx, pose_name, image_path="", product_id="", workpiece_type=""):
        if not isinstance(result, dict):
            result = {
                "ok": False,
                "label": "ERROR",
                "message": f"算法返回非JSON对象: {type(result).__name__}"
            }

        label = str(result.get("label") or ("OK" if result.get("ok", False) else "NG")).upper()
        if label not in ("OK", "NG", "ERROR"):
            label = "ERROR"

        try:
            score = float(result.get("score", 0.0))
        except Exception:
            score = 0.0

        try:
            threshold = float(result.get("threshold", 0.5))
        except Exception:
            threshold = 0.5

        normalized = {
            "idx": idx,
            "pose": pose_name,
            "pose_name": pose_name,
            "image": image_path or result.get("image_path", ""),
            "image_path": image_path or result.get("image_path", ""),
            "ok": bool(result.get("ok", label == "OK")) and label == "OK",
            "label": label,
            "score": score,
            "threshold": threshold,
            "defect_type": result.get("defect_type", ""),
            "message": result.get("message", ""),
            "heatmap_path": result.get("heatmap_path", ""),
            "product_id": product_id or result.get("product_id", ""),
            "workpiece_type": workpiece_type or result.get("workpiece_type", ""),
            "algorithm_script": result.get("algorithm_script", ""),
            "algorithm_profile": result.get("algorithm_profile", ""),
            "algorithm_profile_source": result.get("algorithm_profile_source", ""),
            "elapsed_ms": int(result.get("elapsed_ms", 0) or 0),
            "boxes": result.get("boxes", [])
        }
        return normalized

    def compute_final_label(self, results):
        labels = [str(item.get("label", "")).upper() for item in results]
        if any(label == "ERROR" for label in labels):
            return "ERROR"
        if any(label == "NG" for label in labels):
            return "NG"
        return "OK"

    def save_inspection_report(self, product_id, workpiece_type, start_time, end_time, final_label):
        report_dir = THIS_DIR / "inspection_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        safe_product_id = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(product_id))
        report_path = report_dir / f"{safe_product_id}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        stats = self.calculate_statistics()

        report = {
            "product_id": product_id,
            "workpiece_type": workpiece_type,
            "start_time": start_time,
            "end_time": end_time,
            "final_label": final_label,
            "final_ok": final_label == "OK",
            "ok_count": stats["ok_count"],
            "ng_count": stats["ng_count"],
            "error_count": stats["error_count"],
            "yield_rate": stats["yield_rate"],
            "algorithm_script": self.results[0].get("algorithm_script", "") if self.results else "",
            "results": self.results,
            "logs": self.run_logs
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.last_report_path = str(report_path)
        self.append_log(f"检测报告已保存: {report_path.name}")
        return str(report_path)

    def show_last_report_path(self):
        if not self.last_report_path:
            messagebox.showinfo("最近报告路径", "当前还没有生成检测报告")
            return
        messagebox.showinfo("最近报告路径", self.last_report_path)

    def choose_save_dir(self):
        path = filedialog.askdirectory(initialdir=self.save_dir)
        if path:
            self.save_dir = path
            self.save_dir_label.config(text=path)

    def choose_dataset_root(self):
        path = filedialog.askdirectory(initialdir=self.dataset_root)
        if path:
            self.dataset_root = path
            self.dataset_root_label.config(text=path)

    def clear_results(self):
        self.all_detection_results.clear()
        self.run_logs.clear()
        self.last_report_path = ""
        self.refresh_result_tree()
        self.update_statistics()
        self.reset_final_status()
        self.alarm_controller.set_idle()

    def start_inspection(self):
        if self.is_running:
            return

        if not self.is_robot_ready_for_inspection():
            messagebox.showwarning("提示", "请先连接机械臂")
            return

        if not self.camera_app.camera.is_open:
            messagebox.showwarning("提示", "请先打开相机")
            return

        if not self.robot_app.sequence_list:
            messagebox.showwarning("提示", "请先在“机械臂示教中心”添加检测序列")
            return

        self.prepare_product_id_for_run()
        self.clear_results()
        self.stop_event.clear()
        self.pause_event.clear()
        self.robot_app.stop_requested = False
        self.is_running = True

        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.NORMAL)
        self.btn_resume.config(state=tk.DISABLED)
        self.alarm_controller.set_running()
        self.set_status("检测流程执行中：机械臂移动 -> 拍照 -> 识别")

        threading.Thread(target=self._run_inspection_logic, daemon=True).start()

    def stop_inspection(self):
        self.stop_event.set()
        self.pause_event.clear()
        self.robot_app.stop_requested = True
        self.alarm_controller.set_idle()
        self.root.after(0, lambda: self.set_status("正在请求停止..."))

    def _run_inspection_logic(self):
        product_id = self.product_id_var.get().strip() or self.generate_product_id()
        workpiece_type = self.get_selected_workpiece_type()
        timeout = float(self.capture_timeout_var.get() or 3.0)
        robot_simulation_enabled = self.robot_simulation_enabled_var.get()
        start_time = time.strftime("%Y-%m-%d %H:%M:%S")

        final_label = "ERROR"
        had_runtime_error = False

        try:
            self.append_log(f"开始检测: product_id={product_id}, workpiece_type={workpiece_type}")
            for idx, step in enumerate(list(self.robot_app.sequence_list), start=1):
                if self.stop_event.is_set() or not self.is_robot_ready_for_inspection():
                    self.append_log("检测流程被停止或机械臂连接断开", level="WARN")
                    break

                if not self.wait_if_paused():
                    break

                pose_name = step["name"]
                speed = step["speed"]
                delay = float(step.get("delay", 0))

                if pose_name not in self.robot_app.saved_poses:
                    result = self.normalize_detection_result(
                        {"ok": False, "label": "ERROR", "defect_type": "pose_missing", "message": "该点位不在 saved_poses 中"},
                        idx,
                        pose_name,
                        "",
                        product_id,
                        workpiece_type
                    )
                    self._append_result(result)
                    self.append_log(f"点位不存在: {pose_name}", level="ERROR")
                    continue

                self.append_log(f"[{idx}] 移动到点位: {pose_name}")

                # 1) 机械臂移动到指定点位；execute_movement 内部会等待 getRobotState == 0
                if robot_simulation_enabled:
                    self.append_log(f"[{idx}] 模拟机械臂移动到点位 {pose_name}")
                    time.sleep(0.2)
                else:
                    self.robot_app.execute_movement(self.robot_app.saved_poses[pose_name], speed)

                if self.stop_event.is_set() or not self.is_robot_ready_for_inspection():
                    self.append_log(f"[{idx}] 点位 {pose_name} 移动后检测到停止请求或连接断开", level="WARN")
                    break

                # 2) 到位后稳定等待，复用原序列里的 delay 作为“拍照前停顿”
                stable_start = time.time()
                if not self.wait_if_paused():
                    break

                while time.time() - stable_start < delay:
                    if self.stop_event.is_set() or not self.is_robot_ready_for_inspection():
                        break
                    if not self.wait_if_paused():
                        break
                    time.sleep(0.05)

                if self.stop_event.is_set() or not self.is_robot_ready_for_inspection():
                    self.append_log(f"[{idx}] 点位 {pose_name} 稳定等待中停止", level="WARN")
                    break

                # 3) 相机软件触发拍照并保存
                self.append_log(f"[{idx}] 点位 {pose_name} 到位，开始拍照")
                image_path, frame_rgb, frame_gray, ts = self.camera_app.capture_for_inspection(
                    pose_name=pose_name,
                    product_id=product_id,
                    save_dir=self.save_dir,
                    timeout=timeout
                )
                self.archive_dataset_image(
                    image_path=image_path,
                    product_id=product_id,
                    workpiece_type=workpiece_type,
                    pose_name=pose_name,
                    ts=ts
                )

                # 4) 调用识别算法
                self.append_log(f"[{idx}] 点位 {pose_name} 拍照完成，开始识别")
                if not self.wait_if_paused():
                    break

                result = self.detector.detect(
                    frame_rgb=frame_rgb,
                    frame_gray=frame_gray,
                    image_path=image_path,
                    pose_name=pose_name,
                    product_id=product_id,
                    workpiece_type=workpiece_type
                )

                normalized = self.normalize_detection_result(result, idx, pose_name, image_path, product_id, workpiece_type)
                self._append_result(normalized)
                self.append_log(
                    f"[{idx}] 点位 {pose_name} 识别完成: {normalized['label']} "
                    f"score={normalized['score']:.3f} threshold={normalized['threshold']:.3f}"
                )

            final_label = self.compute_final_label(self.results)
            end_msg = f"检测完成：最终结果 {final_label}"
            if self.stop_event.is_set():
                end_msg = "检测已停止"
            self.append_log(end_msg)

        except Exception as e:
            final_label = "ERROR"
            had_runtime_error = True
            self.append_log(f"自动检测异常: {e}", level="ERROR")
            self.root.after(0, lambda err=str(e): messagebox.showerror("自动检测异常", err))
            self.root.after(0, lambda err=str(e): self.set_status(f"异常：{err}"))
        finally:
            end_time = time.strftime("%Y-%m-%d %H:%M:%S")
            if self.results:
                final_label = "ERROR" if had_runtime_error else self.compute_final_label(self.results)
                try:
                    self.save_inspection_report(product_id, workpiece_type, start_time, end_time, final_label)
                except Exception as report_error:
                    self.append_log(f"保存检测报告失败: {report_error}", level="ERROR")
            if self.results and not self.stop_event.is_set():
                self.root.after(0, lambda label=final_label: self.update_final_status(label))
            elif self.stop_event.is_set():
                self.root.after(0, self.alarm_controller.set_idle)
            self.is_running = False
            self.robot_app.stop_requested = False
            self.root.after(0, self._reset_buttons)

    def _append_result(self, idx, pose_name=None, image_path="", label="", score=0.0, defect_type="", message="", threshold=0.5):
        if isinstance(idx, dict):
            row = dict(idx)
            row.setdefault("result", row.get("label", ""))
            row.setdefault("defect", row.get("defect_type", ""))
            row.setdefault("pose_name", row.get("pose", ""))
        else:
            row = {
                "idx": idx,
                "pose": pose_name,
                "pose_name": pose_name,
                "image": image_path,
                "image_path": image_path,
                "result": label,
                "label": label,
                "score": score,
                "threshold": threshold,
                "defect": defect_type,
                "defect_type": defect_type,
                "message": message
            }
        row.setdefault("boxes", [])
        row.setdefault("heatmap_path", "")
        row.setdefault("workpiece_type", "")
        self.all_detection_results.append(row)
        self.root.after(0, lambda: (self.refresh_result_tree(), self.update_statistics()))

    def get_filtered_results(self):
        """Return results matching the current table filter."""
        mode = self.result_filter_var.get()
        if mode == "NG":
            return [r for r in self.all_detection_results if str(r.get("label", r.get("result", ""))).upper() == "NG"]
        if mode == "ERROR":
            return [r for r in self.all_detection_results if str(r.get("label", r.get("result", ""))).upper() == "ERROR"]
        return list(self.all_detection_results)

    def refresh_result_tree(self):
        """Rebuild the result table without deleting stored detection results."""
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        for row in self.get_filtered_results():
            image_value = row.get("image_path") or row.get("image") or ""
            filename = Path(image_value).name if image_value else ""
            values = (
                row.get("idx", ""),
                row.get("pose", row.get("pose_name", "")),
                filename,
                row.get("label", row.get("result", "")),
                f"{float(row.get('score', 0.0)):.3f}",
                f"{float(row.get('threshold', 0.5)):.3f}",
                row.get("defect_type", row.get("defect", "")),
                row.get("message", "")
            )
            iid = str(row.get("idx", len(self.result_tree.get_children()) + 1))
            self.result_tree.insert("", tk.END, iid=iid, values=values)

    def on_result_tree_select(self, _event=None):
        """Open the selected detection image from the full stored result."""
        selected = self.result_tree.selection()
        if not selected:
            return

        try:
            idx = int(selected[0])
        except Exception:
            return

        for result in self.all_detection_results:
            try:
                if int(result.get("idx", -1)) == idx:
                    self.show_detection_image(result)
                    return
            except Exception:
                continue

    def show_detection_image(self, result):
        """Show one detection image in a separate preview window."""
        image_path = result.get("image_path") or result.get("image") or ""
        if not image_path or not Path(image_path).exists():
            messagebox.showwarning("图片不存在", f"检测图片不存在:\n{image_path}")
            return

        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            messagebox.showwarning("图片读取失败", f"无法读取检测图片:\n{image_path}")
            return

        image = self.overlay_detection_result(image, result)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)

        max_w = max(400, min(1100, self.root.winfo_screenwidth() - 120))
        max_h = max(300, min(800, self.root.winfo_screenheight() - 160))
        pil_image.thumbnail((max_w, max_h), Image.LANCZOS)

        if self.preview_window is None or not self.preview_window.winfo_exists():
            self.preview_window = tk.Toplevel(self.root)
            self.preview_window.title("检测图片大图")
            self.preview_label = ttk.Label(self.preview_window)
            self.preview_label.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        else:
            self.preview_window.lift()

        self.preview_photo = ImageTk.PhotoImage(pil_image)
        self.preview_label.configure(image=self.preview_photo)

    def overlay_detection_result(self, image, result):
        """Overlay heatmap and detection boxes on a BGR image."""
        output = image.copy()
        heatmap_path = result.get("heatmap_path") or ""
        if heatmap_path and Path(heatmap_path).exists():
            heatmap = cv2.imread(str(heatmap_path), cv2.IMREAD_COLOR)
            if heatmap is not None:
                try:
                    heatmap = cv2.resize(heatmap, (output.shape[1], output.shape[0]))
                    output = cv2.addWeighted(output, 0.65, heatmap, 0.35, 0)
                except Exception:
                    pass

        boxes = result.get("boxes") or []
        for box in boxes:
            parsed = self.parse_detection_box(box)
            if parsed is None:
                continue
            x1, y1, x2, y2, box_label, box_score = parsed
            cv2.rectangle(output, (x1, y1), (x2, y2), (0, 0, 255), 2)
            text_label = box_label or result.get("defect_type", "")
            text_score = "" if box_score is None else f" {box_score:.2f}"
            text = f"{text_label}{text_score}".strip()
            if text:
                y_text = max(18, y1 - 6)
                cv2.putText(output, text, (x1, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        return output

    def parse_detection_box(self, box):
        """Parse supported box formats and skip invalid boxes safely."""
        try:
            if isinstance(box, dict):
                x1 = int(float(box.get("x1")))
                y1 = int(float(box.get("y1")))
                x2 = int(float(box.get("x2")))
                y2 = int(float(box.get("y2")))
                label = str(box.get("label") or box.get("class") or "")
                score = box.get("score")
            elif isinstance(box, (list, tuple)) and len(box) >= 4:
                x1, y1, x2, y2 = [int(float(v)) for v in box[:4]]
                label = ""
                score = None
            else:
                return None

            if x2 <= x1 or y2 <= y1:
                return None
            score = None if score in (None, "") else float(score)
            return x1, y1, x2, y2, label, score
        except Exception:
            return None

    def _reset_buttons(self):
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_pause.config(state=tk.DISABLED)
        self.btn_resume.config(state=tk.DISABLED)
        self.pause_event.clear()

    def save_results_csv(self):
        if not self.results:
            messagebox.showwarning("提示", "没有检测结果可保存")
            return

        default_name = f"inspection_results_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        path = filedialog.asksaveasfilename(
            initialdir=self.save_dir,
            initialfile=default_name,
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not path:
            return

        import csv
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["idx", "pose", "image_path", "label", "score", "threshold", "defect_type", "message"],
                extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(self.results)

        messagebox.showinfo("保存成功", f"结果已保存到：\n{path}")


# ==========================================
# [主程序]: 集成窗口框架
# ==========================================
class MainApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("🦾 视觉协同智控中心 (相机与机械臂)")
        self.root.geometry("1650x850") 
        
        style = ttk.Style(self.root)
        try: style.theme_use("vista")
        except Exception: pass

        # 使用 PanedWindow 实现左右分屏，左边放选项卡(控制)，右边放相机预览
        self.paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # ====== 左半边：选项卡控制区 ======
        self.left_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.left_frame, minsize=650) # 保证左边足够装下UI
        
        self.notebook = ttk.Notebook(self.left_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tab_camera = ttk.Frame(self.notebook)
        self.tab_robot = ttk.Frame(self.notebook)
        self.tab_inspection = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_camera, text=" 📷 相机控制台 ")
        self.notebook.add(self.tab_robot, text=" 🦾 机械臂示教中心 ")
        self.notebook.add(self.tab_inspection, text=" ✅ 自动检测流程 ")

        # ====== 右半边：相机图像预览区 (永远可见) ======
        self.right_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.right_frame, minsize=500) # 右侧保证留给画面

        # ====== 实例化两大组件 ======
        # 相机控制器：控制部分画在 tab_camera 里，预览部分画在全局 right_frame 里
        self.camera_app = CameraUIController(self.root, control_parent=self.tab_camera, preview_parent=self.right_frame)
        
        # 机械臂控制器：全部画在 tab_robot 里
        self.robot_app = RobotUIController(self.root, parent_frame=self.tab_robot)

        # 自动检测流程：调用“机械臂移动 -> 相机拍照 -> 算法识别”
        self.inspection_app = InspectionUIController(
            self.root,
            parent_frame=self.tab_inspection,
            camera_app=self.camera_app,
            robot_app=self.robot_app
        )

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        # 安全退出：依次调用两个组件的断开与清理逻辑
        self.camera_app.on_close()
        self.robot_app.on_closing()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = MainApplication(root)
    root.mainloop()

if __name__ == "__main__":
    main()
