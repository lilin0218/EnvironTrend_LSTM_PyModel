"""
环境数据 LSTM 模型训练脚本

从 SQLite 数据库读取传感器历史数据，构建时序训练样本，
训练一个 LSTM 模型来预测未来24小时的五项环境指标。

训练完成后保存：
    - models/enviro_model.pth     : 模型权重
    - models/scaler_params.json   : 归一化参数（用于推理时反归一化）

用法：
    python train.py
"""

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
    """
    自动查找传感器数据库文件

    按优先级检查以下路径：
        1. LSTM/dbData/enviro_data.db
        2. 项目根目录/dbData/enviro_data.db

    如果都找不到，弹出文件选择对话框让用户手动指定。
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(base_dir, "dbData", "enviro_data.db"),
        os.path.join(os.path.dirname(base_dir), "dbData", "enviro_data.db"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    # 自动查找失败，提示用户
    print("\n[错误] 未找到数据库文件")
    print("已检查路径:")
    for path in possible_paths:
        print(f"  - {path}")

    # 循环等待用户选择文件或放弃
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
    """
    选择计算设备

    优先使用 CUDA GPU。如果没有 GPU，询问用户是否用 CPU 继续训练。
    （CPU 训练速度较慢，仅供参考/调试用途）
    """
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
    """
    环境数据 LSTM 预测模型

    结构：
        输入层 → LSTM（多层） → 全连接层 → 输出

    输入：shape (batch, window_size, input_size) 的时序特征序列
    输出：shape (batch, output_points * output_features) 的预测值展平向量
          其中 output_features=5（温度、湿度、光照、MQ135、ZP01）

    10个输入特征：
        0~4: temperature, humidity, light, mq135, zp01（传感器原始值）
        5:   time_delta（相邻记录的时间间隔，秒）
        6~9: hour, day_of_week, month, day_of_month（时间编码特征）

    参数说明：
        input_size     - 输入特征维度（固定为10）
        hidden_size    - LSTM 隐藏层维度（128）
        num_layers     - LSTM 堆叠层数（2）
        output_points  - 预测的时间步数（1440 = 24小时 × 60分钟）
        output_features- 预测的传感器通道数（5）
    """

    def __init__(self, input_size: int, hidden_size: int, num_layers: int, output_points: int, output_features: int = 5):
        super(EnviroLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.output_features = output_features

        # 多层 LSTM，batch_first=True 表示输入格式为 (batch, seq, feature)
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)

        # 全连接层：将最后一个时间步的隐藏状态映射为预测输出
        self.fc = nn.Linear(hidden_size, output_points * output_features)

    def forward(self, x, device):
        """
        前向传播

        参数：
            x:      输入张量，shape (batch_size, window_size, input_size)
            device: 计算设备，用于初始化隐藏状态

        返回：
            预测张量，shape (batch_size, output_points * output_features)
        """
        batch_size = x.size(0)

        # 初始化 LSTM 的隐藏状态 h0 和细胞状态 c0，均为全零
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_size, device=device)
        c0 = torch.zeros(self.num_layers, batch_size, self.hidden_size, device=device)

        # LSTM 前向计算
        out, _ = self.lstm(x, (h0, c0))

        # 取最后一个时间步的隐藏状态，通过全连接层得到预测输出
        return self.fc(out[:, -1, :])


class EnviroDataset(Dataset):
    """
    环境传感器时序数据集

    从 SQLite 数据库加载数据，进行特征工程和归一化，
    然后通过滑动窗口方式构建 (输入窗口, 未来预测目标) 的训练样本对。

    数据处理流程：
        1. 从数据库读取全部非空记录
        2. 提取时间特征（小时、星期、月份、日期）
        3. 计算相邻记录的时间间隔
        4. Min-Max 归一化到 [0, 1]
        5. 滑动窗口切分：每条样本 = 前 window_size 条 → 后 output_points 条

    参数：
        db_path:          数据库文件路径
        window_size:      输入窗口大小（默认360，即6小时的历史数据）
        output_points:    预测目标长度（默认1440，即未来24小时）
        skip_user_prompt: 跳过用户交互提示（用于自动调参场景）
    """

    def __init__(self, db_path: str, window_size: int = 360, output_points: int = 1440, skip_user_prompt: bool = False):
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"数据库未找到: {db_path}")

        # 从数据库读取所有非空的传感器记录
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

        # --- 特征工程 ---
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # 计算相邻记录的时间间隔（秒），第一条记录填充为0
        df["time_delta"] = df["timestamp"].diff().dt.total_seconds().fillna(0.0)

        # 提取时间编码特征，帮助模型学习周期性规律
        df["hour"] = df["timestamp"].dt.hour              # 小时（0~23）
        df["day_of_week"] = df["timestamp"].dt.dayofweek  # 星期几（0=周一）
        df["month"] = df["timestamp"].dt.month             # 月份（1~12）
        df["day_of_month"] = df["timestamp"].dt.day        # 几号（1~31）

        # 组合所有特征为 numpy 数组（共10列）
        self.data_raw = df[["temperature", "humidity", "light", "mq135", "zp01", "time_delta", "hour", "day_of_week", "month", "day_of_month"]].values.astype(np.float64)

        # --- Min-Max 归一化 ---
        # 记录每个特征的最小值和最大值（训练后保存，推理时用于反归一化）
        self.mins = self.data_raw.min(axis=0)
        self.maxs = self.data_raw.max(axis=0)
        self.data = (self.data_raw - self.mins) / (self.maxs - self.mins + 1e-6)

        self.window_size = int(window_size)
        self.output_points = int(output_points)

        # 检查数据量是否足够构建至少一个训练样本
        # 至少需要 window_size + output_points + 1 条数据
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
        """返回数据集中可构建的样本总数"""
        return max(0, len(self.data) - self.window_size - self.output_points)

    def __getitem__(self, idx):
        """
        获取第 idx 个训练样本

        返回：
            x: 输入窗口，shape (window_size, 10)，模型的历史数据输入
            y: 预测目标，shape (output_points * 5,)，5个传感器的未来值展平拼接
               布局：[temp_1..temp_N, hum_1..hum_N, light_1..light_N, mq135_1..mq135_N, zp01_1..zp01_N]
        """
        idx = int(idx)

        # 输入窗口：从 idx 开始的 window_size 条记录
        x = self.data[idx: idx + self.window_size]

        # 预测目标：紧接输入窗口之后的 output_points 条记录
        future = self.data[idx + self.window_size: idx + self.window_size + self.output_points]

        # 按传感器通道拆分，然后拼接成一维向量
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
    """
    主训练流程

    步骤：
        1. 选择计算设备（GPU/CPU）
        2. 加载数据集，自动检测数据量是否充足
        3. 保存归一化参数（推理时需要）
        4. 划分训练集/验证集（80%/20%）
        5. 创建 DataLoader
        6. 实例化模型、优化器、学习率调度器
        7. 训练循环：前向传播 → 计算损失 → 反向传播 → 更新参数
        8. 早停机制：验证集损失连续 PATIENCE 轮不下降则停止
        9. 保存验证集上表现最好的模型权重
    """
    device = get_device()
    print("[训练] 开始训练24小时预测模型...")

    # 模型和参数保存目录
    models_dir = "models"
    os.makedirs(models_dir, exist_ok=True)

    # --- 1. 加载数据集 ---
    DB_PATH = find_database()

    # 训练超参数
    WINDOW_SIZE = 360       # 输入窗口：360条记录 = 6小时历史数据
    PREDICT_STEPS = 1440    # 预测步数：1440条记录 = 未来24小时
    BATCH_SIZE = 64         # 批次大小
    MAX_EPOCHS = 50         # 最大训练轮数（原设计150轮，当前调为50）
    PATIENCE = 15           # 早停耐心值：连续15轮验证损失不下降则停止

    try:
        dataset = EnviroDataset(DB_PATH, window_size=WINDOW_SIZE, output_points=PREDICT_STEPS)
        n_samples = len(dataset)
        print(f"[训练] 可用样本数: {n_samples}")

        # --- 2. 处理数据量不足的情况 ---
        if n_samples == 0:
            print(f"[错误] 无法创建训练样本")
            print(f"[原因] 数据量 ({len(dataset.data)}) < 窗口 ({dataset.window_size}) + 输出 ({dataset.output_points})")
            print("[训练] 是否自动调整参数? (y/n): ")
            while True:
                user_input = input().strip().lower()
                if user_input == 'y':
                    # 自动缩减窗口和输出步数，尽量利用有限数据
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

        # --- 3. 保存归一化参数 ---
        # 推理时需要用相同的 mins/maxs 进行反归一化
        scaler_path = os.path.join(models_dir, "scaler_params.json")
        with open(scaler_path, "w") as f:
            json.dump({"mins": dataset.mins.tolist(), "maxs": dataset.maxs.tolist(), "output_points": dataset.output_points}, f)
        print(f"[训练] 保存缩放参数: {scaler_path}")

        # --- 4. 划分训练集/验证集 ---
        # 随机打乱样本索引
        indices = np.arange(n_samples)
        np.random.shuffle(indices)

        if n_samples == 1:
            # 只有一个样本时，训练集和验证集都用它
            train_indices = indices
            val_indices = indices
        else:
            # 80% 训练，20% 验证
            val_ratio = 0.2
            val_size = max(1, int(n_samples * val_ratio))
            val_indices = indices[:val_size]
            train_indices = indices[val_size:]

        # 确保训练集和验证集都至少有一个样本
        if len(train_indices) == 0:
            train_indices = val_indices[:1]
            if len(val_indices) == 1:
                val_indices = train_indices.copy()
            else:
                val_indices = val_indices[1:]

        # --- 5. 创建 DataLoader ---
        # 使用 SubsetRandomSampler 实现子集随机采样
        train_loader = DataLoader(dataset, batch_size=BATCH_SIZE, sampler=SubsetRandomSampler(train_indices))
        val_loader = DataLoader(dataset, batch_size=BATCH_SIZE, sampler=SubsetRandomSampler(val_indices))

        # --- 6. 初始化模型和优化器 ---
        model = EnviroLSTM(input_size=10, hidden_size=128, num_layers=2, output_points=dataset.output_points, output_features=5).to(device)

        # Adam 优化器，初始学习率 0.001
        optimizer = optim.Adam(model.parameters(), lr=1e-3)

        # 学习率调度器：当验证损失停滞时自动将学习率减半
        # mode="min" 表示监控损失最小值，factor=0.5 表示衰减系数，patience=5 表示容忍5轮
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=5)

        # 损失函数：均方误差（MSE）
        criterion = nn.MSELoss()

        # --- 7. 训练循环 ---
        print("[训练] 开始训练...")
        best_val_loss = float("inf")   # 记录最佳验证损失
        best_epoch = 0                  # 记录最佳轮次

        for epoch in range(1, MAX_EPOCHS + 1):
            # === 训练阶段 ===
            model.train()
            train_loss = 0.0
            for x_batch, y_batch in train_loader:
                x_batch = x_batch.to(device)
                y_batch = y_batch.to(device)

                optimizer.zero_grad()          # 清空梯度
                outputs = model(x_batch, device)  # 前向传播
                loss = criterion(outputs, y_batch) # 计算损失
                loss.backward()                    # 反向传播
                optimizer.step()                   # 更新参数

                train_loss += loss.item() * x_batch.size(0)

            # 计算本轮平均训练损失
            train_loss /= len(train_indices)

            # === 验证阶段 ===
            model.eval()
            val_loss = 0.0
            with torch.no_grad():  # 验证时不需要计算梯度
                for x_batch, y_batch in val_loader:
                    x_batch = x_batch.to(device)
                    y_batch = y_batch.to(device)
                    outputs = model(x_batch, device)
                    loss = criterion(outputs, y_batch)
                    val_loss += loss.item() * x_batch.size(0)
            val_loss /= len(val_indices)

            # 更新学习率（根据验证损失变化自动调整）
            scheduler.step(val_loss)

            print(f"[训练] 轮次 {epoch}/{MAX_EPOCHS} - 训练损失: {train_loss:.6f}, 验证损失: {val_loss:.6f}")

            # === 模型保存 ===
            # 如果本轮验证损失优于历史最佳，保存模型权重
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_epoch = epoch
                best_path = os.path.join(models_dir, "enviro_model.pth")
                torch.save(model.state_dict(), best_path)
                print(f"[训练] 保存最佳模型 (轮次 {epoch}, 损失 {val_loss:.6f})")

            # === 早停检查 ===
            # 如果连续 PATIENCE 轮验证损失都没有改善，提前终止训练
            if epoch - best_epoch >= PATIENCE:
                print(f"[训练] 早停触发 (最佳轮次: {best_epoch}, 损失: {best_val_loss:.6f})")
                break

        print("[训练] 训练完成")

    except Exception as e:
        print(f"[错误] 训练失败: {e}")


if __name__ == "__main__":
    main_train()
