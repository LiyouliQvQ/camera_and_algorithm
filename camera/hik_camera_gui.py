import os
import sys
import time
import threading
from pathlib import Path
from ctypes import *

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# =========================
# SDK import setup
# =========================
# 默认假设: 你已经把 MvImport 文件夹复制到本脚本同级目录。
# 如果不是，请把 SDK_PYTHON_IMPORT_DIR 改成你电脑上的实际路径。
SDK_PYTHON_IMPORT_DIR = None  # 例如 r"C:\Program Files\MVS\Development\Samples\Python\MvImport"

THIS_DIR = Path(__file__).resolve().parent
LOCAL_MVIMPORT = THIS_DIR / "MvImport"

if SDK_PYTHON_IMPORT_DIR and Path(SDK_PYTHON_IMPORT_DIR).exists():
    sys.path.append(SDK_PYTHON_IMPORT_DIR)
elif LOCAL_MVIMPORT.exists():
    sys.path.append(str(LOCAL_MVIMPORT))

try:
    from MvCameraControl_class import *
except ModuleNotFoundError as e:
    raise ModuleNotFoundError(
        "找不到 MvCameraControl_class。请把 MvImport 文件夹复制到本脚本同级目录，"
        "或者修改脚本顶部的 SDK_PYTHON_IMPORT_DIR。"
    ) from e

try:
    from PIL import Image, ImageTk
except ModuleNotFoundError as e:
    raise ModuleNotFoundError(
        "缺少 Pillow。请先运行: pip install pillow"
    ) from e


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

            # GigE 相机尽量设置最优包大小
            if device_info.nTLayerType == MV_GIGE_DEVICE:
                packet_size = self.cam.MV_CC_GetOptimalPacketSize()
                if int(packet_size) > 0:
                    self.cam.MV_CC_SetIntValue("GevSCPSPacketSize", packet_size)

            self.is_open = True
        except Exception:
            try:
                self.cam.MV_CC_DestroyHandle()
            except Exception:
                pass
            self.cam = None
            self.device_info = None
            self.is_open = False
            raise

    def close(self):
        self.stop_grabbing()
        if self.cam is not None:
            try:
                self.cam.MV_CC_CloseDevice()
            except Exception:
                pass
            try:
                self.cam.MV_CC_DestroyHandle()
            except Exception:
                pass
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
        # 预览推荐设置: 连续采集 + 关闭触发
        self.set_enum("TriggerMode", MV_TRIGGER_MODE_OFF)
        # 不同版本 SDK 有的需要显式设置采集模式, 若失败可忽略
        try:
            self.set_enum("AcquisitionMode", 2)  # Continuous 通常为 2
        except Exception:
            pass

    def software_trigger_mode(self):
        self.set_enum("TriggerMode", MV_TRIGGER_MODE_ON)
        try:
            self.set_enum("TriggerSource", MV_TRIGGER_SOURCE_SOFTWARE)
        except Exception:
            pass

    def send_software_trigger(self):
        self._check_ret(self.cam.MV_CC_SetCommandValue("TriggerSoftware"), "软件触发")

    def start_grabbing(self):
        if self.is_grabbing:
            return
        self.stop_event.clear()
        self._check_ret(self.cam.MV_CC_StartGrabbing(), "开始取流")
        self.is_grabbing = True
        self.grab_thread = threading.Thread(target=self._grab_loop, daemon=True)
        self.grab_thread.start()

    def stop_grabbing(self):
        if not self.is_grabbing:
            return
        self.stop_event.set()
        if self.grab_thread is not None:
            self.grab_thread.join(timeout=1.5)
            self.grab_thread = None
        try:
            self.cam.MV_CC_StopGrabbing()
        except Exception:
            pass
        self.is_grabbing = False

    def _grab_loop(self):
        while not self.stop_event.is_set():
            st_out_frame = MV_FRAME_OUT()
            memset(byref(st_out_frame), 0, sizeof(st_out_frame))

            ret = self.cam.MV_CC_GetImageBuffer(st_out_frame, 1000)
            if ret != 0:
                continue

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
                    # 遇到当前示例不支持的像素格式时, 尝试按单通道兜底显示前 width*height 字节
                    size = width * height
                    if raw.size >= size:
                        frame_gray = raw[:size].reshape((height, width))
                        frame_rgb = cv2.cvtColor(frame_gray, cv2.COLOR_GRAY2RGB)
                    else:
                        continue

                with self.frame_lock:
                    self.latest_frame = frame_rgb
                    self.latest_frame_gray = frame_gray
                    self.latest_frame_ts = time.time()
            finally:
                try:
                    self.cam.MV_CC_FreeImageBuffer(st_out_frame)
                except Exception:
                    pass

    def get_latest_frame(self):
        with self.frame_lock:
            if self.latest_frame is None:
                return None, None, 0.0
            return self.latest_frame.copy(), self.latest_frame_gray.copy(), self.latest_frame_ts


class CameraGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("海康工业相机 GUI")
        self.root.geometry("1320x820")

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
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        right = ttk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 设备区
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

        # 参数区
        param_group = ttk.LabelFrame(left, text="关键参数")
        param_group.pack(fill=tk.X, pady=(0, 8))

        # 曝光自动
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

        # 增益自动
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

        # 触发区
        trig_group = ttk.LabelFrame(left, text="触发")
        trig_group.pack(fill=tk.X, pady=(0, 8))
        self.trigger_mode = ttk.Combobox(trig_group, state="readonly", values=["预览模式(Trigger Off)", "软件触发模式"], width=22)
        self.trigger_mode.set("预览模式(Trigger Off)")
        self.trigger_mode.pack(fill=tk.X, padx=8, pady=(8, 6))
        ttk.Button(trig_group, text="应用触发模式", command=self.apply_trigger_mode).pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Button(trig_group, text="软件触发一次", command=self.software_trigger_once).pack(fill=tk.X, padx=8, pady=(0, 8))

        # 保存区
        save_group = ttk.LabelFrame(left, text="保存图像")
        save_group.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(save_group, text="保存当前图像", command=self.save_current_frame).pack(fill=tk.X, padx=8, pady=(8, 6))
        ttk.Button(save_group, text="选择保存目录", command=self.choose_save_dir).pack(fill=tk.X, padx=8, pady=(0, 8))

        self.save_dir_label = ttk.Label(save_group, text=self.last_save_path, wraplength=310)
        self.save_dir_label.pack(anchor=tk.W, padx=8, pady=(0, 8))

        # 状态区
        status_group = ttk.LabelFrame(left, text="状态")
        status_group.pack(fill=tk.X)
        self.status_text = tk.StringVar(value="未连接")
        self.frame_info_text = tk.StringVar(value="分辨率: - | 显示FPS: -")
        ttk.Label(status_group, textvariable=self.status_text, foreground="#0a5").pack(anchor=tk.W, padx=8, pady=(8, 4))
        ttk.Label(status_group, textvariable=self.frame_info_text, wraplength=320).pack(anchor=tk.W, padx=8, pady=(0, 8))

        # 预览区
        preview_group = ttk.LabelFrame(right, text="实时预览")
        preview_group.pack(fill=tk.BOTH, expand=True)

        self.preview_label = ttk.Label(preview_group)
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def set_status(self, msg):
        self.status_text.set(msg)

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
            if idx < 0 or not getattr(self, "devices", None):
                raise CameraError("请先选择设备")
            self.camera.open(self.devices[idx][1])
            self.camera.apply_preview_defaults()
            self.set_status("相机已打开")
        except Exception as e:
            messagebox.showerror("打开相机失败", str(e))
            self.set_status("打开失败")

    def close_camera(self):
        try:
            self.camera.close()
            self.preview_label.configure(image="")
            self.photo = None
            self.frame_info_text.set("分辨率: - | 显示FPS: -")
            self.set_status("相机已关闭")
        except Exception as e:
            messagebox.showerror("关闭相机失败", str(e))

    def start_preview(self):
        try:
            if not self.camera.is_open:
                raise CameraError("请先打开相机")
            self.camera.apply_preview_defaults()
            self.camera.start_grabbing()
            self.set_status("预览中")
        except Exception as e:
            messagebox.showerror("开始预览失败", str(e))

    def stop_preview(self):
        try:
            self.camera.stop_grabbing()
            self.set_status("预览已停止")
        except Exception as e:
            messagebox.showerror("停止预览失败", str(e))

    def apply_exposure_auto(self):
        try:
            if not self.camera.is_open:
                return
            mode = self.exposure_auto.get()
            if mode == "Off":
                self.camera.set_enum("ExposureAuto", 0)
            else:
                self.camera.set_enum("ExposureAuto", 2)  # Continuous
            self.set_status(f"曝光自动: {mode}")
        except Exception as e:
            messagebox.showerror("设置曝光自动失败", str(e))

    def apply_exposure_time(self):
        try:
            if not self.camera.is_open:
                return
            val = float(self.exposure_entry.get())
            self.exposure_var.set(val)
            self.camera.set_float("ExposureTime", val)
            self.set_status(f"曝光时间已设为 {val:.0f} us")
        except Exception as e:
            messagebox.showerror("设置曝光时间失败", str(e))

    def _on_exposure_slide(self, _):
        self.exposure_entry.delete(0, tk.END)
        self.exposure_entry.insert(0, f"{self.exposure_var.get():.0f}")

    def apply_gain_auto(self):
        try:
            if not self.camera.is_open:
                return
            mode = self.gain_auto.get()
            if mode == "Off":
                self.camera.set_enum("GainAuto", 0)
            else:
                self.camera.set_enum("GainAuto", 2)  # Continuous
            self.set_status(f"增益自动: {mode}")
        except Exception as e:
            messagebox.showerror("设置增益自动失败", str(e))

    def apply_gain(self):
        try:
            if not self.camera.is_open:
                return
            val = float(self.gain_entry.get())
            self.gain_var.set(val)
            self.camera.set_float("Gain", val)
            self.set_status(f"增益已设为 {val:.1f} dB")
        except Exception as e:
            messagebox.showerror("设置增益失败", str(e))

    def _on_gain_slide(self, _):
        self.gain_entry.delete(0, tk.END)
        self.gain_entry.insert(0, f"{self.gain_var.get():.1f}")

    def apply_trigger_mode(self):
        try:
            if not self.camera.is_open:
                return
            if self.trigger_mode.get() == "预览模式(Trigger Off)":
                self.camera.apply_preview_defaults()
                self.set_status("已切换到预览模式")
            else:
                self.camera.software_trigger_mode()
                self.set_status("已切换到软件触发模式")
        except Exception as e:
            messagebox.showerror("设置触发模式失败", str(e))

    def software_trigger_once(self):
        try:
            if not self.camera.is_open:
                raise CameraError("请先打开相机")
            if not self.camera.is_grabbing:
                self.camera.start_grabbing()
            self.camera.software_trigger_mode()
            self.camera.send_software_trigger()
            self.set_status("已软件触发一次")
        except Exception as e:
            messagebox.showerror("软件触发失败", str(e))

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

        if frame_gray is not None:
            ok = cv2.imwrite(str(path), frame_gray)
        else:
            ok = cv2.imwrite(str(path), cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))

        if ok:
            self.set_status(f"已保存: {path.name}")
            messagebox.showinfo("保存成功", f"图像已保存到:\n{path}")
        else:
            messagebox.showerror("保存失败", "OpenCV 写文件失败")

    def _schedule_preview(self):
        self.preview_after_id = self.root.after(30, self._update_preview)

    def _update_preview(self):
        try:
            frame_rgb, frame_gray, ts = self.camera.get_latest_frame()
            if frame_rgb is not None:
                h, w = frame_rgb.shape[:2]
                label_w = max(self.preview_label.winfo_width(), 640)
                label_h = max(self.preview_label.winfo_height(), 480)
                scale = min(label_w / w, label_h / h)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                disp = cv2.resize(frame_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

                if ts != self.last_frame_time and self.last_frame_time > 0:
                    dt = ts - self.last_frame_time
                    if dt > 0:
                        self.display_fps = 1.0 / dt
                self.last_frame_time = ts

                img = Image.fromarray(disp)
                self.photo = ImageTk.PhotoImage(img)
                self.preview_label.configure(image=self.photo)
                self.frame_info_text.set(f"分辨率: {w} x {h} | 显示FPS: {self.display_fps:.1f}")
        finally:
            self._schedule_preview()

    def on_close(self):
        try:
            if self.preview_after_id is not None:
                self.root.after_cancel(self.preview_after_id)
        except Exception:
            pass
        try:
            self.camera.close()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except Exception:
        pass
    CameraGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
