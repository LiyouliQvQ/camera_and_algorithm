# 汽车差速器壳体工业视觉检测系统

## 文档导航

- `PROJECT_INDEX.md`：项目地图和 Codex 接力优先入口，包含主流程、核心文件、算法脚本分级、配置回退逻辑、禁读目录和后续建议。
- `CODEX_HANDOFF.md`：最近开发记录、验证状态和下一步交接说明。
- `PROJECT_OVERVIEW.md`：项目目标与整体结构的简要说明。
- `algorithm_config.example.json`：算法 profile、工件型号和位姿模型映射示例；真实现场配置请放在被忽略的 `algorithm_config.json`。

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
  `camera GUI -> 机械臂移动 -> 海康相机拍照 -> 读取算法配置 -> subprocess 调用 active_profile 脚本 -> 返回 JSON -> GUI 显示 OK/NG`
- dummy 算法脚本支持 OK/NG 分支验证。
- 每次自动检测结束后生成轻量 JSON 报告，默认保存到 `camera/inspection_reports/`。
- 自动检测流程已增加运行日志、结果标准化、整件最终判定和最近报告路径查看。

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
5. `DefectDetector.detect()` 读取 `algorithm_config.json` 或 `algorithm_config.example.json` 中的 `active_profile`。
6. GUI 通过 `subprocess.run()` 调用当前 profile 对应的算法脚本，默认是 `CV_Project/scripts/infer_one_dummy.py`。
7. 算法脚本输出 JSON。
8. GUI 解析 JSON 并显示 `OK`、`NG` 或 `ERROR`。
9. GUI 汇总整件产品最终结果，并保存 JSON 检测报告。

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
6. 检查结果表格中的点位、图片、结果、score、threshold、缺陷类型和说明。
7. 检测结束后点击“最近报告路径”，确认 JSON 报告保存位置。

## 如何单独测试 dummy 算法脚本

在项目根目录执行 OK 分支测试：

```powershell
python CV_Project\scripts\infer_one_dummy.py --image CV_Project\scripts\infer_one_dummy.py --pose P1 --product-id PART001
```

NG 分支测试可以传入任意存在且文件名主体包含 `ng`、`bad` 或 `defect` 的文件，例如临时创建一个轻量文本文件，测试后删除：

```powershell
New-Item -ItemType File -Force -Path CV_Project\scripts\tmp_ng_probe.txt
python CV_Project\scripts\infer_one_dummy.py --image CV_Project\scripts\tmp_ng_probe.txt --pose P_NG --product-id PART_NG
Remove-Item -Force -Path CV_Project\scripts\tmp_ng_probe.txt
```

脚本 stdout 只输出 JSON。日志和错误信息应输出到 stderr，避免 GUI 解析 stdout 失败。

## 算法调用配置

GUI 启动后会优先读取根目录 `algorithm_config.json`，如果不存在则读取 `algorithm_config.example.json`；两者都不存在时，自动回退到 dummy 脚本。

默认示例配置的 `active_profile` 是 `dummy`，不会默认启用实验版 PatchCore。需要本机配置时，先复制一份：

```powershell
Copy-Item algorithm_config.example.json algorithm_config.json
```

切换算法时修改 `algorithm_config.json` 中的 `active_profile`：

```json
{
  "active_profile": "dummy"
}
```

可选 profile：

- `dummy`：使用当前 Python 调用 `CV_Project/scripts/infer_one_dummy.py`，默认超时 5 秒。
- `patchcore_cv_lab`：使用 `conda run --no-capture-output -n cv_lab python` 调用实验版 `CV_Project/scripts/infer_one_patchcore.py`，需要本机模型路径有效，默认超时 30 秒。

PatchCore 当前仍是实验版，不建议作为正式检测算法接入现场流程。回退到 dummy 时，把 `active_profile` 改回 `dummy` 即可。

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

## 检测报告

GUI 自动检测流程结束后会保存 JSON 报告，默认目录：

