from flask import Blueprint, jsonify
import os
import sys
import subprocess
import json
from utils import log

predict_bp = Blueprint('predict', __name__)


@predict_bp.route('/api/predict', methods=['GET'])
def get_prediction():
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        predict_script = os.path.join(base_dir, 'LSTM', 'predict.py')
        
        if not os.path.exists(predict_script):
            error_msg = f'预测脚本未找到: {predict_script}'
            if log:
                log.error('API', error_msg)
            print(error_msg)
            return jsonify({'error': error_msg}), 404
        
        process = subprocess.Popen(
            [sys.executable, predict_script, '144', '600'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(timeout=120)
        
        if process.returncode != 0:
            error_msg = f'预测脚本执行失败: {stderr}'
            if log:
                log.error('API', error_msg)
            print(error_msg)
            return jsonify({'error': error_msg}), 500
        
        try:
            predictions = json.loads(stdout)
            if log:
                log.info('API', f'预测成功，共 {len(predictions)} 条数据')
            print(f'预测成功，共 {len(predictions)} 条数据')
            return jsonify({'predictions': predictions}), 200
        except json.JSONDecodeError as e:
            error_msg = f'解析预测结果失败: {str(e)}'
            if log:
                log.error('API', error_msg)
            print(error_msg)
            return jsonify({'error': error_msg}), 500
            
    except subprocess.TimeoutExpired:
        error_msg = '预测脚本执行超时'
        if log:
            log.error('API', error_msg)
        print(error_msg)
        return jsonify({'error': error_msg}), 500
    except Exception as e:
        error_msg = f'预测过程发生错误: {str(e)}'
        if log:
            log.error('API', error_msg)
        print(error_msg)
        return jsonify({'error': error_msg}), 500