from flask import Flask, send_from_directory
from flask_cors import CORS
from models import db
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from common import Logger
    log = Logger.instance()
except Exception as e:
    log = None
    print(f"Failed to initialize Logger: {str(e)}")

app = Flask(__name__)

app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'data', 'enviro_data.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), 'frontend')

SCREEN_DIR = os.path.join(BASE_DIR, 'screen')

if not os.path.exists(SCREEN_DIR):
    os.makedirs(SCREEN_DIR)
    if log:
        log.info('WebServer', f'Created screen directory: {SCREEN_DIR}')
    print(f'Created screen directory: {SCREEN_DIR}')

app.config['SCREEN_DIR'] = SCREEN_DIR

CORS(app)
db.init_app(app)

with app.app_context():
    db.create_all()


@app.route('/frontend/<path:path>')
def send_frontend(path):
    return send_from_directory(FRONTEND_DIR, path)


@app.route('/api/screenshots/<filename>')
def send_screenshot(filename):
    return send_from_directory(app.config['SCREEN_DIR'], filename)


@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


from routes import data_bp, screenshot_bp, predict_bp
app.register_blueprint(data_bp)
app.register_blueprint(screenshot_bp)
app.register_blueprint(predict_bp)

if __name__ == '__main__':
    if log:
        log.info('WebServer', 'Starting Flask server on http://0.0.0.0:5000')
    print('Starting Flask server on http://0.0.0.0:5000')
    try:
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        if log:
            log.critical('WebServer', f'Server failed to start: {str(e)}')
        print(f'Server failed to start: {str(e)}')
        raise