```text
camera/inspection_reports/
```

报告包含：

- `product_id`
- `workpiece_type`
- `start_time`
- `end_time`
- `final_label`
- `final_ok`
- `algorithm_script`
- 每个点位的检测结果
- 运行日志

每个点位结果会尽量保留以下字段：

- `idx`
- `pose`
- `workpiece_type`
- `image_path`
- `label`
- `score`
- `threshold`
- `defect_type`
- `message`
- `heatmap_path`
- `algorithm_script`
- `elapsed_ms`

最终判定规则：

- 任一点位 `ERROR`，整件产品 `ERROR`。
- 否则任一点位 `NG`，整件产品 `NG`。
- 全部点位 `OK`，整件产品 `OK`。

## 多工件型号与多位姿算法配置

算法配置分为两层：

- `profiles`：定义算法脚本如何运行，例如 `dummy`、`patchcore_default`、`patchcore_cv_lab`。
- `workpiece_models`：定义工件型号，以及每个型号下不同 `pose_name` 使用的 profile、模型路径、threshold 和 timeout。

`algorithm_config.example.json` 是可提交的模板；真实现场路径、真实模型权重和阈值请复制到本地 `algorithm_config.json` 后修改。`algorithm_config.json` 已加入 `.gitignore`，不要提交。

默认配置保持：

```json
{
  "active_profile": "dummy",
  "active_workpiece_type": "demo_default"
}
```

`demo_default` 的 `default_profile` 必须保持为 `dummy`，这样 GUI 默认不会误调用 PatchCore / EfficientAD。

同一工件型号下，可以按机械臂位姿配置不同模型：

```json
{
  "workpiece_models": {
    "differential_housing_v1": {
      "default_profile": "patchcore_default",
      "pose_profiles": {
        "P01_front": {
          "profile": "patchcore_default",
          "model": "D:/path/to/P01_front/model.ckpt",
          "threshold": 0.45,
          "timeout": 30
        }
      }
    }
  }
}
```

选择逻辑：

1. 优先使用 `workpiece_type + pose_name` 对应的 `pose_profiles`。
2. 如果该位姿未配置，回退到当前工件型号的 `default_profile`。
3. 如果工件型号不存在，回退到全局 `active_profile`。
4. 如果全局 profile 也无效，最终回退到内置 dummy。

如需从 dummy 切换到实验 PatchCore，可在本地 `algorithm_config.json` 中把某个工件型号的 `default_profile` 或某个 `pose_profiles` 项改为 `patchcore_default` / `patchcore_cv_lab`，并填写本机真实模型路径与阈值。当前 PatchCore / EfficientAD 仍是实验选项，不默认启用。

## 数据采集模式

自动检测页提供“数据采集模式”，用于在真实相机和真实机械臂流程跑通后，高效采集后续 PatchCore / EfficientAD 训练需要的图片。该模式只做图片归档和 `manifest.csv` 记录，不训练模型、不调用 PatchCore、不需要画框、mask 或人工标注。

使用方式：

1. 在自动检测页选择当前 `workpiece_type`。
2. 勾选“启用数据采集模式”。
3. 填写 `batch_id`，用于区分采集批次。
4. 选择采集类型：`train/good`、`test/good`、`test/defect`、`raw/unlabeled`。
5. 执行原有自动检测流程。每个点位拍照成功后，GUI 会复制图片到数据集采集目录，并继续原有 dummy 检测流程。

默认采集目录：

```text
CV_Project/datasets_collected/
```

目标目录结构：

```text
CV_Project/datasets_collected/<workpiece_type>/<split>/<label>/<pose_name>/
```

示例：

```text
CV_Project/datasets_collected/differential_housing_v1/train/good/P01_front/
```

文件名格式：

```text
YYYYMMDD_HHMMSS_productid_pose_originalname.png
```

`train/good` 是后续无监督异常检测训练的主要数据来源；`test/good` 和 `test/defect` 用于后续模型评估；`raw/unlabeled` 用于临时归档尚未确认用途的图片。

