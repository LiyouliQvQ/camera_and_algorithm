# Codex Handoff

## 本次更新：GUI 算法模式下拉框第一版（2026-05-29）

本次完成：
- 在 `camera/vision_robot_inspection_gui.py` 自动检测页面的“工件型号”附近新增“算法模式”下拉框。
- 下拉选项与内部 profile 映射：
  - `自动配置` -> `auto`
  - `Dummy` -> `dummy`
  - `PatchCore` -> `patchcore_default`
  - `EfficientAD` -> `efficientad_default`
  - `FastFlow` -> `fastflow_default`
- `auto` 保持原有 `workpiece_type + pose_name` 配置解析逻辑。
- `dummy` 强制使用 dummy profile，作为安全工程链路验证模式。
- `patchcore_default` / `efficientad_default` / `fastflow_default` 会优先匹配当前工件型号 + 点位下同 profile 配置，找不到再回退对应全局 profile；profile 或脚本缺失时返回 `label="ERROR"`，GUI 不崩溃。
- 检测结果和 JSON 报告中补充 `algorithm_mode`，并保留 `algorithm_profile` / `algorithm_profile_source`。
- `algorithm_config.example.json` 补充 `efficientad_default` 和 `fastflow_default` 示例 profile；`active_profile`、`active_workpiece_type` 和 `demo_default.default_profile` 仍保持 dummy 安全默认。
- FastFlow 示例使用 `CV_Project/scripts/infer_one_fastflow.py`、`mode=conda`、`conda_env=cv_lab`，并预留 `checkpoint` 字段。
- EfficientAD 示例使用预留脚本 `CV_Project/scripts/infer_one_efficientad.py`；脚本当前可以不存在，选择后应返回 ERROR 而不是崩溃。
- 更新 `README.md` 和 `PROJECT_INDEX.md`，记录 GUI 算法模式选择，但默认仍不启用真实模型。

本次限制：
- 未运行 PatchCore / FastFlow / EfficientAD。
- 未训练模型。
- 未连接相机或机械臂。
- 未读取数据集、结果目录、输出目录、模型权重或图片文件。
- 未修改海康 SDK、机械臂通信底层、算法脚本、workflow 或 requirements。

## 本次更新：FastFlow 实验文件提交前整理（2026-05-29）

本次完成：
- FastFlow 5 个实验相关文件已准备纳入仓库：
  - `CV_Project/scripts/README_fastflow_infer.md`
  - `CV_Project/scripts/README_fastflow_mvtec.md`
  - `CV_Project/scripts/export_fastflow_demo_assets.py`
  - `CV_Project/scripts/infer_one_fastflow.py`
  - `CV_Project/scripts/train_fastflow_mvtec_metal_nut.py`
- 修复 `train_fastflow_mvtec_metal_nut.py` 顶部 docstring 的 Windows 路径 `SyntaxWarning: invalid escape sequence`，仅改为 raw docstring，未修改训练逻辑或默认参数。
- 更新 `PROJECT_INDEX.md`：记录 FastFlow 实验文件准备入库、当前不默认接 GUI、不进入 GitHub Actions、训练/推理/素材导出都需手动运行。
- 明确 `export_fastflow_demo_assets.py` 会读取本地 `CV_Project/results/` 和 `CV_Project/datasets/`，不能放入 CI。

本次验证：
- `python -m py_compile CV_Project\scripts\infer_one_fastflow.py`：通过
- `python -m py_compile CV_Project\scripts\train_fastflow_mvtec_metal_nut.py`：通过，SyntaxWarning 已修复
- `python -m py_compile CV_Project\scripts\export_fastflow_demo_assets.py`：通过
- `git diff --check`：通过

本次限制：
- 未运行训练。
- 未运行推理。
- 未运行 `export_fastflow_demo_assets.py`。
- 未读取数据集、结果目录、输出目录、模型权重或图片文件。
- 未修改 GUI、相机或机械臂代码。

## 本次更新：新增项目索引文档（2026-05-29）

本次完成：
- 新增 `PROJECT_INDEX.md`，作为新 Codex 对话和人工接力的项目地图。
- 索引内容包括：项目目标、当前主流程、顶层目录地图、核心文件地图、`camera/` 关键类、`CV_Project/` 关键脚本、`algorithm_config` 配置结构、工件型号 + 位姿 + 模型选择逻辑、dummy/PatchCore/FastFlow/EfficientAD 当前状态、GitHub Actions、常用测试命令、优先阅读文件、禁读目录和后续推荐任务。
- `README.md` 新增“文档导航”小节，指向 `PROJECT_INDEX.md`、`CODEX_HANDOFF.md`、`PROJECT_OVERVIEW.md` 和 `algorithm_config.example.json`。

本次限制：
- 未修改任何 Python 代码。
- 未修改 `algorithm_config.example.json`。
- 未修改 workflow。
- 未读取或修改数据集、结果、模型权重、SDK、采集图片或 anomalib 大目录。

建议：
- 后续新对话先读取 `AGENTS.md`、`PROJECT_INDEX.md`、`CODEX_HANDOFF.md`，再按任务需要读取具体代码文件。

## 本次更新：Fastflow 30 epoch 组会展示素材导出（2026-05-26）

