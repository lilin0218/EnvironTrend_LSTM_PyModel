from flask import Blueprint, request, jsonify
from datetime import datetime
import os
import glob
from werkzeug.utils import secure_filename
from utils import log

screenshot_bp = Blueprint('screenshot', __name__)


def cleanup_old_screenshots(app):
    try:
        screen_dir = app.config['SCREEN_DIR']
        screenshots = sorted(
            glob.glob(os.path.join(screen_dir, 'screenshot_*.png')),
            key=os.path.getmtime,
            reverse=True
        )
        
        if len(screenshots) > 100:
            for old_file in screenshots[100:]:
                try:
                    os.remove(old_file)
                    if log:
                        log.info('API', f'Deleted old screenshot: {old_file}')
                    print(f'Deleted old screenshot: {old_file}')
                except Exception as e:
                    if log:
                        log.warning('API', f'Failed to delete screenshot {old_file}: {str(e)}')
                    print(f'Failed to delete screenshot {old_file}: {str(e)}')
    except Exception as e:
        if log:
            log.warning('API', f'Failed to cleanup screenshots: {str(e)}')
        print(f'Failed to cleanup screenshots: {str(e)}')


@screenshot_bp.route('/api/screenshot', methods=['POST'])
def receive_screenshot():
    try:
        from app import app
        if 'screenshot' not in request.files:
            if log:
                log.warning('API', 'No screenshot file provided in request')
            print('No screenshot file provided')
            return jsonify({'error': 'No screenshot file provided'}), 400
        
        file = request.files['screenshot']
        
        if file.filename == '':
            if log:
                log.warning('API', 'Empty filename for screenshot')
            print('Empty filename for screenshot')
            return jsonify({'error': 'Empty filename'}), 400
        
        if not file.filename.lower().endswith('.png'):
            if log:
                log.warning('API', f'Invalid file type: {file.filename}')
            print(f'Invalid file type: {file.filename}')
            return jsonify({'error': 'Only PNG files are allowed'}), 400
        
        now = datetime.now()
        timestamp_str = now.strftime('%Y%m%d_%H%M%S')
        
        original_filename = secure_filename(file.filename)
        if original_filename.endswith('.png'):
            filename = f"screenshot_{timestamp_str}_{original_filename}"
        else:
            filename = f"screenshot_{timestamp_str}.png"
        
        screen_dir = app.config['SCREEN_DIR']
        filepath = os.path.join(screen_dir, filename)
        file.save(filepath)
        
        if log:
            log.info('API', f'Screenshot saved: {filename}')
        print(f'Screenshot saved: {filename}')
        
        cleanup_old_screenshots(app)
        
        screenshot_url = f'/api/screenshots/{filename}'
        return jsonify({
            'message': 'Screenshot received successfully',
            'filename': filename,
            'url': screenshot_url,
            'timestamp': now.isoformat()
        }), 201
        
    except Exception as e:
        if log:
            log.error('API', f'Error receiving screenshot: {str(e)}')
        print(f'Error receiving screenshot: {str(e)}')
        return jsonify({'error': str(e)}), 500


@screenshot_bp.route('/api/screenshots', methods=['GET'])
def get_screenshots():
    try:
        from app import app
        screen_dir = app.config['SCREEN_DIR']
        
        screenshots = sorted(
            glob.glob(os.path.join(screen_dir, 'screenshot_*.png')),
            key=os.path.getmtime,
            reverse=True
        )
        
        result = []
        for filepath in screenshots:
            filename = os.path.basename(filepath)
            stat = os.stat(filepath)
            result.append({
                'filename': filename,
                'url': f'/api/screenshots/{filename}',
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        
        return jsonify({
            'screenshots': result,
            'count': len(result)
        }), 200
        
    except Exception as e:
        if log:
            log.error('API', f'Error getting screenshots: {str(e)}')
        print(f'Error getting screenshots: {str(e)}')
        return jsonify({'error': str(e)}), 500


@screenshot_bp.route('/api/screenshots/<filename>', methods=['DELETE'])
def delete_screenshot(filename):
    try:
        from app import app
        filename = secure_filename(filename)
        if not filename.startswith('screenshot_') or not filename.endswith('.png'):
            if log:
                log.warning('API', f'Invalid screenshot filename: {filename}')
            return jsonify({'error': 'Invalid filename'}), 400
        
        screen_dir = app.config['SCREEN_DIR']
        filepath = os.path.join(screen_dir, filename)
        
        if not os.path.exists(filepath):
            if log:
                log.warning('API', f'Screenshot not found: {filename}')
            return jsonify({'error': 'Screenshot not found'}), 404
        
        os.remove(filepath)
        
        if log:
            log.info('API', f'Screenshot deleted: {filename}')
        print(f'Screenshot deleted: {filename}')
        
        return jsonify({'message': 'Screenshot deleted successfully'}), 200
        
    except Exception as e:
        if log:
            log.error('API', f'Error deleting screenshot: {str(e)}')
        print(f'Error deleting screenshot: {str(e)}')
        return jsonify({'error': str(e)}), 500