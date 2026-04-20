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

# 屏蔽所有警告，确保控制台输出只有纯净的 JSON（日志在 stdout 前半部分，由 Qt 侧截断）
warnings.filterwarnings("ignore")


# 与训练脚本保持一致的模型结构
class EnviroLSTM(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int, output_points: int):
        super(EnviroLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, output_points * 2)

    def forward(self, x, device):
        batch_size = x.size(0)
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_size, device=device)
        c0 = torch.zeros(self.num_layers, batch_size, self.hidden_size, device=device)
        out, _ = self.lstm(x, (h0, c0))
        return self.fc(out[:, -1, :])


def get_device():
    """
    推理阶段默认使用 CPU，但如果有可用 GPU 也可以启用。
    为避免嵌入式开发板上额外依赖，这里只做简单探测。
    """
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        return torch.device("cuda")
    return torch.device("cpu")


def predict():
    requested_pts = int(sys.argv[1]) if len(sys.argv) > 1 else 1440
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    WINDOW_SIZE = 360
    PREDICT_STEPS = 1440

    device = get_device()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "models")
    db_path = os.path.join(os.path.dirname(base_dir), "dbData", "enviro_data.db")

    scaler_path = os.path.join(models_dir, "scaler_params.json")
    model_path = os.path.join(models_dir, "enviro_model.pth")

    if not os.path.exists(scaler_path):
        print(f"[PREDICT] scaler_params.json not found at {scaler_path}")
        return
    if not os.path.exists(model_path):
        print(f"[PREDICT] enviro_model.pth not found at {model_path}")
        return
    if not os.path.exists(db_path):
        print(f"[PREDICT] SQLite database not found at {db_path}")
        return

    with open(scaler_path, "r") as f:
        scaler = json.load(f)
    f_min = np.array(scaler["mins"], dtype=np.float64)
    f_max = np.array(scaler["maxs"], dtype=np.float64)

    conn = sqlite3.connect(db_path)
    query = """
        SELECT timestamp, temp, hum 
        FROM sensor_data 
        WHERE temp IS NOT NULL AND hum IS NOT NULL
        ORDER BY timestamp DESC 
        LIMIT 2000
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty or len(df) < 2:
        print("[PREDICT] Insufficient data in database")
        return

    df = df.sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["time_delta"] = df["timestamp"].diff().dt.total_seconds().fillna(0.0)

    features = df[["temp", "hum", "time_delta"]].values.astype(np.float64)

    if len(features) >= WINDOW_SIZE:
        recent = features[-WINDOW_SIZE:]
    else:
        pad_len = WINDOW_SIZE - len(features)
        pad_block = np.repeat(features[:1, :], pad_len, axis=0)
        recent = np.concatenate([pad_block, features], axis=0)

    scaled = (recent - f_min) / (f_max - f_min + 1e-6)
    input_tensor = torch.from_numpy(scaled.astype(np.float32)).unsqueeze(0).to(device)

    model = EnviroLSTM(input_size=3, hidden_size=128, num_layers=2, output_points=PREDICT_STEPS).to(device)
    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    with torch.no_grad():
        pred = model(input_tensor, device).cpu().numpy().flatten()

    p_temp = pred[:PREDICT_STEPS] * (f_max[0] - f_min[0]) + f_min[0]
    p_hum = pred[PREDICT_STEPS:] * (f_max[1] - f_min[1]) + f_min[1]

    num_pts = min(requested_pts, PREDICT_STEPS)
    results = []
    last_time = df["timestamp"].iloc[-1]

    for i in range(num_pts):
        results.append(
            {
                "timestamp": (last_time + timedelta(seconds=(i + 1) * interval)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "temp": round(float(p_temp[i]), 2),
                "hum": round(float(p_hum[i]), 2),
            }
        )

    sys.stdout.write(json.dumps(results))
    sys.stdout.flush()


if __name__ == "__main__":
    predict()