本次完成：
- 新增 `CV_Project/scripts/export_fastflow_demo_assets.py`。
- 基于 FastFlow 30 epoch `pre_trained=True` 结果整理组会 PPT 素材。
- 未使用 1 epoch 指标，未重新训练，未推理。
- 输出目录：`CV_Project/output_results/fastflow_demo_metal_nut`。
- 生成文件：
  - `metrics_summary.md`
  - `metrics_summary.json`
  - `selected_cases.csv`
  - `selected_cases.md`
  - `visualizations/<class>/...png`
- 选择样本：
  - `bent`: `000.png`, `001.png`, `002.png`
  - `color`: `000.png`, `001.png`, `002.png`
  - `flip`: `000.png`, `001.png`, `002.png`
  - `scratch`: `000.png`, `001.png`, `002.png`
  - `good`: `000.png`, `001.png`
- 缺陷类均记录到对应 GT mask 路径；`good` 类无 GT mask。
- 说明：当前导出使用 Anomalib 已生成 visualization 图，不伪造原图/热力图/overlay 拆分。

测试命令：
```powershell
D:\project_environment\envs\cv_lab\python.exe -m py_compile CV_Project\scripts\export_fastflow_demo_assets.py
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\export_fastflow_demo_assets.py
```

注意：
- `CV_Project/output_results/` 已被 `.gitignore` 忽略，不要提交导出的图片和素材。
- 不要提交 `datasets/`、`results/`、模型权重、GT mask、热力图或 prediction 图片。

## 本次更新：Fastflow 单图推理脚本第一版（2026-05-25）

本次完成：
- 新增 `CV_Project/scripts/infer_one_fastflow.py`。
  - 支持 `--image`、`--checkpoint`、`--threshold`、`--pose`、`--product-id`、`--output-dir`、`--device`。
  - stdout 只输出 GUI 兼容 JSON。
  - stderr 输出 Fastflow / Anomalib 调试日志。
  - 图片不存在、checkpoint 不存在、模型加载失败或预测失败时返回 `label="ERROR"`，不让进程崩溃。
  - 推理时使用 `Fastflow(backbone="resnet18", pre_trained=False)`，避免联网下载 timm/Hugging Face 权重。
  - 若预测结果含 `anomaly_map`，会尝试保存灰度 heatmap 到 `--output-dir` 并返回 `heatmap_path`；失败则返回空字符串。
- 新增 `CV_Project/scripts/README_fastflow_infer.md`，记录命令、JSON 协议和注意事项。

本次限制：
- 未修改 `camera/`。
- 未修改 `CV_Project/anomalib/`、`CV_Project/datasets/`、`CV_Project/results/`、`CV_Project/pre_trained/` 或 `MvImport/`。
- 未训练，未批量推理，未提交，未推送。

下一步建议：
- 先用一张明确允许读取的测试图和 `v2/weights/lightning/model.ckpt` 做单图烟测。
- 验证 stdout JSON、stderr 日志、score 提取和 heatmap_path 后，再考虑写入本地 `algorithm_config.json` 的 Fastflow profile。

## 本次更新：Fastflow 1 epoch 流程验证通过（2026-05-25）

本次完成：
- FastFlow + MVTec AD `metal_nut` 已成功完成 `fit`、`test`、`predict`。
- 当前运行环境：
  - `torch 2.5.1+cu121`
  - `anomalib 2.3.0dev`
  - CUDA 可用
  - GPU: `NVIDIA GeForce RTX 3060 Ti`
- Windows PowerShell 成功运行前需要设置 UTF-8 环境变量：
```powershell
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONLEGACYWINDOWSSTDIO="0"
```
- 成功运行命令：
```powershell
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\train_fastflow_mvtec_metal_nut.py --run-train --max-epochs 1 --batch-size 4 --image-size 256 --pre-trained false
```
- 当前指标：
```text
image_AUROC: 0.5171065330505371
image_F1Score: 0.8888888955116272
pixel_AUROC: 0.7789766192436218
pixel_F1Score: 0.3588261902332306
```
- 说明：这些指标只是 `max_epochs=1` 且 `pre_trained=False` 的流程验证结果，不代表最终检测效果。
- 输出目录：`CV_Project/results/fastflow_mvtec_metal_nut`。
- 已确认 `CV_Project/results/` 被 `.gitignore` 忽略；不要提交 `results/`、`datasets/`、模型权重、热力图图片或预测图片。

下一步建议：
- 编写 `CV_Project/scripts/infer_one_fastflow.py`，封装单图推理，并输出与 GUI 兼容的 JSON。
- 继续保持 `subprocess + JSON` 边界，不把 PyTorch/anomalib 直接 import 到 Tkinter GUI 主进程。

## 本次更新：Fastflow 离线预训练开关（2026-05-25）

本次完成：
- 修改 `CV_Project/scripts/train_fastflow_mvtec_metal_nut.py`，新增 `--pre-trained` 参数。
- `--pre-trained` 默认值为 `False`，默认离线运行，不触发 `timm` / Hugging Face 权重下载。
- 布尔解析支持 `true/false`、`1/0`、`yes/no`、`y/n`，避免字符串 `"false"` 被当作 True。
- Fastflow 初始化改为 `Fastflow(backbone="resnet18", pre_trained=args.pre_trained)`。
- 脚本启动时会打印 `pre_trained=False/True`。
- 更新 `CV_Project/scripts/README_fastflow_mvtec.md`，说明离线模式只验证流程，1 epoch 指标不代表真实性能。

