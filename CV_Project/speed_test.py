import torch
import time
from anomalib.models import Patchcore, EfficientAd

# 1. 设置硬件
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"🖥️  测试硬件: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")

def measure_speed(model_name, model, input_size=(1, 3, 256, 256), loop_count=100):
    """
    专门用来测速的函数
    """
    model = model.to(device)
    model.eval() # 切换到评估模式

    # 生成一张假的随机图片 (模拟 256x256 的输入)
    dummy_input = torch.randn(input_size).to(device)

    print(f"\n正在测试 {model_name} ...")

    # --- 阶段 A: GPU 热身 (Warm-up) ---
    print("   ...正在热身 GPU...")
    try:
        with torch.no_grad():
            for _ in range(10):
                _ = model(dummy_input)
    except Exception as e:
        print(f"   ⚠️ 热身阶段出现小错误 (可能是还没有注入记忆库，可忽略): {e}")

    # --- 阶段 B: 正式计时 ---
    print(f"   ...开始 {loop_count} 次连续推理...")
    
    if torch.cuda.is_available():
        torch.cuda.synchronize() 
    
    start_time = time.time()

    try:
        with torch.no_grad():
            for _ in range(loop_count):
                _ = model(dummy_input)
    except Exception as e:
        print(f"❌ 测速中断: {e}")
        return 0, 0
            
    if torch.cuda.is_available():
        torch.cuda.synchronize() # 等 GPU 全部算完
        
    end_time = time.time()

    # --- 阶段 C: 计算结果 ---
    total_time = end_time - start_time
    if total_time == 0: return 0, 0
    
    avg_time_ms = (total_time / loop_count) * 1000  # 毫秒
    fps = loop_count / total_time                   # 帧率

    print(f"{model_name} 结果:")
    print(f"   平均耗时: {avg_time_ms:.2f} ms / 张")
    print(f"   推理速度: {fps:.2f} FPS (帧/秒)")
    
    return avg_time_ms, fps

def main():
    # ==========================================
    # 1. 准备 EfficientAD
    # ==========================================
    model_eff = EfficientAd()
    
    # ==========================================
    # 2. 准备 PatchCore
    # ==========================================
    print("\n📦 正在加载 PatchCore (WideResNet50)...")
    model_patch = Patchcore(backbone="wide_resnet50_2")
    
    # 【核心修复点】
    print("   🔧 [Fix] 正在注入虚拟记忆库 (Feature Dim = 1536)...")
    model_patch = model_patch.to(device)
    
    # 🔴 关键修改：将 384 改为 1536
    # WideResNet50 的 Layer2(512) + Layer3(1024) = 1536 维特征
    # 将 1000 改为 50000 (模拟真实的重负载情况)
    print("   Weighting up: Simulating a large memory bank (50k features)...")
    dummy_memory = torch.randn(50000, 1536).to(device)
    
    # 强制注入
    if hasattr(model_patch, "model") and hasattr(model_patch.model, "memory_bank"):
        model_patch.model.memory_bank = dummy_memory
    elif hasattr(model_patch, "memory_bank"):
        model_patch.memory_bank = dummy_memory
    else:
        try:
            model_patch.model.register_buffer("memory_bank", dummy_memory)
        except:
            print("   ⚠️ 警告: 无法自动注入，可能会报错。")

    # ==========================================
    # 3. 开始 PK
    # ==========================================
    print("==========================================")
    t1, fps1 = measure_speed("EfficientAD", model_eff)
    
    print("------------------------------------------")
    t2, fps2 = measure_speed("PatchCore", model_patch)
    print("==========================================")

    # 4. 最终结论
    if t1 > 0 and t2 > 0:
        speedup = t2 / t1
        print(f"\nEfficientAD 比 PatchCore 快了 {speedup:.1f} 倍！")
        if fps1 > 30:
            print("EfficientAD 的速度完全满足实时检测要求。")
    else:
        print("\n⚠️ 测试未完全成功，请检查报错信息。")

if __name__ == "__main__":
    main()