import os
import json
import sqlite3
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# 加载模型结构
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

# 获取设备
def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")

# 加载数据
def load_data(db_path, end_time, window_size):
    conn = sqlite3.connect(db_path)
    
    # 首先查询数据库中的所有时间范围
    query_time_range = "SELECT MIN(timestamp), MAX(timestamp) FROM sensor_data WHERE temp IS NOT NULL AND hum IS NOT NULL"
    time_range = pd.read_sql_query(query_time_range, conn)
    min_time, max_time = time_range.iloc[0, 0], time_range.iloc[0, 1]
    
    if min_time is None or max_time is None:
        conn.close()
        raise ValueError("No valid data found in database")
    
    min_time = pd.to_datetime(min_time)
    max_time = pd.to_datetime(max_time)
    
    print(f"Database time range: {min_time} to {max_time}")
    
    # 计算开始时间
    start_time = end_time - timedelta(minutes=window_size)
    
    # 确保时间范围在数据库范围内
    if start_time < min_time:
        start_time = min_time
        print(f"Adjusted start time to database minimum: {start_time}")
    if end_time > max_time:
        end_time = max_time
        print(f"Adjusted end time to database maximum: {end_time}")
    
    # 确保start_time < end_time
    if start_time >= end_time:
        # 调整为数据库中的最后window_size分钟
        new_end_time = max_time
        new_start_time = new_end_time - timedelta(minutes=window_size)
        if new_start_time < min_time:
            new_start_time = min_time
        start_time, end_time = new_start_time, new_end_time
        print(f"Adjusted time range to ensure valid window: {start_time} to {end_time}")
    
    query = f"""
        SELECT timestamp, temp, hum 
        FROM sensor_data 
        WHERE temp IS NOT NULL AND hum IS NOT NULL
        AND timestamp >= '{start_time}' AND timestamp <= '{end_time}'
        ORDER BY timestamp ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        raise ValueError(f"No data found in the specified time range: {start_time} to {end_time}")
    
    # 计算时间差
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["time_delta"] = df["timestamp"].diff().dt.total_seconds().fillna(0.0)
    
    # 添加日期时间特征
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month
    df["day_of_month"] = df["timestamp"].dt.day
    
    return df

# 加载模型和参数
def load_model(model_path, scaler_path, device):
    # 加载缩放参数
    with open(scaler_path, "r") as f:
        scaler_params = json.load(f)
    mins = np.array(scaler_params["mins"])
    maxs = np.array(scaler_params["maxs"])
    
    # 先加载模型权重以确定输出点数量
    checkpoint = torch.load(model_path, map_location=device)
    # 从fc层的权重形状推断输出点数量
    fc_weight_shape = checkpoint["fc.weight"].shape
    output_points = fc_weight_shape[0] // 2  # 因为输出包含温度和湿度
    
    # 加载模型
    model = EnviroLSTM(input_size=7, hidden_size=128, num_layers=2, output_points=output_points).to(device)
    model.load_state_dict(checkpoint)
    model.eval()
    
    print(f"Loaded model with output_points={output_points}")
    return model, mins, maxs, output_points

# 准备输入数据
def prepare_input(df, mins, maxs, device):
    data = df[["temp", "hum", "time_delta", "hour", "day_of_week", "month", "day_of_month"]].values.astype(np.float64)
    # 归一化
    normalized_data = (data - mins) / (maxs - mins + 1e-6)
    # 转换为张量并移动到指定设备
    input_tensor = torch.from_numpy(normalized_data.astype(np.float32)).unsqueeze(0).to(device)  # 添加 batch 维度并移动到设备
    return input_tensor

# 预测
def predict(model, input_tensor, device, mins, maxs):
    with torch.no_grad():
        output = model(input_tensor, device)
    
    # 反归一化
    output = output.cpu().numpy()[0]
    output_points = len(output) // 2
    
    # 分离温度和湿度
    temp_pred = output[:output_points] * (maxs[0] - mins[0]) + mins[0]
    hum_pred = output[output_points:] * (maxs[1] - mins[1]) + mins[1]
    
    return temp_pred, hum_pred

# 生成预测时间序列
def generate_time_series(start_time, output_points):
    times = []
    current_time = start_time
    for i in range(output_points):
        times.append(current_time)
        current_time += timedelta(minutes=1)
    return times

# 计算准确率
def calculate_accuracy(predicted, actual):
    # 确保两者长度相同
    min_length = min(len(predicted), len(actual))
    predicted = predicted[:min_length]
    actual = actual[:min_length]
    
    # 计算均方根误差
    rmse = np.sqrt(np.mean((predicted - actual) ** 2))
    # 计算平均绝对误差
    mae = np.mean(np.abs(predicted - actual))
    # 计算相对误差
    mean_actual = np.mean(actual)
    relative_error = rmse / mean_actual if mean_actual > 0 else 0
    
    return {
        "rmse": rmse,
        "mae": mae,
        "relative_error": relative_error,
        "accuracy": 1 - relative_error if relative_error < 1 else 0
    }

# 主函数
def main():
    # 参数设置
    DB_PATH = "dbData/enviro_data.db"
    MODEL_PATH = "models/enviro_model.pth"
    SCALER_PATH = "models/scaler_params.json"
    WINDOW_SIZE = 360  # 与训练时一致
    
    # 检查文件是否存在
    if not os.path.exists(MODEL_PATH):
        print("Error: Model file not found")
        return
    if not os.path.exists(SCALER_PATH):
        print("Error: Scaler params file not found")
        return
    
    # 获取设备
    device = get_device()
    print(f"Using device: {device}")
    
    # 加载模型和参数
    model, mins, maxs, output_points = load_model(MODEL_PATH, SCALER_PATH, device)
    
    # 获取数据库中的最后时间
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT MAX(timestamp) FROM sensor_data"
    last_time = pd.read_sql_query(query, conn).iloc[0, 0]
    conn.close()
    
    if last_time is None:
        print("Error: No data in database")
        return
    
    last_time = pd.to_datetime(last_time)
    print(f"Last time in database: {last_time}")
    
    # 计算预测的开始和结束时间
    prediction_start = last_time - timedelta(hours=24)
    prediction_end = last_time
    print(f"Predicting from {prediction_start} to {prediction_end}")
    
    # 加载输入数据（用于预测的数据）
    input_df = load_data(DB_PATH, prediction_start, WINDOW_SIZE)
    print(f"Loaded {len(input_df)} data points for prediction")
    
    # 准备输入数据
    input_tensor = prepare_input(input_df, mins, maxs, device)
    
    # 预测
    temp_pred, hum_pred = predict(model, input_tensor, device, mins, maxs)
    print(f"Predicted {len(temp_pred)} points")
    
    # 生成预测时间序列
    predicted_times = generate_time_series(prediction_start, len(temp_pred))
    
    # 加载实际数据
    conn = sqlite3.connect(DB_PATH)
    query = f"""
        SELECT timestamp, temp, hum 
        FROM sensor_data 
        WHERE temp IS NOT NULL AND hum IS NOT NULL
        AND timestamp >= '{prediction_start}' AND timestamp <= '{prediction_end}'
        ORDER BY timestamp ASC
    """
    actual_df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"Loaded {len(actual_df)} actual data points")
    
    # 对齐预测数据和实际数据
    actual_times = pd.to_datetime(actual_df["timestamp"])
    actual_temp = actual_df["temp"].values
    actual_hum = actual_df["hum"].values
    
    # 创建时间到值的映射
    time_to_temp = {time: temp for time, temp in zip(actual_times, actual_temp)}
    time_to_hum = {time: hum for time, hum in zip(actual_times, actual_hum)}
    
    # 对齐数据，跳过空缺
    aligned_pred_temp = []
    aligned_actual_temp = []
    aligned_pred_hum = []
    aligned_actual_hum = []
    aligned_times = []
    
    for time, pred_temp, pred_hum in zip(predicted_times, temp_pred, hum_pred):
        if time in time_to_temp and time in time_to_hum:
            aligned_pred_temp.append(pred_temp)
            aligned_actual_temp.append(time_to_temp[time])
            aligned_pred_hum.append(pred_hum)
            aligned_actual_hum.append(time_to_hum[time])
            aligned_times.append(time)
    
    # 转换为numpy数组
    aligned_pred_temp = np.array(aligned_pred_temp)
    aligned_actual_temp = np.array(aligned_actual_temp)
    aligned_pred_hum = np.array(aligned_pred_hum)
    aligned_actual_hum = np.array(aligned_actual_hum)
    
    # 计算准确率
    temp_accuracy = calculate_accuracy(aligned_pred_temp, aligned_actual_temp)
    print(f"Temperature prediction accuracy: {temp_accuracy['accuracy']:.4f}")
    print(f"Temperature RMSE: {temp_accuracy['rmse']:.4f}")
    print(f"Temperature MAE: {temp_accuracy['mae']:.4f}")
    
    hum_accuracy = calculate_accuracy(aligned_pred_hum, aligned_actual_hum)
    print(f"Humidity prediction accuracy: {hum_accuracy['accuracy']:.4f}")
    print(f"Humidity RMSE: {hum_accuracy['rmse']:.4f}")
    print(f"Humidity MAE: {hum_accuracy['mae']:.4f}")
    
    # 计算误差
    temp_errors = np.abs(aligned_pred_temp - aligned_actual_temp)
    hum_errors = np.abs(aligned_pred_hum - aligned_actual_hum)
    
    # 绘制图表
    fig, axes = plt.subplots(4, 1, figsize=(14, 16), sharex=True)
    
    # 确保x轴范围覆盖整个时间序列
    if aligned_times:
        min_time = min(aligned_times)
        max_time = max(aligned_times)
        # 扩展时间范围，确保图表从左侧开始到右侧结束
        time_range = max_time - min_time
        padding = time_range * 0.05  # 5%的 padding
        x_min = min_time - padding
        x_max = max_time + padding
    else:
        x_min = None
        x_max = None
    
    # 温度折线图：预测值 vs 实际值
    ax1 = axes[0]
    ax1.plot(aligned_times, aligned_actual_temp, label='Actual Temperature', color='blue', linewidth=2)
    ax1.plot(aligned_times, aligned_pred_temp, label='Predicted Temperature', color='red', linestyle='--', linewidth=2)
    ax1.set_title('Temperature: Actual vs Predicted')
    ax1.set_ylabel('Temperature (°C)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    if x_min and x_max:
        ax1.set_xlim(x_min, x_max)
    
    # 温度误差柱状图
    ax2 = axes[1]
    # 使用与折线图相同的时间数据，设置柱状图宽度
    if aligned_times:
        # 计算时间间隔作为柱宽
        time_diffs = np.diff(aligned_times)
        # 将Timedelta转换为秒数
        time_diff_seconds = [td.total_seconds() for td in time_diffs]
        time_diff = np.mean(time_diff_seconds)
        # 转换为天数（matplotlib的时间单位）
        bar_width = time_diff / (24 * 3600) * 0.8  # 80%的时间间隔
        ax2.bar(aligned_times, temp_errors, width=bar_width, color='green', alpha=0.6)
    ax2.set_title('Temperature Prediction Error')
    ax2.set_ylabel('Error (°C)')
    ax2.set_ylim(0, 8)  # 设置误差柱状图高度为8
    ax2.grid(True, alpha=0.3)
    if x_min and x_max:
        ax2.set_xlim(x_min, x_max)
    
    # 湿度折线图：预测值 vs 实际值
    ax3 = axes[2]
    ax3.plot(aligned_times, aligned_actual_hum, label='Actual Humidity', color='blue', linewidth=2)
    ax3.plot(aligned_times, aligned_pred_hum, label='Predicted Humidity', color='red', linestyle='--', linewidth=2)
    ax3.set_title('Humidity: Actual vs Predicted')
    ax3.set_ylabel('Humidity (%)')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    if x_min and x_max:
        ax3.set_xlim(x_min, x_max)
    
    # 湿度误差柱状图
    ax4 = axes[3]
    if aligned_times:
        ax4.bar(aligned_times, hum_errors, width=bar_width, color='green', alpha=0.6)
    ax4.set_title('Humidity Prediction Error')
    ax4.set_ylabel('Error (%)')
    ax4.set_ylim(0, 20)  # 设置湿度误差柱状图高度为20
    ax4.set_xlabel('Time')
    ax4.grid(True, alpha=0.3)
    if x_min and x_max:
        ax4.set_xlim(x_min, x_max)
    
    # 确保时间轴标注清晰
    fig.autofmt_xdate()  # 自动格式化日期
    plt.xticks(rotation=45)  # 旋转x轴标签以便更好地显示
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图表
    plt.savefig('prediction_comparison.png')
    print("Chart saved as prediction_comparison.png")
    
    # 显示图表
    plt.show()

if __name__ == "__main__":
    main()