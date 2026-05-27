"""
环境数据趋势预测脚本

使用训练好的 LSTM 模型，从数据库中读取最近的传感器数据，
预测未来一段时间的温度、湿度、光照、MQ135、ZP01 五项指标。

用法：
    python predict.py [预测点数] [间隔秒数]
    例如：python predict.py 1440 60   # 预测1440个点，每点间隔60秒（即24小时）

输出格式：
    JSON 数组，每个元素包含 timestamp 和五项传感器预测值。
"""

import json
import os
import sys
import warnings
from datetime import timedelta
import sqlite3

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

# 屏蔽 PyTorch 等库的警告信息，保持输出整洁
warnings.filterwarnings("ignore")


class EnviroLSTM(nn.Module):
    """
    环境数据 LSTM 预测模型

    结构：
        输入层 → LSTM（多层） → 全连接层 → 输出

    输入：shape (batch, window_size, input_size) 的时序特征序列
    输出：shape (batch, output_points * output_features) 的预测值展平向量
          其中 output_features=5（温度、湿度、光照、MQ135、ZP01）
          output_points 由模型权重自动推断（与训练时一致）

    参数说明：
        input_size     - 输入特征维度（10个特征，见下方说明）
        hidden_size    - LSTM 隐藏层维度
        num_layers     - LSTM 堆叠层数
        output_points  - 预测的时间步数
        output_features- 预测的传感器通道数（默认5）

    10个输入特征：
        0~4: temperature, humidity, light, mq135, zp01（传感器原始值）
        5:   time_delta（相邻记录的时间间隔，秒）
        6~9: hour, day_of_week, month, day_of_month（时间编码特征）
    """

    def __init__(self, input_size: int, hidden_size: int, num_layers: int, output_points: int, output_features: int = 5):
        super(EnviroLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.output_features = output_features

        # 多层 LSTM，batch_first=True 表示输入格式为 (batch, seq, feature)
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)

        # 全连接层：将最后一个时间步的隐藏状态映射为预测输出
        # 输出维度 = output_points × output_features，随后在外部 reshape
        self.fc = nn.Linear(hidden_size, output_points * output_features)

    def forward(self, x, device):
        """
        前向传播

        参数：
            x:      输入张量，shape (batch_size, window_size, input_size)
            device: 计算设备（cpu/cuda），用于初始化隐藏状态

        返回：
            预测张量，shape (batch_size, output_points * output_features)
        """
        batch_size = x.size(0)

        # 初始化 LSTM 的隐藏状态 h0 和细胞状态 c0，均为全零
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_size, device=device)
        c0 = torch.zeros(self.num_layers, batch_size, self.hidden_size, device=device)

        # LSTM 前向计算，out 为每个时间步的隐藏状态序列
        out, _ = self.lstm(x, (h0, c0))

        # 取最后一个时间步的隐藏状态，通过全连接层得到预测输出
        return self.fc(out[:, -1, :])


def get_device():
    """
    自动选择计算设备

    优先使用 CUDA GPU（如果可用），否则回退到 CPU。
    """
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        return torch.device("cuda")
    return torch.device("cpu")


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
    print("\n[错误] 未找到数据库文件", file=sys.stderr)
    print("已检查路径:", file=sys.stderr)
    for path in possible_paths:
        print(f"  - {path}", file=sys.stderr)

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
            print("[错误] 文件不存在，请重新选择", file=sys.stderr)
        elif choice == 'n':
            print("[退出] 程序终止", file=sys.stderr)
            sys.exit(1)


