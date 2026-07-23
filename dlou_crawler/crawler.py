from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from .client import HttpClient
from .html_tools import extract_list_links, extract_article, date_from_text, date_from_url


@dataclass
class Article:
    title: str = ""
    url: str = ""
    category: str = ""
    source: str = ""
    date: Optional[datetime] = None
    content: str = ""
    images: list = field(default_factory=list)
    attachments: list = field(default_factory=list)


SOURCES = [
    # 学校要闻
    {"name": "学校要闻", "url": "http://news.dlou.edu.cn/1281/list.htm", "category": "学校要闻"},
    {"name": "综合新闻", "url": "http://news.dlou.edu.cn/jcfc/list.htm", "category": "学校要闻"},
    {"name": "校园快讯", "url": "http://news.dlou.edu.cn/1283/list.htm", "category": "学校要闻"},
    {"name": "媒体报道", "url": "http://news.dlou.edu.cn/1288/list.htm", "category": "学校要闻"},
    {"name": "校园喜报", "url": "http://news.dlou.edu.cn/xyxb/list.htm", "category": "学校要闻"},
    # 通知公告
    {"name": "信息公告", "url": "https://www.dlou.edu.cn/89/list.htm", "category": "通知公告"},
    {"name": "学术通知", "url": "https://www.dlou.edu.cn/190/list.htm", "category": "通知公告"},
    # 学生发展
    {"name": "本科生教育", "url": "http://jwch.dlou.edu.cn/8998/list.htm", "category": "学生发展"},
    {"name": "研究生教育", "url": "http://master.dlou.edu.cn/9052/list.htm", "category": "学生发展"},
    {"name": "继续教育", "url": "http://jxjyxy.dlou.edu.cn/", "category": "学生发展"},
    {"name": "研究生就业", "url": "https://master.dlou.edu.cn/9068/list.htm", "category": "学生发展"},
    # 各学院动态
    {"name": "水产与生命学院", "url": "https://life.dlou.edu.cn/907/list.htm", "category": "各学院动态"},
    {"name": "海洋科技与环境学院", "url": "https://hhxy.dlou.edu.cn/xyxw_8738/list.htm", "category": "各学院动态"},
    {"name": "食品科学与工程学院", "url": "https://food.dlou.edu.cn/1680/list.htm", "category": "各学院动态"},
    {"name": "海洋与土木工程学院", "url": "https://tmgc.dlou.edu.cn/3822/list.htm", "category": "各学院动态"},
    {"name": "机械与动力工程学院", "url": "https://jixie.dlou.edu.cn/4323/list.htm", "category": "各学院动态"},
    {"name": "航海与船舶工程学院", "url": "https://sea.dlou.edu.cn/1533/list.htm", "category": "各学院动态"},
    {"name": "信息工程学院", "url": "https://xxgc.dlou.edu.cn/3965/list.htm", "category": "各学院动态"},
    {"name": "经济管理学院", "url": "https://jjgl.dlou.edu.cn/2128/list.htm", "category": "各学院动态"},
    {"name": "海洋法律与人文学院", "url": "https://fxy.dlou.edu.cn/8482/list.htm", "category": "各学院动态"},
    {"name": "外国语学院", "url": "https://wgy.dlou.edu.cn/xwdt/list.htm", "category": "各学院动态"},
    {"name": "中新合作学院", "url": "https://zwhzbx.dlou.edu.cn/xwdt/list.htm", "category": "各学院动态"},
    {"name": "马克思主义学院", "url": "https://mks.dlou.edu.cn/xyxw/list.htm", "category": "各学院动态"},
    {"name": "应用技术学院", "url": "https://gzy.dlou.edu.cn/xyxw/list.htm", "category": "各学院动态"},
]

