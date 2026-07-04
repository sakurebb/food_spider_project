"""
课设保底方案：美食天下移动版（m.meishichina.com）菜谱爬虫
===========================================================
爬取策略（课设需求：10页限制 + 温和爬取）：
  1. 从分类列表页 /recipe/category/recai/ 直接获取菜谱卡片
  2. 逐页翻页提取菜谱列表（上限 10 页）
  3. 进入每个菜谱详情页，提取标题/食材/步骤/封面图/作者/难度/时间
  4. 低并发 + 2秒延迟 + 移动端UA 确保不冲击服务器

目标站点：https://m.meishichina.com（美食天下移动版）
迁移原因：PC版下厨房(xiachufang.com)反爬过严(TLS指纹检测+HTTP 429限流)，
          美食杰(meishijie.cc)域名失效无法访问，
          移动版下厨房(m.xiachufang.com)经实测已下线/无索引。
          美食天下移动版HTML结构简单、反爬宽松、2026年6月仍有大量活跃索引。

温和策略（通过 custom_settings 覆盖全局 settings）：
  - DOWNLOAD_DELAY = 2（请求间隔2秒）
  - CONCURRENT_REQUESTS = 2（全局并发数2）
  - USER_AGENT = iPhone Safari 移动端UA
  - COOKIES_ENABLED = False（移动版无需Cookie）

HTML 结构分析（基于 2026年6月 实际页面源码）：
  - 列表页：ul.alist > li > a（每个li为一个菜谱卡片，跳过li.insertlist广告位）
    - 标题：div.detail > h3
    - 封面图：div.pic > img/@data-src（懒加载，非src属性）
    - 链接：a/@href → /recipe/{id}/
  - 翻页：div.page > a/@href → /recipe/category/recai/{page}/
  - 详情页：
    - 标题：div.topbox > h1 > a/text()
    - 作者：div.topbox > div.author > a/text()
    - 封面图：div.row.mb20 > img/@src
    - 难度/工艺/口味/时间：ul.recipeicon > li span/text()
    - 食材：#ingredientlist > ul.rlist.rlist-nopic > li（分主料/辅料/调料区）
    - 步骤：ul.steplist > li > div/text()（含步骤序号前缀）
    - 标签：#tags > a/text()

start_urls 验证记录（2026-07-03）：
  $ curl -s -o /dev/null -w "%{http_code}" \
      -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)..." \
      "https://m.meishichina.com/recipe/category/recai/"
  → HTTP 200 ✓
"""

import re
import scrapy
from food_spider_project.items import FoodItem