FastFlow 1 epoch 首次尝试记录：
- 失败原因：`pre_trained=True` 时，`timm` 尝试联网从 Hugging Face 下载 `resnet18.a1_in1k` 预训练权重，当前环境网络/权限不允许，报 `WinError 10013`。
- 当前解决方案：默认 `pre_trained=False`，先离线跑通 Fastflow fit/test/predict 流程。
- 后续如果追求效果，再处理 `timm` 预训练权重本地缓存或联网下载问题。

本次测试：
```powershell
D:\project_environment\envs\cv_lab\python.exe -m py_compile CV_Project\scripts\train_fastflow_mvtec_metal_nut.py
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\train_fastflow_mvtec_metal_nut.py --check-only
```

未做事项：
- 未训练。
- 未下载数据或权重。
- 未修改 `camera/`。
- 未提交、未推送。

## 本次更新：Fastflow + MVTec AD metal_nut 最小实验脚本准备（2026-05-25）

本次完成：
- 新增 `CV_Project/scripts/train_fastflow_mvtec_metal_nut.py`。
  - 默认只做 check-only，不训练、不下载数据。
  - 使用已确认 API：`MVTecAD`、`Fastflow`、`Engine`。
  - 类名使用 `Fastflow`，不是 `FastFlow`。
  - 默认类别为 `metal_nut`，不是 `hazelnut`。
  - 默认数据根目录：`D:\run_code\camera_and_algorithm\CV_Project\datasets\MVTec`。
  - 默认输出目录：`D:\run_code\camera_and_algorithm\CV_Project\results\fastflow_mvtec_metal_nut`。
  - 只有显式传入 `--run-train` 才会执行训练、测试、预测。
- 新增 `CV_Project/scripts/README_fastflow_mvtec.md`。
  - 记录 `metal_nut` 选择原因、数据放置位置、check-only 命令、1 epoch 小测试命令、输出目录和后续迁移到差速器壳体自采数据的建议。
- 未修改 `camera/`、`CV_Project/anomalib/`、`CV_Project/datasets/`、`CV_Project/pre_trained/`、`CV_Project/results/`、`CV_Project/output_results/`、`CV_Project/bad_records/`。
- 未读取图片、模型权重或训练输出大文件。

当前可运行流程：
```powershell
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\train_fastflow_mvtec_metal_nut.py --check-only
```

1 epoch 小测试命令（仅在 MVTec AD metal_nut 数据集已放好后手动执行）：
```powershell
D:\project_environment\envs\cv_lab\python.exe CV_Project\scripts\train_fastflow_mvtec_metal_nut.py --run-train --max-epochs 1 --batch-size 4 --image-size 256
```

测试命令和结果：
```powershell
D:\project_environment\envs\cv_lab\python.exe -m py_compile CV_Project\scripts\train_fastflow_mvtec_metal_nut.py
```
- 结果：通过。

仍未完成：
- 未下载 MVTec AD 数据集。
- 未训练 Fastflow。
- 未生成模型、可视化图片或预测结果。
- 未接入 GUI。

下一步建议：
- 将 MVTec AD `metal_nut` 放到 `CV_Project\datasets\MVTec\metal_nut`。
- 先运行 check-only，确认 `train/good`、`test`、`ground_truth` 都存在。
- 再手动运行 1 epoch 小测试，观察 `CV_Project\results\fastflow_mvtec_metal_nut` 输出。
- 验证官方 API 链路后，再单独设计差速器壳体自采数据的 Fastflow/Folder 实验入口。

新 Codex 对话启动提示词：
```text
请继续 D:\run_code\camera_and_algorithm 项目。Fastflow + MVTec AD metal_nut 最小实验脚本已新增：CV_Project/scripts/train_fastflow_mvtec_metal_nut.py，说明文档为 CV_Project/scripts/README_fastflow_mvtec.md。后续 Fastflow/Anomalib 命令不要使用 conda run，请直接使用 D:\project_environment\envs\cv_lab\python.exe。不要读取或修改 camera/MvImport、captures、inspection_captures、CV_Project/MvImport、CV_Project/anomalib、datasets、pre_trained、results、output_results、bad_records、图片文件或模型权重，除非用户明确允许。
```

## 本次更新：机械臂模拟模式第一版（2026-05-22）

本次完成：
- 在 `camera/vision_robot_inspection_gui.py` 自动检测页新增“启用机械臂模拟模式”checkbox，默认关闭。
- 新增 `robot_simulation_enabled_var = tk.BooleanVar(value=False)`。
- 新增 `InspectionUIController.is_robot_ready_for_inspection()`：
  - 模拟模式开启时返回 `True`。
  - 模拟模式关闭时返回 `self.robot_app.connected`。
- `start_inspection()` 改为使用 `is_robot_ready_for_inspection()` 做机械臂可用性检查；默认关闭时仍必须连接真实机械臂。
- `_run_inspection_logic()` 在模拟模式开启时不调用 `RobotUIController.execute_movement()`，只记录“模拟机械臂移动到点位 xxx”并 `sleep(0.2)`，随后继续真实相机拍照、算法调用、结果显示、报告保存和可选数据采集归档。
- 点位存在性检查保持不变：`pose_name` 不在 `saved_poses` 中仍按现有逻辑返回 `ERROR`。
- 未修改 `RobotUIController.send_cmd()`、`RobotUIController.execute_movement()` 或任何机械臂 socket 通信底层。
- 未模拟相机；仍要求真实海康相机打开，`capture_for_inspection()` 仍走真实相机。
- 未训练模型，未调用 PatchCore，未修改 dummy/PatchCore 算法脚本。

