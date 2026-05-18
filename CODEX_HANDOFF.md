# Codex Handoff

本文档是给 Codex 后续继续开发时读取的上下文浓缩文件，不是普通用户文档。

## 当前项目背景

这是一个汽车差速器壳体工业视觉检测项目。目标是在 `camera/` 中通过 Tkinter GUI 控制艾利特 EC66 机械臂运动到指定点位，调用海康工业相机拍照，再调用 `CV_Project/` 中的视觉算法完成 OK/NG 检测。

项目目前优先追求最小闭环和现场稳定性，不进行大规模重构。

GitHub 仓库地址：

```text
https://github.com/LiyouliQvQ/camera_and_algorithm
```

## 当前目录结构

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
    MvImport/                  # 本地 SDK，已忽略
    captures/                  # 本地采集图，已忽略
    inspection_captures/       # 本地检测采图，已忽略
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
    MvImport/                  # 本地 SDK，已忽略
    datasets/                  # 本地数据集，已忽略
    pre_trained/               # 本地预训练权重，已忽略
    results/                   # 本地训练/推理结果，已忽略
    output_results/            # 本地输出结果，已忽略
    bad_records/               # 本地 NG 记录，已忽略
```

## 已完成工作

- 初始化根 Git 仓库并推送到 GitHub。
- 将 `CV_Project` 从嵌套 Git 仓库改为根仓库下的普通目录。
- 将原 `CV_Project/.git` 备份为 `CV_Project/.git_backup_before_root_upload/`，并通过 `.gitignore` 忽略。
- 配置 `.gitignore`，排除数据集、采集图片、运行结果、模型权重、SDK、缓存和环境文件。
- 新增 `CV_Project/scripts/infer_one_dummy.py`。
- 修改 `camera/vision_robot_inspection_gui.py` 中的 `DefectDetector.detect()`，通过 `subprocess + JSON` 调用 dummy 算法脚本。
- 完成最小闭环：
  `camera GUI -> 机械臂移动 -> 海康相机拍照 -> subprocess 调用 CV_Project/scripts/infer_one_dummy.py -> 返回 JSON -> GUI 显示 OK/NG`

## 关键文件说明

- `camera/vision_robot_inspection_gui.py`
  - 当前主 GUI。
  - 包含 `HikCamera`、`CameraUIController`、`RobotUIController`、`DefectDetector`、`InspectionUIController`。
  - `DefectDetector.detect()` 是 camera 调用算法的最小改动入口。

- `camera/hik_camera_gui.py`
  - 独立海康相机 GUI 示例。
  - 用于相机预览、触发和保存图片验证。

- `camera/ec66_hik_single_pose_capture.py`
  - 单点位机械臂运动和相机拍照脚本。
  - 用于硬件单点闭环验证。

- `CV_Project/scripts/infer_one_dummy.py`
  - 当前算法侧 dummy 单图推理入口。
  - 接收 `--image`、`--pose`、`--product-id`。
  - stdout 输出 JSON，stderr 输出日志和错误。

- `CV_Project/vision_server_ai.py`
  - 算法推理服务骨架，目前仍偏演示。

- `CV_Project/train_my_data.py`
  - PatchCore 或异常检测训练入口之一。

- `CV_Project/train_my_data_efficientAD.py`
  - EfficientAD 训练入口之一。

## camera 与 CV_Project 的集成方式

当前推荐并已采用：

```text
subprocess + JSON
```

原因：

- 避免 Tkinter GUI、海康 SDK、机械臂通信与 PyTorch/anomalib 环境强耦合。
- 算法脚本异常时，GUI 可以返回 `ERROR`，不直接崩溃。
- 后续真实模型可以在 `CV_Project` 内部替换实现，不影响 GUI 主流程。

当前调用路径：

```text
camera/vision_robot_inspection_gui.py
  DefectDetector.detect()
    -> subprocess.run(sys.executable, CV_Project/scripts/infer_one_dummy.py, ...)
    -> json.loads(stdout)
    -> return result dict to InspectionUIController
```

## dummy 算法闭环说明

`CV_Project/scripts/infer_one_dummy.py` 参数：

```text
--image       必填，图片路径
--pose        可选，点位名
--product-id  可选，工件编号
```

判定规则：

- `Path(image).stem.lower()` 包含 `ng`、`bad`、`defect` 时返回 NG。
- 其他情况返回 OK。

输出字段：

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

GUI 侧失败兜底：

- 脚本不存在
- subprocess 执行失败
- 超时
- JSON 解析失败

以上情况返回 `label="ERROR"`，GUI 不崩溃。

## 已知约束

后续开发必须遵守：

- 不要修改 `camera/MvImport/`。
- 不要修改 `CV_Project/MvImport/`。
- 不要修改海康 SDK 底层导入、取流、打开、关闭、预览逻辑，除非用户明确要求。
- 不要修改 EC66 机械臂 socket 通信底层函数，尤其是 `RobotUIController.send_cmd()` 和 `RobotUIController.execute_movement()`。
- 不要读取或扫描大型目录：
  - `CV_Project/datasets/`
  - `CV_Project/pre_trained/`
  - `CV_Project/results/`
  - `CV_Project/output_results/`
  - `CV_Project/bad_records/`
  - `camera/captures/`
  - `camera/inspection_captures/`
  - `camera/MvImport/`
  - `CV_Project/MvImport/`
- 不要删除本地数据集、图片、模型或 SDK 文件。
- 默认保持最小闭环验证，不做大规模重构。

## 下一步建议任务

1. 为真实算法新增 `CV_Project/scripts/infer_one.py`，保持与 dummy 脚本相同 JSON 协议。
2. 在 `DefectDetector` 中增加算法脚本路径配置，支持 dummy 与真实推理切换。
3. 接入 PatchCore / EfficientAD 单图推理。
4. 增加 heatmap 输出字段并在 GUI 中显示或链接。
5. 增加多点位模型管理，例如按 pose_name 选择不同模型或阈值。
6. 增加整件产品检测报告，汇总多点位 OK/NG、score、缺陷类型和图片路径。
7. 现场联调机械臂节拍、相机曝光、稳定等待时间和算法耗时。

## 推荐给 Codex 的后续提示词

```text
请基于 CODEX_HANDOFF.md 继续开发当前项目。

只处理一个小目标，不要扫描大型目录，不要读取 datasets/pre_trained/results/output_results/bad_records/MvImport/captures/inspection_captures。

优先保持 camera/vision_robot_inspection_gui.py 中现有 GUI、海康相机 SDK 逻辑、EC66 机械臂通信逻辑稳定。

当前集成方式是 subprocess + JSON：
camera/vision_robot_inspection_gui.py 的 DefectDetector.detect()
调用 CV_Project/scripts/infer_one_dummy.py。

下一步请在不破坏 dummy 闭环的前提下，设计或实现真实算法 infer_one.py，并保持 JSON 输出协议兼容。
修改代码前先说明计划和要修改的文件。
```

## 当前 GitHub 仓库

```text
https://github.com/LiyouliQvQ/camera_and_algorithm
```
