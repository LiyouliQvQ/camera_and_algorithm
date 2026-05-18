# Codex Handoff

本文档是给 Codex 后续继续开发时读取的上下文浓缩文件，不是普通用户文档。

## 最新交接状态（2026-05-18）

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
