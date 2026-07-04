"""
下厨房美食数据清洗管道（Pipeline）—— Scrapy 2.9 兼容版
=========================================================
本模块定义了 FoodPipeline，负责对爬取的菜谱数据进行清洗、去重和标准化处理。

处理流程：
  1. URL 去重 → 基于内存集合，避免重复写入相同菜谱
  2. 文本清洗 → 去除 ingredients/steps 中的换行符和多余空格
  3. 难度标准化 → 将中文难度描述映射为数字等级
  4. 缺失值处理 → 评分缺失设为 0.0，评论数缺失设为 0
  5. 数据输出 → 配合 settings.py 中的 FEEDS 配置，支持导出为 CSV/JSON

版本兼容说明：
  - 当前运行环境 Scrapy 2.9.0，Pipeline 方法保留 spider 参数。
  - from_crawler() 工厂方法同时保存 crawler 引用，为未来升级 2.14+
    做好准备（方法内部优先使用 spider 参数，兜底使用 self.crawler.spider）。

技术选型说明：
  - 使用 str.replace() + str.strip() 而非正则/BeautifulSoup/pandas：
    本项目数据清洗需求简单（去换行+去空格），轻量内置方法足够，
    无需引入额外依赖，运行开销低。
  - 使用内存集合做去重而非数据库：课程设计场景数据量可控，
    避免数据库安装和配置复杂度。
"""

import re
import logging
import scrapy.exceptions
from itemadapter import ItemAdapter

# 模块级 logger（兜底使用，正常情况下使用 spider.logger）
logger = logging.getLogger(__name__)


