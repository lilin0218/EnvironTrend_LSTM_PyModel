from flask import Flask, send_from_directory
from flask_cors import CORS
from models import db
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common import Logger

app = Flask(__name__)

# 直接设置配置
app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 使用绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'data', 'enviro_data.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

# 静态文件目录
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), 'frontend')

CORS(app)
db.init_app(app)

# 创建数据库表
with app.app_context():
    db.create_all()

# 静态文件路由
@app.route('/frontend/<path:path>')
def send_frontend(path):
    return send_from_directory(FRONTEND_DIR, path)

# 根路径重定向到前端
@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

from routes import *

if __name__ == '__main__':
    log = Logger.instance()
    log.info('WebServer', 'Starting Flask server on http://0.0.0.0:5000')
    try:
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        log.critical('WebServer', f'Server failed to start: {str(e)}')
        raise