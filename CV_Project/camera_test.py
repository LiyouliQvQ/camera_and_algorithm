import sys
import os

print("=======================================")
print("⏳ 正在测试 Python 与海康底层的跨界通讯...")

# 🌟 1. 尝试导入海康 SDK (只要这一步不报错，说明偷渡成功！)
try:
    from MvImport.MvCameraControl_class import *
    print("第一关通过：海康 SDK 导入成功！你的 Python 已具备控制相机的超能力。")
except ImportError:
    print("第一关失败：找不到海康 SDK！请检查 MvImport 文件夹是否真的复制到了本项目下。")
    sys.exit()

# 🌟 2. 尝试向底层网卡和 USB 接口发送广播，寻找海康设备
try:
    # 召唤海康相机控制类的实例
    MvCamera = MvCamera()
    
    # 设定我们要寻找的设备类型 (GigE网口相机 和 USB3.0相机 我全都要)
    tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
    deviceList = MV_CC_DEVICE_INFO_LIST()
    
    # 向系统底层发送扫描指令
    ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
    
    if ret != 0:
        print(f"第二关失败：底层驱动扫描异常，错误码: {ret}")
    else:
        print(f"第二关通过：底层接口扫描完毕！")
        print(f"报告长官：当前电脑物理接口共连接了 【{deviceList.nDeviceNum}】 台海康工业相机。")
        
       
except Exception as e:
    print(f"❌ 运行发生未知错误: {e}")

print("=======================================")