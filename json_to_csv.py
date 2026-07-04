"""
mobile_10pages.json → mobile_10pages.csv 预处理脚本
====================================================
将爬取结果 JSON 转为 CSV，支持 Excel 直接打开（中文不乱码）。

预处理内容：
  1. 列表字段（ingredients/steps/tags）用 "|" 拼接为单列文本
  2. 输出 utf-8-sig 编码（BOM 头，Excel 直接打开中文正常）
  3. 列顺序：recipe_id, title, author, difficulty, time, rating,
     review_count, tags, ingredients, steps, cover_image, url, description
"""

import json
import csv
import os

INPUT = "mobile_10pages.json"
OUTPUT = "mobile_10pages.csv"

# ---- 读取 JSON ----
with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"[INFO] 读取 {len(data)} 条菜谱数据")

# ---- 字段顺序（列） ----
FIELD_ORDER = [
    "recipe_id",
    "title",
    "author",
    "difficulty",
    "time",
    "rating",
    "review_count",
    "tags",
    "ingredients",
    "steps",
    "cover_image",
    "url",
    "description",
]

# ---- 写入 CSV ----
with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=FIELD_ORDER, extrasaction="ignore")
    writer.writeheader()

    for item in data:
        row = dict(item)

        # 列表字段 → 用 "|" 拼接成单列
        for key in ["ingredients", "steps", "tags"]:
            val = row.get(key, [])
            if isinstance(val, list):
                row[key] = "|".join(val)
            elif not val:
                row[key] = ""

        # 数值字段保底
        row.setdefault("rating", 0.0)
        row.setdefault("review_count", 0)
        row.setdefault("difficulty", 0)

        writer.writerow(row)

file_size = os.path.getsize(OUTPUT)
print(f"[INFO] 输出 {OUTPUT} → {len(data)} 行 × {len(FIELD_ORDER)} 列, {file_size/1024:.1f} KB")
print(f"[INFO] 编码: utf-8-sig (BOM), Excel 可直接打开")