适用场景：
- 无 EC66 机械臂但有真实相机时，验证 GUI 自动检测流程、真实拍照、dummy/配置算法调用、报告保存和数据采集归档。

本次测试：
- `python -m py_compile camera/vision_robot_inspection_gui.py`：通过
- `python scripts/smoke_test_dummy.py`：通过
- `git diff --check`：通过（仅有 LF/CRLF 提示）

## 本次更新：数据采集模式第一版（2026-05-22）

当前未提交改动包括：

```text
 M .gitignore
 M CODEX_HANDOFF.md
 M README.md
 M algorithm_config.example.json
 M camera/vision_robot_inspection_gui.py
?? HANDOFF_20260521_153625.md
```

本次完成：
- 在 `camera/vision_robot_inspection_gui.py` 自动检测页新增“数据采集模式”区域。
- 控件包括：启用 checkbox、`batch_id` 输入框、采集类型下拉框（`train/good`、`test/good`、`test/defect`、`raw/unlabeled`）、数据集根目录选择。
- 默认数据集根目录：`CV_Project/datasets_collected`。
- 自动检测流程中，每个点位拍照成功后，如果启用采集模式，会复制图片到：
  `CV_Project/datasets_collected/<workpiece_type>/<split>/<label>/<pose_name>/`
- 文件名格式：`YYYYMMDD_HHMMSS_productid_pose_originalname.png`，并使用 ASCII safe name 规避中文、空格和特殊字符路径风险。
- 不覆盖已有文件；重名时追加 `_001`、`_002`。
- 自动追加 `CV_Project/datasets_collected/manifest.csv`，字段为：
  `timestamp, workpiece_type, product_id, pose_name, split, label, batch_id, source_image_path, target_image_path`。
- 复制或 manifest 写入失败时只写 GUI 运行日志，不中断原有检测流程。
- 未训练模型，未调用 PatchCore，未修改 `infer_one_dummy.py` / `infer_one_patchcore.py`。
- 未修改海康 SDK 底层、机械臂通信底层、`RobotUIController.send_cmd()`、`RobotUIController.execute_movement()`。
- `.gitignore` 已新增 `CV_Project/datasets_collected/`，采集图片和 manifest 不提交 GitHub。
- `README.md` 已补充数据采集模式用途、目录结构、manifest 说明和 Git 忽略提醒。

本次测试：
- `python -m py_compile camera/vision_robot_inspection_gui.py`：通过
- `python scripts/smoke_test_dummy.py`：通过

下一步建议：
- 在真实设备现场小批量启用 `train/good` 采集，先验证目录结构、文件名和 manifest 是否符合后续训练习惯。
- 数据量充足后，再按 `workpiece_type + pose_name` 重新训练/评估 PatchCore 或 EfficientAD。
- 不要提交 `CV_Project/datasets_collected/`、真实图片、模型权重或运行结果目录。

## 新对话接力摘要（2026-05-22）

当前未提交状态：

```text
 M CODEX_HANDOFF.md
 M README.md
 M algorithm_config.example.json
 M camera/vision_robot_inspection_gui.py
?? HANDOFF_20260521_153625.md
```

本轮已完成但尚未提交：

- 工件型号 + 位姿级算法配置化。
- `algorithm_config.example.json` 已支持 `workpiece_models`、`active_workpiece_type`、`pose_profiles`。
- GUI 自动检测页已增加“工件型号” Combobox。
- `DefectDetector` 已支持按 `workpiece_type + pose_name` 选择模型配置。
- 默认仍然是 `dummy`，不默认启用 PatchCore / EfficientAD。

本轮根据 B handoff 已合并的低风险修复：

- `DefectDetector.detect()` 的 subprocess 调用增加 `PYTHONIOENCODING=utf-8`。
- `subprocess.run()` 增加 `encoding="utf-8"`、`errors="replace"`、`env=child_env`。
- stderr 摘要截断到 300 字符。
- `CameraUIController` 新增 `save_image_windows_safe(path, image)`。
- inspection image 保存改为 `cv2.imencode(".png", image)[1].tofile(str(path))`。
- 保存前创建父目录，保存后检查文件存在和大小。
- 保留 `safe_name()`，降低中文路径、中文点位名、空格和特殊字符导致保存失败的风险。

B handoff 的真实设备验证事实：

- 真实海康相机预览已验证。
- 真实 EC66 机械臂序列已验证。
- 真实相机拍照保存已验证。
- dummy 算法调用已验证。
- 9 个点位 OK，最终 PASS。
- 这只是工程链路验证，不代表真实缺陷检测模型已验证。

当前暂未采纳的 B 建议：

- dummy robot mode。
- dummy capture。
- 原因：这两个会改自动检测流程，后续如需要无硬件测试再单独做。

当前不应提交：

- `HANDOFF_20260521_153625.md`，除非用户明确要求。
- `algorithm_config.json`。
- `datasets/`、`results/`、`output_results/`、`pre_trained/`。
- `MvImport/`、`captures/`、`inspection_captures/`。
- 图片文件、模型权重、`.env`、`__pycache__/`、`.venv/`。

新 Codex 对话启动提示词：

