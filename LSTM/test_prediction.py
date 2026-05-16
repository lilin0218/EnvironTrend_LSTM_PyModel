import os
import json
import sqlite3
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import matplotlib.pyplot as plt
from datetime import datetime, timedelta


class EnviroLSTM(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int, output_points: int,
                 output_features: int = 5):
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
        return torch.device("cuda")
    return torch.device("cpu")


def load_data(db_path, end_time, window_size):
    conn = sqlite3.connect(db_path)

    query_time_range = "SELECT MIN(timestamp), MAX(timestamp) FROM sensor_data WHERE temperature IS NOT NULL AND humidity IS NOT NULL AND light IS NOT NULL AND mq135 IS NOT NULL AND zp01 IS NOT NULL"
    time_range = pd.read_sql_query(query_time_range, conn)
    min_time, max_time = time_range.iloc[0, 0], time_range.iloc[0, 1]

    if min_time is None or max_time is None:
        conn.close()
        raise ValueError("No valid data found in database")

    min_time = pd.to_datetime(min_time)
    max_time = pd.to_datetime(max_time)

    print(f"Database time range: {min_time} to {max_time}")

    start_time = end_time - timedelta(minutes=window_size)

    if start_time < min_time:
        start_time = min_time
        print(f"Adjusted start time to database minimum: {start_time}")
    if end_time > max_time:
        end_time = max_time
        print(f"Adjusted end time to database maximum: {end_time}")

    if start_time >= end_time:
        new_end_time = max_time
        new_start_time = new_end_time - timedelta(minutes=window_size)
        if new_start_time < min_time:
            new_start_time = min_time
        start_time, end_time = new_start_time, new_end_time
        print(f"Adjusted time range to ensure valid window: {start_time} to {end_time}")

    query = f"""
        SELECT timestamp, temperature, humidity, light, mq135, zp01 
        FROM sensor_data 
        WHERE temperature IS NOT NULL AND humidity IS NOT NULL AND light IS NOT NULL AND mq135 IS NOT NULL AND zp01 IS NOT NULL
        AND timestamp >= '{start_time}' AND timestamp <= '{end_time}'
        ORDER BY timestamp ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        raise ValueError(f"No data found in the specified time range: {start_time} to {end_time}")

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["time_delta"] = df["timestamp"].diff().dt.total_seconds().fillna(0.0)
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month
    df["day_of_month"] = df["timestamp"].dt.day

    return df


def load_model(model_path, scaler_path, device):
    with open(scaler_path, "r") as f:
        scaler_params = json.load(f)
    mins = np.array(scaler_params["mins"])
    maxs = np.array(scaler_params["maxs"])

    checkpoint = torch.load(model_path, map_location=device)
    fc_weight_shape = checkpoint["fc.weight"].shape
    output_points = fc_weight_shape[0] // 5

    model = EnviroLSTM(input_size=10, hidden_size=128, num_layers=2, output_points=output_points, output_features=5).to(
        device)
    model.load_state_dict(checkpoint)
    model.eval()

    print(f"Loaded model with output_points={output_points}")
    return model, mins, maxs, output_points


def prepare_input(df, mins, maxs, device):
    data = df[["temperature", "humidity", "light", "mq135", "zp01", "time_delta", "hour", "day_of_week", "month",
               "day_of_month"]].values.astype(np.float64)
    normalized_data = (data - mins) / (maxs - mins + 1e-6)
    input_tensor = torch.from_numpy(normalized_data.astype(np.float32)).unsqueeze(0).to(device)
    return input_tensor


def predict(model, input_tensor, device, mins, maxs):
    with torch.no_grad():
        output = model(input_tensor, device)

    output = output.cpu().numpy()[0]
    output_points = len(output) // 5

    temp_pred = output[:output_points] * (maxs[0] - mins[0]) + mins[0]
    hum_pred = output[output_points:2 * output_points] * (maxs[1] - mins[1]) + mins[1]
    light_pred = output[2 * output_points:3 * output_points] * (maxs[2] - mins[2]) + mins[2]
    mq135_pred = output[3 * output_points:4 * output_points] * (maxs[3] - mins[3]) + mins[3]
    zp01_pred = output[4 * output_points:5 * output_points] * (maxs[4] - mins[4]) + mins[4]

    return temp_pred, hum_pred, light_pred, mq135_pred, zp01_pred


def generate_time_series(start_time, output_points):
    times = []
    current_time = start_time
    for i in range(output_points):
        times.append(current_time)
        current_time += timedelta(minutes=1)
    return times


def calculate_accuracy(predicted, actual, tolerance=None):
    min_length = min(len(predicted), len(actual))
    predicted = predicted[:min_length]
    actual = actual[:min_length]

    rmse = np.sqrt(np.mean((predicted - actual) ** 2))
    mae = np.mean(np.abs(predicted - actual))
    mean_actual = np.mean(actual)
    relative_error = rmse / mean_actual if mean_actual > 0 else 0
    
    within_tolerance = None
    if tolerance is not None:
        errors = np.abs(predicted - actual)
        within_tolerance = np.mean(errors <= tolerance) * 100

    return {
        "rmse": rmse,
        "mae": mae,
        "relative_error": relative_error,
        "accuracy": 1 - relative_error if relative_error < 1 else 0,
        "within_tolerance_percent": within_tolerance
    }


def save_tolerances(tolerances, base_dir):
    tolerances_path = os.path.join(base_dir, "tolerances.json")
    with open(tolerances_path, "w", encoding="utf-8") as f:
        json.dump(tolerances, f, ensure_ascii=False, indent=2)
    print(f"✓ Tolerances saved to {tolerances_path}")


def load_tolerances(base_dir):
    tolerances_path = os.path.join(base_dir, "tolerances.json")
    default_tolerances = {
        "temperature": 1.0,
        "humidity": 2.5,
        "light": 0.5,
        "mq135": 2.0,
        "zp01": 2.0
    }
    
    if os.path.exists(tolerances_path):
        with open(tolerances_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_tolerances


def run_prediction_and_generate_chart():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "models")
    DB_PATH = os.path.join(os.path.dirname(base_dir), "dbData", "enviro_data.db")
    MODEL_PATH = os.path.join(models_dir, "enviro_model.pth")
    SCALER_PATH = os.path.join(models_dir, "scaler_params.json")
    WINDOW_SIZE = 360

    if not os.path.exists(MODEL_PATH):
        print("Error: Model file not found")
        return None
    if not os.path.exists(SCALER_PATH):
        print("Error: Scaler params file not found")
        return None

    device = get_device()
    print(f"Using device: {device}")

    model, mins, maxs, output_points = load_model(MODEL_PATH, SCALER_PATH, device)

    conn = sqlite3.connect(DB_PATH)
    query = "SELECT MAX(timestamp) FROM sensor_data"
    last_time = pd.read_sql_query(query, conn).iloc[0, 0]
    conn.close()

    if last_time is None:
        print("Error: No data in database")
        return None

    last_time = pd.to_datetime(last_time)
    print(f"Last time in database: {last_time}")

    prediction_start = last_time - timedelta(hours=24)
    prediction_end = last_time
    print(f"Predicting from {prediction_start} to {prediction_end}")

    input_df = load_data(DB_PATH, prediction_start, WINDOW_SIZE)
    print(f"Loaded {len(input_df)} data points for prediction")

    input_tensor = prepare_input(input_df, mins, maxs, device)

    temp_pred, hum_pred, light_pred, mq135_pred, zp01_pred = predict(model, input_tensor, device, mins, maxs)
    print(f"Predicted {len(temp_pred)} points")

    predicted_times = generate_time_series(prediction_start, len(temp_pred))

    conn = sqlite3.connect(DB_PATH)
    query = f"""
        SELECT timestamp, temperature, humidity, light, mq135, zp01 
        FROM sensor_data 
        WHERE temperature IS NOT NULL AND humidity IS NOT NULL AND light IS NOT NULL AND mq135 IS NOT NULL AND zp01 IS NOT NULL
        AND timestamp >= '{prediction_start}' AND timestamp <= '{prediction_end}'
        ORDER BY timestamp ASC
    """
    actual_df = pd.read_sql_query(query, conn)
    conn.close()

    print(f"Loaded {len(actual_df)} actual data points")

    actual_times = pd.to_datetime(actual_df["timestamp"])
    actual_temp = actual_df["temperature"].values
    actual_hum = actual_df["humidity"].values
    actual_light = actual_df["light"].values
    actual_mq135 = actual_df["mq135"].values
    actual_zp01 = actual_df["zp01"].values

    actual_times_datetime = [t.to_pydatetime() for t in actual_times]
    time_to_temp = {time: temp for time, temp in zip(actual_times_datetime, actual_temp)}
    time_to_hum = {time: hum for time, hum in zip(actual_times_datetime, actual_hum)}
    time_to_light = {time: light for time, light in zip(actual_times_datetime, actual_light)}
    time_to_mq135 = {time: mq for time, mq in zip(actual_times_datetime, actual_mq135)}
    time_to_zp01 = {time: zp for time, zp in zip(actual_times_datetime, actual_zp01)}

    aligned_pred_temp = []
    aligned_actual_temp = []
    aligned_pred_hum = []
    aligned_actual_hum = []
    aligned_pred_light = []
    aligned_actual_light = []
    aligned_pred_mq135 = []
    aligned_actual_mq135 = []
    aligned_pred_zp01 = []
    aligned_actual_zp01 = []
    aligned_times = []

    time_to_temp_minute = {t.replace(second=0): v for t, v in time_to_temp.items()}
    time_to_hum_minute = {t.replace(second=0): v for t, v in time_to_hum.items()}
    time_to_light_minute = {t.replace(second=0): v for t, v in time_to_light.items()}
    time_to_mq135_minute = {t.replace(second=0): v for t, v in time_to_mq135.items()}
    time_to_zp01_minute = {t.replace(second=0): v for t, v in time_to_zp01.items()}

    for time, pred_temp, pred_hum, pred_light, pred_mq135, pred_zp01 in zip(predicted_times, temp_pred, hum_pred,
                                                                            light_pred, mq135_pred, zp01_pred):
        time_minute = time.replace(second=0)
        if (time_minute in time_to_temp_minute and
                time_minute in time_to_hum_minute and
                time_minute in time_to_light_minute and
                time_minute in time_to_mq135_minute and
                time_minute in time_to_zp01_minute):
            aligned_pred_temp.append(pred_temp)
            aligned_actual_temp.append(time_to_temp_minute[time_minute])
            aligned_pred_hum.append(pred_hum)
            aligned_actual_hum.append(time_to_hum_minute[time_minute])
            aligned_pred_light.append(pred_light)
            aligned_actual_light.append(time_to_light_minute[time_minute])
            aligned_pred_mq135.append(pred_mq135)
            aligned_actual_mq135.append(time_to_mq135_minute[time_minute])
            aligned_pred_zp01.append(pred_zp01)
            aligned_actual_zp01.append(time_to_zp01_minute[time_minute])
            aligned_times.append(time_minute)

    aligned_pred_temp = np.array(aligned_pred_temp)
    aligned_actual_temp = np.array(aligned_actual_temp)
    aligned_pred_hum = np.array(aligned_pred_hum)
    aligned_actual_hum = np.array(aligned_actual_hum)
    aligned_pred_light = np.array(aligned_pred_light)
    aligned_actual_light = np.array(aligned_actual_light)
    aligned_pred_mq135 = np.array(aligned_pred_mq135)
    aligned_actual_mq135 = np.array(aligned_actual_mq135)
    aligned_pred_zp01 = np.array(aligned_pred_zp01)
    aligned_actual_zp01 = np.array(aligned_actual_zp01)

    fig, axes = plt.subplots(5, 2, figsize=(16, 20), sharex=True)

    if aligned_times:
        min_time = min(aligned_times)
        max_time = max(aligned_times)
        time_range = max_time - min_time
        padding = time_range * 0.05
        x_min = min_time - padding
        x_max = max_time + padding
    else:
        x_min = None
        x_max = None

    time_diffs = np.diff(aligned_times).tolist() if aligned_times else []
    time_diff_seconds = [td.total_seconds() for td in time_diffs] if time_diffs else [60]
    time_diff = np.mean(time_diff_seconds)
    bar_width = time_diff / (24 * 3600) * 0.8

    ax = axes[0, 0]
    ax.plot(aligned_times, aligned_actual_temp, label='Actual', color='blue', linewidth=2)
    ax.plot(aligned_times, aligned_pred_temp, label='Predicted', color='red', linestyle='--', linewidth=2)
    ax.set_title('Temperature: Actual vs Predicted')
    ax.set_ylabel('Temperature (°C)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    if x_min and x_max:
        ax.set_xlim(x_min, x_max)

    ax = axes[0, 1]
    ax.bar(aligned_times, np.abs(aligned_pred_temp - aligned_actual_temp), width=bar_width, color='green', alpha=0.6)
    ax.set_title('Temperature Prediction Error')
    ax.set_ylabel('Error (°C)')
    ax.grid(True, alpha=0.3)
    if x_min and x_max:
        ax.set_xlim(x_min, x_max)

    ax = axes[1, 0]
    ax.plot(aligned_times, aligned_actual_hum, label='Actual', color='blue', linewidth=2)
    ax.plot(aligned_times, aligned_pred_hum, label='Predicted', color='red', linestyle='--', linewidth=2)
    ax.set_title('Humidity: Actual vs Predicted')
    ax.set_ylabel('Humidity (%)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    if x_min and x_max:
        ax.set_xlim(x_min, x_max)

    ax = axes[1, 1]
    ax.bar(aligned_times, np.abs(aligned_pred_hum - aligned_actual_hum), width=bar_width, color='green', alpha=0.6)
    ax.set_title('Humidity Prediction Error')
    ax.set_ylabel('Error (%)')
    ax.grid(True, alpha=0.3)
    if x_min and x_max:
        ax.set_xlim(x_min, x_max)

    ax = axes[2, 0]
    ax.plot(aligned_times, aligned_actual_light, label='Actual', color='blue', linewidth=2)
    ax.plot(aligned_times, aligned_pred_light, label='Predicted', color='red', linestyle='--', linewidth=2)
    ax.set_title('Light: Actual vs Predicted')
    ax.set_ylabel('Light')
    ax.legend()
    ax.grid(True, alpha=0.3)
    if x_min and x_max:
        ax.set_xlim(x_min, x_max)

    ax = axes[2, 1]
    ax.bar(aligned_times, np.abs(aligned_pred_light - aligned_actual_light), width=bar_width, color='green', alpha=0.6)
    ax.set_title('Light Prediction Error')
    ax.set_ylabel('Error')
    ax.grid(True, alpha=0.3)
    if x_min and x_max:
        ax.set_xlim(x_min, x_max)

    ax = axes[3, 0]
    ax.plot(aligned_times, aligned_actual_mq135, label='Actual', color='blue', linewidth=2)
    ax.plot(aligned_times, aligned_pred_mq135, label='Predicted', color='red', linestyle='--', linewidth=2)
    ax.set_title('MQ135: Actual vs Predicted')
    ax.set_ylabel('MQ135')
    ax.legend()
    ax.grid(True, alpha=0.3)
    if x_min and x_max:
        ax.set_xlim(x_min, x_max)

    ax = axes[3, 1]
    ax.bar(aligned_times, np.abs(aligned_pred_mq135 - aligned_actual_mq135), width=bar_width, color='green', alpha=0.6)
    ax.set_title('MQ135 Prediction Error')
    ax.set_ylabel('Error')
    ax.grid(True, alpha=0.3)
    if x_min and x_max:
        ax.set_xlim(x_min, x_max)

    ax = axes[4, 0]
    ax.plot(aligned_times, aligned_actual_zp01, label='Actual', color='blue', linewidth=2)
    ax.plot(aligned_times, aligned_pred_zp01, label='Predicted', color='red', linestyle='--', linewidth=2)
    ax.set_title('ZP01: Actual vs Predicted')
    ax.set_ylabel('ZP01')
    ax.set_xlabel('Time')
    ax.legend()
    ax.grid(True, alpha=0.3)
    if x_min and x_max:
        ax.set_xlim(x_min, x_max)

    ax = axes[4, 1]
    ax.bar(aligned_times, np.abs(aligned_pred_zp01 - aligned_actual_zp01), width=bar_width, color='green', alpha=0.6)
    ax.set_title('ZP01 Prediction Error')
    ax.set_ylabel('Error')
    ax.set_xlabel('Time')
    ax.grid(True, alpha=0.3)
    if x_min and x_max:
        ax.set_xlim(x_min, x_max)

    fig.autofmt_xdate()
    plt.xticks(rotation=45)

    plt.tight_layout()

    chart_path = os.path.join(base_dir, 'prediction_comparison.png')
    plt.savefig(chart_path)
    print(f"✓ Chart saved as {chart_path}")
    
    plt.close()

    return {
        "temp": (aligned_pred_temp, aligned_actual_temp),
        "hum": (aligned_pred_hum, aligned_actual_hum),
        "light": (aligned_pred_light, aligned_actual_light),
        "mq135": (aligned_pred_mq135, aligned_actual_mq135),
        "zp01": (aligned_pred_zp01, aligned_actual_zp01)
    }


def show_avg_errors(prediction_data):
    print("\n" + "=" * 50)
    print("平均误差统计")
    print("=" * 50)
    
    sensor_names = {
        "temp": ("Temperature", "°C"),
        "hum": ("Humidity", "%"),
        "light": ("Light", ""),
        "mq135": ("MQ135", ""),
        "zp01": ("ZP01", "")
    }
    
    for sensor_key, (name, unit) in sensor_names.items():
        pred, actual = prediction_data[sensor_key]
        result = calculate_accuracy(pred, actual)
        print(f"\n{name}:")
        print(f"  MAE (平均绝对误差): {result['mae']:.4f} {unit}")
        print(f"  RMSE (均方根误差): {result['rmse']:.4f} {unit}")
    
    print("\n" + "=" * 50)


def set_tolerances(base_dir):
    print("\n" + "=" * 50)
    print("设置容忍误差")
    print("=" * 50)
    
    current_tolerances = load_tolerances(base_dir)
    
    print("\n当前容忍误差设置:")
    sensor_names = {
        "temperature": ("Temperature", "°C"),
        "humidity": ("Humidity", "%"),
        "light": ("Light", ""),
        "mq135": ("MQ135", ""),
        "zp01": ("ZP01", "")
    }
    
    for key, (name, unit) in sensor_names.items():
        print(f"  {name}: {current_tolerances.get(key, 'N/A')} {unit}")
    
    print("\n请输入新的容忍误差（直接回车保持原值）:")
    new_tolerances = {}
    
    for key, (name, unit) in sensor_names.items():
        while True:
            try:
                current_val = current_tolerances.get(key, 0)
                user_input = input(f"  {name} [当前: {current_val}] {unit}: ").strip()
                
                if user_input == "":
                    new_tolerances[key] = current_val
                    break
                
                val = float(user_input)
                if val < 0:
                    print("    错误: 容忍误差不能为负数")
                    continue
                
                new_tolerances[key] = val
                break
            except ValueError:
                print("    错误: 请输入有效的数字")
    
    save_tolerances(new_tolerances, base_dir)
    print("\n" + "=" * 50)


def query_hit_rate(prediction_data, base_dir):
    print("\n" + "=" * 50)
    print("预测命中率查询")
    print("=" * 50)
    
    tolerances = load_tolerances(base_dir)
    
    print("\n当前容忍误差设置:")
    sensor_names = {
        "temp": ("Temperature", "°C", "temperature"),
        "hum": ("Humidity", "%", "humidity"),
        "light": ("Light", "", "light"),
        "mq135": ("MQ135", "", "mq135"),
        "zp01": ("ZP01", "", "zp01")
    }
    
    print("\n预测命中率:")
    print("-" * 50)
    
    for sensor_key, (name, unit, tolerance_key) in sensor_names.items():
        pred, actual = prediction_data[sensor_key]
        tolerance = tolerances.get(tolerance_key, 0)
        result = calculate_accuracy(pred, actual, tolerance)
        
        hit_rate = result['within_tolerance_percent'] or 0
        print(f"\n{name} (容忍误差: {tolerance} {unit}):")
        print(f"  命中率: {hit_rate:.2f}%")
        print(f"  MAE: {result['mae']:.4f} {unit}")
        print(f"  RMSE: {result['rmse']:.4f} {unit}")
    
    print("\n" + "=" * 50)


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("=" * 60)
    print("环境预测分析工具")
    print("=" * 60)
    
    print("\n[步骤 1] 生成预测对比图...")
    prediction_data = run_prediction_and_generate_chart()
    
    if prediction_data is None:
        print("预测失败，程序退出")
        return
    
    while True:
        print("\n" + "=" * 60)
        print("请选择操作:")
        print("  1. 查看误差平均值")
        print("  2. 设置容忍误差")
        print("  3. 查询预测命中率")
        print("  4. 退出")
        print("=" * 60)
        
        choice = input("\n请输入选项 (1-4): ").strip()
        
        if choice == "1":
            show_avg_errors(prediction_data)
        elif choice == "2":
            set_tolerances(base_dir)
        elif choice == "3":
            query_hit_rate(prediction_data, base_dir)
        elif choice == "4":
            print("\n程序终了")
            break
        else:
            print("\n无效选项，请重新输入")


if __name__ == "__main__":
    main()
