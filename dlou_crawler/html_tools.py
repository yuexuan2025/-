import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


class _ArticleExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.content_parts = []
        self.images = []
        self._in_title = False
        self._in_content = False
        self._content_depth = 0
        self._skip_tags = {"script", "style", "nav", "header", "footer"}
        self._skip_depth = 0
        self._current_href = None
        self._current_link_text = []
        self.attachments = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag in self._skip_tags:
            self._skip_depth += 1
            return

        if self._skip_depth > 0:
            return

        if tag == "title":
            self._in_title = True
            return

        if tag == "img":
            src = attrs_dict.get("src", "")
            alt = attrs_dict.get("alt", "")
            if src:
                self.images.append({"src": src, "alt": alt})
            if self._in_content:
                self.content_parts.append(f'<img src="{src}" alt="{alt}">')
            return

        if tag == "a":
            href = attrs_dict.get("href", "")
            self._current_href = href
            self._current_link_text = []
            return

        class_attr = attrs_dict.get("class", "")
        id_attr = attrs_dict.get("id", "")

        content_indicators = [
            "article", "content", "main", "text", "detail",
            "news_content", "v_news_content", "article-content",
            "entry-content", "post-content", "wp-content",
        ]

        if not self._in_content:
            for indicator in content_indicators:
                if indicator in class_attr.lower() or indicator in id_attr.lower():
                    self._in_content = True
                    self._content_depth = 1
                    break
        else:
            self._content_depth += 1

        if self._in_content and tag not in ("img",):
            if tag == "p":
                self.content_parts.append("<p>")
            elif tag == "br":
                self.content_parts.append("<br>")
            elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self.content_parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip_depth -= 1
            if self._skip_depth < 0:
                self._skip_depth = 0
            return

        if self._skip_depth > 0:
            return

        if tag == "title":
            self._in_title = False
            return

        if tag == "a" and self._current_href:
            link_text = "".join(self._current_link_text).strip()
            if is_attachment(self._current_href, link_text):
                self.attachments.append({
                    "name": link_text or self._current_href,
                    "url": self._current_href,
                })
            if self._in_content and link_text:
                self.content_parts.append(
                    f'<a href="{self._current_href}">{link_text}</a>'
                )
            self._current_href = None
            self._current_link_text = []
            return

        if self._in_content:
            self._content_depth -= 1
            if self._content_depth <= 0:
                self._in_content = False
                self._content_depth = 0

            if tag == "p":
                self.content_parts.append("</p>")
            elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self.content_parts.append(f"</{tag}>")

    def handle_data(self, data):
        if self._skip_depth > 0:
            return

        if self._in_title:
            self.title += data
            return

        if self._current_href is not None:
            self._current_link_text.append(data)
            return

        if self._in_content and data.strip():
            self.content_parts.append(data)


def extract_article(html: str, base_url: str = "") -> dict:
    if not html:
        return {"title": "", "content": "", "images": [], "attachments": []}

    parser = _ArticleExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass

    title = parser.title.strip() if parser.title else ""

    content = "".join(parser.content_parts)
    content = re.sub(r"\s+", " ", content).strip()

    images = []
    for img in parser.images:
        src = img["src"]
        if base_url and src:
            src = urljoin(base_url, src)
        images.append({"src": src, "alt": img["alt"]})

    attachments = []
    for att in parser.attachments:
        url = att["url"]
        if base_url and url:
            url = urljoin(base_url, url)
        attachments.append({"name": att["name"], "url": url})

    return {
        "title": title,
        "content": content,
        "images": images,
        "attachments": attachments,
    }


def date_from_text(text) -> datetime | None:
    if text is None:
        return None
    if not isinstance(text, str):
        return None
    if not text.strip():
        return None

    patterns = [
        r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})",
        r"(\d{4})(\d{2})(\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime(year, month, day)
            except (ValueError, IndexError):
                continue

    return None


def date_from_url(url) -> datetime | None:
    if url is None:
        return None
    if not isinstance(url, str):
        return None
    if not url.strip():
        return None

    parsed = urlparse(url)
    path = parsed.path

    patterns = [
        r"/(\d{4})/(\d{2})(\d{2})/",
        r"/(\d{4})[-_](\d{2})[-_](\d{2})/",
        r"/(\d{4})/(\d{1,2})/(\d{1,2})/",
    ]

    for pattern in patterns:
        match = re.search(pattern, path)
        if match:
            try:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime(year, month, day)
            except (ValueError, IndexError):
                continue

    return None


def is_article_link(href, text=None) -> bool:
    if href is None:
        return False
    if not isinstance(href, str):
        return False
    if not href.strip():
        return False

    href_lower = href.lower()

    if href_lower.startswith(("javascript:", "#", "mailto:", "tel:")):
        return False

    article_indicators = [
        "/article", "/news", "/notice", "/announce",
        "/info", "/detail", "/content", "/page.",
        ".psp", ".htm", ".html", ".shtml",
    ]

    has_indicator = any(ind in href_lower for ind in article_indicators)

    if not has_indicator:
        return False

    skip_extensions = [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".ppt", ".pptx", ".zip", ".rar", ".7z",
        ".mp3", ".mp4", ".avi", ".mov",
    ]

    if any(href_lower.endswith(ext) for ext in skip_extensions):
        return False

    if text is not None and isinstance(text, str):
        text = text.strip()
        if len(text) < 4:
            return False

    return True


def is_attachment(href, text=None) -> bool:
    if href is None:
        return False
    if not isinstance(href, str):
        return False
    if not href.strip():
        return False

    href_lower = href.lower()

    attachment_extensions = [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".ppt", ".pptx", ".zip", ".rar", ".7z",
        ".txt", ".csv",
    ]

    if any(href_lower.endswith(ext) for ext in attachment_extensions):
        return True

    if text and isinstance(text, str):
        text_lower = text.lower()
        download_indicators = ["下载", "附件", "附表", "附录", "相关下载"]
        if any(ind in text_lower for ind in download_indicators):
            return True

    return False


def extract_list_links(html: str, base_url: str) -> list[dict]:
    if not html:
        return []

    class _ListLinkExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self._current_href = None
            self._current_text = []
            self._in_li = False
            self.found_links = []

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            if tag == "li":
                self._in_li = True
            if tag == "a" and self._in_li:
                self._current_href = attrs_dict.get("href", "")
                self._current_text = []

        def handle_endtag(self, tag):
            if tag == "a" and self._current_href is not None:
                text = "".join(self._current_text).strip()
                if is_article_link(self._current_href, text):
                    url = urljoin(base_url, self._current_href)
                    self.found_links.append({
                        "url": url,
                        "title": text,
                        "date": None,
                    })
                self._current_href = None
                self._current_text = []
            if tag == "li":
                self._in_li = False

        def handle_data(self, data):
            if self._current_href is not None:
                self._current_text.append(data)

    parser = _ListLinkExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass

    for link in parser.found_links:
        if not link["date"]:
            link["date"] = date_from_url(link["url"])

    return parser.found_links
