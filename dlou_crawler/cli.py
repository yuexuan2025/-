"""命令行入口：解析参数、组装爬虫并写出结果。"""

from __future__ import annotations

import argparse
from pathlib import Path

from .client import HttpClient
from .crawler import DlouCrawler
from .output import write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="采集大连海洋大学官网公开的新闻、通知和附件链接。"
    )
    parser.add_argument("--pages", type=int, default=3, help="每个栏目最多采集的列表页数（默认 3）")
    parser.add_argument("--max-articles", type=int, default=50, help="最多采集文章数（默认 50）")
    parser.add_argument("--delay", type=float, default=0.0, help="两次请求的最短间隔，单位秒（默认 0，即不限速）")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="并发拉取正文的最大线程数（默认 4，站点慢可调大）",
    )
    parser.add_argument("--output", type=Path, default=Path("output"), help="结果保存目录")
    parser.add_argument("--download-files", action="store_true", help="下载文章中的公开附件")
    parser.add_argument(
        "--user-agent",
        default="DlouStudentCrawler/0.2.0 (educational use)",
        help="请求标识；请勿伪装成浏览器绕过限制",
    )
    return parser


def main() -> None:
    """解析命令行参数，运行爬虫，并把结果写入 output 目录。"""
    args = build_parser().parse_args()
    print("大连海洋大学官网公开信息采集器 · by yuexuan")
    print("=" * 60)
    if args.pages < 1 or args.max_articles < 1:
        raise SystemExit("--pages 和 --max-articles 必须大于 0。")
    if args.delay < 0 or args.concurrency < 1:
        raise SystemExit("--delay 不能为负数，--concurrency 不能小于 1。")
    client = HttpClient(args.user_agent, args.delay)
    crawler = DlouCrawler(
        client=client,
        pages_per_source=args.pages,
        max_articles=args.max_articles,
        download_files=args.download_files,
        output_dir=args.output,
        concurrency=args.concurrency,
    )
    articles = crawler.crawl()
    write_outputs(args.output, articles, crawler.warnings)
    print(f"\n采集完成，共读取 {len(articles)} 篇文章。")
    print(f"结果已保存到：{args.output.resolve()}")
    if crawler.warnings:
        print(f"注：有 {len(crawler.warnings)} 条内容因需登录或暂时无法访问而未完整采集，详见 采集报告.txt。")
