import requests
from config import Config
from db_handler import DBHandler

class DataCrawler:
    """数据爬取类"""
    def __init__(self):
        """初始化爬取器"""
        self.api_url = Config.API_URL
        self.db_handler = DBHandler(Config.SQLITE_DB)

    def crawl_data(self):
        """爬取数据"""
        try:
            response = requests.get(self.api_url)
            if response.status_code == 200:
                data = response.json()
                if data:
                    # 只保存最新的一条数据
                    latest_data = data[0]
                    success = self.db_handler.insert_data(latest_data)
                    if success:
                        print(f"成功爬取数据: {latest_data['timestamp']}")
                        return True
                    else:
                        print("保存数据失败")
                        return False
                else:
                    print("API返回空数据")
                    return False
            else:
                print(f"API请求失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"爬取数据失败: {e}")
            return False

    def get_local_data(self):
        """获取本地数据"""
        return self.db_handler.get_all_data()

    def clear_local_data(self):
        """清空本地数据"""
        return self.db_handler.clear_data()