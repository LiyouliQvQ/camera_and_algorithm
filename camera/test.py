import sys
import ctypes
from ctypes import *
import numpy as np
import cv2

# 这里假设你已经把 SDK 的 Python 封装文件放进工程，或加到了 PYTHONPATH
from MvImport.MvCameraControl_class import *

def check_ret(ret, msg):
    if ret != 0:
        raise RuntimeError(f"{msg} failed, ret=0x{ret:x}")

def main():
    # 1) 枚举设备：GigE / USB 都可以枚举，这里主要用 GigE
    device_list = MV_CC_DEVICE_INFO_LIST()
    tlayer_type = MV_GIGE_DEVICE | MV_USB_DEVICE

    ret = MvCamera.MV_CC_EnumDevices(tlayer_type, device_list)
    check_ret(ret, "EnumDevices")

    if device_list.nDeviceNum == 0:
        raise RuntimeError("没有找到相机，请先确认 MVS 中可以看到相机。")

    print(f"找到设备数量: {device_list.nDeviceNum}")

    # 2) 这里先默认取第 0 台
    cam = MvCamera()
    st_device_info = cast(device_list.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents

    # 3) 创建句柄
    ret = cam.MV_CC_CreateHandle(st_device_info)
    check_ret(ret, "CreateHandle")

    try:
        # 4) 打开设备
        ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        check_ret(ret, "OpenDevice")

        # 5) 如果是 GigE，相机包大小尽量调到最优
        if st_device_info.nTLayerType == MV_GIGE_DEVICE:
            packet_size = cam.MV_CC_GetOptimalPacketSize()
            if int(packet_size) > 0:
                ret = cam.MV_CC_SetIntValue("GevSCPSPacketSize", packet_size)
                if ret != 0:
                    print(f"设置包大小失败，ret=0x{ret:x}")
            else:
                print("未获取到最优包大小，继续使用默认值。")

        # 6) 设置连续采集、关闭触发
        ret = cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
        check_ret(ret, "Set TriggerMode Off")

        # 如果你后面想做“程序拍一张”，就改成软件触发：
        # cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_ON)
        # cam.MV_CC_SetEnumValue("TriggerSource", MV_TRIGGER_SOURCE_SOFTWARE)

        # 7) 开始取流
        ret = cam.MV_CC_StartGrabbing()
        check_ret(ret, "StartGrabbing")

        # 8) 取一帧
        st_out_frame = MV_FRAME_OUT()
        memset(byref(st_out_frame), 0, sizeof(st_out_frame))

        ret = cam.MV_CC_GetImageBuffer(st_out_frame, 1000)
        check_ret(ret, "GetImageBuffer")

        try:
            width = st_out_frame.stFrameInfo.nWidth
            height = st_out_frame.stFrameInfo.nHeight
            frame_len = st_out_frame.stFrameInfo.nFrameLen

            print(f"获取到图像: {width} x {height}, len={frame_len}")

            # 关键修改：不要再用 from_address
            buf_ptr = cast(st_out_frame.pBufAddr, POINTER(c_ubyte * frame_len))
            img = np.frombuffer(buf_ptr.contents, dtype=np.uint8).reshape((height, width)).copy()

            cv2.imwrite("test_capture.png", img)
            print("已保存 test_capture.png")

            cv2.imshow("frame", img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        finally:
            ret = cam.MV_CC_FreeImageBuffer(st_out_frame)
            check_ret(ret, "FreeImageBuffer")

        # 9) 停止取流
        ret = cam.MV_CC_StopGrabbing()
        check_ret(ret, "StopGrabbing")

    finally:
        # 10) 关闭设备 + 销毁句柄
        try:
            cam.MV_CC_CloseDevice()
        except:
            pass
        try:
            cam.MV_CC_DestroyHandle()
        except:
            pass

if __name__ == "__main__":
    main()