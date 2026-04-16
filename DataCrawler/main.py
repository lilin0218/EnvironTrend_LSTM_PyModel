from crawler import DataCrawler
import time
from config import Config

def main():
    crawler = DataCrawler()
    print("环境数据爬取工具")
    print("1. 爬取最新数据")
    print("2. 查看本地数据")
    print("3. 清空本地数据")
    print("4. 定时爬取")
    print("5. 退出")

    while True:
        choice = input("请选择操作: ")
        if choice == '1':
            crawler.crawl_data()
        elif choice == '2':
            data = crawler.get_local_data()
            if data:
                for item in data:
                    print(f"ID: {item['id']}, 时间: {item['timestamp']}, 温度: {item['temperature']}°C, 湿度: {item['humidity']}%, 光照: {item['light']}lux, 有害气体: {item['gas']}, 空气质量: {item['air_quality']}, 噪音: {item['noise']}dB")
            else:
                print("本地无数据")
        elif choice == '3':
            if crawler.clear_local_data():
                print("本地数据已清空")
            else:
                print("清空数据失败")
        elif choice == '4':
            print(f"开始定时爬取，间隔 {Config.CRAWL_INTERVAL} 秒")
            print("按 Ctrl+C 退出")
            try:
                while True:
                    crawler.crawl_data()
                    time.sleep(Config.CRAWL_INTERVAL)
            except KeyboardInterrupt:
                print("定时爬取已停止")
        elif choice == '5':
            print("退出程序")
            break
        else:
            print("无效选择，请重新输入")

if __name__ == '__main__':
    main()