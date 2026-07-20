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
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from .client import FetchError, HttpClient
from .html_tools import Link, date_from_text, date_from_url, is_article_link, is_attachment, parse_page
from .models import Article, Attachment


ALLOWED_HOSTS = frozenset({"www.dlou.edu.cn", "news.dlou.edu.cn"})
SOURCES = (
    ("学校要闻", "https://news.dlou.edu.cn/1281/list.htm"),
    ("综合新闻", "https://news.dlou.edu.cn/jcfc/list.htm"),
    ("校园快讯", "https://news.dlou.edu.cn/1288/list.htm"),
    ("媒体报道", "https://news.dlou.edu.cn/1283/list.htm"),
    ("校园喜报", "https://news.dlou.edu.cn/xyxb/list.htm"),
    ("信息公告", "https://www.dlou.edu.cn/89/list.htm"),
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
    ) -> None:
        self.client = client
        self.pages_per_source = pages_per_source
        self.max_articles = max_articles
        self.download_files = download_files
        self.output_dir = output_dir
        self.concurrency = max(1, concurrency)
        self.warnings: list[str] = []
        self._warn_lock = threading.Lock()

    def _warn(self, msg: str) -> None:
        with self._warn_lock:
            self.warnings.append(msg)

    @staticmethod
    def is_allowed(url: str) -> bool:
        parts = urlsplit(url)
        return parts.scheme in {"http", "https"} and parts.hostname in ALLOWED_HOSTS

    @staticmethod
    def _canonical_url(url: str) -> str:
        """The homepage contains some HTTP links; use HTTPS for every request."""
        parts = urlsplit(url)
        return urlunsplit(("https", parts.netloc, parts.path, parts.query, ""))

    def crawl(self) -> list[Article]:
        """执行一次完整采集：扫描栏目 → 并发读取正文 → 按标题去重返回文章列表。"""
        candidates: dict[str, tuple[str, str]] = {}
        for category, source_url in SOURCES:
            print(f"· 扫描栏目：{category}（读取列表页中…）")
            self._collect_listing_links(category, source_url, candidates)
        total = len(candidates)
        if total == 0:
            print("未找到可采集的文章链接，请稍后重试。")
            return []
        print(f"共找到 {total} 条文章，开始读取正文（并发 {self.concurrency} 线程）...")

        articles: list[Article] = []
        seen_titles: set[str] = set()
        articles_lock = threading.Lock()
        counter = {"done": 0}
        counter_lock = threading.Lock()

        # Build the job list up to max_articles
        jobs = list(candidates.items())[: self.max_articles]

        def fetch_one(item: tuple[str, tuple[str, str]]) -> tuple[str, Article | None]:
            url, (title, category) = item
            with counter_lock:
                counter["done"] += 1
                label = title if len(title) <= 42 else title[:41] + "\u2026"
                print(f"  [{counter['done']}/{total}] {label}")
            try:
                return url, self._collect_article(url, title, category)
            except Exception as exc:  # 单篇失败不拖垮整个采集
                self._warn(f"读取文章失败（已跳过）：{url} —— {exc}")
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

        return articles

    def _collect_listing_links(
        self, category: str, source_url: str, candidates: dict[str, tuple[str, str]]
    ) -> None:
        """广度优先扫描栏目列表页，收集文章链接与下一页链接。"""
        pages = deque([source_url])
        seen: set[str] = set()
        while pages and len(seen) < self.pages_per_source:
            url = pages.popleft()
            if url in seen or not self._permitted(url):
                continue
            seen.add(url)
            try:
                page = parse_page(self.client.get_text(url), url)
            except FetchError as error:
                self._warn(str(error))
                continue
            for link in page.links:
                if self.is_allowed(link.url) and is_article_link(link):
                    article_url = self._canonical_url(link.url)
                    candidates.setdefault(article_url, (link.text, self._category_for(article_url, category)))
                if self._is_next_page(link, url) and self.is_allowed(link.url):
                    pages.append(self._canonical_url(link.url))

    def _collect_article(self, url: str, fallback_title: str, category: str) -> Article | None:
        """读取单篇文章：解析正文、日期、附件；需要登录时返回占位文章。"""
        if not self._permitted(url):
            return None
        try:
            page = parse_page(self.client.get_text(url), url)
        except FetchError as error:
            self._warn(str(error))
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
        # Article URLs embed a section code; map the known ones to section names.
        section_map = {
            "/c1281a": "学校要闻",
            "/c4820a": "学校要闻",
            "/c7118a": "综合新闻",
            "/c1288a": "校园快讯",
            "/c1283a": "媒体报道",
            "/c5057a": "校园喜报",
            "/c89a": "信息公告",
        }
        for segment, name in section_map.items():
            if segment in url:
                return name
        return fallback
