import os
from anomalib.engine import Engine
from anomalib.data import MVTecAD
from anomalib.models import Supersimplenet, EfficientAd

def run_metal_nut_comparison():
    print("🚀 准备环境: MVTec (Metal Nut) | 参赛选手: SimpleNet vs EfficientAD")
    
    # 1. 实例化官方数据集 (金属螺母)
    # 注意：为了让 EfficientAD 顺利跑通，我们强制全局 train_batch_size=1
    # num_workers=2 用于防止 Windows 报 1455 内存错误
    datamodule = MVTecAD(
        root="./datasets/MVTec",
        category="metal_nut",
        train_batch_size=1,  
        eval_batch_size=1,   
        num_workers=2        
    )

    # 2. 实例化两位参赛选手
    models_to_test = {
        "SimpleNet": Supersimplenet(),
        "EfficientAD": EfficientAd()
    }

    # 3. 循环进行训练和测试
    for model_name, model in models_to_test.items():
        print(f"\n{'='*60}")
        print(f"🔥 当前出战模型: [{model_name}]")
        print(f"{'='*60}\n")
        
        result_dir = f"./results/mvtec_metal_nut/{model_name}"
        
        # 定义引擎
        # 为了快速看到对比效果，这里 max_epochs 设置为 15 轮 (你可以根据耐心改为 50 或更高)
        engine = Engine(
            default_root_dir=result_dir,
            max_epochs=160,       
            accelerator="auto",
            devices=1,
            precision="16-mixed" # 开启半精度加速
        )

        print(f"⏳ 开始训练 {model_name}...")
        engine.fit(datamodule=datamodule, model=model)

        print(f"🔍 训练完毕！正在测试集上打分并画热力图...")
        test_results = engine.test(
            model=model, 
            datamodule=datamodule
        )
        
        print(f"\n✅ [{model_name}] 测试完成！")
        print(f"📊 评估得分: {test_results}")

    print("\n" + "="*60)
    print("🎉 全部测试完毕！")
    print("👉 请前往目录查看对比热力图: ./results/mvtec_metal_nut/")
    print("="*60)

if __name__ == "__main__":
    run_metal_nut_comparison()