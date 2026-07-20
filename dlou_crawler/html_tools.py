"""网页解析工具：从学校官网页面中抽取标题、正文、链接、日期与附件。

仅依赖标准库（html.parser），无需第三方包。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin


DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2}[./-]\d{1,2}[./-]\d{1,2})(?!\d)")
CHINESE_DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
SPACE_PATTERN = re.compile(r"\s+")
ATTACHMENT_PATTERN = re.compile(r"\.(?:pdf|docx?|xlsx?|pptx?|zip|rar|txt)(?:$|[?#])", re.I)


def clean_text(value: str) -> str:
    """把连续空白压成单个空格，并去掉首尾空白。"""
    return SPACE_PATTERN.sub(" ", value).strip()


@dataclass(slots=True)
class Link:
    text: str
    url: str


@dataclass(slots=True)
class ParsedPage:
    title: str
    text: str
    links: list[Link] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)


class _PageParser(HTMLParser):
    """Small dependency-free parser for the WebPlus-style pages used by the site."""

    CONTENT_WORDS = ("vsb_content", "article-content", "article_content", "content")

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[Link] = []
        self._link_url: str | None = None
        self._link_parts: list[str] = []
        self._all_text: list[str] = []
        self._content_text: list[str] = []
        self._headings: list[str] = []
        self._heading_parts: list[str] | None = None
        self._title_parts: list[str] | None = None
        self._ignored_depth = 0
        self._content_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1
        if tag == "a" and attributes.get("href"):
            self._link_url = urljoin(self.base_url, attributes["href"])
            self._link_parts = []
        if tag == "title":
            self._title_parts = []
        if tag in {"h1", "h2"}:
            self._heading_parts = []
        marker = (attributes.get("id", "") + " " + attributes.get("class", "")).lower()
        if any(word in marker for word in self.CONTENT_WORDS):
            self._content_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1
        if tag == "a" and self._link_url is not None:
            text = clean_text(" ".join(self._link_parts))
            if text:
                self.links.append(Link(text, self._link_url))
            self._link_url = None
            self._link_parts = []
        if tag == "title" and self._title_parts is not None:
            self.title = clean_text(" ".join(self._title_parts))
            self._title_parts = None
        if tag in {"h1", "h2"} and self._heading_parts is not None:
            heading = clean_text(" ".join(self._heading_parts))
            if heading:
                self._headings.append(heading)
            self._heading_parts = None
        if self._content_depth and tag in {"div", "article", "section", "td"}:
            self._content_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = clean_text(data)
        if not text:
            return
        self._all_text.append(text)
        if self._link_url is not None:
            self._link_parts.append(text)
        if self._title_parts is not None:
            self._title_parts.append(text)
        if self._heading_parts is not None:
            self._heading_parts.append(text)
        if self._content_depth:
            self._content_text.append(text)

    def result(self) -> ParsedPage:
        return ParsedPage(
            title=getattr(self, "title", ""),
            text=clean_text(" ".join(self._content_text or self._all_text)),
            links=self.links,
            headings=self._headings,
        )


def parse_page(html: str, base_url: str) -> ParsedPage:
    """解析一段 HTML，返回标题、正文、链接与标题行。"""
    parser = _PageParser(base_url)
    parser.feed(html)
    parser.close()
    return parser.result()


def date_from_text(text: str) -> str | None:
    """从正文中识别发布日期（支持 2026-07-20 与 2026年7月20日 两种写法）。"""
    match = DATE_PATTERN.search(text)
    if match:
        return match.group(1).replace("/", "-").replace(".", "-")
    chinese_match = CHINESE_DATE_PATTERN.search(text)
    if chinese_match:
        year, month, day = chinese_match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return None


def date_from_url(url: str) -> str | None:
    """Article URLs normally contain their publication date, for example /2026/0717/."""
    match = re.search(r"/(20\d{2})/(\d{2})(\d{2})/", url)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{year}-{month}-{day}"


def is_attachment(url: str) -> bool:
    """判断链接是否指向常见附件类型（pdf/docx/xlsx/pptx/zip 等）。"""
    return bool(ATTACHMENT_PATTERN.search(url))


def is_article_link(link: Link) -> bool:
    """Keep article-looking pages and reject menus, images and pagination links."""
    lowered = link.url.lower()
    if len(link.text) < 6 or is_attachment(lowered):
        return False
    if any(word in link.text for word in ("下一页", "上一页", "首页", "尾页", "更多", "进入")):
        return False
    return bool(re.search(r"/(?:info/\d+|20\d{2}/\d{4}/c\d+a\d+)/", lowered))
