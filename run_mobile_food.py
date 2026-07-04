"""
美食天下移动版（m.meishichina.com）爬虫运行脚本
===================================================
用法：
  python run_mobile_food.py

功能：
  1. 修复 Scrapy 2.9 + Windows _handleSignals 兼容性问题
  2. 运行 mobile_food 爬虫，爬取最多10页热菜分类
  3. 输出到 mobile_10pages.json
  4. 打印运行结果摘要

课设保底方案：美食天下移动版
  目标站点：https://m.meishichina.com
  TLS指纹绕过：curl_cffi + impersonate="chrome110"
"""

import os
import sys
import json
import time

# ---- Scrapy Windows 适配（信号处理兼容）----
import scrapy.utils.ossignal
scrapy.utils.ossignal.install_shutdown_handlers = lambda *args, **kwargs: None

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from food_spider_project.spiders.mobile_food import MobileFoodSpider

OUTPUT_FILE = "mobile_10pages.json"

settings = get_project_settings()
settings.set("LOG_LEVEL", "INFO")
settings.set("FEEDS", {
    OUTPUT_FILE: {
        "format": "json",
        "encoding": "utf-8",
        "store_empty": False,
        "overwrite": True,
    },
})

print("=" * 60)
print("美食天下移动版爬虫启动")
print(f"目标站点：https://m.meishichina.com/recipe/category/recai/")
print(f"爬取上限：10 页")
print(f"输出文件：{OUTPUT_FILE}")
print("=" * 60)
print()

start_time = time.time()

process = CrawlerProcess(settings)
process.crawl(MobileFoodSpider)
process.start()

elapsed = time.time() - start_time

print("\n" + "=" * 60)
print("运行结果")
print("=" * 60)
print(f"总耗时：{elapsed:.1f} 秒")

if os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"输出记录数：{len(data)}")
    valid = sum(
        1 for item in data
        if item.get("title") and item.get("url")
        and item.get("ingredients") and item.get("steps")
    )
    print(f"完整有效记录：{valid}/{len(data)}")
    print(f"课设要求 ≥5 条：{'✅ PASS' if len(data) >= 5 else '❌ FAIL'}")
else:
    print("❌ FAIL: 输出文件不存在!")
