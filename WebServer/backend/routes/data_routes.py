from flask import Blueprint, request, jsonify
from models import EnvironmentalData, db
from datetime import datetime
from sqlalchemy import func
from utils import log

data_bp = Blueprint('data', __name__)


@data_bp.route('/api/data', methods=['POST'])
def receive_data():
    try:
        data = request.get_json()
        if not data:
            if log:
                log.warning('API', 'No data provided in POST request')
            print('No data provided in POST request')
            return jsonify({'error': 'No data provided'}), 400

        if 'timestamp' not in data:
            if log:
                log.warning('API', 'Missing required field: timestamp')
            print('Missing required field: timestamp')
            return jsonify({'error': 'Missing field: timestamp'}), 400

        timestamp_str = data['timestamp']
        if isinstance(timestamp_str, str):
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                if log:
                    log.warning('API', f'Invalid timestamp format: {timestamp_str}')
                print(f'Invalid timestamp format: {timestamp_str}')
                return jsonify({'error': 'Invalid timestamp format, use ISO format'}), 400
        else:
            timestamp = timestamp_str

        new_data = EnvironmentalData(
            timestamp=timestamp,
            temperature=data.get('temperature'),
            humidity=data.get('humidity'),
            light=data.get('light'),
            mq135=data.get('mq135'),
            zp01=data.get('zp01')
        )

        db.session.add(new_data)
        db.session.commit()

        if log:
            log.info('API', f'Data received successfully at {timestamp_str}')
        print(f'Data received successfully at {timestamp_str}')
        return jsonify({'message': 'Data received successfully'}), 201
    except Exception as e:
        if log:
            log.error('API', f'Error receiving data: {str(e)}')
        print(f'Error receiving data: {str(e)}')
        return jsonify({'error': str(e)}), 500


@data_bp.route('/api/data', methods=['GET'])
def get_data():
    try:
        data = EnvironmentalData.query.order_by(EnvironmentalData.id.desc()).all()
        result = []
        for item in data:
            timestamp_value = item.timestamp
            if isinstance(timestamp_value, str):
                timestamp_str = timestamp_value
            elif hasattr(timestamp_value, 'isoformat'):
                timestamp_str = timestamp_value.isoformat()
            else:
                timestamp_str = None

            result.append({
                'id': item.id,
                'timestamp': timestamp_str,
                'temperature': item.temperature,
                'humidity': item.humidity,
                'light': item.light,
                'mq135': item.mq135,
                'zp01': item.zp01
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@data_bp.route('/api/data/statistics', methods=['GET'])
def get_statistics():
    try:
        stats = db.session.query(
            func.max(EnvironmentalData.temperature).label('max_temperature'),
            func.min(EnvironmentalData.temperature).label('min_temperature'),
            func.avg(EnvironmentalData.temperature).label('avg_temperature'),
            func.max(EnvironmentalData.humidity).label('max_humidity'),
            func.min(EnvironmentalData.humidity).label('min_humidity'),
            func.avg(EnvironmentalData.humidity).label('avg_humidity'),
            func.max(EnvironmentalData.light).label('max_light'),
            func.min(EnvironmentalData.light).label('min_light'),
            func.avg(EnvironmentalData.light).label('avg_light'),
            func.max(EnvironmentalData.mq135).label('max_mq135'),
            func.min(EnvironmentalData.mq135).label('min_mq135'),
            func.avg(EnvironmentalData.mq135).label('avg_mq135'),
            func.max(EnvironmentalData.zp01).label('max_zp01'),
            func.min(EnvironmentalData.zp01).label('min_zp01'),
            func.avg(EnvironmentalData.zp01).label('avg_zp01'),
            func.count(EnvironmentalData.id).label('total_records')
        ).first()

        result = {
            'temperature': {
                'max': round(stats.max_temperature, 2) if stats.max_temperature else None,
                'min': round(stats.min_temperature, 2) if stats.min_temperature else None,
                'avg': round(stats.avg_temperature, 2) if stats.avg_temperature else None
            },
            'humidity': {
                'max': round(stats.max_humidity, 2) if stats.max_humidity else None,
                'min': round(stats.min_humidity, 2) if stats.min_humidity else None,
                'avg': round(stats.avg_humidity, 2) if stats.avg_humidity else None
            },
            'light': {
                'max': round(stats.max_light, 2) if stats.max_light else None,
                'min': round(stats.min_light, 2) if stats.min_light else None,
                'avg': round(stats.avg_light, 2) if stats.avg_light else None
            },
            'mq135': {
                'max': round(stats.max_mq135, 2) if stats.max_mq135 else None,
                'min': round(stats.min_mq135, 2) if stats.min_mq135 else None,
                'avg': round(stats.avg_mq135, 2) if stats.avg_mq135 else None
            },
            'zp01': {
                'max': round(stats.max_zp01, 2) if stats.max_zp01 else None,
                'min': round(stats.min_zp01, 2) if stats.min_zp01 else None,
                'avg': round(stats.avg_zp01, 2) if stats.avg_zp01 else None
            },
            'total_records': stats.total_records if stats.total_records else 0
        }

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@data_bp.route('/api/data/paged', methods=['GET'])
def get_paged_data():
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20

        total_records = db.session.query(func.count(EnvironmentalData.id)).scalar()
        total_pages = (total_records + page_size - 1) // page_size

        offset = (page - 1) * page_size
        data = EnvironmentalData.query.order_by(EnvironmentalData.id.desc()).offset(offset).limit(page_size).all()

        result = []
        for item in data:
            timestamp_value = item.timestamp
            if isinstance(timestamp_value, str):
                timestamp_str = timestamp_value
            elif hasattr(timestamp_value, 'isoformat'):
                timestamp_str = timestamp_value.isoformat()
            else:
                timestamp_str = None

            result.append({
                'id': item.id,
                'timestamp': timestamp_str,
                'temperature': item.temperature,
                'humidity': item.humidity,
                'light': item.light,
                'mq135': item.mq135,
                'zp01': item.zp01
            })

        return jsonify({
            'data': result,
            'page': page,
            'page_size': page_size,
            'total_records': total_records,
            'total_pages': total_pages
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@data_bp.route('/api/data/<int:id>', methods=['GET'])
def get_data_by_id(id):
    try:
        data = EnvironmentalData.query.get(id)
        if not data:
            return jsonify({'error': 'Data not found'}), 404

        timestamp_value = data.timestamp
        if isinstance(timestamp_value, str):
            timestamp_str = timestamp_value
        elif hasattr(timestamp_value, 'isoformat'):
            timestamp_str = timestamp_value.isoformat()
        else:
            timestamp_str = None

        return jsonify({
            'id': data.id,
            'timestamp': timestamp_str,
            'temperature': data.temperature,
            'humidity': data.humidity,
            'light': data.light,
            'mq135': data.mq135,
            'zp01': data.zp01
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500