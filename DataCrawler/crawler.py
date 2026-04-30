import os
import shutil
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import Logger
from config import Config
from db_handler import DBHandler

class DataCrawler:
    """数据拷贝工具类"""
    def __init__(self):
        """初始化拷贝工具"""
        self.db_handler = DBHandler(Config.SQLITE_DB)
        self.log = Logger.instance()
        self.web_db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'WebServer', 'backend', 'data', 'enviro_data.db'
        )
        self.local_db_path = Config.SQLITE_DB

    def copy_web_db(self):
        """从网站后端拷贝数据库到本地"""
        try:
            self.log.info('Crawler', f'开始拷贝数据库，源路径: {self.web_db_path}')
            
            if not os.path.exists(self.web_db_path):
                self.log.error('Crawler', f'网站数据库不存在: {self.web_db_path}')
                return False
            
            local_db_dir = os.path.dirname(self.local_db_path)
            if not os.path.exists(local_db_dir):
                os.makedirs(local_db_dir)
                self.log.info('Crawler', f'创建本地数据库目录: {local_db_dir}')
            
            shutil.copy2(self.web_db_path, self.local_db_path)
            self.log.info('Crawler', f'数据库拷贝成功，目标路径: {self.local_db_path}')
            return True
        except Exception as e:
            self.log.error('Crawler', f'拷贝数据库失败: {str(e)}')
            return False

    def get_local_data(self):
        """获取本地数据"""
        return self.db_handler.get_all_data()

    def clear_local_data(self):
        """清空本地数据"""
        return self.db_handler.clear_data()

    def get_web_db_path(self):
        """获取网站数据库路径"""
        return self.web_db_path