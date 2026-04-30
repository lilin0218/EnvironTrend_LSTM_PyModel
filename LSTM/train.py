import os
import json
import sqlite3

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
    优先尝试使用 GPU（如支持的 AMD/NVIDIA），失败则提示用户并让其选择是否继续使用 CPU 训练。
    """
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        print(f"[TRAIN] Using CUDA GPU: {name}")
        return torch.device("cuda")

    # 其他后端（如 MPS）按需扩展，这里统一回退到 CPU
    print("[TRAIN] WARNING: CUDA not available.")
    while True:
        user_input = input("[TRAIN] Continue with CPU training? (y/n): ").strip().lower()
        if user_input == 'y':
            print("[TRAIN] Proceeding with CPU training.")
            return torch.device("cpu")
        elif user_input == 'n':
            print("[TRAIN] Training aborted.")
            exit(1)


# ==========================================
# 1. 网络结构：输入最近一段历史，预测未来 24h(1440 点)的温度+湿度
# ==========================================
class EnviroLSTM(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int, output_points: int, output_features: int = 5):
        super(EnviroLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.output_features = output_features
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        # 输出: [batch, output_points * output_features] (温度+湿度+光照+mq135+zp01)
        self.fc = nn.Linear(hidden_size, output_points * output_features)

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
    def __init__(self, db_path: str, window_size: int = 360, output_points: int = 1440, skip_user_prompt: bool = False):
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")

        conn = sqlite3.connect(db_path)
        query = """
            SELECT timestamp, temperature, humidity, light, mq135, zp01 
            FROM sensor_data 
            WHERE temperature IS NOT NULL AND humidity IS NOT NULL AND light IS NOT NULL AND mq135 IS NOT NULL AND zp01 IS NOT NULL
            ORDER BY timestamp ASC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty or len(df.columns) < 6:
            raise ValueError("Database is empty or has insufficient columns")

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["time_delta"] = df["timestamp"].diff().dt.total_seconds().fillna(0.0)
        
        # 添加日期时间特征
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek
        df["month"] = df["timestamp"].dt.month
        df["day_of_month"] = df["timestamp"].dt.day

        self.data_raw = df[["temperature", "humidity", "light", "mq135", "zp01", "time_delta", "hour", "day_of_week", "month", "day_of_month"]].values.astype(np.float64)

        self.mins = self.data_raw.min(axis=0)
        self.maxs = self.data_raw.max(axis=0)
        self.data = (self.data_raw - self.mins) / (self.maxs - self.mins + 1e-6)

        self.window_size = int(window_size)
        self.output_points = int(output_points)

        if len(self.data) < self.window_size + self.output_points + 1:
            if not skip_user_prompt:
                print(f"[TRAIN] WARNING: Insufficient data ({len(self.data)} records) for training")
                print(f"[TRAIN] Required: {self.window_size + self.output_points + 1} records")
                while True:
                    user_input = input("[TRAIN] Continue with training anyway? (y/n): ").strip().lower()
                    if user_input == 'y':
                        print("[TRAIN] Proceeding with training despite insufficient data.")
                        break
                    elif user_input == 'n':
                        print("[TRAIN] Training aborted.")
                        exit(1)
            else:
                print(f"[TRAIN] Using adjusted parameters with available data ({len(self.data)} records)")

    def __len__(self):
        return max(0, len(self.data) - self.window_size - self.output_points)

    def __getitem__(self, idx):
        idx = int(idx)
        x = self.data[idx: idx + self.window_size]
        future = self.data[idx + self.window_size: idx + self.window_size + self.output_points]
        y_temp = future[:, 0]
        y_hum = future[:, 1]
        y_light = future[:, 2]
        y_mq135 = future[:, 3]
        y_zp01 = future[:, 4]
        y = np.concatenate([y_temp, y_hum, y_light, y_mq135, y_zp01], axis=0)

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

    DB_PATH = "../dbData/enviro_data.db"
    WINDOW_SIZE = 360
    PREDICT_STEPS = 1440
    BATCH_SIZE = 64
    MAX_EPOCHS = 150
    PATIENCE = 15

    try:
        dataset = EnviroDataset(DB_PATH, window_size=WINDOW_SIZE, output_points=PREDICT_STEPS)
        n_samples = len(dataset)
        print(f"[TRAIN] Total sliding samples: {n_samples}")

        if n_samples == 0:
            print(f"[TRAIN] ERROR: No valid samples available for training.")
            print(f"[TRAIN] Reason: Data length ({len(dataset.data)}) < window_size ({dataset.window_size}) + output_points ({dataset.output_points})")
            print("[TRAIN] Would you like to automatically adjust window size and output points to fit available data? (y/n): ")
            while True:
                user_input = input().strip().lower()
                if user_input == 'y':
                    # 自动调整参数
                    max_possible = len(dataset.data) - 1
                    if max_possible <= 0:
                        print("[TRAIN] ERROR: Not enough data to create any samples.")
                        print("[TRAIN] Training aborted.")
                        exit(1)
                    # 调整为可用的最大值
                    new_window_size = min(360, max_possible // 2)
                    new_output_points = max_possible - new_window_size
                    print(f"[TRAIN] Automatically adjusted parameters:")
                    print(f"[TRAIN] New window_size: {new_window_size}")
                    print(f"[TRAIN] New output_points: {new_output_points}")
                    # 重新创建数据集，跳过用户提示
                    dataset = EnviroDataset(DB_PATH, window_size=new_window_size, output_points=new_output_points, skip_user_prompt=True)
                    n_samples = len(dataset)
                    print(f"[TRAIN] Total sliding samples after adjustment: {n_samples}")
                    if n_samples == 0:
                        print("[TRAIN] ERROR: Still not enough data after adjustment.")
                        print("[TRAIN] Training aborted.")
                        exit(1)
                    break
                elif user_input == 'n':
                    print("[TRAIN] Training aborted.")
                    exit(1)

        scaler_path = os.path.join(models_dir, "scaler_params.json")
        with open(scaler_path, "w") as f:
            json.dump({"mins": dataset.mins.tolist(), "maxs": dataset.maxs.tolist()}, f)
        print(f"[TRAIN] Saved scaler params to {scaler_path}")

        indices = np.arange(n_samples)
        np.random.shuffle(indices)
        
        # 处理样本数较少的情况
        if n_samples == 1:
            # 只有一个样本时，全部用于训练
            train_indices = indices
            val_indices = indices  # 验证集也使用同一个样本
        else:
            val_ratio = 0.2
            val_size = max(1, int(n_samples * val_ratio))  # 确保至少有一个验证样本
            val_indices = indices[:val_size]
            train_indices = indices[val_size:]

        # 确保训练集至少有一个样本
        if len(train_indices) == 0:
            train_indices = val_indices[:1]
            # 确保验证集至少有一个样本
            if len(val_indices) == 1:
                val_indices = train_indices.copy()
            else:
                val_indices = val_indices[1:]

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

        model = EnviroLSTM(input_size=10, hidden_size=128, num_layers=2, output_points=dataset.output_points, output_features=5).to(device)
        optimizer = optim.Adam(model.parameters(), lr=1e-3)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=0.5, patience=5
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

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_epoch = epoch
                best_path = os.path.join(models_dir, "enviro_model.pth")
                torch.save(model.state_dict(), best_path)
                print(f"[TRAIN] New best model saved at epoch {epoch}, val_loss={val_loss:.6f}")

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