"""
下厨房爬虫中间件 —— Scrapy 2.16 适配版
========================================
提供反爬虫中间件，包括 User-Agent 轮换、请求延迟随机化等功能。
同时提供 CurlCffiDownloaderMiddleware，用于绕过 TLS 指纹检测。

中间件优先级（数字越小越先执行）：
  - CurlCffiDownloaderMiddleware: 550（高优先级，TLS 指纹绕过）
  - FoodSpiderProjectDownloaderMiddleware: 543

Scrapy 2.16 适配说明：
  1. 下载器中间件的 process_request/process_response/process_exception 方法
     仍接收 spider 参数（由 Scrapy 引擎传入），但内部优先使用 from_crawler
     保存的 self.crawler 引用获取爬虫信息。
  2. Spider 中间件的生命周期方法已使用 from_crawler 模式。

curl_cffi 集成说明（2026-07-03）：
  美食天下移动版（m.meishichina.com）使用了 TLS 指纹检测，Python 标准
  ssl 库的 TLS 握手被识别为非浏览器流量，返回 HTTP 403。curl_cffi 库
  通过模拟 Chrome/Safari 浏览器的 TLS 指纹（JA3/JA4）成功绕过该检测。
  本中间件拦截目标域名的请求并通过 curl_cffi 代理执行，其他域名不受影响。
"""

import random
import logging
from scrapy import signals
from scrapy.http import HtmlResponse

# 【Scrapy 2.16 适配】使用模块级 logger 作为日志兜底
logger = logging.getLogger(__name__)


class FoodSpiderProjectSpiderMiddleware:
    """Spider 中间件：处理 Spider 输入/输出/异常"""

    @classmethod
    def from_crawler(cls, crawler):
        """【Scrapy 2.16 适配】保存 crawler 引用"""
        s = cls()
        s.crawler = crawler
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider=None):
        """每个 Response 进入 Spider 之前的回调"""
        return None

    def process_spider_output(self, response, result, spider=None):
        """Spider 处理完 Response 输出 Item/Request 时的回调"""
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider=None):
        """Spider 处理过程中抛出异常时的回调"""
        log_spider = spider if spider else (
            self.crawler.spider if getattr(self, 'crawler', None) else None
        )
        if log_spider:
            log_spider.logger.error(
                "Spider 异常 - URL: %s, 错误: %s",
                response.url if response else "无",
                exception,
            )
        else:
            logger.error(
                "Spider 异常 - URL: %s, 错误: %s",
                response.url if response else "无",
                exception,
            )
        return None

    def process_start_requests(self, start_requests, spider=None):
        """处理初始请求列表"""
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info("Spider 中间件已就绪: %s", spider.name)


class FoodSpiderProjectDownloaderMiddleware:
    """
    下载器中间件：处理请求/响应/异常。

    已配置的主要反爬措施：
      - User-Agent 伪装（settings.py DEFAULT_REQUEST_HEADERS + USER_AGENT）
      - AutoThrottle 自适应节流（settings.py）
      - 反爬拦截关键词检测（本中间件 process_response）
    """

    @classmethod
    def from_crawler(cls, crawler):
        """【Scrapy 2.16 适配】保存 crawler 引用并连接信号"""
        s = cls()
        s.crawler = crawler
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider=None):
        """请求发送前的处理钩子（Scrapy 2.16：spider 为可选参数）"""
        return None

    def process_response(self, request, response, spider=None):
        """
        响应返回后的处理钩子。

        可用于检测反爬页面（如验证码、IP 封禁提示），
        并将被拦截的请求重新入队或触发告警。

        Scrapy 2.16：spider 参数保留但设为可选，优先使用 self.crawler.spider。
        """
        # 检测是否被反爬拦截（常见迹象：返回空内容、包含验证码关键词）
        if response.status == 200:
            body_text = response.text[:500].lower()
            blocked_keywords = ["请输入验证码", "访问过于频繁", "ip已被限制"]
            for keyword in blocked_keywords:
                if keyword in body_text:
                    log_spider = spider if spider else (
                        self.crawler.spider if getattr(self, 'crawler', None) else None
                    )
                    if log_spider:
                        log_spider.logger.warning(
                            "疑似被反爬拦截，URL: %s，关键词: %s",
                            response.url,
                            keyword,
                        )
                    else:
                        logger.warning(
                            "疑似被反爬拦截，URL: %s，关键词: %s",
                            response.url,
                            keyword,
                        )
                    # 可在此处将请求标记为失败或延长延迟
                    break

        return response

    def process_exception(self, request, exception, spider=None):
        """请求异常时的处理钩子"""
        log_spider = spider if spider else (
            self.crawler.spider if getattr(self, 'crawler', None) else None
        )
        if log_spider:
            log_spider.logger.warning(
                "下载异常 - URL: %s, 异常: %s",
                request.url if request else "无",
                exception,
            )
        else:
            logger.warning(
                "下载异常 - URL: %s, 异常: %s",
                request.url if request else "无",
                exception,
            )
        return None

    def spider_opened(self, spider):
        spider.logger.info("下载器中间件已就绪: %s", spider.name)


