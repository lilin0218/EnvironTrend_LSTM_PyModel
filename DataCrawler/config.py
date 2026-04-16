import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_URL = os.environ.get('API_URL') or 'http://localhost:5000/api/data'
    # 使用绝对路径
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SQLITE_DB = os.environ.get('SQLITE_DB') or os.path.join(BASE_DIR, '..', 'dbData', 'enviro_data.db')
    CRAWL_INTERVAL = int(os.environ.get('CRAWL_INTERVAL', '300'))  # 默认5分钟