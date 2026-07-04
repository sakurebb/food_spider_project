"""
下厨房（xiachufang.com）美食数据 Item 定义
=============================================
本模块定义了 FoodItem，所有字段均对应下厨房菜谱详情页中真实可提取的内容。
参考页面结构（2024 版）：
  - 列表页：div.normal-recipe-list > ul > li
  - 详情页：h1.page-title / div.ings / div.steps / div.recipe-cats 等
"""

import scrapy


class FoodItem(scrapy.Item):
    """下厨房菜谱数据条目，每个实例代表一道菜谱的完整信息"""

    # ==================== 基本信息 ====================
    # 菜谱标题，对应详情页 <h1 class="page-title"> 标签内文本
    title = scrapy.Field()

    # 菜谱详情页完整 URL，用于去重和后续查询
    url = scrapy.Field()

    # 菜谱唯一 ID，从 URL 中提取（如 /recipe/104906521/ → 104906521）
    recipe_id = scrapy.Field()

    # ==================== 作者信息 ====================
    # 发布者昵称，对应详情页 <div class="author"> 区域
    author = scrapy.Field()

    # ==================== 菜谱属性 ====================
    # 烹饪难度：简单 / 中等 / 困难
    # 下厨房部分菜谱在描述区或标签中包含难度信息，提取后经 Pipeline 数字标准化
    difficulty = scrapy.Field()

    # 烹饪时间（字符串），如 "30分钟"、"1小时" 等
    # 来源：详情页描述区或统计区的时间提示
    time = scrapy.Field()

    # ==================== 食材与步骤 ====================
    # 用料清单（列表），对应详情页 <div class="ings"> 下的 <table> 行
    # 每行含食材名称 <td class="name"> 和用量 <td class="unit">
    ingredients = scrapy.Field()

    # 制作步骤（列表），对应详情页 <div class="steps"> > <ol> > <li>
    # 每个 <li> 包含步骤文字描述（可能夹杂图片）
    steps = scrapy.Field()

    # ==================== 评价数据 ====================
    # 综合评分（浮点数），对应详情页 <div class="score float-left">
    #   <span class="number"> 内数值，如 "8.2"
    rating = scrapy.Field()

    # 评价/做过人数（整数），对应详情页 <div class="cooked float-left">
    #   <span class="number"> 内数值
    review_count = scrapy.Field()

    # ==================== 分类标签 ====================
    # 菜谱分类标签（列表），对应详情页 <div class="recipe-cats"> 下的 <a> 标签
    tags = scrapy.Field()

    # ==================== 辅助信息 ====================
    # 封面图片 URL（可选），对应详情页 <div class="cover image"> > <img>
    cover_image = scrapy.Field()

    # 菜谱描述/简介，对应详情页 <div class="desc mt30"> 文本内容
    description = scrapy.Field()