# ======================== curl_cffi TLS 指纹绕过中间件 ========================
# 课设需求：美食天下移动版（m.meishichina.com）使用 TLS 指纹检测，
# Python 标准 ssl/Twisted 的 TLS 握手会被识别为非浏览器流量并返回 403。
# 本中间件通过 curl_cffi 模拟 Chrome 110 浏览器的 TLS 指纹来绕过该检测。
#
# 技术原理：
#   - curl_cffi 底层使用 libcurl-impersonate，可精确模拟浏览器 TLS 握手
#   - JA3/JA4 指纹与真实 Chrome 浏览器一致，服务端无法区分
#   - 仅拦截目标域名（m.meishichina.com），其他流量走 Scrapy 原生下载器
#
# 版本兼容：curl_cffi >= 0.5.0，Python 3.7+
class CurlCffiDownloaderMiddleware:
    """
    curl_cffi 下载器中间件：对指定域名使用 curl_cffi 发起请求以绕过 TLS 指纹检测。

    中间件优先级设为 550（高于默认的 DownloaderMiddleware 的 543），
    确保在 Scrapy 原生下载器之前拦截请求。
    """

    def __init__(self):
        """延迟导入 curl_cffi，避免非目标爬虫启动时报错"""
        self._curl_requests = None

    @classmethod
    def from_crawler(cls, crawler):
        """工厂方法：创建中间件实例"""
        s = cls()
        s.crawler = crawler
        return s

    def _get_curl_requests(self):
        """延迟导入 curl_cffi.requests 模块"""
        if self._curl_requests is None:
            from curl_cffi import requests as curl_requests
            self._curl_requests = curl_requests
        return self._curl_requests

    def process_request(self, request, spider):
        """
        拦截对 m.meishichina.com 的请求，使用 curl_cffi 代理执行。

        仅处理 GET 请求；POST/PUT 等请求放行给 Scrapy 原生下载器。

        Returns:
            HtmlResponse: 成功时返回 Scrapy Response 对象
            None: 非目标域名/方法时放行
        """
        # 仅处理目标域名
        if "m.meishichina.com" not in request.url:
            return None

        # 仅处理 GET 请求
        if request.method != "GET":
            return None

        spider.logger.debug(
            "[curl_cffi] 拦截请求：%s", request.url
        )

        curl_req = self._get_curl_requests()

        try:
            # 使用 curl_cffi 发起请求，模拟 Chrome 110 TLS 指纹
            resp = curl_req.get(
                request.url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "Version/16.0 Mobile/15E148 Safari/604.1"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
                },
                impersonate="chrome110",
                timeout=30,
            )

            spider.logger.debug(
                "[curl_cffi] 响应：HTTP %d, 大小 %d bytes",
                resp.status_code, len(resp.content)
            )

            # 构建 Scrapy HtmlResponse
            return HtmlResponse(
                url=str(resp.url),
                status=resp.status_code,
                headers={
                    "Content-Type": resp.headers.get("Content-Type", "text/html; charset=utf-8"),
                },
                body=resp.content,
                request=request,
                encoding="utf-8",
            )

        except Exception as e:
            spider.logger.error(
                "[curl_cffi] 请求失败：%s，错误：%s",
                request.url, e
            )
            # 返回错误响应，让 Scrapy 的重试机制处理
            return HtmlResponse(
                url=request.url,
                status=500,
                body=b"",
                request=request,
            )