```text
请继续 D:\run_code\camera_and_algorithm 项目。先只读取 AGENTS.md、CODEX_HANDOFF.md、README.md、algorithm_config.example.json、camera/vision_robot_inspection_gui.py，不要修改代码，先总结当前状态。不要读取 datasets、results、output_results、pre_trained、MvImport、captures、inspection_captures、anomalib、图片文件或模型权重。当前有未提交改动：工件型号+位姿级算法配置化、B handoff 的 subprocess UTF-8 修复、Windows-safe inspection image 保存修复、CODEX_HANDOFF 更新；HANDOFF_20260521_153625.md 是审查资料，除非用户明确要求不要提交。
```

本文档是给 Codex 后续继续开发时读取的上下文浓缩文件，不是普通用户文档。

## 最新交接状态（2026-05-19）

当前项目根目录：

```text
D:\run_code\camera_and_algorithm
```

当前 GitHub 仓库：

```text
https://github.com/LiyouliQvQ/camera_and_algorithm
```

当前 Git 状态：

```text
git status -sb
## main...origin/main

git status --short
<无输出，工作区干净>
```

最近完成并已 push：

- `camera/vision_robot_inspection_gui.py` GUI 工业现场功能增强已提交并推送：
  - 结果表格点击查看检测图片大图。
  - 支持 `boxes` 缺陷框叠加显示。
  - 支持 `heatmap_path` 热力图半透明叠加。
  - 结果表格支持 `ALL / NG / ERROR` 过滤。
  - 增加实时统计横条：已检测总数、OK、NG、ERROR、良率。
  - 检测结束显示大字号 `PASS / FAIL / ERROR`。
  - 增加暂停/继续流程控制。
  - 增加扫码枪键盘输入预留入口。
  - 增加三色灯/蜂鸣器 mock/stub 接口，不控制真实硬件。
- `AGENTS.md` 已加入长期规则：每次完成明确开发任务后，检查并按需维护 `CODEX_HANDOFF.md`。
- GitHub Actions 已通过。
- 新增 `CV_Project/scripts/check_model_ready.py`：
  - 用于在接入真实 PatchCore / EfficientAD 前检查模型文件和算法环境是否准备好。
  - 接收 `--model` 参数。
  - 检查模型文件是否存在。
  - 检查模型后缀是否支持 `.ckpt/.pt/.pth/.onnx/.engine`。
  - 检查 `torch` 是否可导入。
  - 检查 `anomalib` 是否可导入。
  - 输出清晰的 `OK / MISSING / UNSUPPORTED / NOT_READY` 状态。
- 新增 `CV_Project/scripts/infer_one_patchcore.py` 第一版：
  - 通过 `cv_lab` 环境加载 PatchCore ckpt 做单张图片推理。
  - 参数兼容 dummy：`--image --pose --product-id`，并新增 `--model --threshold --device`。
  - stdout 输出 GUI 兼容 JSON。
  - stderr 输出模型加载、推理日志和错误信息。
  - 第一版只返回 `score`、`OK/NG/ERROR`、`threshold`、`image_path` 等基础字段。
  - 第一版暂不保存 heatmap，`heatmap_path` 返回空字符串。
  - 第一版暂不提取 boxes，`boxes` 返回空数组。
  - 已修正 score 提取逻辑：除 `pred_score` 外，也会使用 `anomaly_map.max` 作为候选分数，并取最大候选值。
- 当前 PatchCore 模型与测试路径：
  - conda 环境：`cv_lab`
  - 模型路径：`D:\run_code\camera_and_algorithm\CV_Project\results\Patchcore\differential_housing\v5\weights\lightning\model.ckpt`
  - good 测试目录：`D:\run_code\camera_and_algorithm\CV_Project\datasets\differential_housing\test\good`
  - defect 测试目录：`D:\run_code\camera_and_algorithm\CV_Project\datasets\differential_housing\test\defect`
- 已更新 `.gitignore`，新增根目录 `results/` 忽略规则。不要删除 `results/`，也不要提交该运行产物目录。

当前算法策略调整：

- `CV_Project/scripts/infer_one_patchcore.py` 明确定位为 PatchCore 单图推理实验版，用于验证真实模型推理链路和 JSON 协议，不作为当前正式上线检测算法。
- 当前模型与数据量不足以稳定区分 good/defect，3 good + 3 defect 小样本已出现 score 分布重叠；现阶段暂时不继续调 threshold。
- 暂时不把 PatchCore 实验版接入 GUI 作为正式检测算法，GUI 仍保持 dummy 闭环，避免现场误以为真实算法已稳定上线。
- 后续等数据集收集和标注足够后，再重新训练 PatchCore / EfficientAD，并重新评估 score 分布、threshold、heatmap 与 boxes 输出。
- 下一步工作重点从调模型转为数据采集与标注闭环：稳定采图、归档 OK/NG 样本、整理缺陷类别、形成可复训数据集。

算法调用配置化方案：

- 新增根目录 `algorithm_config.example.json`，默认 `active_profile` 为 `dummy`，不会默认启用实验版 PatchCore。
- GUI 启动后 `DefectDetector` 优先读取 `algorithm_config.json`，不存在则读取 `algorithm_config.example.json`，两者都不存在则回退到内置 dummy 调用逻辑。
- `dummy` profile 使用当前 Python 调用 `CV_Project/scripts/infer_one_dummy.py`，timeout 为 5 秒。
- `patchcore_cv_lab` profile 使用 `conda run --no-capture-output -n cv_lab python` 调用 `CV_Project/scripts/infer_one_patchcore.py`，传入 model、threshold 和 timeout 30 秒。
- `DefectDetector.detect()` 根据 profile 构造命令，统一传入 `--image --pose --product-id`，配置含 `model/threshold` 时追加 `--model/--threshold`。
- stdout 仍只解析 JSON；脚本失败、超时、JSON 解析失败或配置错误时返回 `label="ERROR"`，GUI 不崩溃。
- 本次只做配置化，不改变自动检测主流程，不运行 PatchCore 推理，不接真实相机或机械臂测试。

