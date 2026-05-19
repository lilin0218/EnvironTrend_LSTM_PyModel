import os
import json
import sqlite3
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, SubsetRandomSampler


def find_database():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(base_dir, "dbData", "enviro_data.db"),
        os.path.join(os.path.dirname(base_dir), "dbData", "enviro_data.db"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    print("\n[错误] 未找到数据库文件")
    print("已检查路径:")
    for path in possible_paths:
        print(f"  - {path}")
    
    while True:
        choice = input("\n是否手动选择数据库位置? (y/n): ").strip().lower()
        if choice == 'y':
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            file_path = filedialog.askopenfilename(
                title="选择数据库文件",
                filetypes=[("SQLite数据库", "*.db"), ("所有文件", "*.*")]
            )
            if file_path and os.path.exists(file_path):
                return file_path
            print("[错误] 文件不存在，请重新选择")
        elif choice == 'n':
            print("[退出] 程序终止")
            exit(1)


def get_device():
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        print(f"[训练] 使用GPU: {name}")
        return torch.device("cuda")
    
    print("[警告] CUDA不可用")
    while True:
        user_input = input("[训练] 是否使用CPU继续? (y/n): ").strip().lower()
        if user_input == 'y':
            print("[训练] 使用CPU训练")
            return torch.device("cpu")
        elif user_input == 'n':
            print("[退出] 训练终止")
            exit(1)


class EnviroLSTM(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int, output_points: int, output_features: int = 5):
        super(EnviroLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.output_features = output_features
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, output_points * output_features)

    def forward(self, x, device):
        batch_size = x.size(0)
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_size, device=device)
        c0 = torch.zeros(self.num_layers, batch_size, self.hidden_size, device=device)
        out, _ = self.lstm(x, (h0, c0))
        return self.fc(out[:, -1, :])


class EnviroDataset(Dataset):
    def __init__(self, db_path: str, window_size: int = 360, output_points: int = 1440, skip_user_prompt: bool = False):
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"数据库未找到: {db_path}")

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
            raise ValueError("数据库为空或列数不足")

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["time_delta"] = df["timestamp"].diff().dt.total_seconds().fillna(0.0)
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
                print(f"[警告] 数据不足 ({len(self.data)} 条)")
                print(f"[需求] 至少需要 {self.window_size + self.output_points + 1} 条数据")
                while True:
                    user_input = input("[训练] 是否继续? (y/n): ").strip().lower()
                    if user_input == 'y':
                        break
                    elif user_input == 'n':
                        print("[退出] 训练终止")
                        exit(1)
            else:
                print(f"[训练] 使用可用数据 ({len(self.data)} 条)")

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


def main_train():
    device = get_device()
    print("[训练] 开始训练24小时预测模型...")

    models_dir = "models"
    os.makedirs(models_dir, exist_ok=True)

    DB_PATH = find_database()
    WINDOW_SIZE = 360
    PREDICT_STEPS = 1440
    BATCH_SIZE = 64
    MAX_EPOCHS = 150
    PATIENCE = 15

    try:
        dataset = EnviroDataset(DB_PATH, window_size=WINDOW_SIZE, output_points=PREDICT_STEPS)
        n_samples = len(dataset)
        print(f"[训练] 可用样本数: {n_samples}")

        if n_samples == 0:
            print(f"[错误] 无法创建训练样本")
            print(f"[原因] 数据量 ({len(dataset.data)}) < 窗口 ({dataset.window_size}) + 输出 ({dataset.output_points})")
            print("[训练] 是否自动调整参数? (y/n): ")
            while True:
                user_input = input().strip().lower()
                if user_input == 'y':
                    max_possible = len(dataset.data) - 1
                    if max_possible <= 0:
                        print("[错误] 数据量不足")
                        exit(1)
                    new_window_size = min(360, max_possible // 2)
                    new_output_points = max_possible - new_window_size
                    print(f"[训练] 调整参数: 窗口={new_window_size}, 输出={new_output_points}")
                    dataset = EnviroDataset(DB_PATH, window_size=new_window_size, output_points=new_output_points, skip_user_prompt=True)
                    n_samples = len(dataset)
                    print(f"[训练] 调整后样本数: {n_samples}")
                    if n_samples == 0:
                        print("[错误] 调整后仍无样本")
                        exit(1)
                    break
                elif user_input == 'n':
                    exit(1)

        scaler_path = os.path.join(models_dir, "scaler_params.json")
        with open(scaler_path, "w") as f:
            json.dump({"mins": dataset.mins.tolist(), "maxs": dataset.maxs.tolist(), "output_points": dataset.output_points}, f)
        print(f"[训练] 保存缩放参数: {scaler_path}")

        indices = np.arange(n_samples)
        np.random.shuffle(indices)
        
        if n_samples == 1:
            train_indices = indices
            val_indices = indices
        else:
            val_ratio = 0.2
            val_size = max(1, int(n_samples * val_ratio))
            val_indices = indices[:val_size]
            train_indices = indices[val_size:]

        if len(train_indices) == 0:
            train_indices = val_indices[:1]
            if len(val_indices) == 1:
                val_indices = train_indices.copy()
            else:
                val_indices = val_indices[1:]

        train_loader = DataLoader(dataset, batch_size=BATCH_SIZE, sampler=SubsetRandomSampler(train_indices))
        val_loader = DataLoader(dataset, batch_size=BATCH_SIZE, sampler=SubsetRandomSampler(val_indices))

        model = EnviroLSTM(input_size=10, hidden_size=128, num_layers=2, output_points=dataset.output_points, output_features=5).to(device)
        optimizer = optim.Adam(model.parameters(), lr=1e-3)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=5)
        criterion = nn.MSELoss()

        print("[训练] 开始训练...")
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

            print(f"[训练] 轮次 {epoch}/{MAX_EPOCHS} - 训练损失: {train_loss:.6f}, 验证损失: {val_loss:.6f}")

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_epoch = epoch
                best_path = os.path.join(models_dir, "enviro_model.pth")
                torch.save(model.state_dict(), best_path)
                print(f"[训练] 保存最佳模型 (轮次 {epoch}, 损失 {val_loss:.6f})")

            if epoch - best_epoch >= PATIENCE:
                print(f"[训练] 早停触发 (最佳轮次: {best_epoch}, 损失: {best_val_loss:.6f})")
                break

        print("[训练] 训练完成")

    except Exception as e:
        print(f"[错误] 训练失败: {e}")


if __name__ == "__main__":
    main_train()
