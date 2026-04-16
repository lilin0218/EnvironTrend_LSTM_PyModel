from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime

# 初始化数据库对象
db = SQLAlchemy()

class EnvironmentalData(db.Model):
    """环境数据模型"""
    id = db.Column(db.Integer, primary_key=True)  # 主键ID
    timestamp = db.Column(DateTime, nullable=False)  # 时间戳，不允许为空
    temperature = db.Column(db.Float, nullable=True)  # 温度，允许为空
    humidity = db.Column(db.Float, nullable=True)  # 湿度，允许为空
    light = db.Column(db.Float, nullable=True)  # 光照，允许为空
    gas = db.Column(db.Float, nullable=True)  # 有害气体，允许为空
    air_quality = db.Column(db.Float, nullable=True)  # 空气质量，允许为空
    noise = db.Column(db.Float, nullable=True)  # 噪音，允许为空

    def __repr__(self):
        return f'<EnvironmentalData {self.timestamp}>'