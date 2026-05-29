# PROJECT_INDEX.md

## 1. 项目一句话目标

本项目用于汽车差速器壳体工业视觉检测：由 GUI 控制 EC66 机械臂到达检测点位，触发海康工业相机拍照，再调用视觉算法脚本返回 OK/NG/ERROR 结果。

## 2. 当前系统主流程

```text
GUI 自动检测页
  -> 读取工件型号、检测序列、算法配置
  -> EC66 机械臂移动到 pose
  -> 海康相机软件触发拍照
  -> 保存检测图片
  -> subprocess 调用 CV_Project 算法脚本
  -> 算法 stdout 返回 JSON
  -> GUI 展示单点位结果和整件 PASS/FAIL
  -> 可选：数据采集模式归档图片并追加 manifest.csv
```

当前已支持机械臂模拟模式：只跳过真实机械臂运动，不模拟相机，仍要求真实海康相机可用。

## 3. 顶层目录地图

```text
camera_and_algorithm/
  README.md
  PROJECT_INDEX.md
  CODEX_HANDOFF.md
  PROJECT_OVERVIEW.md
  AGENTS.md
  algorithm_config.example.json
  requirements.txt
  .github/workflows/python-smoke-test.yml
  camera/
  CV_Project/
```

不要默认扫描数据集、结果、模型权重、SDK、采集图片和缓存目录。

## 4. 核心文件地图

- `camera/vision_robot_inspection_gui.py`：当前主 GUI 和自动检测流程入口。
- `camera/hik_camera_gui.py`：独立海康相机 GUI 验证工具。
- `camera/ec66_hik_single_pose_capture.py`：单点位 EC66 + 海康拍照硬件验证脚本。
- `algorithm_config.example.json`：算法 profile、工件型号、位姿模型映射示例。
- `CV_Project/scripts/infer_one_dummy.py`：当前默认稳定 dummy 算法接口。
- `CV_Project/scripts/infer_one_patchcore.py`：PatchCore 单图推理实验接口。
- `CV_Project/scripts/infer_one_fastflow.py`：FastFlow 单图推理实验接口。
- `.github/workflows/python-smoke-test.yml`：轻量 CI smoke test。

## 5. camera/ 关键类与职责

主要集中在 `camera/vision_robot_inspection_gui.py`：

- `HikCamera`：海康相机 SDK 封装，负责枚举、打开、关闭、取流、软件触发和单帧采集。
- `CameraUIController`：相机 GUI 面板，负责设备选择、预览、曝光/增益、触发、保存图片，以及自动检测拍照入口 `capture_for_inspection()`。
- `RobotUIController`：EC66 连接、点位示教、检测序列管理和真实运动执行。不要轻易修改 `send_cmd()` 和 `execute_movement()`。
- `DefectDetector`：算法调用统一入口，读取 algorithm config，解析 profile，并通过 subprocess 调用算法脚本。
- `InspectionUIController`：自动检测主流程、结果表格、数据采集模式、机械臂模拟模式和检测报告保存。
- `AlarmLightController`：当前为报警灯状态日志/占位控制。

## 6. CV_Project/ 关键脚本与职责

### 当前 GUI 链路相关

- `scripts/infer_one_dummy.py`：稳定 dummy 推理脚本，stdout 输出 GUI 兼容 JSON。
- `scripts/infer_one_patchcore.py`：PatchCore 单图推理脚本，支持 ckpt、threshold、device，当前仍为实验能力。
- `scripts/infer_one_fastflow.py`：FastFlow 单图推理脚本，支持 checkpoint、threshold、device、heatmap 输出，当前未默认接 GUI。
- `scripts/check_model_ready.py`：检查模型文件、后缀和 torch/anomalib 环境，不加载模型。

### 可复现实验

- `scripts/train_fastflow_mvtec_metal_nut.py`：FastFlow + MVTec metal_nut 实验，默认 check-only，只有 `--run-train` 才训练。
- `scripts/export_fastflow_demo_assets.py`：从已有 FastFlow 结果导出会议演示素材，不训练、不推理。

### 历史/临时实验

- `train_my_data.py`：早期 PatchCore 自定义差速器数据训练脚本。
- `train_my_data_efficientAD.py`：早期 EfficientAD 自定义差速器数据训练脚本。
- `compare_models.py`：MVTec bottle 上的 SimpleNet/Supersimplenet 训练实验。
- `compare_nut.py`：MVTec metal_nut 上 SimpleNet 与 EfficientAD 对比实验。
- `run_demo.py`：PatchCore + MVTec bottle 早期 demo。
- `speed_test.py`：随机输入下 EfficientAD 与 PatchCore 粗略测速。
- `demo_generalization.py`：二维 toy demo，用于解释 SimpleNet 类截断损失思想。

### 环境/硬件测试

- `gpu_test.py`：PyTorch CUDA 环境检查。
- `camera_test.py`：海康 SDK 导入和设备枚举测试。
- `camera/test.py`：底层海康取一帧测试，会访问相机、保存图片并弹窗。

## 7. algorithm_config 配置结构

