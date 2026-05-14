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

warnings.filterwarnings("ignore")


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


def get_device():
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        return torch.device("cuda")
    return torch.device("cpu")


def predict():
    requested_pts = int(sys.argv[1]) if len(sys.argv) > 1 else 1440
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    WINDOW_SIZE = 360
    OUTPUT_FEATURES = 5

    device = get_device()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "models")

    db_path_primary = os.path.join(base_dir, "dbData", "enviro_data.db")
    db_path_secondary = os.path.join(base_dir, "..", "QtProject", "EnviroTrend_demo-main", "deploy", "dbData", "enviro_data.db")
    db_path_secondary = os.path.normpath(os.path.expanduser(db_path_secondary))
    db_path = db_path_primary if os.path.exists(db_path_primary) else db_path_secondary

    scaler_path = os.path.join(models_dir, "scaler_params.json")
    model_path = os.path.join(models_dir, "enviro_model.pth")

    if not os.path.exists(scaler_path):
        print(f"[PREDICT] scaler_params.json not found at {scaler_path}")
        return
    if not os.path.exists(model_path):
        print(f"[PREDICT] enviro_model.pth not found at {model_path}")
        return
    if not os.path.exists(db_path):
        print(f"[PREDICT] SQLite database not found. Checked:")
        print(f"  - {db_path_primary}")
        print(f"  - {db_path_secondary}")
        return

    with open(scaler_path, "r") as f:
        scaler = json.load(f)
    f_min = np.array(scaler["mins"], dtype=np.float64)
    f_max = np.array(scaler["maxs"], dtype=np.float64)
    PREDICT_STEPS = scaler.get("output_points", 1440)

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
        print("[PREDICT] Insufficient data in database")
        return

    df = df.sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["time_delta"] = df["timestamp"].diff().dt.total_seconds().fillna(0.0)
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month
    df["day_of_month"] = df["timestamp"].dt.day

    features = df[["temperature", "humidity", "light", "mq135", "zp01", "time_delta", "hour", "day_of_week", "month", "day_of_month"]].values.astype(np.float64)

    if len(features) >= WINDOW_SIZE:
        recent = features[-WINDOW_SIZE:]
    else:
        pad_len = WINDOW_SIZE - len(features)
        pad_block = np.repeat(features[:1, :], pad_len, axis=0)
        recent = np.concatenate([pad_block, features], axis=0)

    scaled = (recent - f_min) / (f_max - f_min + 1e-6)
    input_tensor = torch.from_numpy(scaled.astype(np.float32)).unsqueeze(0).to(device)

    model = EnviroLSTM(input_size=10, hidden_size=128, num_layers=2, output_points=PREDICT_STEPS, output_features=OUTPUT_FEATURES).to(device)
    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    with torch.no_grad():
        pred = model(input_tensor, device).cpu().numpy().flatten()

    p_temp = pred[:PREDICT_STEPS] * (f_max[0] - f_min[0]) + f_min[0]
    p_hum = pred[PREDICT_STEPS:2*PREDICT_STEPS] * (f_max[1] - f_min[1]) + f_min[1]
    p_light = pred[2*PREDICT_STEPS:3*PREDICT_STEPS] * (f_max[2] - f_min[2]) + f_min[2]
    p_mq135 = pred[3*PREDICT_STEPS:4*PREDICT_STEPS] * (f_max[3] - f_min[3]) + f_min[3]
    p_zp01 = pred[4*PREDICT_STEPS:5*PREDICT_STEPS] * (f_max[4] - f_min[4]) + f_min[4]

    num_pts = min(requested_pts, PREDICT_STEPS)
    results = []
    last_time = df["timestamp"].iloc[-1]

    for i in range(num_pts):
        results.append(
            {
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

    sys.stdout.write(json.dumps(results))
    sys.stdout.flush()


if __name__ == "__main__":
    predict()