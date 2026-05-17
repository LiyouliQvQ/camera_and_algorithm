# 🏭 Defect-Detection-PatchCore (工业级表面缺陷检测系统)

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-1.12+-EE4C2C.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

本项目是一个端到端的工业级表面缺陷检测（Anomaly Detection）解决方案。核心算法基于业界领先的 **PatchCore**，并深度整合了 **海康威视（Hikvision）工业相机** 的底层 SDK，实现了从“硬件图像采集”到“AI 深度学习推理”的完整闭环。

## ✨ 核心特性

- **🚀 SOTA 算法驱动**: 基于 `anomalib` 框架重构的 PatchCore 算法，具备极高的冷启动能力和极低的误检率。
- **📷 硬件原生接入**: 完美打通海康威视工业相机底层 DLL 驱动，支持零延迟的实时流视频抓取与推理。
- **🛡️ 工业级工程架构**: 严格的代码分层，独立的模型权重、数据集与日志管理机制。
- **⚡ 极简部署**: 提供一键式硬件自检与全链路测试脚本。

## 📂 目录结构说明

为了保证云端仓库的轻量化与安全性，大型预训练权重和隐私数据集已通过 `.gitignore` 隔离，克隆到本地后请按需建立以下高亮目录：

```text
CV_PROJECT/
├── MvImport/              # 海康威视底层驱动及常量定义
├── bad_records/           # 🔴 (需自建) 存放推理阶段产生的 NG (缺陷) 记录截图
├── datasets/              # 🔴 (需自建) 存放训练用的自定义数据集 (MVTec 格式)
├── pre_trained/           # 🔴 (需自建) 存放 EfficientNet 等骨干网络的 .pth 预训练权重
├── results/               # 🔴 (需自建) 存放训练输出的 .ckpt 模型权重及评估报告
├── camera_test.py         # 硬件测试脚本 (一键验证相机连通性)
├── train_my_data.py       # 模型训练脚本
├── run_demo.py            # 推理演示脚本 (全链路跑通)
├── vision_server_ai.py    # 视觉 AI 推理核心服务
├── vision_server.py       # 视觉底层控制服务
├── compare_models.py      # 模型对比评估脚本
└── .gitignore             # 严格的 Git 忽略配置文件
```

## 🛠️ 环境依赖与安装

1. **克隆仓库**:
```bash
git clone [https://github.com/LiyouliQvQ/Defect-Detection-PatchCore.git](https://github.com/LiyouliQvQ/Defect-Detection-PatchCore.git)
cd Defect-Detection-PatchCore
```

2. **配置 Python 环境**:
推荐使用 Conda 管理环境。
```bash
conda create -n cv_lab python=3.8
conda activate cv_lab
pip install -r requirements.txt  # 请确保已安装 torch, anomalib 等依赖
```

3. **配置海康驱动**:
请确保电脑已正确安装海康 MVS 客户端，且相机处于可连接状态。

## 🚀 快速开始 (Quick Start)

**Step 1: 硬件神经通路测试**
运行以下指令，验证海康 SDK 导入及物理相机连接是否正常：
```bash
python camera_test.py
```

**Step 2: 自定义数据训练**
将你的良品/不良品图片放入 `datasets/` 目录下，执行：
```bash
python train_my_data.py
```

**Step 3: 端到端实时推理**
调用训练好的 `.ckpt` 模型，启动连接相机的实时检测：
```bash
python run_demo.py
```

## 🗺️ Roadmap (未来规划)

- [x] 跑通 PatchCore 算法与海康底层驱动闭环。
- [x] 完成 Git 工程化部署与 `.gitignore` 规范。
- [ ] 开发基于 PyQt/PySide 的可视化交互界面 (GUI)。
- [ ] 增加多相机并发推理支持。

## 🤝 贡献与反馈
如果你在工业部署中遇到任何问题，欢迎提交 Issue。