本次新增多工件/多位姿算法配置预留：

- `algorithm_config.example.json` 已预留 `active_workpiece_type` 和 `workpiece_models`。
- GUI 自动检测页新增“工件型号”下拉框，默认读取 `active_workpiece_type=demo_default`。
- `demo_default` 的 `default_profile` 仍为 `dummy`，默认不会调用 PatchCore / EfficientAD。
- `DefectDetector.detect()` 已支持接收 `workpiece_type`，并按 `workpiece_type + pose_name` 优先查找 `pose_profiles`。
- 已预留按工件型号切换整套权重：每个 `workpiece_models.<type>` 可配置自己的 `default_profile`。
- 已预留按 `pose_name` 切换单点位权重：每个 pose 可覆盖 `profile/model/threshold/timeout`。
- 回退顺序：`workpiece_type + pose_name` -> 工件 `default_profile` -> 全局 `active_profile` -> 内置 dummy。
- 检测结果和 JSON 报告新增 `workpiece_type` 字段，旧字段保持兼容。
- 后续数据足够后，可为每个工件型号、每个检测位姿单独训练 PatchCore / EfficientAD 模型，再填入本地 `algorithm_config.json`。
- 本次检查通过：
  - `python -m json.tool algorithm_config.example.json`
  - `python -m py_compile camera/vision_robot_inspection_gui.py`
  - `python scripts/smoke_test_dummy.py`
- 机械臂示教点位保存已增加重名覆盖确认：覆盖前提示 `saved_poses.json` 坐标会更新、检测序列会使用新坐标、`algorithm_config.json` 同名 `pose_profiles` 仍继续匹配；取消时不覆盖。
- 点位覆盖确认修改后已通过 `python -m py_compile camera/vision_robot_inspection_gui.py`。

B handoff 审查合并记录（HANDOFF_20260521_153625.md）：

- 另一个环境已验证真实相机 + 真实机械臂 + dummy 算法工程链路：
  - 真实相机预览正常。
  - 真实机械臂执行检测序列。
  - 真实相机拍照并保存 inspection image。
  - GUI 成功调用 `CV_Project/scripts/infer_one_dummy.py`。
  - 9 个点位全部 OK。
  - 最终状态 PASS。
- 该结果只代表工程链路验证通过，不代表真实 PatchCore / EfficientAD 缺陷检测模型已经验证。
- 本轮已采纳低风险修复：
  - `DefectDetector.detect()` 子进程调用设置 `PYTHONIOENCODING=utf-8`，并使用 `encoding="utf-8"`、`errors="replace"`。
  - `CameraUIController.capture_for_inspection()` 的 inspection image 保存改为 Windows-safe PNG 保存：`cv2.imencode(".png", image)[1].tofile(str(path))`，并检查文件存在且大小大于 0。
- 本轮暂未采纳：
  - dummy robot mode。
  - dummy capture。
  - 原因：先降低改动风险，只合并真实设备链路中暴露的编码和保存稳定性问题；无硬件 GUI 测试能力后续如需要再单独实现。

本轮测试命令与结果：

```powershell
python -m py_compile camera\vision_robot_inspection_gui.py
python -m py_compile CV_Project\scripts\check_model_ready.py
python CV_Project\scripts\check_model_ready.py
python CV_Project\scripts\check_model_ready.py --model D:\not_exist_model.ckpt
python CV_Project\scripts\check_model_ready.py --model D:\fake_model.txt
python -m py_compile CV_Project\scripts\infer_one_patchcore.py
conda run --no-capture-output -n cv_lab python CV_Project\scripts\infer_one_patchcore.py --image "D:\run_code\CV_Project\datasets\differential_housing\test\defect\bad_01.png" --model "D:\run_code\camera_and_algorithm\CV_Project\results\Patchcore\differential_housing\v5\weights\lightning\model.ckpt" --threshold 0.5 --pose P1 --product-id TEST001
```

结果：

- `camera/vision_robot_inspection_gui.py` 语法检查通过。
- `CV_Project/scripts/check_model_ready.py` 语法检查通过。
- 缺少 `--model` 时退出码 1，符合预期。
- 模型不存在时输出 `NOT_READY`，符合预期。
- 后缀不支持时输出 `UNSUPPORTED`，符合预期。
- 当前环境 `torch_import` 和 `anomalib_import` 为 `MISSING`，需要后续配置真实算法环境。
- `CV_Project/scripts/infer_one_patchcore.py` 语法检查通过。
- 使用 `cv_lab`、`model.ckpt` 和指定测试图完成单图推理，输出合法 JSON。
- `bad_01.png` 诊断结果：`pred_score=0`，但 `anomaly_map.max=0.20731699466705322`，因此已将 `anomaly_map.max` 纳入 score 候选。
- 3 张 good + 3 张 defect 测试结果：
  - `goodtest_01.png`: `score=0.180768`, `label=OK`
  - `goodtest_02.png`: `score=0.196435`, `label=OK`
  - `goodtest_03.png`: `score=0.234565`, `label=OK`
  - `bad_01.png`: `score=0.207317`, `label=OK`
  - `bad_02.png`: `score=0.507737`, `label=NG`
  - `bad_03.png`: `score=0.535620`, `label=NG`
