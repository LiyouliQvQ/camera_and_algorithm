import os
from anomalib.engine import Engine
from anomalib.data import MVTecAD
from anomalib.models import Supersimplenet

def run_mvtec_simplenet_fast():
    print("🚀 [极速验证模式] 准备环境: MVTec (Bottle) + SimpleNet")
    
    # 1. 实例化 SimpleNet 模型
    model = Supersimplenet()

    # 2. 实例化官方数据集
    # 提速秘籍 1：num_workers=2，既不会撑爆 Windows 内存，又能喂饱显卡
    datamodule = MVTecAD(
        root="./datasets/MVTec",
        category="bottle",
        num_workers=2 
    )

    # 3. 实例化训练引擎
    result_dir = "./results/mvtec_baseline/SimpleNet_Fast"
    engine = Engine(
        default_root_dir=result_dir,
        max_epochs=50,        # <--- 【核心修改】只跑 10 轮！几分钟就能跑完
        accelerator="auto",
        devices=1,
        precision="16-mixed"  # <--- 提速秘籍 2：开启 RTX 3060Ti 的半精度硬件加速
    )

    # 4. 开始训练
    print("\n" + "="*50)
    print("⏳ 开始极速训练 SimpleNet (仅 10 轮)...")
    print("="*50)
    engine.fit(datamodule=datamodule, model=model)

    # 5. 测试并出图
    print("\n" + "="*50)
    print("🔍 训练完毕！正在生成热力图...")
    print("="*50)
    test_results = engine.test(
        model=model, 
        datamodule=datamodule
    )
    
    print("\n✅ 极速版测试大功告成！量化评估指标如下：")
    print(test_results)
    print(f"\n👉 快去打开 {result_dir} 查看热力图效果！")

if __name__ == "__main__":
    run_mvtec_simplenet_fast()