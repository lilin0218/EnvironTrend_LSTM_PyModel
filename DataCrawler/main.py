from crawler import DataCrawler

def main():
    crawler = DataCrawler()
    print("环境数据拷贝工具")
    print("1. 拷贝网站数据库到本地")
    print("2. 查看本地数据")
    print("3. 清空本地数据")
    print("4. 退出")

    while True:
        choice = input("请选择操作: ")
        if choice == '1':
            if crawler.copy_web_db():
                print("数据库拷贝成功")
            else:
                print("数据库拷贝失败")
        elif choice == '2':
            data = crawler.get_local_data()
            if data:
                for item in data:
                    print(f"ID: {item['id']}, 时间: {item['timestamp']}, 温度: {item['temperature']}°C, 湿度: {item['humidity']}%, 光照: {item['light']}, MQ135: {item['mq135']}, ZP01: {item['zp01']}")
            else:
                print("本地无数据")
        elif choice == '3':
            if crawler.clear_local_data():
                print("本地数据已清空")
            else:
                print("清空数据失败")
        elif choice == '4':
            print("退出程序")
            break
        else:
            print("无效选择，请重新输入")

if __name__ == '__main__':
    main()