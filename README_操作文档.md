# 美食天下移动版爬虫 —— 运行操作文档

> 爬虫名称：`mobile_food` | 目标站点：m.meishichina.com | 策略：温和爬取 + 10 页限制

---

## 一、环境要求

| 项        | 要求                               |
| --------- | ---------------------------------- |
| Python    | 3.7+                               |
| Scrapy    | 2.9+（项目验证）/ 2.16（设计目标） |
| curl_cffi | 0.5.10+（TLS 指纹绕过，必需）      |
| 网络      | 需能访问`m.meishichina.com`      |

安装依赖：

```bash
pip install scrapy curl_cffi
```

---

## 二、运行方式

### 方式 1：运行脚本（推荐，自动处理 Windows 兼容性）

```bash
cd f:/food_spider_project
python run_mobile_food.py
```

### 方式 2：直接 scrapy 命令

```bash
cd f:/food_spider_project
scrapy crawl mobile_food -o mobile_10pages.json -s LOG_LEVEL=INFO
```

---

## 三、项目结构

```
food_spider_project/
├── scrapy.cfg                        # Scrapy 项目配置
├── run_mobile_food.py                # 一键运行脚本
├── mobile_10pages.json               # 运行输出（60条菜谱）
├── README_操作文档.md                 # 本文件
├── 课程设计说明书_美食天下移动版数据采集与预处理.md
└── food_spider_project/
    ├── __init__.py
    ├── items.py                      # FoodItem 字段定义
    ├── pipelines.py                  # FoodPipeline 数据清洗
    ├── middlewares.py                # CurlCffiDownloaderMiddleware (TLS绕过)
    ├── settings.py                   # Scrapy 全局配置
    └── spiders/
        ├── __init__.py
        └── mobile_food.py            # 美食天下移动版爬虫（课设保底方案）
```

---

## 四、配置说明

| 配置项                             | 值            | 说明              |
| ---------------------------------- | ------------- | ----------------- |
| `DOWNLOAD_DELAY`                 | 2             | 请求间隔 2 秒     |
| `CONCURRENT_REQUESTS`            | 2             | 全局并发数 2      |
| `CONCURRENT_REQUESTS_PER_DOMAIN` | 1             | 同域串行          |
| `COOKIES_ENABLED`                | False         | 移动版无需 Cookie |
| `USER_AGENT`                     | iPhone Safari | 移动端 UA         |
| `max_pages`                      | 10            | 爬取页数上限      |

TLS 指纹绕过：`CurlCffiDownloaderMiddleware` 通过 curl_cffi 模拟 Chrome 110 TLS 指纹。

---
