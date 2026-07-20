import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from dlou_crawler.client import HttpClient
from dlou_crawler.crawler import DlouCrawler
from dlou_crawler.html_tools import date_from_text, date_from_url, is_article_link, parse_page


class HtmlToolsTests(unittest.TestCase):
    def test_extracts_article_content_and_absolute_links(self) -> None:
        html = """
        <html><head><title>示例通知</title></head><body>
        <h1>暑假安排</h1><div id='vsb_content'>发布于 2026-07-01。请查看附件。</div>
        <a href='/2026/0701/c89a100/page.htm'>关于暑假的通知</a>
        <a href='/files/notice.pdf'>附件 PDF</a></body></html>
        """
        page = parse_page(html, "https://www.dlou.edu.cn/89/list.htm")

        self.assertEqual(page.headings, ["暑假安排"])
        self.assertIn("发布于 2026-07-01", page.text)
        self.assertEqual(page.links[0].url, "https://www.dlou.edu.cn/2026/0701/c89a100/page.htm")
        self.assertTrue(is_article_link(page.links[0]))

    def test_date_and_domain_guard(self) -> None:
        self.assertEqual(date_from_text("日期：2026/07/19"), "2026-07-19")
        self.assertEqual(date_from_text("发布于2026年7月19日"), "2026-07-19")
        self.assertEqual(date_from_url("https://news.dlou.edu.cn/2026/0717/c1a2/page.htm"), "2026-07-17")
        self.assertTrue(DlouCrawler.is_allowed("https://news.dlou.edu.cn/info/1030/1.htm"))
        self.assertTrue(DlouCrawler.is_allowed("http://news.dlou.edu.cn/info/1030/1.htm"))
        self.assertFalse(DlouCrawler.is_allowed("https://example.com/info/1030/1.htm"))
