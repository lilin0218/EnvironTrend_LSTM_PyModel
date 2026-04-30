from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DateTime

# 初始化数据库对象
db = SQLAlchemy()

class EnvironmentalData(db.Model):
    """环境数据模型"""
    __tablename__ = 'sensor_data'
    id = db.Column(db.Integer, primary_key=True)  # 主键ID
    timestamp = db.Column(DateTime, nullable=False)  # 时间戳，不允许为空
    temperature = db.Column(db.Float, nullable=True)  # 温度，允许为空
    humidity = db.Column(db.Float, nullable=True)  # 湿度，允许为空
    light = db.Column(db.Float, nullable=True)  # 光照，允许为空
    mq135 = db.Column(db.Float, nullable=True)  # MQ135有害气体传感器，允许为空
    zp01 = db.Column(db.Float, nullable=True)  # ZP01空气质量传感器，允许为空

    def __repr__(self):
        return f'<EnvironmentalData {self.timestamp}>'