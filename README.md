# 汽车差速器壳体工业视觉检测系统

本项目用于汽车差速器壳体的工业视觉检测实验与现场集成。系统由机械臂、海康工业相机和视觉检测算法组成，目标是在 GUI 中按检测流程控制艾利特 EC66 机械臂运动到指定点位，触发海康相机拍照，并调用视觉算法返回 OK/NG 检测结果。

当前仓库包含两个主要部分：

- `camera/`：机械臂与海康工业相机控制程序，包含 Tkinter GUI、EC66 通信、相机预览与自动拍照流程。
- `CV_Project/`：视觉检测算法实验项目，包含训练、推理、演示和 dummy 算法闭环脚本。

## 当前系统功能

- Tkinter 集成 GUI。
- 海康工业相机设备枚举、打开、关闭、预览、软件触发和保存图片。
- 艾利特 EC66 机械臂点位示教、序列管理和按点位运动。
- 自动检测流程面板。
- 自动检测最小闭环：
  `camera GUI -> 机械臂移动 -> 海康相机拍照 -> subprocess 调用 CV_Project/scripts/infer_one_dummy.py -> 返回 JSON -> GUI 显示 OK/NG`
- dummy 算法脚本支持 OK/NG 分支验证。

## 项目目录结构

```text
camera_and_algorithm/
  README.md
  CODEX_HANDOFF.md
  AGENTS.md
  PROJECT_OVERVIEW.md
  camera/
    vision_robot_inspection_gui.py
    ec66_hik_single_pose_capture.py
    hik_camera_gui.py
  CV_Project/
    README.md
    config.py
    main_system.py
    vision_server.py
    vision_server_ai.py
    robot_client.py
    train_my_data.py
    train_my_data_efficientAD.py
    scripts/
      infer_one_dummy.py
```

部分大型或本地环境目录不会上传到 GitHub，见下方说明。

## camera/ 目录说明

`camera/` 是现场控制与 GUI 侧代码：

- `vision_robot_inspection_gui.py`：当前主 GUI 程序，集成相机控制、机械臂示教、自动检测流程和 dummy 算法调用。
- `hik_camera_gui.py`：独立海康相机 GUI 示例，可用于相机预览、触发和保存图片验证。
- `ec66_hik_single_pose_capture.py`：单点位机械臂运动与相机拍照验证脚本。

自动检测流程主要位于 `vision_robot_inspection_gui.py`：

- `HikCamera`：海康相机底层控制封装。
- `CameraUIController`：相机 GUI 控制面板。
- `RobotUIController`：EC66 机械臂连接、示教和运动控制。
- `DefectDetector`：算法调用统一入口。
- `InspectionUIController`：自动检测流程控制。

## CV_Project/ 目录说明

`CV_Project/` 是视觉算法实验与推理侧代码：

- `scripts/infer_one_dummy.py`：当前最小闭环使用的 dummy 单图推理脚本。
- `vision_server_ai.py`：视觉推理服务骨架。
- `main_system.py`：机器人与视觉检测联动演示入口。
- `train_my_data.py`、`train_my_data_efficientAD.py`：训练脚本入口。

当前阶段暂未在 GUI 闭环中接入真实模型，先通过 dummy 脚本验证跨项目调用链路。

## 当前已完成的最小闭环

自动检测流程如下：

1. 在 `camera/vision_robot_inspection_gui.py` 启动 GUI。
2. GUI 控制 EC66 机械臂移动到检测点位。
3. 机械臂到位后，GUI 调用海康相机软件触发拍照。
4. 图片保存到本地检测图片目录。
5. `DefectDetector.detect()` 通过 `subprocess.run()` 调用：
   `CV_Project/scripts/infer_one_dummy.py`
6. dummy 算法脚本输出 JSON。
7. GUI 解析 JSON 并显示 `OK`、`NG` 或 `ERROR`。

dummy 判定规则：

- 图片文件名主体包含 `ng`、`bad` 或 `defect` 时返回 `NG`。
- 否则返回 `OK`。

## 运行环境

建议环境：

- Windows
- Python 3.8+
- OpenCV
- NumPy
- Pillow
- Tkinter
- 海康 MVS SDK 与本机相机驱动
- 艾利特 EC66 机械臂网络连接

真实算法训练或推理可能还需要：

- PyTorch
- anomalib
- CUDA 相关依赖

## 如何运行 GUI

在项目根目录执行：

```powershell
cd D:\run_code\camera_and_algorithm
python camera\vision_robot_inspection_gui.py
```

GUI 使用流程：

1. 打开海康相机。
2. 连接机械臂。
3. 在机械臂示教中心配置点位和检测序列。
4. 切换到自动检测流程。
5. 点击开始检测，执行移动、拍照、识别和结果显示。

## 如何单独测试 dummy 算法脚本

在项目根目录执行：

```powershell
python CV_Project\scripts\infer_one_dummy.py --image CV_Project\scripts\infer_one_dummy.py --pose P1 --product-id PART001
```

如果传入的图片路径存在，脚本会向 stdout 输出 JSON。错误信息输出到 stderr。

## JSON 输出协议

OK 示例：

```json
{
  "ok": true,
  "label": "OK",
  "score": 0.0,
  "threshold": 0.5,
  "defect_type": "none",
  "message": "dummy检测正常",
  "image_path": "",
  "heatmap_path": "",
  "pose": "",
  "product_id": ""
}
```

NG 示例：

```json
{
  "ok": false,
  "label": "NG",
  "score": 0.9,
  "threshold": 0.5,
  "defect_type": "dummy_defect",
  "message": "dummy检测到缺陷",
  "image_path": "",
  "heatmap_path": "",
  "pose": "",
  "product_id": ""
}
```

## 未上传到 GitHub 的内容

以下内容为本地数据、SDK、模型或运行产物，不上传到 GitHub：

- `CV_Project/datasets/`
- `camera/captures/`
- `camera/inspection_captures/`
- `CV_Project/pre_trained/`
- `CV_Project/results/`
- `CV_Project/output_results/`
- `CV_Project/bad_records/`
- `camera/MvImport/`
- `CV_Project/MvImport/`
- 模型权重：`*.pt`、`*.pth`、`*.ckpt`、`*.onnx`、`*.engine`
- 图片文件：`*.png`、`*.jpg`、`*.bmp`
- Python 缓存与虚拟环境

## 后续计划

1. 接入 PatchCore / EfficientAD。
2. 多点位模型管理。
3. 热力图输出。
4. 整件产品检测报告。
5. 现场联调。