def predict():
    """
    主预测流程

    步骤：
        1. 解析命令行参数（预测点数、时间间隔）
        2. 加载模型和缩放参数
        3. 从数据库读取最近的传感器数据
        4. 特征工程（时间特征提取）+ 归一化
        5. 模型推理，得到归一化的预测值
        6. 反归一化，还原为真实物理量
        7. 组装 JSON 结果输出到 stdout
    """

    # --- 1. 解析命令行参数 ---
    # sys.argv[1]: 预测的时间步数，默认1440（即24小时 × 60分钟）
    # sys.argv[2]: 每个预测点的时间间隔（秒），默认60秒
    requested_pts = int(sys.argv[1]) if len(sys.argv) > 1 else 1440
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    # 模型固定参数（与训练时保持一致）
    WINDOW_SIZE = 360       # 输入窗口大小：360条记录（6小时）
    OUTPUT_FEATURES = 5     # 预测的传感器通道数

    device = get_device()

    # --- 2. 定位模型和缩放参数文件 ---
    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "models")
    db_path = find_database()

    scaler_path = os.path.join(models_dir, "scaler_params.json")
    model_path = os.path.join(models_dir, "enviro_model.pth")

    if not os.path.exists(scaler_path):
        print(f"[预测] 缩放参数文件未找到: {scaler_path}", file=sys.stderr)
        return
    if not os.path.exists(model_path):
        print(f"[预测] 模型文件未找到: {model_path}", file=sys.stderr)
        return

    # 加载训练时保存的归一化参数（每个特征的最小值和最大值）
    with open(scaler_path, "r") as f:
        scaler = json.load(f)
    f_min = np.array(scaler["mins"], dtype=np.float64)
    f_max = np.array(scaler["maxs"], dtype=np.float64)

    # --- 3. 从数据库读取最近的完整数据 ---
    # 只取最近2000条，且要求五项传感器值均非空
    conn = sqlite3.connect(db_path)
    query = """
        SELECT timestamp, temperature, humidity, light, mq135, zp01 
        FROM sensor_data 
        WHERE temperature IS NOT NULL AND humidity IS NOT NULL AND light IS NOT NULL AND mq135 IS NOT NULL AND zp01 IS NOT NULL
        ORDER BY timestamp DESC 
        LIMIT 2000
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty or len(df) < 2:
        print("[预测] 数据库数据不足", file=sys.stderr)
        return

    # --- 4. 特征工程 ---
    # 按时间升序排列
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # 计算相邻记录的时间间隔（秒），第一条填充为0
    df["time_delta"] = df["timestamp"].diff().dt.total_seconds().fillna(0.0)

    # 提取时间编码特征，帮助模型学习日周期等时间规律
    df["hour"] = df["timestamp"].dt.hour              # 小时（0~23）
    df["day_of_week"] = df["timestamp"].dt.dayofweek  # 星期几（0=周一）
    df["month"] = df["timestamp"].dt.month             # 月份（1~12）
    df["day_of_month"] = df["timestamp"].dt.day        # 几号（1~31）

    # 组合所有特征为 numpy 数组，共10列
    features = df[["temperature", "humidity", "light", "mq135", "zp01", "time_delta", "hour", "day_of_week", "month", "day_of_month"]].values.astype(np.float64)

    # --- 5. 构造输入窗口 ---
    # 取最后 WINDOW_SIZE 条记录作为模型输入
    if len(features) >= WINDOW_SIZE:
        recent = features[-WINDOW_SIZE:]
    else:
        # 数据不足时，用第一条记录填充前面的空位
        pad_len = WINDOW_SIZE - len(features)
        pad_block = np.repeat(features[:1, :], pad_len, axis=0)
        recent = np.concatenate([pad_block, features], axis=0)

    # Min-Max 归一化（与训练时一致）
    scaled = (recent - f_min) / (f_max - f_min + 1e-6)

    # 添加 batch 维度：(WINDOW_SIZE, 10) → (1, WINDOW_SIZE, 10)
    input_tensor = torch.from_numpy(scaled.astype(np.float32)).unsqueeze(0).to(device)

    # --- 6. 加载模型并推理 ---
    # 从模型权重中自动推断预测步数（确保与训练时一致）
    state_dict = torch.load(model_path, map_location=device)
    fc_weight_shape = state_dict["fc.weight"].shape
    PREDICT_STEPS = fc_weight_shape[0] // OUTPUT_FEATURES

    # 实例化模型、加载权重、切换到评估模式
    model = EnviroLSTM(input_size=10, hidden_size=128, num_layers=2, output_points=PREDICT_STEPS, output_features=OUTPUT_FEATURES).to(device)
    model.load_state_dict(state_dict)
    model.eval()

    # 推理（不计算梯度）
    with torch.no_grad():
        pred = model(input_tensor, device).cpu().numpy().flatten()

    # --- 7. 反归一化 ---
    # 将预测值从 [0,1] 还原为真实物理量
    # pred 的布局：前 PREDICT_STEPS 个是温度，接下来是湿度，以此类推
    p_temp = pred[:PREDICT_STEPS] * (f_max[0] - f_min[0]) + f_min[0]
    p_hum = pred[PREDICT_STEPS:2*PREDICT_STEPS] * (f_max[1] - f_min[1]) + f_min[1]
    p_light = pred[2*PREDICT_STEPS:3*PREDICT_STEPS] * (f_max[2] - f_min[2]) + f_min[2]
    p_mq135 = pred[3*PREDICT_STEPS:4*PREDICT_STEPS] * (f_max[3] - f_min[3]) + f_min[3]
    p_zp01 = pred[4*PREDICT_STEPS:5*PREDICT_STEPS] * (f_max[4] - f_min[4]) + f_min[4]

    # --- 8. 组装结果 ---
    # 实际输出点数 = 用户请求数 与 模型最大输出数 的较小值
    num_pts = min(requested_pts, PREDICT_STEPS)
    results = []
    last_time = df["timestamp"].iloc[-1]

    for i in range(num_pts):
        results.append(
            {
                # 时间戳：从最后一条真实记录开始，按 interval 秒递增
                "timestamp": (last_time + timedelta(seconds=(i + 1) * interval)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "temperature": round(float(p_temp[i]), 2),
                "humidity": round(float(p_hum[i]), 2),
                "light": round(float(p_light[i]), 2),
                "mq135": round(float(p_mq135[i]), 2),
                "zp01": round(float(p_zp01[i]), 2),
            }
        )

    # 输出 JSON 到 stdout，供 WebServer 或其他程序解析
    sys.stdout.write(json.dumps(results))
    sys.stdout.flush()


if __name__ == "__main__":
    predict()