采集 manifest 位于：

```text
CV_Project/datasets_collected/manifest.csv
```

字段包括：

- `timestamp`
- `workpiece_type`
- `product_id`
- `pose_name`
- `split`
- `label`
- `batch_id`
- `source_image_path`
- `target_image_path`

`CV_Project/datasets_collected/` 已加入 `.gitignore`，采集图片和 manifest 不提交到 GitHub。

## 机械臂模拟模式

自动检测页提供“机械臂模拟模式”，用于在没有真实 EC66 机械臂连接时验证 GUI 自动检测流程。该模式默认关闭；关闭时仍保持原有真实机械臂连接和运动逻辑。

启用后：

- 可以在未连接 EC66 机械臂时开始自动检测。
- 不调用真实机械臂 socket 命令。
- 不调用 `RobotUIController.execute_movement()`。
- 每个检测位姿会记录“模拟机械臂移动到点位 xxx”，并短暂等待约 0.2 秒。
- 点位仍必须存在于 `saved_poses.json`，否则继续按原有逻辑返回 `ERROR`。
- 不模拟相机，仍要求真实海康相机已打开，拍照仍走 `capture_for_inspection()`。
- 不影响数据采集模式；如果同时启用数据采集模式，拍照成功后仍会复制图片并追加 manifest。

该模式适合“无机械臂但有相机”的桌面或现场调试，用来验证：

```text
GUI 自动检测流程 -> 真实相机拍照 -> dummy/配置算法调用 -> 结果显示 -> 报告保存 -> 可选数据采集归档
```

## 如何接入 PatchCore / EfficientAD

建议保持现有 `subprocess + JSON` 集成方式，不直接把 GUI 与深度学习环境强绑定。

推荐步骤：

1. 在 `algorithm_config.json` 中新增或切换算法 profile。
2. 保持与 `infer_one_dummy.py` 相同的命令行参数：`--image`、`--pose`、`--product-id`。
3. 加载 PatchCore / EfficientAD 模型并对单张图片推理。
4. stdout 只输出兼容 JSON，字段至少包含 `ok`、`label`、`score`、`threshold`、`defect_type`、`message`、`image_path`、`heatmap_path`、`pose`、`product_id`。
5. 如果生成热力图，将路径写入 `heatmap_path`。
6. GUI 侧优先只通过配置切换算法脚本，不要改机械臂和相机底层。
7. 先用单图脚本验证 OK/NG/ERROR，再接入 GUI 完整流程。

## FastFlow + MVTec AD metal_nut 实验记录

`CV_Project/scripts/train_fastflow_mvtec_metal_nut.py` 已完成一次 FastFlow + MVTec AD `metal_nut` 的 1 epoch 流程验证，包含 `fit`、`test`、`predict`。该实验使用 `cv_lab` 环境：`torch 2.5.1+cu121`、`anomalib 2.3.0dev`、CUDA 可用，GPU 为 `NVIDIA GeForce RTX 3060 Ti`。

Windows PowerShell 运行前需要设置 UTF-8 环境变量：

```powershell
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONLEGACYWINDOWSSTDIO="0"
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\train_fastflow_mvtec_metal_nut.py --run-train --max-epochs 1 --batch-size 4 --image-size 256 --pre-trained false
```

当前 1 epoch 离线指标仅用于流程验证，不代表最终检测效果：

```text
image_AUROC: 0.5171065330505371
image_F1Score: 0.8888888955116272
pixel_AUROC: 0.7789766192436218
pixel_F1Score: 0.3588261902332306
```

输出目录为 `CV_Project/results/fastflow_mvtec_metal_nut`。不要提交 `CV_Project/results/`、`CV_Project/datasets/`、模型权重、预测图或热力图。下一步建议新增 `CV_Project/scripts/infer_one_fastflow.py`，封装单图推理 JSON 输出。

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
4. 完善整件产品检测报告与结果追溯。
5. 现场联调。
