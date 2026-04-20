from flask import request, jsonify
from app import app
from models import EnvironmentalData, db
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common import Logger

log = Logger.instance()

@app.route('/api/data', methods=['POST'])
def receive_data():
    """接收环境数据"""
    try:
        data = request.get_json()
        if not data:
            log.warning('API', 'No data provided in POST request')
            return jsonify({'error': 'No data provided'}), 400

        if 'timestamp' not in data:
            log.warning('API', 'Missing required field: timestamp')
            return jsonify({'error': 'Missing field: timestamp'}), 400

        try:
            timestamp = datetime.fromisoformat(data['timestamp'])
        except ValueError:
            log.warning('API', f'Invalid timestamp format: {data.get("timestamp")}')
            return jsonify({'error': 'Invalid timestamp format, use ISO format'}), 400

        new_data = EnvironmentalData(
            timestamp=timestamp,
            temperature=data.get('temperature'),
            humidity=data.get('humidity'),
            light=data.get('light'),
            gas=data.get('gas'),
            air_quality=data.get('air_quality'),
            noise=data.get('noise')
        )

        db.session.add(new_data)
        db.session.commit()
        
        log.info('API', f'Data received successfully at {timestamp}')
        return jsonify({'message': 'Data received successfully'}), 201
    except Exception as e:
        log.error('API', f'Error receiving data: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/data', methods=['GET'])
def get_data():
    """获取环境数据列表"""
    try:
        data = EnvironmentalData.query.order_by(EnvironmentalData.id.desc()).all()
        result = []
        for item in data:
            result.append({
                'id': item.id,
                'timestamp': item.timestamp.isoformat() if item.timestamp else None,
                'temperature': item.temperature,
                'humidity': item.humidity,
                'light': item.light,
                'gas': item.gas,
                'air_quality': item.air_quality,
                'noise': item.noise
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data/<int:id>', methods=['GET'])
def get_data_by_id(id):
    """根据ID获取环境数据"""
    try:
        data = EnvironmentalData.query.get(id)
        if not data:
            return jsonify({'error': 'Data not found'}), 404
        return jsonify({
            'id': data.id,
            'timestamp': data.timestamp.isoformat() if data.timestamp else None,
            'temperature': data.temperature,
            'humidity': data.humidity,
            'light': data.light,
            'gas': data.gas,
            'air_quality': data.air_quality,
            'noise': data.noise
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500