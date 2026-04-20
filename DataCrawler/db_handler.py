import sqlite3
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import Logger
from datetime import datetime

class DBHandler:
    """数据库处理类"""
    def __init__(self, db_path):
        """初始化数据库连接"""
        self.db_path = db_path
        self.log = Logger.instance()
        self._create_table()

    def _create_table(self):
        """创建数据库表"""
        # 确保数据库目录存在
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS environmental_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                temperature REAL,
                humidity REAL,
                light REAL,
                gas REAL,
                air_quality REAL,
                noise REAL
            )
        ''')
        conn.commit()
        conn.close()

    def insert_data(self, data):
        """插入数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 确保时间戳是字符串格式
            timestamp = data['timestamp']
            if isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()

            cursor.execute('''
                INSERT INTO environmental_data (timestamp, temperature, humidity, light, gas, air_quality, noise)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp,
                data.get('temperature'),
                data.get('humidity'),
                data.get('light'),
                data.get('gas'),
                data.get('air_quality'),
                data.get('noise')
            ))
            conn.commit()
            return True
        except Exception as e:
            self.log.error('DBHandler', f'插入数据失败: {str(e)}')
            return False
        finally:
            conn.close()

    def get_all_data(self):
        """获取所有数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM environmental_data ORDER BY id DESC')
            rows = cursor.fetchall()
            result = []
            for row in rows:
                result.append({
                    'id': row[0],
                    'timestamp': row[1],
                    'temperature': row[2],
                    'humidity': row[3],
                    'light': row[4],
                    'gas': row[5],
                    'air_quality': row[6],
                    'noise': row[7]
                })
            return result
        except Exception as e:
            self.log.error('DBHandler', f'获取数据失败: {str(e)}')
            return []
        finally:
            conn.close()

    def clear_data(self):
        """清空数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM environmental_data')
            conn.commit()
            return True
        except Exception as e:
            self.log.error('DBHandler', f'清空数据失败: {str(e)}')
            return False
        finally:
            conn.close()