- 结论：`infer_one_patchcore.py` 初步可运行，但 good/defect 分布有重叠，暂时不要接 GUI。

当前可运行流程：

```text
camera GUI -> 机械臂移动 -> 海康相机拍照 -> DefectDetector 读取算法配置 -> subprocess 调用 active_profile 脚本 -> 返回 JSON -> GUI 显示 OK/NG/ERROR -> 保存 JSON 报告
```

仍未完成：

- 已新增 PatchCore 单图推理脚本第一版，但尚未接入 GUI。
- 尚未新增真实算法入口 `CV_Project/scripts/infer_one.py`。
- 尚未在 GUI 中提供 dummy/真实算法脚本切换配置。
- 暂不继续完整 `test/good` 与 `test/defect` 的 score 分布调参；当前数据量不足，先转向采集更多真实样本。
- 尚未确定最终 threshold；当前 0.5 可检出部分 defect，但会漏掉 `bad_01.png` 等低分缺陷样本，因此不作为正式检测阈值。
- 普通 Python 环境中 `torch` 和 `anomalib` 尚不可导入；`cv_lab` 环境中已可导入并可运行 PatchCore 单图脚本。
- 三色灯/蜂鸣器、扫码枪目前仅为 mock/stub 预留，不接真实硬件。

下一步建议：

进入数据采集与标注闭环阶段。下一步建议：

1. 先用现有 GUI/相机流程稳定采集更多 OK 与 NG 图片，按产品、点位、缺陷类型归档。
2. 建立最小标注规范：OK、NG、缺陷类别、点位、采集时间、备注，保证后续可复训。
3. 数据集充足后，重新训练 PatchCore / EfficientAD，再批量统计 good/defect score 分布。
4. 分布稳定前不要把 `infer_one_patchcore.py` 接入 GUI 作为正式算法，不要删除 PatchCore 实验脚本，不要提交 `results/`。
5. 后续算法稳定后，再实现 heatmap 保存、boxes 提取，并通过 `subprocess + JSON` 小步接入 GUI。

推荐新 Codex 对话启动提示词：

```text
请继续 D:\run_code\camera_and_algorithm 项目。先读取 AGENTS.md、CODEX_HANDOFF.md、README.md、CV_Project/scripts/infer_one_patchcore.py、CV_Project/scripts/infer_one_dummy.py。不要读取或修改 MvImport、pre_trained、captures、inspection_captures、results、output_results、bad_records、图片或模型权重；如需测试，只允许按用户明确指定读取 test/good 和 test/defect 图片。当前 GUI 已完成结果大图查看、boxes/heatmap 叠加、表格过滤、良率统计、PASS/FAIL/ERROR、暂停/继续、扫码枪预留和三色灯/蜂鸣器 stub。PatchCore 第一版脚本已可用 cv_lab + model.ckpt 单图推理，score 已改为 max(pred_score, anomaly_map.max)，但 good/defect 分布有重叠，暂时不要接 GUI。下一步建议批量跑完整 test/good 与 test/defect，统计 score 分布并确定 threshold，或判断是否需要重新训练 / EfficientAD。
```

## 历史交接状态（2026-05-18）

当前项目根目录：

```text
D:\run_code\camera_and_algorithm
```

当前 GitHub 仓库：

```text
https://github.com/LiyouliQvQ/camera_and_algorithm
```

当前 Git 状态：

```text
git status -sb
## main...origin/main

git status --short
<无输出，工作区干净>
```

最近提交：

```text
7ba367f Improve inspection workflow reporting and documentation
190abe4 Add project README and Codex handoff notes
566c0be Initial commit: robot camera GUI and dummy inspection pipeline
```

根据本地 Git 状态，`main` 当前与 `origin/main` 对齐。最新已提交内容包括：

- 初始项目代码、根 `.gitignore`、`camera/` 主 GUI 与 `CV_Project/` 普通代码目录。
- `CV_Project/scripts/infer_one_dummy.py` dummy 单图推理脚本。
- 根目录 `README.md` 和本交接文档。
- GUI 自动检测流程增强：
  - 统一点位检测结果结构。
  - 增加 `threshold` 显示。
  - 增加运行日志。
  - 整件最终判定规则：`ERROR > NG > OK`。
  - 每次完整检测后保存 JSON 报告到 `camera/inspection_reports/`。
  - 增加“最近报告路径”按钮。

本轮交接前的最后请求是：更新 `CODEX_HANDOFF.md` 作为新 Codex 对话完整交接文件。当前这次修改只更新本文档，尚未提交、尚未 push。

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
- 增强自动检测流程：
  - 统一点位检测结果结构。
  - 增加运行日志。
  - 整件产品按 `ERROR > NG > OK` 汇总最终结果。
  - 每次检测后保存 JSON 报告到 `camera/inspection_reports/`。
  - GUI 表格增加 `threshold` 字段。
  - 增加“最近报告路径”按钮，方便现场确认报告落盘位置。

## 尚未完成的任务

- 尚未接入真实 PatchCore / EfficientAD 推理。
- 尚未新增真实算法入口 `CV_Project/scripts/infer_one.py`。
- 尚未在 GUI 中提供 dummy/真实算法脚本切换配置。
- 尚未生成或显示热力图。
- 尚未实现多点位模型和阈值管理。
- 尚未做现场完整联调，包括机械臂节拍、相机曝光、稳定等待时间、算法耗时。
- 尚未完善报告可视化，只是保存 JSON 报告和显示最近报告路径。

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

