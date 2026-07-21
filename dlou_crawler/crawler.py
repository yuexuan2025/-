"""大连海洋大学官网公开信息采集器核心逻辑。

流程：
1. 遍历预设栏目，收集文章链接（遵守官网域名白名单）。
2. 并发拉取每篇文章的正文、元信息与附件。
3. 按标题去重后返回 Article 列表，交由 output 模块写出。

仅采集学校官网的公开内容，不登录、不绕过限制。
"""
from __future__ import annotations

import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlsplit, urlunsplit

from .client import FetchError, HttpClient
from .html_tools import Link, date_from_text, date_from_url, is_article_link, is_attachment, parse_page
from .models import Article, Attachment


ALLOWED_HOSTS = frozenset({
    "www.dlou.edu.cn", "news.dlou.edu.cn",
    "life.dlou.edu.cn", "hhxy.dlou.edu.cn", "food.dlou.edu.cn",
    "tmgc.dlou.edu.cn", "jixie.dlou.edu.cn", "sea.dlou.edu.cn",
    "xxgc.dlou.edu.cn", "jjgl.dlou.edu.cn", "fxy.dlou.edu.cn",
    "wgy.dlou.edu.cn", "zwhzbx.dlou.edu.cn", "mks.dlou.edu.cn",
    "jxjyxy.dlou.edu.cn", "gzy.dlou.edu.cn", "master.dlou.edu.cn",
    "tyxy.dlou.edu.cn", "jiuye.dlou.edu.cn", "jzszx.dlou.edu.cn",
})

CATEGORY_GROUPS = [
    ("📰 学校要闻", ["学校要闻", "综合新闻", "校园快讯", "媒体报道", "校园喜报"]),
    ("📢 通知公告", ["信息公告", "学术海大", "今日活动", "下载专区"]),
    ("🎓 学生发展", ["本科生教育", "研究生教育", "本科生招生", "研究生招生",
                      "本科生就业", "研究生就业", "继续教育"]),
    ("🏫 各学院动态", ["水产与生命学院", "海洋科技与环境学院", "食品科学与工程学院",
                        "海洋与土木工程学院", "机械与动力工程学院", "航海与船舶工程学院",
                        "信息工程学院", "经济管理学院", "海洋法律与人文学院",
                        "外国语学院", "中新合作学院", "马克思主义学院",
                        "体育与教育学院", "应用技术学院"]),
]

SOURCES = (
    # 学校要闻
    ("学校要闻", "https://news.dlou.edu.cn/1281/list.htm"),
    ("综合新闻", "https://news.dlou.edu.cn/jcfc/list.htm"),
    ("校园快讯", "https://news.dlou.edu.cn/1288/list.htm"),
    ("媒体报道", "https://news.dlou.edu.cn/1283/list.htm"),
    ("校园喜报", "https://news.dlou.edu.cn/xyxb/list.htm"),
    # 通知公告
    ("信息公告", "https://www.dlou.edu.cn/89/list.htm"),
    ("学术海大", "https://www.dlou.edu.cn/190/list.htm"),
    ("今日活动", "https://www.dlou.edu.cn/jrhd/list.htm"),
    ("下载专区", "https://news.dlou.edu.cn/1290/list.htm"),
    # 学生发展
    ("本科生教育", "https://www.dlou.edu.cn/78/list.htm"),
    ("研究生教育", "https://master.dlou.edu.cn/9044/list.htm"),
    ("本科生招生", "https://jzszx.dlou.edu.cn/bkszs/list.htm"),
    ("研究生招生", "https://master.dlou.edu.cn/9043/list.htm"),
    ("本科生就业", "https://jiuye.dlou.edu.cn/xbjy/list.htm"),
    ("研究生就业", "https://master.dlou.edu.cn/9068/list.htm"),
    ("继续教育", "https://jxjyxy.dlou.edu.cn/"),
    # 各学院
    ("水产与生命学院", "https://life.dlou.edu.cn/"),
    ("海洋科技与环境学院", "https://hhxy.dlou.edu.cn/"),
    ("食品科学与工程学院", "https://food.dlou.edu.cn/"),
    ("海洋与土木工程学院", "https://tmgc.dlou.edu.cn/"),
    ("机械与动力工程学院", "https://jixie.dlou.edu.cn/"),
    ("航海与船舶工程学院", "https://sea.dlou.edu.cn/"),
    ("信息工程学院", "https://xxgc.dlou.edu.cn/"),
    ("经济管理学院", "https://jjgl.dlou.edu.cn/"),
    ("海洋法律与人文学院", "https://fxy.dlou.edu.cn/"),
    ("外国语学院", "https://wgy.dlou.edu.cn/"),
    ("中新合作学院", "https://zwhzbx.dlou.edu.cn/"),
    ("马克思主义学院", "https://mks.dlou.edu.cn/"),
    ("体育与教育学院", "https://tyxy.dlou.edu.cn/"),
    ("应用技术学院", "https://gzy.dlou.edu.cn/"),
)


