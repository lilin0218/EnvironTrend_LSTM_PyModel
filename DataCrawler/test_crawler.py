from crawler import DataCrawler

# 测试爬取功能
crawler = DataCrawler()
print("开始测试爬取功能...")
success = crawler.crawl_data()
if success:
    print("爬取成功！")
    # 查看本地数据
    data = crawler.get_local_data()
    print("本地数据:")
    for item in data:
        print(f"ID: {item['id']}, 时间: {item['timestamp']}, 温度: {item['temperature']}°C, 湿度: {item['humidity']}%, 光照: {item['light']}lux, 有害气体: {item['gas']}, 空气质量: {item['air_quality']}, 噪音: {item['noise']}dB")
else:
    print("爬取失败！")