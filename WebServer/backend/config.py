import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    # 使用相对路径，确保data目录存在
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///data/enviro_data.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True