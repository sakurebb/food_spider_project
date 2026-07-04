"""
Scrapy 项目配置文件
===================
通用配置，各爬虫通过 custom_settings 覆盖特定项。

当前爬虫：mobile_food（美食天下移动版）
历史爬虫：meishi（美食杰，已废弃）、food（下厨房，已废弃）
"""

# ======================== 基本配置 ========================
BOT_NAME = "food_spider_project"

SPIDER_MODULES = ["food_spider_project.spiders"]
NEWSPIDER_MODULE = "food_spider_project.spiders"

# ======================== 爬虫协议 ========================
ROBOTSTXT_OBEY = False

# ======================== 并发与延迟控制 ========================
CONCURRENT_REQUESTS = 2
DOWNLOAD_DELAY = 3
CONCURRENT_REQUESTS_PER_DOMAIN = 1

# ======================== 请求头伪装 ========================
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

DEFAULT_REQUEST_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
}

# ======================== Cookie 与重试 ========================
COOKIES_ENABLED = True
DOWNLOAD_TIMEOUT = 30

RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504]

# ======================== 管道配置 ========================
ITEM_PIPELINES = {
    "food_spider_project.pipelines.FoodPipeline": 300,
}

# ======================== 自动限速（AutoThrottle） ========================
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3
AUTOTHROTTLE_MAX_DELAY = 15.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 0.33
AUTOTHROTTLE_DEBUG = False

# ======================== 数据导出配置 ========================
FEED_EXPORT_ENCODING = "utf-8"

# ======================== 日志配置 ========================
LOG_LEVEL = "INFO"

# ======================== 其他配置 ========================
TELNETCONSOLE_ENABLED = False
HTTPCACHE_ENABLED = False

# ======================== Scrapy 版本兼容 ========================
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
