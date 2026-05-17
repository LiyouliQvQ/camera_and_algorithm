```text
# AGENTS.md

## 项目背景

这是一个汽车差速器壳体工业视觉检测项目。

项目由两个主要子目录组成：

- `camera/`：机械臂与海康工业相机控制程序。包含 Tkinter GUI、艾利特 EC66 机械臂通信、海康 MVS SDK 相机取流、自动拍照流程。
- `CV_Project/`：工业视觉检测算法实验项目。包含异常检测、训练脚本、推理脚本、模型、数据集和测试代码。

目标是让 `camera/` 中的 GUI 按照流程控制机械臂运动到指定点位，调用海康相机拍照，然后调用 `CV_Project/` 中的算法程序完成 OK/NG 检测。

## 工作原则

1. 不要一次性扫描整个项目。
2. 不要主动读取大型目录、数据集目录、模型权重目录、SDK 目录。
3. 每次任务只处理一个小目标。
4. 修改代码前，先说明计划和要修改的文件。
5. 优先保持现有 GUI、机械臂通信、相机 SDK 逻辑稳定。
6. 先使用最小闭环验证，不要一上来大规模重构。

## 默认不要读取或修改的目录

除非用户明确要求，否则不要读取、分析或修改以下目录：

- `camera/MvImport/`
- `camera/captures/`
- `camera/inspection_captures/`
- `CV_Project/MvImport/`
- `CV_Project/anomalib/`
- `CV_Project/datasets/`
- `CV_Project/pre_trained/`
- `CV_Project/results/`
- `CV_Project/output_results/`
- `CV_Project/bad_records/`
- `__pycache__/`
- `.venv/`
- `venv/`

## 优先阅读的关键文件

第一次理解项目时，只优先阅读这些小范围文件：

### camera 目录

- `camera/vision_robot_inspection_gui.py`
- `camera/ec66_hik_single_pose_capture.py`
- `camera/hik_camera_gui.py`

### CV_Project 目录

- `CV_Project/README.md`
- `CV_Project/config.py`
- `CV_Project/main_system.py`
- `CV_Project/vision_server.py`
- `CV_Project/vision_server_ai.py`
- `CV_Project/robot_client.py`
- `CV_Project/train_my_data.py`
- `CV_Project/train_my_data_efficientAD.py`

如果这些文件不足以判断，再向用户请求允许读取其他文件。

## 禁止轻易修改的内容

除非用户明确要求，不要修改：

- 海康 MVS SDK 导入逻辑
- `MvImport/` 目录
- EC66 机械臂 socket 通信底层函数
- 已经可以正常运行的相机预览、打开、关闭、取流逻辑
- 已有数据集和模型权重文件

## 推荐集成方式

优先使用 `subprocess + JSON` 方式让 `camera/` 调用 `CV_Project/` 的算法脚本。

推荐流程：

1. `camera/` 控制 EC66 移动到点位。
2. `camera/` 调用海康相机软件触发拍照。
3. 图片保存到 `camera/inspection_captures/`。
4. `camera/` 调用 `CV_Project/scripts/infer_one.py` 或已有推理脚本。
5. 算法脚本输出 JSON。
6. GUI 读取 JSON 并显示 OK/NG、score、message、heatmap_path。

## 推荐算法接口输出格式

算法推理脚本应返回 JSON，字段包括：

```json
{
  "ok": true,
  "label": "OK",
  "score": 0.0,
  "threshold": 0.5,
  "defect_type": "none",
  "message": "检测正常",
  "image_path": "",
  "heatmap_path": ""
}xxxxxxxxxx camera_and_algorithm/  camera/    vision_robot_inspection_gui.py    ec66_hik_single_pose_capture.py    hik_camera_gui.py    MvImport/    captures/    inspection_captures/  CV_Project/    config.py    main_system.py    vision_server.py    vision_server_ai.py    robot_client.py    train_my_data.py    train_my_data_efficientAD.py    anomalib/    datasets/    pre_trained/    results/    output_results/text