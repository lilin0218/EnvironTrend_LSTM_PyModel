# Qt端数据上传API文档

## 1. 服务器地址

**开发环境**: `http://localhost:5000`  
**生产环境**: 根据实际部署配置

## 2. API端点

### 2.1 数据上传接口

| 属性 | 值 |
|------|-----|
| **URL** | `/api/data` |
| **方法** | `POST` |
| **Content-Type** | `application/json` |

### 2.2 请求参数

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `timestamp` | `string` | **是** | ISO 8601格式时间戳，如 `"2024-01-15T10:30:00"` |
| `temperature` | `float` | 否 | 温度值 |
| `humidity` | `float` | 否 | 湿度值 |
| `light` | `float` | 否 | 光照强度值 |
| `gas` | `float` | 否 | 有害气体浓度值 |
| `air_quality` | `float` | 否 | 空气质量值 |
| `noise` | `float` | 否 | 噪音值 |

### 2.3 成功响应

**HTTP状态码**: `201 Created`

```json
{
    "message": "Data received successfully"
}
```

### 2.4 失败响应

**HTTP状态码**: `400 Bad Request` 或 `500 Internal Server Error`

```json
{
    "error": "错误描述信息"
}
```

## 3. 请求示例

### 3.1 cURL示例

```bash
curl -X POST http://localhost:5000/api/data \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2024-01-15T10:30:00",
    "temperature": 25.5,
    "humidity": 60.2,
    "light": 350.0,
    "gas": 0.3,
    "air_quality": 85.0,
    "noise": 45.0
  }'
```

## 4. Qt C++ 示例代码

### 4.1 简单上传示例

```cpp
#include <QCoreApplication>
#include <QNetworkAccessManager>
#include <QNetworkRequest>
#include <QNetworkReply>
#include <QJsonDocument>
#include <QJsonObject>
#include <QDateTime>
#include <QUrl>

void uploadEnvironmentalData() {
    // 创建网络访问管理器
    QNetworkAccessManager *manager = new QNetworkAccessManager();
    
    // 设置目标URL
    QUrl url("http://localhost:5000/api/data");
    QNetworkRequest request(url);
    
    // 设置请求头
    request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
    
    // 构造JSON数据
    QJsonObject jsonData;
    jsonData["timestamp"] = QDateTime::currentDateTime().toString(Qt::ISODate);
    jsonData["temperature"] = 25.5;   // 温度示例值
    jsonData["humidity"] = 60.2;      // 湿度示例值
    jsonData["light"] = 350.0;        // 光照示例值
    jsonData["gas"] = 0.3;            // 有害气体示例值
    jsonData["air_quality"] = 85.0;   // 空气质量示例值
    jsonData["noise"] = 45.0;         // 噪音示例值
    
    // 转换为JSON文档
    QJsonDocument doc(jsonData);
    QByteArray data = doc.toJson(QJsonDocument::Compact);
    
    // 发送POST请求
    QNetworkReply *reply = manager->post(request, data);
    
    // 连接响应信号
    QObject::connect(reply, &QNetworkReply::finished, [reply, manager]() {
        if (reply->error() == QNetworkReply::NoError) {
            // 读取响应数据
            QByteArray response = reply->readAll();
            qDebug() << "上传成功:" << response;
        } else {
            // 输出错误信息
            qDebug() << "上传失败:" << reply->errorString();
        }
        
        // 清理资源
        reply->deleteLater();
        manager->deleteLater();
    });
}

int main(int argc, char *argv[]) {
    QCoreApplication a(argc, argv);
    
    // 上传数据
    uploadEnvironmentalData();
    
    return a.exec();
}
```

### 4.2 封装为类的示例

```cpp
#ifndef ENVIRONMENTALDATAUPLOADER_H
#define ENVIRONMENTALDATAUPLOADER_H

#include <QObject>
#include <QNetworkAccessManager>
#include <QJsonObject>

class EnvironmentalDataUploader : public QObject {
    Q_OBJECT
    
public:
    explicit EnvironmentalDataUploader(QObject *parent = nullptr) 
        : QObject(parent), manager(new QNetworkAccessManager(this)) {}
    
    ~EnvironmentalDataUploader() {}
    
    // 上传环境数据
    void uploadData(const QJsonObject& data) {
        QUrl url("http://localhost:5000/api/data");
        QNetworkRequest request(url);
        request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
        
        QJsonDocument doc(data);
        QNetworkReply *reply = manager->post(request, doc.toJson(QJsonDocument::Compact));
        
        connect(reply, &QNetworkReply::finished, this, [this, reply]() {
            if (reply->error() == QNetworkReply::NoError) {
                emit uploadSuccess(reply->readAll());
            } else {
                emit uploadFailed(reply->errorString());
            }
            reply->deleteLater();
        });
    }
    
signals:
    void uploadSuccess(const QByteArray& response);
    void uploadFailed(const QString& error);

private:
    QNetworkAccessManager *manager;
};

#endif // ENVIRONMENTALDATAUPLOADER_H
```

### 4.3 使用封装类

```cpp
#include "EnvironmentalDataUploader.h"

void usageExample() {
    EnvironmentalDataUploader *uploader = new EnvironmentalDataUploader();
    
    // 构造数据
    QJsonObject data;
    data["timestamp"] = QDateTime::currentDateTime().toString(Qt::ISODate);
    data["temperature"] = 26.0;
    data["humidity"] = 55.0;
    // ... 其他字段
    
    // 连接信号
    QObject::connect(uploader, &EnvironmentalDataUploader::uploadSuccess, 
        [](const QByteArray& response) {
            qDebug() << "成功:" << response;
        });
    
    QObject::connect(uploader, &EnvironmentalDataUploader::uploadFailed, 
        [](const QString& error) {
            qDebug() << "失败:" << error;
        });
    
    // 上传
    uploader->uploadData(data);
}
```

## 5. 注意事项

1. **时间戳格式**: 必须使用ISO 8601格式，可以使用 `QDateTime::toString(Qt::ISODate)` 生成
2. **网络权限**: Qt项目需要在 `pro` 文件中添加 `QT += network`
3. **异步处理**: Qt网络请求是异步的，请确保在事件循环中处理响应
4. **错误处理**: 建议在实际应用中添加超时处理和重试机制
5. **数据验证**: 发送前建议对数据进行有效性检查

## 6. Qt项目配置

在 `.pro` 文件中添加网络模块：

```qmake
QT += network
```
