import torch
import torch.nn as nn
import numpy as np
import matplotlib.pyplot as plt

# ==========================================
# 1. 生成二维模拟数据
# ==========================================
np.random.seed(42)
torch.manual_seed(42)

N = 200 # 样本数量
# 正常的特征 (绿点)，非常紧凑
normal_features = np.random.randn(N, 2) * 0.15 

# 生成的假想异常特征 (灰点，噪声)
fake_anomalies = normal_features + np.random.randn(N, 2) * 0.8

# 真实的、未见过的残次品缺陷 (红星，专门放在角落和边缘)
real_unseen_anomalies = np.array([
    [2.2, -2.0], [-2.0, 2.0], [1.5, 1.8], [-1.8, -1.2], [2.0, 0.0]
])

X_normal = torch.tensor(normal_features, dtype=torch.float32)
X_fake = torch.tensor(fake_anomalies, dtype=torch.float32)

# ==========================================
# 2. 定义判别器 (加深网络，让过拟合更疯狂)
# ==========================================
def create_discriminator():
    return nn.Sequential(
        nn.Linear(2, 128),
        nn.ReLU(),
        nn.Linear(128, 128),
        nn.ReLU(),
        nn.Linear(128, 128),
        nn.ReLU(),
        nn.Linear(128, 1)
    )

model_standard = create_discriminator()
model_truncated = create_discriminator()

optimizer_std = torch.optim.Adam(model_standard.parameters(), lr=0.005)
optimizer_trunc = torch.optim.Adam(model_truncated.parameters(), lr=0.005)

# ==========================================
# 3. 训练循环 (增加到 1000 轮)
# ==========================================
epochs = 1000

for epoch in range(epochs):
    # -------- 模型 A: 普通损失函数 (死磕到底) --------
    out_std_normal = model_standard(X_normal)
    out_std_fake = model_standard(X_fake)
    # 强制正常点为1，假异常为-1
    loss_std = torch.mean((out_std_normal - 1.0)**2) + torch.mean((out_std_fake - (-1.0))**2)
    
    optimizer_std.zero_grad()
    loss_std.backward()
    optimizer_std.step()

    # -------- 模型 B: SimpleNet 截断损失函数 (及格万岁) --------
    out_trunc_normal = model_truncated(X_normal)
    out_trunc_fake = model_truncated(X_fake)
    # 截断机制：达到0.5和-0.5就不产生Loss
    loss_trunc_normal = torch.mean(torch.relu(0.5 - out_trunc_normal))
    loss_trunc_fake = torch.mean(torch.relu(0.5 + out_trunc_fake))
    loss_trunc = loss_trunc_normal + loss_trunc_fake
    
    optimizer_trunc.zero_grad()
    loss_trunc.backward()
    optimizer_trunc.step()

# ==========================================
# 4. 可视化
# ==========================================
xx, yy = np.meshgrid(np.linspace(-2.5, 2.5, 200), np.linspace(-2.5, 2.5, 200))
grid = torch.tensor(np.c_[xx.ravel(), yy.ravel()], dtype=torch.float32)

with torch.no_grad():
    Z_std = model_standard(grid).numpy().reshape(xx.shape)
    Z_trunc = model_truncated(grid).numpy().reshape(xx.shape)

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

def plot_decision_boundary(ax, Z, title):
    ax.contourf(xx, yy, Z, levels=[-100, 0, 100], colors=['#ffa8a8', '#a8d8ff'], alpha=0.5)
    ax.contour(xx, yy, Z, levels=[0], linewidths=2, colors='k')
    ax.scatter(fake_anomalies[:, 0], fake_anomalies[:, 1], c='gray', s=10, label='Fake Anomalies')
    ax.scatter(normal_features[:, 0], normal_features[:, 1], c='green', s=20, label='Normal Features')
    ax.scatter(real_unseen_anomalies[:, 0], real_unseen_anomalies[:, 1], c='red', marker='*', s=200, edgecolor='black', label='REAL Unseen Defects')
    ax.set_title(title, fontsize=14, pad=10)
    ax.set_xlim([-2.5, 2.5])
    ax.set_ylim([-2.5, 2.5])
    if ax == axes[1]:
        ax.legend(loc='upper right')

plot_decision_boundary(axes[0], Z_std, "Model A: Standard Loss (Extreme Overfitting)")
plot_decision_boundary(axes[1], Z_trunc, "Model B: Truncated Loss (SimpleNet)")

plt.tight_layout()
plt.show()