import os
import json

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, SubsetRandomSampler


# ==========================================
# 0. 设备选择：优先 GPU，失败自动回退 CPU
# ==========================================
def get_device():
    """
    优先尝试使用 GPU（如支持的 AMD/NVIDIA），失败则自动回退到 CPU，并打印日志。
    """
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        print(f"[TRAIN] Using CUDA GPU: {name}")
        return torch.device("cuda")

    # 其他后端（如 MPS）按需扩展，这里统一回退到 CPU
    print("[TRAIN] CUDA not available. Fallback to CPU.")
    return torch.device("cpu")


# ==========================================
# 1. 网络结构：输入最近一段历史，预测未来 24h(1440 点)的温度+湿度
# ==========================================
class EnviroLSTM(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int, output_points: int):
        super(EnviroLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        # 输出: [batch, output_points*2] (温度+湿度)
        self.fc = nn.Linear(hidden_size, output_points * 2)

    def forward(self, x, device):
        batch_size = x.size(0)
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_size, device=device)
        c0 = torch.zeros(self.num_layers, batch_size, self.hidden_size, device=device)
        out, _ = self.lstm(x, (h0, c0))
        return self.fc(out[:, -1, :])


# ==========================================
# 2. 数据集：从 csvData/data.csv 生成滑动窗口样本
# ==========================================
class EnviroDataset(Dataset):
    def __init__(self, csv_path: str, window_size: int = 360, output_points: int = 1440):
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"找不到数据文件: {csv_path}")

        df = pd.read_csv(csv_path)
        if df.shape[1] < 3:
            raise ValueError("CSV 数据格式不正确，预期至少包含 timestamp,temp,hum 三列。")

        df["timestamp"] = pd.to_datetime(df.iloc[:, 0])
        # 时间差（秒），第一行设为 0
        df["time_delta"] = df["timestamp"].diff().dt.total_seconds().fillna(0.0)

        # 特征: 温度、湿度、时间差
        self.data_raw = df[["temp", "hum", "time_delta"]].values.astype(np.float64)

        # 列向量级别的归一化参数 (min-max)
        self.mins = self.data_raw.min(axis=0)
        self.maxs = self.data_raw.max(axis=0)
        self.data = (self.data_raw - self.mins) / (self.maxs - self.mins + 1e-6)

        self.window_size = int(window_size)
        self.output_points = int(output_points)

        if len(self.data) < self.window_size + self.output_points + 1:
            raise ValueError(
                f"CSV 数据量太少（{len(self.data)} 条），不足以训练 "
                f"window_size={self.window_size}, output_points={self.output_points} 的模型。"
            )

    def __len__(self):
        # 可用的起始索引数量：总长度 - 输入窗口 - 预测长度
        return len(self.data) - self.window_size - self.output_points

    def __getitem__(self, idx):
        idx = int(idx)
        x = self.data[idx: idx + self.window_size]
        future = self.data[idx + self.window_size: idx + self.window_size + self.output_points]
        # 只从 future 中取温度、湿度两列作为监督信号
        y_temp = future[:, 0]
        y_hum = future[:, 1]
        y = np.concatenate([y_temp, y_hum], axis=0)

        return (
            torch.from_numpy(x.astype(np.float32)),
            torch.from_numpy(y.astype(np.float32)),
        )


# ==========================================
# 3. 训练主函数（带 train/val 划分与简单 early stopping）
# ==========================================
def main_train():
    device = get_device()
    print("[TRAIN] Environment ready. Start training 24h prediction model...")

    models_dir = "models"
    os.makedirs(models_dir, exist_ok=True)

    CSV_PATH = "csvData/data.csv"
    WINDOW_SIZE = 360          # 使用最近 6 小时作为输入
    PREDICT_STEPS = 1440       # 预测未来 24 小时
    BATCH_SIZE = 64
    MAX_EPOCHS = 150
    PATIENCE = 15              # 验证集无提升早停

    try:
        dataset = EnviroDataset(CSV_PATH, window_size=WINDOW_SIZE, output_points=PREDICT_STEPS)
        n_samples = len(dataset)
        print(f"[TRAIN] Total sliding samples: {n_samples}")

        # 导出归一化参数
        scaler_path = os.path.join(models_dir, "scaler_params.json")
        with open(scaler_path, "w") as f:
            json.dump({"mins": dataset.mins.tolist(), "maxs": dataset.maxs.tolist()}, f)
        print(f"[TRAIN] Saved scaler params to {scaler_path}")

        # 划分训练集 / 验证集
        indices = np.arange(n_samples)
        np.random.shuffle(indices)
        val_ratio = 0.2
        val_size = int(n_samples * val_ratio)
        val_indices = indices[:val_size]
        train_indices = indices[val_size:]

        train_loader = DataLoader(
            dataset,
            batch_size=BATCH_SIZE,
            sampler=SubsetRandomSampler(train_indices),
        )
        val_loader = DataLoader(
            dataset,
            batch_size=BATCH_SIZE,
            sampler=SubsetRandomSampler(val_indices),
        )

        # 初始化模型
        model = EnviroLSTM(input_size=3, hidden_size=128, num_layers=2, output_points=PREDICT_STEPS).to(device)
        optimizer = optim.Adam(model.parameters(), lr=1e-3)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=0.5, patience=5, verbose=True
        )
        criterion = nn.MSELoss()

        print("[TRAIN] Start training...")
        best_val_loss = float("inf")
        best_epoch = 0

        for epoch in range(1, MAX_EPOCHS + 1):
            model.train()
            train_loss = 0.0
            for x_batch, y_batch in train_loader:
                x_batch = x_batch.to(device)
                y_batch = y_batch.to(device)

                optimizer.zero_grad()
                outputs = model(x_batch, device)
                loss = criterion(outputs, y_batch)
                loss.backward()
                optimizer.step()

                train_loss += loss.item() * x_batch.size(0)

            train_loss /= len(train_indices)

            # 验证
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for x_batch, y_batch in val_loader:
                    x_batch = x_batch.to(device)
                    y_batch = y_batch.to(device)
                    outputs = model(x_batch, device)
                    loss = criterion(outputs, y_batch)
                    val_loss += loss.item() * x_batch.size(0)
            val_loss /= len(val_indices)

            scheduler.step(val_loss)

            print(
                f"[TRAIN] Epoch [{epoch}/{MAX_EPOCHS}] "
                f"train_loss={train_loss:.6f}, val_loss={val_loss:.6f}"
            )

            # 记录最佳模型（基于验证集）
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_epoch = epoch
                best_path = os.path.join(models_dir, "enviro_model.pth")
                torch.save(model.state_dict(), best_path)
                print(f"[TRAIN] New best model saved at epoch {epoch}, val_loss={val_loss:.6f}")

            # 简单 early stopping
            if epoch - best_epoch >= PATIENCE:
                print(
                    f"[TRAIN] Early stopping triggered. "
                    f"Best epoch={best_epoch}, best_val_loss={best_val_loss:.6f}"
                )
                break

        print("[TRAIN] Training finished.")

    except Exception as e:
        print(f"[TRAIN] Training aborted due to error: {e}")


if __name__ == "__main__":
    main_train()