CATEGORY_GROUPS = [
    ("📰 学校要闻", ["学校要闻", "综合新闻", "校园快讯", "媒体报道", "校园喜报"]),
    ("📢 通知公告", ["信息公告", "学术通知"]),
    ("🎓 学生发展", ["本科生教育", "研究生教育", "继续教育", "研究生就业"]),
    ("🏫 各学院动态", ["水产与生命学院", "海洋科技与环境学院", "食品科学与工程学院",
                  "海洋与土木工程学院", "机械与动力工程学院", "航海与船舶工程学院",
                  "信息工程学院", "经济管理学院", "海洋法律与人文学院",
                  "外国语学院", "中新合作学院", "马克思主义学院",
                  "应用技术学院"]),
]


class Crawler:
    def __init__(
        self,
        max_workers: int = 20,
        max_articles_per_source: int = 15,
        request_interval: float = 0.1,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.client = HttpClient(timeout=15)
        self.max_workers = max_workers
        self.max_articles_per_source = max_articles_per_source
        self.request_interval = request_interval
        self._log = log_callback or (lambda msg: None)
        self.articles: list[Article] = []
        self._stop_flag = False

    def stop(self) -> None:
        self._stop_flag = True

    def _log_msg(self, msg: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log(f"[{timestamp}] {msg}")

    def _fetch_list(self, source: dict) -> list[dict]:
        if self._stop_flag:
            return []

        url = source["url"]
        name = source["name"]

        html = self.client.get(url, retries=2)
        if not html:
            self._log_msg(f"列表页访问失败：{name}")
            return []

        links = extract_list_links(html, url)
        if not links:
            self._log_msg(f"未找到文章链接：{name}")
            return []

        for link in links:
            if not link["date"]:
                link["date"] = date_from_url(link["url"])

        return links[:self.max_articles_per_source]

    def _fetch_article(self, link: dict, source: dict) -> Optional[Article]:
        if self._stop_flag:
            return None

        url = link["url"]
        title = link.get("title", "")
        date = link.get("date")

        html = self.client.get(url, retries=2)
        if not html:
            return None

        extracted = extract_article(html, url)

        article_title = extracted["title"] or title
        article_date = date
        if not article_date and extracted["content"]:
            article_date = date_from_text(extracted["content"])

        article = Article(
            title=article_title,
            url=url,
            category=source["category"],
            source=source["name"],
            date=article_date,
            content=extracted["content"],
            images=extracted["images"],
            attachments=extracted["attachments"],
        )

        return article

    def crawl(self) -> list[Article]:
        self._stop_flag = False
        self.articles = []

        self._log_msg("开始采集...")
        self._log_msg(f"共 {len(SOURCES)} 个栏目，并发线程 {self.max_workers}")

        all_links: list[tuple[dict, dict]] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_source = {}
            for source in SOURCES:
                future = executor.submit(self._fetch_list, source)
                future_to_source[future] = source

            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    links = future.result()
                    if links:
                        self._log_msg(f"{source['name']}：找到 {len(links)} 篇文章")
                        for link in links:
                            all_links.append((link, source))
                except Exception as e:
                    self._log_msg(f"{source['name']}：列表页异常 - {e}")

        if not all_links:
            self._log_msg("未找到任何文章链接")
            return []

        self._log_msg(f"共找到 {len(all_links)} 篇文章，开始采集正文...")

        success_count = 0
        fail_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_link = {}
            for link, source in all_links:
                future = executor.submit(self._fetch_article, link, source)
                future_to_link[future] = (link, source)

            for future in as_completed(future_to_link):
                if self._stop_flag:
                    break

                link, source = future_to_link[future]
                try:
                    article = future.result()
                    if article and article.title:
                        self.articles.append(article)
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    fail_count += 1
                    self._log_msg(f"采集失败：{e}")

        self.articles.sort(
            key=lambda a: a.date or datetime.min,
            reverse=True,
        )

        self._log_msg(f"采集完成：成功 {success_count} 篇，失败 {fail_count} 篇")
        return self.articles
