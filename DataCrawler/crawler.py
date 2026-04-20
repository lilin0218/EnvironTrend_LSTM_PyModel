import requests
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import Logger
from config import Config
from db_handler import DBHandler

class DataCrawler:
    """数据爬取类"""
    def __init__(self):
        """初始化爬取器"""
        self.api_url = Config.API_URL
        self.db_handler = DBHandler(Config.SQLITE_DB)
        self.log = Logger.instance()

    def crawl_data(self):
        """爬取数据"""
        try:
            self.log.info('Crawler', f'开始爬取数据，目标URL: {self.api_url}')
            response = requests.get(self.api_url)
            if response.status_code == 200:
                data = response.json()
                if data:
                    latest_data = data[0]
                    success = self.db_handler.insert_data(latest_data)
                    if success:
                        self.log.info('Crawler', f'成功爬取数据: {latest_data["timestamp"]}')
                        return True
                    else:
                        self.log.error('Crawler', '保存数据失败')
                        return False
                else:
                    self.log.warning('Crawler', 'API返回空数据')
                    return False
            else:
                self.log.error('Crawler', f'API请求失败: {response.status_code}')
                return False
        except Exception as e:
            self.log.error('Crawler', f'爬取数据失败: {str(e)}')
            return False

    def get_local_data(self):
        """获取本地数据"""
        return self.db_handler.get_all_data()

    def clear_local_data(self):
        """清空本地数据"""
        return self.db_handler.clear_data()