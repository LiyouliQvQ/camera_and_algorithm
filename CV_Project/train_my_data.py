import os
import csv  # 👈 新增：用于导出表格
from anomalib.data import Folder
from anomalib.models import Patchcore
from anomalib.engine import Engine

def main():
    print("🚀 正在初始化差速器壳体视觉检测系统 (PatchCore 分割模式)...")

    # ---------------------------------------------------------
    # 1. 配置数据集 (精准匹配你左侧的文件夹结构)
    # ---------------------------------------------------------
    datamodule = Folder(
        name="differential_housing",
        root="./datasets/differential_housing", 
        normal_dir="train/good",                
        abnormal_dir="test/bad",                
        normal_test_dir="test/good",            
    )
    # datamodule.setup() # 新版引擎在 fit 时会自动 setup，这行可以注释掉或保留
    print("✅ 数据集挂载成功！")

    # ---------------------------------------------------------
    # 2. 初始化 PatchCore 模型
    # ---------------------------------------------------------
    model = Patchcore(
        backbone="wide_resnet50_2", 
        layers=["layer2", "layer3"],            
        coreset_sampling_ratio=0.1              
    )
    print("✅ 算法模型初始化完成！")

    # ---------------------------------------------------------
    # 3. 初始化引擎 (Engine)
    # ---------------------------------------------------------
    engine = Engine(
        default_root_dir="./results"            
    )

    # ---------------------------------------------------------
    # 4. 开始建立特征库 (Training)
    # ---------------------------------------------------------
    print("\n🧠 正在提取正常壳体特征，建立记忆库... (PatchCore 提特征较慢，请耐心等待)")
    engine.fit(datamodule=datamodule, model=model)
    print("✅ 记忆库构建完毕！")

    # ---------------------------------------------------------
    # 5. 测试并生成热力图 (Testing)
    # ---------------------------------------------------------
    print("\n🔍 正在测试缺陷样本，生成热力图...")
    # 因为上面刚 fit 完，这里不用传 ckpt_path，它会自动用热乎的特征库
    engine.test(datamodule=datamodule, model=model)

    # ---------------------------------------------------------
    # 6. 提取每张图的具体分数并导出 CSV (对标 EfficientAD)
    # ---------------------------------------------------------
    print("\n📊 正在从 PatchCore 模型中提取精确异常分数并导出 CSV...")
    
    # 调用 predict 拿到详细结果
    predictions = engine.predict(datamodule=datamodule, model=model)

    # 自动定位到 Patchcore 的最新结果目录
    # 注意这里路径从 EfficientAd 换成了 Patchcore
    save_dir = "./results/Patchcore/differential_housing/latest"
    os.makedirs(save_dir, exist_ok=True)  # 防弹设计：确保文件夹存在
    csv_file = os.path.join(save_dir, "my_scores.csv")
    
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["图片路径 (Image_Path)", "异常分数 (Anomaly_Score)", "AI判定 (1=坏, 0=好)"])
        
        for batch in predictions:
            # 兼容新老版本的完美提取逻辑
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
                
    print(f"✅ 分数提取成功！CSV 文件已保存至: {csv_file}")
    
    print("\n🎉 全部完成！去对比一下两个模型的成绩单吧！")

if __name__ == "__main__":
    main()