`DefectDetector` 优先读取本地 `algorithm_config.json`，不存在时读取 `algorithm_config.example.json`，再失败则使用内置 dummy 配置。

主要字段：

- `active_profile`：全局默认算法 profile。
- `active_workpiece_type`：GUI 默认工件型号。
- `profiles`：算法运行方式、脚本路径、Python/conda 环境、模型路径、阈值、超时等。
- `workpiece_models`：工件型号配置。
- `default_profile`：某个工件型号的默认算法 profile。
- `pose_profiles`：某个工件型号下，按 pose 覆盖算法、模型、阈值或超时。

真实模型路径、现场阈值和本地环境应放在被 `.gitignore` 忽略的 `algorithm_config.json`，不要提交到 example。

## 8. 工件型号 + 位姿 + 模型权重选择逻辑

算法选择回退顺序：

1. 若 `workpiece_models[workpiece_type].pose_profiles[pose_name]` 存在，则使用该位姿专用配置。
2. 否则使用 `workpiece_models[workpiece_type].default_profile`。
3. 否则使用全局 `active_profile`。
4. 若配置异常或脚本缺失，GUI 返回 ERROR；若配置文件完全不可用，则回退内置 dummy。

推荐后续训练和部署按 `workpiece_type + pose_name` 独立管理模型，因为每个检测位姿的外观分布可能不同。

## 9. dummy / PatchCore / FastFlow / EfficientAD 当前状态

- dummy：当前默认稳定工程链路验证脚本，不代表真实缺陷检测能力。
- PatchCore：单图推理脚本已存在，但真实缺陷模型仍不稳定，不应默认接入 GUI 生产流程。
- FastFlow：已有 MVTec metal_nut 复现实验、单图推理脚本和演示素材导出工具；当前仍是实验能力。
- EfficientAD：已有早期训练脚本和对比实验脚本，但未接入 GUI 默认检测链路。

当前训练优先级应先补充真实 OK 数据，尤其是每个 `workpiece_type + pose_name` 的 `train/good`。

## 10. GitHub Actions 作用

`.github/workflows/python-smoke-test.yml` 在 push 和 pull request 时运行轻量检查：

```powershell
python -m py_compile camera/vision_robot_inspection_gui.py
python -m py_compile CV_Project/scripts/infer_one_dummy.py
python scripts/smoke_test_dummy.py
```

CI 不连接相机、不连接机械臂、不运行 PatchCore/FastFlow/EfficientAD、不训练模型。

## 11. 常用测试命令

轻量本地检查：

```powershell
python -m py_compile camera/vision_robot_inspection_gui.py
python scripts/smoke_test_dummy.py
git diff --check
```

FastFlow 环境检查，不训练：

```powershell
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\train_fastflow_mvtec_metal_nut.py --check-only
```

GPU 环境检查：

```powershell
python CV_Project\gpu_test.py
```

硬件脚本只在明确允许连接设备时运行：

```powershell
python camera\hik_camera_gui.py
python camera\ec66_hik_single_pose_capture.py
```

## 12. 新 Codex 对话优先阅读文件

建议新对话先读取：

1. `AGENTS.md`
2. `PROJECT_INDEX.md`
3. `CODEX_HANDOFF.md`
4. `README.md`
5. `algorithm_config.example.json`
6. `camera/vision_robot_inspection_gui.py`
7. `CV_Project/scripts/infer_one_dummy.py`
8. 需要算法实验时再读取 `infer_one_patchcore.py` 或 `infer_one_fastflow.py`

## 13. 禁止读取的大目录

除非用户明确允许，不要读取或扫描：

- `datasets/`
- `CV_Project/datasets/`
- `results/`
- `CV_Project/results/`
- `output_results/`
- `CV_Project/output_results/`
- `pre_trained/`
- `CV_Project/pre_trained/`
- `MvImport/`
- `camera/MvImport/`
- `CV_Project/MvImport/`
- `captures/`
- `camera/captures/`
- `inspection_captures/`
- `camera/inspection_captures/`
- `bad_records/`
- `CV_Project/bad_records/`
- `anomalib/`
- `CV_Project/anomalib/`
- `__pycache__/`
- `.venv/`
- `venv/`
- 图片文件
- 模型权重：`.ckpt`、`.pt`、`.pth`、`.onnx`、`.engine`

## 14. 后续推荐任务

1. 用真实相机 + 机械臂模拟模式验证自动检测和数据采集模式。
2. 用 1 个确认 OK 工件采集每个 pose 的 `train/good` 图片。
3. 检查 `CV_Project/datasets_collected/manifest.csv` 是否完整记录 `workpiece_type`、`product_id`、`pose_name`、`split`、`label` 和路径。
4. 数据量足够后，按 `workpiece_type + pose_name` 训练 PatchCore / EfficientAD / FastFlow 对比模型。
5. 只在真实模型稳定后，把本地 `algorithm_config.json` 指向对应 profile；不要修改 example 暴露真实路径。
6. 若要清理历史实验脚本，先只分类记录，不要直接删除。