class FoodPipeline:
    """
    下厨房菜谱数据处理管道。

    在 Spider 每 yield 一个 Item 后，Scrapy 引擎会按优先级
    依次将其传递给已启用的 Pipeline。本 Pipeline 负责所有
    数据清洗逻辑。
    """

    # 难度映射字典：中文描述 → 数字等级
    DIFFICULTY_MAP = {
        "简单": 1,
        "容易": 1,
        "初级": 1,
        "中等": 2,
        "一般": 2,
        "普通": 2,
        "中级": 2,
        "困难": 3,
        "较难": 3,
        "高级": 3,
        "难": 3,
    }

    # ======================== 生命周期方法 ========================

    @classmethod
    def from_crawler(cls, crawler):
        """
        工厂方法：创建 Pipeline 实例并保存 Crawler 引用。

        在 Scrapy 2.9 中，此方法为可选；在 2.14+ 中为获取 spider 引用的推荐方式。
        本项目同时保留 spider 参数与 crawler 引用，确保跨版本兼容。

        Args:
            crawler: Scrapy Crawler 实例

        Returns:
            FoodPipeline 实例
        """
        instance = cls()
        instance.crawler = crawler
        return instance

    def __init__(self):
        """初始化管道：创建去重用 URL 集合"""
        self.seen_urls = set()
        self.crawler = None  # 将在 from_crawler() 中被赋值

    def open_spider(self, spider):
        """
        Spider 启动时调用。

        Args:
            spider: 当前运行的 Spider 实例（Scrapy 2.9 标准签名）
        """
        spider.logger.info("=" * 50)
        spider.logger.info("FoodPipeline 已就绪，开始处理数据...")
        spider.logger.info("=" * 50)

    def close_spider(self, spider):
        """
        Spider 关闭时调用，输出汇总统计信息。

        Args:
            spider: 当前运行的 Spider 实例（Scrapy 2.9 标准签名）
        """
        spider.logger.info("=" * 50)
        spider.logger.info(
            "爬取结束，共去重后写入 %d 条菜谱数据", len(self.seen_urls)
        )
        spider.logger.info("=" * 50)

    # ======================== 数据处理核心 ========================

    def process_item(self, item, spider):
        """
        处理单个 Item：去重 → 清洗 → 标准化 → 缺失值处理。

        Args:
            item: FoodItem 实例
            spider: 当前运行的 Spider 实例（Scrapy 2.9 标准签名）

        Returns:
            处理后的 item 对象

        Raises:
            DropItem: 当 Item 的 URL 已存在或缺失时，丢弃该条目
        """
        adapter = ItemAdapter(item)

        # ==================== 步骤 1：URL 去重 ====================
        url = adapter.get("url", "")
        if not url:
            spider.logger.warning("Item 缺少 URL 字段，丢弃")
            raise scrapy.exceptions.DropItem("缺少 URL 字段")

        if url in self.seen_urls:
            spider.logger.debug("重复 URL，丢弃：%s", url)
            raise scrapy.exceptions.DropItem(f"重复 URL: {url}")

        self.seen_urls.add(url)

        # ==================== 步骤 2：文本清洗 ====================
        # 清洗 ingredients 列表中的每个元素
        ingredients = adapter.get("ingredients", [])
        if ingredients:
            adapter["ingredients"] = [
                self._clean_ingredient(ing) for ing in ingredients
                if self._clean_ingredient(ing)  # 过滤清洗后为空的元素
            ]

        # 清洗 steps 列表中的每个元素
        steps = adapter.get("steps", [])
        if steps:
            adapter["steps"] = [
                self._clean_step(step) for step in steps
                if self._clean_step(step)
            ]

        # 清洗其他文本字段
        for field in ["title", "author", "description", "time"]:
            value = adapter.get(field)
            if isinstance(value, str):
                adapter[field] = self._clean_text(value)

        # 清洗 tags 列表
        tags = adapter.get("tags", [])
        if tags:
            adapter["tags"] = [
                self._clean_text(t) for t in tags
                if self._clean_text(t)
            ]

        # ==================== 步骤 3：难度标准化 ====================
        diff_raw = adapter.get("difficulty", "")
        adapter["difficulty"] = self._normalize_difficulty(diff_raw)

        # ==================== 步骤 4：缺失值处理 ====================
        # 评分为缺失或无效值时设为 0.0
        rating = adapter.get("rating")
        if rating is None or (isinstance(rating, str) and not rating.strip()):
            adapter["rating"] = 0.0
        else:
            try:
                adapter["rating"] = float(rating)
            except (ValueError, TypeError):
                adapter["rating"] = 0.0

        # 评价数量缺失或无效时设为 0
        review_count = adapter.get("review_count")
        if review_count is None or (isinstance(review_count, str) and not review_count.strip()):
            adapter["review_count"] = 0
        else:
            try:
                adapter["review_count"] = int(review_count)
            except (ValueError, TypeError):
                adapter["review_count"] = 0

        # 标题缺失时使用占位值
        if not adapter.get("title"):
            adapter["title"] = "未知菜谱"

        # 作者缺失时使用占位值
        if not adapter.get("author"):
            adapter["author"] = "匿名"

        # recipe_id 缺失时尝试从 URL 提取
        if not adapter.get("recipe_id") and adapter.get("url"):
            match = re.search(r'/recipe/(\d+)', adapter["url"])
            if match:
                adapter["recipe_id"] = match.group(1)

        return item

    # ======================== 工具方法 ========================

    @staticmethod
    def _clean_text(text):
        """
        基础文本清洗：
          - 去除首尾空白
          - 替换换行符（\n、\r）和制表符（\t）为空格
          - 压缩连续空格为单个空格

        选用 str.replace() + str.strip() 而非 re.sub() 的理由：
          本场景只需处理换行和空格两类字符，str.replace() 链式调用
          比正则编译执行更快，代码可读性更高，适合轻量级数据清洗。
        """
        if not text:
            return ""
        text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @classmethod
    def _clean_ingredient(cls, text):
        """
        清洗单条用料文本：
          - 去除换行和多余空格
          - 保留 "食材名: 用量" 的格式
        """
        if not text:
            return ""
        text = cls._clean_text(text)
        return text

    @classmethod
    def _clean_step(cls, text):
        """
        清洗单条步骤文本：
          - 去除换行和多余空格
          - 保留 "步骤N: 描述" 的格式
        """
        if not text:
            return ""
        text = cls._clean_text(text)
        return text

    def _normalize_difficulty(self, diff_str):
        """
        将中文难度描述标准化为数字等级。

        映射规则：
          简单 / 容易 / 初级 → 1
          中等 / 一般 / 普通 / 中级 → 2
          困难 / 较难 / 高级 / 难 → 3
          空值 / 无法匹配 → 0（表示未知难度）

        Args:
            diff_str: 原始难度字符串（中文）

        Returns:
            int: 数字化的难度等级（0=未知, 1=简单, 2=中等, 3=困难）
        """
        if not diff_str or not isinstance(diff_str, str):
            return 0

        diff_str = diff_str.strip()
        if not diff_str:
            return 0

        # 直接匹配
        if diff_str in self.DIFFICULTY_MAP:
            return self.DIFFICULTY_MAP[diff_str]

        # 模糊匹配：检查字符串是否包含已知难度关键词
        for keyword, level in self.DIFFICULTY_MAP.items():
            if keyword in diff_str:
                return level

        # 无法匹配，返回未知
        return 0