单独测试 OK 分支：

```powershell
python CV_Project\scripts\infer_one_dummy.py --image CV_Project\scripts\infer_one_dummy.py --pose P_OK --product-id PART_OK
```

单独测试 NG 分支：

```powershell
New-Item -ItemType File -Force -Path CV_Project\scripts\tmp_ng_probe.txt
python CV_Project\scripts\infer_one_dummy.py --image CV_Project\scripts\tmp_ng_probe.txt --pose P_NG --product-id PART_NG
Remove-Item -Force -Path CV_Project\scripts\tmp_ng_probe.txt
```

注意：dummy 脚本 stdout 必须只输出 JSON。任何日志、异常说明都应写到 stderr，否则 `DefectDetector.detect()` 的 JSON 解析会失败并返回 `label="ERROR"`。

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

## 自动检测报告

`InspectionUIController` 现在会在完整检测结束后保存轻量 JSON 报告：

```text
camera/inspection_reports/
```

报告字段包括：

- `product_id`
- `start_time`
- `end_time`
- `final_label`
- `final_ok`
- `algorithm_script`
- `results`
- `logs`

每个点位结果建议保持字段：

- `idx`
- `pose`
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

GUI 测试流程：

```powershell
python camera\vision_robot_inspection_gui.py
```

现场测试检查点：

- 相机可打开并预览。
- 机械臂可连接。
- 检测序列中至少有一个已保存点位。
- 自动检测流程可以完成移动、拍照、识别。
- 表格显示 `pose/image/label/score/threshold/defect/message`。
- 检测结束后 `camera/inspection_reports/` 生成 JSON 报告。
- “最近报告路径”按钮能显示最新报告路径。

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

## 不要读取/不要修改的目录

除非用户明确要求，否则不要读取、扫描、分析或修改：

```text
camera/MvImport/
camera/captures/
camera/inspection_captures/
camera/inspection_reports/       # 可说明报告格式，但不要提交实际报告
CV_Project/MvImport/
CV_Project/anomalib/
CV_Project/datasets/
CV_Project/pre_trained/
CV_Project/results/
CV_Project/output_results/
CV_Project/bad_records/
CV_Project/.git_backup_before_root_upload/
__pycache__/
.venv/
venv/
```

也不要读取或提交：

```text
*.png
*.jpg
*.jpeg
*.bmp
*.tif
*.tiff
*.pt
*.pth
*.ckpt
*.onnx
*.engine
.env
```

## 下一步建议任务

1. 为真实算法新增 `CV_Project/scripts/infer_one.py`，保持与 dummy 脚本相同 JSON 协议。
2. 在 `DefectDetector` 中增加算法脚本路径配置，支持 dummy 与真实推理切换。
3. 接入 PatchCore / EfficientAD 单图推理。
4. 增加 heatmap 输出字段并在 GUI 中显示或链接。
5. 增加多点位模型管理，例如按 pose_name 选择不同模型或阈值。
6. 增加整件产品检测报告，汇总多点位 OK/NG、score、缺陷类型和图片路径。
7. 现场联调机械臂节拍、相机曝光、稳定等待时间和算法耗时。

PatchCore / EfficientAD 接入建议：

1. 不要把 PyTorch/anomalib 直接 import 到 Tkinter GUI 主进程。
2. 在 `CV_Project/scripts/infer_one.py` 内加载真实模型，保持 `--image --pose --product-id` 参数不变。
3. stdout 只输出 JSON，stderr 输出日志。
4. JSON 字段保持兼容 dummy 协议，新增字段也不要破坏 GUI 当前解析。
5. `heatmap_path` 可指向轻量输出图，注意不要提交实际热力图文件。
6. 先单独运行 `infer_one.py` 验证 OK/NG/ERROR，再让 GUI 从 dummy 切换到真实脚本。

## 推荐新对话启动提示词

```text
请继续 D:\run_code\camera_and_algorithm 项目开发。先阅读 CODEX_HANDOFF.md、README.md、AGENTS.md、PROJECT_OVERVIEW.md、camera/vision_robot_inspection_gui.py、CV_Project/scripts/infer_one_dummy.py。

不要读取或修改 camera/MvImport/、camera/captures/、camera/inspection_captures/、camera/inspection_reports/、CV_Project/MvImport/、CV_Project/anomalib/、CV_Project/datasets/、CV_Project/pre_trained/、CV_Project/results/、CV_Project/output_results/、CV_Project/bad_records/、CV_Project/.git_backup_before_root_upload/，也不要读取图片、模型权重或 .env。

当前项目已完成 dummy 自动检测闭环：
camera GUI -> 机械臂移动 -> 海康相机拍照 -> subprocess 调用 CV_Project/scripts/infer_one_dummy.py -> 返回 JSON -> GUI 显示 OK/NG/ERROR -> 保存 JSON 报告到 camera/inspection_reports/。

请保持最小改动，不要重写 GUI，不要修改海康 SDK 底层，不要修改 RobotUIController.send_cmd() 或 RobotUIController.execute_movement()。

下一步建议：设计并实现真实算法入口 CV_Project/scripts/infer_one.py，用 PatchCore / EfficientAD 做单图推理，但保持与 dummy 脚本相同的 JSON 输出协议。修改前先给出计划和文件清单。
```

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