class MobileFoodSpider(scrapy.Spider):
    """美食天下移动版菜谱爬虫 —— 课设保底方案"""

    name = "mobile_food"
    allowed_domains = ["m.meishichina.com"]

    # ======================== start_urls 验证：curl 实测返回 200 ========================
    # 2026-07-03 验证通过：m.meishichina.com/recipe/category/recai/ → HTTP 200
    # 热菜分类有约100页菜谱，足够满足10页课设需求
    start_urls = ["https://m.meishichina.com/recipe/category/recai/"]

    # ======================== 课设需求：爬取页数上限 ========================
    max_pages = 10

    # ======================== 移动版温和爬取配置 ========================
    # 覆盖 settings.py 中美食杰的全局配置，使用移动版专用设置
    custom_settings = {
        # 课设需求：移动版温和策略
        "DOWNLOAD_DELAY": 2,          # 请求间隔2秒
        "CONCURRENT_REQUESTS": 2,     # 全局并发数2
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,  # 同域串行，最温和
        # 移动端 iPhone Safari User-Agent
        "USER_AGENT": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.0 Mobile/15E148 Safari/604.1"
        ),
        # 移动版无需 Cookie
        "COOKIES_ENABLED": False,
        # 移动版请求头精简
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        },
        # AutoThrottle 适配移动版
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 0.5,
        # 重试配置
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504],
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 30,
        # ==================== 课设关键：TLS 指纹绕过中间件 ====================
        # 美食天下移动版使用 TLS 指纹检测，Python 标准 ssl/Twisted 的 TLS
        # 握手会被识别为非浏览器流量并返回 HTTP 403。
        # CurlCffiDownloaderMiddleware 通过 curl_cffi 模拟 Chrome 110 浏览器的
        # TLS 指纹（JA3/JA4）来绕过该检测，在 process_request 中直接返回 Response
        # 从而短路 Scrapy 原生下载流程。
        "DOWNLOADER_MIDDLEWARES": {
            "food_spider_project.middlewares.CurlCffiDownloaderMiddleware": 550,
        },
    }

    def parse(self, response):
        """
        解析分类列表页，提取菜谱卡片并处理翻页。

        列表页 HTML 结构（美食天下移动版 2026年6月）：
          <div class="rbox">
            <ul class="alist">
              <li>                                        ← 菜谱卡片
                <a href="/recipe/{id}/" title="菜名">
                  <div class="pic">
                    <img data-src="封面图URL" ... />        ← 懒加载，取 @data-src
                  </div>
                  <div class="detail">
                    <h3>菜谱名称</h3>
                    <div>食材预览文本</div>
                    <div class="substatus">收藏数</div>
                  </div>
                </a>
              </li>
              <li class="insertlist">...</li>               ← 广告位，跳过
            </ul>
          </div>

        翻页 HTML 结构：
          <div class="page">
            <a href="/recipe/category/recai/2/">下一页</a>
            <b>(1/100)</b>
          </div>
        """
        current_page = response.meta.get("page", 1)
        self.logger.info(
            "[美食天下移动版] 已爬取第%d页（上限%d页）URL: %s",
            current_page, self.max_pages, response.url
        )

        # ==================== 提取菜谱卡片 ====================
        # 选择器：ul.alist > li，排除 li.insertlist（广告位）
        recipe_cards = response.xpath('//ul[@class="alist"]/li[not(contains(@class, "insertlist"))]')

        self.logger.info("[美食天下移动版] 第%d页共提取 %d 个菜谱卡片", current_page, len(recipe_cards))

        for card in recipe_cards:
            # 提取链接和标题
            link = card.xpath('./a/@href').get()
            title = card.xpath('.//h3/text()').get()

            if not link or not title:
                continue

            title = title.strip()
            detail_url = response.urljoin(link)

            # 提取封面图（懒加载，取 data-src 而非 src）
            cover_img = card.xpath('.//div[contains(@class, "pic")]/img/@data-src').get()
            if not cover_img:
                cover_img = card.xpath('.//img/@data-src').get()
            if not cover_img:
                cover_img = card.xpath('.//img/@src').get()

            # 从 URL 中提取菜谱 ID
            recipe_id_match = re.search(r'/recipe/(\d+)', detail_url)
            recipe_id = recipe_id_match.group(1) if recipe_id_match else None

            # 将详情页请求加入调度队列
            yield scrapy.Request(
                url=detail_url,
                callback=self.parse_detail,
                errback=self.handle_error,
                meta={
                    "recipe_id": recipe_id,
                    "title": title,
                    "detail_url": detail_url,
                    "cover_img_preview": cover_img or "",
                },
            )

        # ==================== 课设需求：翻页控制 ====================
        if current_page >= self.max_pages:
            self.logger.info(
                "[美食天下移动版] 已达到预设爬取上限（%d页），停止翻页。"
                "体现尊重服务器资源的工程伦理。",
                self.max_pages
            )
            return

        # ==================== 处理翻页 ====================
        # 移动版翻页在 div.page 中，取第一个 a 标签的 href
        next_page = response.xpath('//div[contains(@class, "page")]/a/@href').get()

        if next_page:
            next_url = response.urljoin(next_page)
            self.logger.info(
                "[美食天下移动版] 翻页 → 第%d页：%s",
                current_page + 1, next_url
            )
            yield scrapy.Request(
                url=next_url,
                callback=self.parse,
                errback=self.handle_error,
                meta={
                    **response.meta,
                    "page": current_page + 1,
                },
            )
        else:
            self.logger.info(
                "[美食天下移动版] 已无下一页，翻页结束：%s", response.url
            )

    def parse_detail(self, response):
        """
        解析菜谱详情页，提取全部字段。

        详情页 HTML 结构（美食天下移动版 2026年6月）：
          <!-- 顶部标题区 -->
          <div class="topbox">
            <h1><a href="/recipe/{id}/">菜谱名称</a></h1>
            <div class="author"><a href="/space/{uid}/">作者名</a> 发布</div>
          </div>

          <!-- 封面大图 -->
          <div class="row mb20">
            <img src="封面图URL" ... />
          </div>

          <!-- 菜品属性图标（难度/工艺/口味/时间） -->
          <ul class="recipeicon">
            <li><a><div></div><span>简单</span></a></li>     ← 难度
            <li><a><div></div><span>煮</span></a></li>       ← 工艺
            <li><a><div></div><span>原味</span></a></li>     ← 口味
            <li><a><div></div><span>一小时</span></a></li>   ← 时间
          </ul>

          <!-- 食材明细 -->
          <div id="ingredientlist">
            <h3>主料</h3>
            <ul class="rlist rlist-nopic">
              <li>
                <a href="/ingredient/.../">
                  <span>食材名</span><span class="grey">用量</span>
                </a>
              </li>
            </ul>
            <h3>辅料</h3> ... <h3>调料</h3> ...
          </div>

          <!-- 做法步骤 -->
          <ul class="steplist">
            <li>
              <img data-src="步骤图URL" ... />
              <div><span>1.</span>步骤描述文本</div>
            </li>
          </ul>

          <!-- 分类标签 -->
          <div id="tags">
            分类：
            <a href="/recipe/category/.../">标签名</a>
          </div>
        """
        # 检查 HTTP 状态码，4xx/5xx 错误直接跳过
        if response.status >= 400:
            self.logger.warning(
                "[美食天下移动版] 详情页返回 %d，跳过：%s",
                response.status, response.url
            )
            return

        # ---------- 创建 Item 实例 ----------
        item = FoodItem()
        item["recipe_id"] = response.meta.get("recipe_id")
        item["url"] = response.meta.get("detail_url", response.url)

        # ==================== 标题 ====================
        # 主选择器：div.topbox > h1 > a/text()
        title = response.xpath('//div[@class="topbox"]/h1/a/text()').get()
        if not title:
            title = response.xpath('//h1//text()').get()
        if not title:
            title = response.meta.get("title", "")
        item["title"] = self._clean_text(title) if title else "未知菜谱"

        # ==================== 作者 ====================
        author = response.xpath('//div[@class="topbox"]/div[@class="author"]/a/text()').get()
        if not author:
            author = response.xpath('//div[contains(@class, "author")]/a/text()').get()
        item["author"] = self._clean_text(author) if author else "匿名"

        # ==================== 封面图片 ====================
        cover_img = response.xpath('//div[contains(@class, "row") and contains(@class, "mb20")]/img/@src').get()
        if not cover_img:
            cover_img = response.xpath('//div[contains(@class, "row")]//img[contains(@src, "recipe")]/@src').get()
        if not cover_img:
            cover_img = response.meta.get("cover_img_preview", "")
        item["cover_image"] = cover_img or ""

        # ==================== 难度 ====================
        # recipeicon 第1个 li 是难度
        difficulty = response.xpath('//ul[@class="recipeicon"]/li[1]//span/text()').get()
        if not difficulty:
            difficulty = response.xpath('//ul[contains(@class, "recipeicon")]/li[1]//span/text()').get()
        item["difficulty"] = self._clean_text(difficulty) if difficulty else ""

        # ==================== 烹饪时间 ====================
        # recipeicon 第4个 li 是时间
        time_str = response.xpath('//ul[@class="recipeicon"]/li[4]//span/text()').get()
        if not time_str:
            time_str = response.xpath('//ul[contains(@class, "recipeicon")]/li[last()]//span/text()').get()
        item["time"] = self._clean_text(time_str) if time_str else ""

        # ==================== 烹饪工艺（存入 tags 前缀） ====================
        technic = response.xpath('//ul[@class="recipeicon"]/li[2]//span/text()').get()
        technic = self._clean_text(technic) if technic else ""

        # ==================== 口味（存入 tags 前缀） ====================
        flavor = response.xpath('//ul[@class="recipeicon"]/li[3]//span/text()').get()
        flavor = self._clean_text(flavor) if flavor else ""

        # ==================== 评分（移动版无评分，设为0） ====================
        item["rating"] = 0.0

        # ==================== 评价数量（移动版无此数据，设为0） ====================
        item["review_count"] = 0

        # ==================== 用料清单 ====================
        ingredients = []
        # 所有食材列表：ul.rlist.rlist-nopic > li
        ing_items = response.xpath('//div[@id="ingredientlist"]//ul[@class="rlist rlist-nopic"]/li')
        for li in ing_items:
            # 食材名称：span:first-child
            name = li.xpath('.//span[1]/text()').get()
            if not name:
                # 可能被包裹在 a 或 div 中
                name = li.xpath('.//a/span[1]/text()').get()
            if not name:
                name = li.xpath('.//div/span[1]/text()').get()

            # 用量：span.grey 或 span:last-child
            amount = li.xpath('.//span[contains(@class, "grey")]/text()').get()
            if not amount:
                amount = li.xpath('.//span[last()]/text()').get()
                # 如果 last-child 与 name 相同则清空
                if amount and name and amount.strip() == name.strip():
                    amount = ""

            name = self._clean_text(name) if name else ""
            amount = self._clean_text(amount) if amount else ""

            if name:
                if amount:
                    ingredients.append(f"{name}: {amount}")
                else:
                    ingredients.append(name)
        item["ingredients"] = ingredients

        # ==================== 制作步骤 ====================
        steps = []
        step_items = response.xpath('//ul[@class="steplist"]/li')
        for i, step_el in enumerate(step_items, 1):
            # 步骤文本在 div 中，取所有文本
            step_text = self._clean_text(
                "".join(step_el.xpath('./div//text()').getall())
            )
            if not step_text:
                step_text = self._clean_text(
                    "".join(step_el.xpath('.//text()').getall())
                )
            # 去除步骤编号前缀（如 "1."），保留描述文本
            step_text = re.sub(r'^\d+\.\s*', '', step_text)
            if step_text:
                steps.append(f"步骤{i}: {step_text}")
        item["steps"] = steps

        # ==================== 分类标签 ====================
        tags = response.xpath('//div[@id="tags"]/a/text()').getall()
        tags = [self._clean_text(t) for t in tags if self._clean_text(t)]
        # 将工艺和口味也加入标签
        if technic:
            tags.insert(0, technic)
        if flavor:
            tags.insert(1, flavor)
        item["tags"] = tags

        # ==================== 描述/简介 ====================
        # 取 meta description 作为简介
        desc = response.xpath('//meta[@name="description"]/@content').get()
        item["description"] = self._clean_text(desc) if desc else ""

        self.logger.info("[美食天下移动版] 成功解析菜谱：%s", item.get("title", "未知"))
        yield item

    # ======================== 工具方法 ========================

    @staticmethod
    def _clean_text(text):
        """
        清洗文本：去除首尾空白、多余换行符和制表符。

        Args:
            text: 原始文本字符串

        Returns:
            清洗后的文本，若输入为空则返回空字符串
        """
        if not text:
            return ""
        text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def handle_error(self, failure):
        """
        全局异常回调：处理请求失败（超时、DNS 错误、HTTP 错误码等）。

        Args:
            failure: Twisted Failure 对象，包含异常信息
        """
        self.logger.error(
            "[美食天下移动版] 请求失败：%s，错误：%s",
            failure.request.url if failure.request else "未知URL",
            failure.value,
        )
