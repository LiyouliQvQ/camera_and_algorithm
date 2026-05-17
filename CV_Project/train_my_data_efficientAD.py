import os
import csv
from anomalib.data import Folder
import torch
torch.set_float32_matmul_precision('medium')
from anomalib.models import EfficientAd
from anomalib.engine import Engine

def main():
    print("[System] 正在初始化 EfficientAD 训练环境...")

    # ==========================================
    # 1. 配置你的自定义数据集 (Folder 模块)
    # 完美契合你截图中的目录结构
    # ==========================================
    dataset_root = "datasets/differential_housing"
    
    datamodule = Folder(
        name="differential_housing",
        root=dataset_root,
        normal_dir="train/good",         
        abnormal_dir="test/bad",         
        normal_test_dir="test/good",     
        train_batch_size=1,              # 👈 必须强制改为 1
        eval_batch_size=8,               # 👈 测试批次大小保持 8 不变
        num_workers=4
    )

    # ==========================================
    # 2. 初始化 EfficientAD 模型
    # ==========================================
    model = EfficientAd(
        model_size="small",  # 👈 把大写的 "S" 改成小写的 "small"
        # model_size="medium", # 如果以后想换高精度版本，就用 "medium"
    )

    # ==========================================
    # 3. 配置训练引擎 (Engine - 基于 PyTorch Lightning)
    # ==========================================
    engine = Engine(
        max_epochs=100,             # EfficientAD 推荐训练 100-200 轮
        accelerator="gpu",          # 强制使用显卡训练
        devices=1,                  # 使用 1 张显卡
        default_root_dir="./results", # 训练完的权重和热力图结果会保存在这个文件夹下
        check_val_every_n_epoch=5   # 每隔 5 轮跑一次 test 评估精度
    )

   # ==========================================
    # 4. 开始炼丹！（把注释去掉，恢复训练）
    # ==========================================
    print(f"[System] 开始在 {dataset_root} 上训练 EfficientAD...")
    engine.fit(datamodule=datamodule, model=model)

    # ==========================================
    # 5. 直接测试并生成图片！
    # ==========================================
    print("[System] 训练结束，开始自动生成测试集效果图...")
    
    # 【核心改动】：我们删掉了 ckpt_path 变量！
    # 只要你不传具体的路径，引擎在 fit() 刚跑完时，
    # 极其聪明地知道要直接用它刚才新鲜出炉的“最强权重”来跑测试！
    engine.test(datamodule=datamodule, model=model)
    
    # ==========================================
    # 6. 提取每张图的具体分数并导出 CSV 
    # ==========================================
    print("[System] 正在从新鲜的大脑中提取分数并导出 CSV...")
    
    # 同理，也不需要传 ckpt_path 了
    predictions = engine.predict(datamodule=datamodule, model=model)

    # 我们把 CSV 文件动态保存在本次训练的 results 目录下
    # default_root_dir 默认会指向 latest 的最新那次
    import os
    csv_file = "results/EfficientAd/differential_housing/latest/my_scores.csv"
    
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["图片路径 (Image_Path)", "异常分数 (Anomaly_Score)", "AI判定 (1=坏, 0=好)"])
        
        for batch in predictions:
            if isinstance(batch, dict):
                paths = batch.get("image_path", [])
                scores = batch.get("pred_score", batch.get("pred_scores", []))
                labels = batch.get("pred_label", batch.get("pred_labels", []))
            else:
                paths = getattr(batch, "image_path", [])
                scores = getattr(batch, "pred_score", getattr(batch, "pred_scores", []))
                labels = getattr(batch, "pred_label", getattr(batch, "pred_labels", []))
            
            for i in range(len(paths)):
                s = scores[i].item() if hasattr(scores[i], 'item') else float(scores[i])
                l = labels[i].item() if hasattr(labels[i], 'item') else float(labels[i])
                writer.writerow([paths[i], s, l])
                
    print(f"[System] 端到端全流程大功告成！🎉 图片和 CSV 已双双保存至 latest 文件夹！")

if __name__ == "__main__":
    main()