class DlouCrawler:
    """官网公开信息采集器：按栏目收集链接并并发读取正文。"""

    def __init__(
        self,
        client: HttpClient,
        pages_per_source: int,
        max_articles: int,
        download_files: bool,
        output_dir: Path,
        concurrency: int = 4,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.client = client
        self.pages_per_source = pages_per_source
        self.max_articles = max_articles
        self.download_files = download_files
        self.output_dir = output_dir
        self.concurrency = max(1, concurrency)
        self.warnings: list[str] = []
        self._warn_lock = threading.Lock()
        self._start_time = 0.0
        self._progress_callback = progress_callback

    def _warn(self, msg: str) -> None:
        with self._warn_lock:
            self.warnings.append(msg)

    def _log(self, msg: str) -> None:
        """输出日志，支持回调到 GUI。"""
        if self._progress_callback:
            self._progress_callback(msg)
        print(msg)

    @staticmethod
    def is_allowed(url: str) -> bool:
        parts = urlsplit(url)
        return parts.scheme in {"http", "https"} and parts.hostname in ALLOWED_HOSTS

    @staticmethod
    def _canonical_url(url: str) -> str:
        parts = urlsplit(url)
        return urlunsplit(("https", parts.netloc, parts.path, parts.query, ""))

    def crawl(self) -> list[Article]:
        """执行一次完整采集：并发扫描栏目 → 并发读取正文 → 按标题去重返回文章列表。"""
        self._start_time = time.monotonic()
        candidates: dict[str, tuple[str, str]] = {}
        candidates_lock = threading.Lock()

        self._log("📁 正在并发扫描各栏目，收集文章链接...")

        # 第一阶段：并发扫描所有栏目的列表页
        def scan_source(idx_category_url: tuple[int, tuple[str, str]]) -> None:
            idx, (category, source_url) = idx_category_url
            self._log(f"   [{idx}/{len(SOURCES)}] 开始扫描：{category}")
            local_candidates: dict[str, tuple[str, str]] = {}
            self._collect_listing_links(category, source_url, local_candidates)
            with candidates_lock:
                for url, (title, cat) in local_candidates.items():
                    candidates.setdefault(url, (title, cat))
            count = len(local_candidates)
            self._log(f"   ✔  {category}：找到 {count} 篇文章")

        with ThreadPoolExecutor(max_workers=min(self.concurrency * 2, 32)) as pool:
            list(pool.map(scan_source, enumerate(SOURCES, start=1)))

        total = len(candidates)
        elapsed = time.monotonic() - self._start_time
        self._log(f"✅ 扫描完成，共找到 {total} 条链接（耗时 {elapsed:.1f} 秒）")

        if total == 0:
            self._log("❌ 未找到可采集的文章链接，请稍后重试。")
            return []

        self._log(f"🚀 开始并发读取正文（{self.concurrency} 线程）...")

        articles: list[Article] = []
        seen_titles: set[str] = set()
        articles_lock = threading.Lock()
        counter = {"done": 0, "failed": 0}
        counter_lock = threading.Lock()

        jobs = list(candidates.items())[: self.max_articles]

        def fetch_one(item: tuple[str, tuple[str, str]]) -> tuple[str, Article | None]:
            url, (title, category) = item
            with counter_lock:
                counter["done"] += 1
                done = counter["done"]
            label = title if len(title) <= 42 else title[:41] + "\u2026"

            self._log(f"   [{done}/{len(jobs)}] {label}")

            try:
                return url, self._collect_article(url, title, category)
            except Exception as exc:
                with counter_lock:
                    counter["failed"] += 1
                short = str(exc)[:50]
                self._warn(f"读取失败：{label}（{short}）")
                return url, None

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = {pool.submit(fetch_one, job): job for job in jobs}
            for future in as_completed(futures):
                _url, article = future.result()
                title_key = article.title.casefold() if article else ""
                if article and title_key not in seen_titles:
                    with articles_lock:
                        articles.append(article)
                        seen_titles.add(title_key)

        total_elapsed = time.monotonic() - self._start_time
        self._log(f"📊 正文读取完成：成功 {len(articles)} 篇，失败 {counter['failed']} 篇")
        self._log(f"⏱️  总耗时：{total_elapsed:.1f} 秒")

        return articles

    def _collect_listing_links(
        self, category: str, source_url: str, candidates: dict[str, tuple[str, str]]
    ) -> None:
        """广度优先扫描栏目列表页，收集文章链接与下一页链接。"""
        pages = deque([source_url])
        seen: set[str] = set()
        page_num = 0
        
        while pages and len(seen) < self.pages_per_source:
            url = pages.popleft()
            if url in seen or not self._permitted(url):
                continue
            seen.add(url)
            page_num += 1
            
            try:
                page = parse_page(self.client.get_text(url), url)
            except FetchError as error:
                msg = str(error)
                # CAS 登录重定向是正常的，不算警告
                if "cas/login" in msg or "portal.dlou.edu.cn" in msg:
                    continue
                self._warn(f"{category}：列表页访问失败（{msg[:60]}）")
                continue
            
            found_count = 0
            for link in page.links:
                if self.is_allowed(link.url) and is_article_link(link):
                    article_url = self._canonical_url(link.url)
                    candidates.setdefault(article_url, (link.text, self._category_for(article_url, category)))
                    found_count += 1
                if self._is_next_page(link, url) and self.is_allowed(link.url):
                    pages.append(self._canonical_url(link.url))
            
            if found_count > 0:
                self._log(f"      ├─ 第 {page_num} 页：找到 {found_count} 篇文章")

    def _collect_article(self, url: str, fallback_title: str, category: str) -> Article | None:
        """读取单篇文章：解析正文、日期、附件；需要登录时返回占位文章。"""
        if not self._permitted(url):
            return None
        try:
            page = parse_page(self.client.get_text(url), url)
        except FetchError as error:
            msg = str(error)
            # CAS 登录重定向是正常的，不算警告
            if "cas/login" not in msg and "portal.dlou.edu.cn" not in msg:
                self._warn(f"读取失败：{fallback_title[:30]}（{msg[:50]}）")
            return Article(
                title=fallback_title,
                url=url,
                category=category,
                published_at=None,
                content="正文需要登录或暂时无法公开访问，未采集。请通过原文链接在学校网站查看。",
            )
        title = page.headings[0] if page.headings else page.title or fallback_title
        attachments = [
            Attachment(link.text, link.url)
            for link in page.links
            if self.is_allowed(link.url) and is_attachment(link.url)
        ]
        article = Article(
            title=title,
            url=url,
            category=category,
            published_at=date_from_text(page.text) or date_from_url(url),
            content=page.text,
            attachments=attachments,
        )
        if self.download_files:
            self._download_attachments(article)
        return article

    def _download_attachments(self, article: Article) -> None:
        """把文章中的公开附件下载到 output/files 目录。"""
        for index, attachment in enumerate(article.attachments, start=1):
            if not self._permitted(attachment.url):
                continue
            filename = self._safe_filename(attachment.url, index)
            destination = self.output_dir / "files" / filename
            try:
                self.client.download(attachment.url, destination)
                attachment.local_path = str(destination)
            except FetchError as error:
                self._warn(str(error))

    def _permitted(self, url: str) -> bool:
        """仅在链接属于官网域名时才允许访问，否则记录警告并返回 False。"""
        if not self.is_allowed(url):
            self._warn(f"已跳过非官网链接：{url}")
            return False
        return True

    @staticmethod
    def _is_next_page(link: Link, current_url: str) -> bool:
        return "下一页" in link.text and link.url != current_url

    @staticmethod
    def _safe_filename(url: str, index: int) -> str:
        original = Path(unquote(urlsplit(url).path)).name or f"attachment-{index}"
        cleaned = re.sub(r'[<>:"/\\|?*]', "_", original)
        return f"{index:03d}-{cleaned}"

    @staticmethod
    def _category_for(url: str, fallback: str) -> str:
        section_map = {
            "/c1281a": "学校要闻",
            "/c4820a": "学校要闻",
            "/c7118a": "综合新闻",
            "/c1288a": "校园快讯",
            "/c1283a": "媒体报道",
            "/c5057a": "校园喜报",
            "/c89a": "信息公告",
            "/c190a": "学术海大",
            "/c5a": "学校简介",
            "/c6a": "学校简介",
            "/c7a": "学校领导",
            "/c13a": "教学单位",
            "/c73a": "科研机构",
            "/c77a": "人才培养",
            "/gdtp": "滚动图片",
            "/c1290a": "下载专区",
        }
        for segment, name in section_map.items():
            if segment in url:
                return name
        return fallback