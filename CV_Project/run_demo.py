# run_demo.py
# 1. 导入改为 MVTecAD (适配新版)
from anomalib.data import MVTecAD 
from anomalib.models import Patchcore
from anomalib.engine import Engine
import torch

def main():
    print("🚀 正在初始化实验 (v2.3.0dev 适配版)...")

    # 2. 准备数据
    # 使用 MVTecAD 类，并显式打开 create_dataset 选项
    datamodule = MVTecAD(
        root="./datasets", 
        category="bottle",
        train_batch_size=8, 
        eval_batch_size=8
    )

    # 3. 定义模型
    model = Patchcore(backbone="wide_resnet50_2")

    # 4. 定义引擎
    # ⚠️ 关键修改：删除了 'task="segmentation"' 参数
    # 新版 Engine 会自动处理，或者不需要传给 Trainer
    engine = Engine(
        max_epochs=1,       
        accelerator="gpu",
        devices=1
    )

    # 5. 开始训练
    print("📥 开始训练...")
    engine.fit(datamodule=datamodule, model=model)

    # 6. 开始测试
    print("🧪 正在测试模型效果...")
    engine.test(datamodule=datamodule, model=model)
    
    print("✅ 实验结束！请去 results 文件夹查看可视化结果。")

if __name__ == "__main__":
    main()