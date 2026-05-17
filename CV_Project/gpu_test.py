import torch
import time

# 1. 检查显卡
print(f"PyTorch Version: {torch.__version__}")
if torch.cuda.is_available():
    device = torch.device("cuda")
    print(f"Success! Using GPU: {torch.cuda.get_device_name(0)}")
else:
    print("Error: GPU not found!")
    exit()

# 2. 跑个分 (大矩阵乘法)
x = torch.randn(10000, 10000).to(device)
y = torch.randn(10000, 10000).to(device)

print("Starting Matrix Multiplication...")
start = time.time()
z = torch.matmul(x, y)
torch.cuda.synchronize() # 等待 GPU 算完
end = time.time()

print(f"Calculation finished in {end - start:.4f} seconds.")
print("Environment is perfect. Ready for research!")