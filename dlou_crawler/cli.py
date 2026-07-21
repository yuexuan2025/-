"""命令行入口：解析参数、组装爬虫并写出结果。"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from .client import HttpClient
from .crawler import DlouCrawler
from .output import write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="采集大连海洋大学官网公开的新闻、通知和附件链接。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  python -m dlou_crawler                    # 默认：每个栏目3页，最多50篇
  python -m dlou_crawler --pages 5 --max-articles 100  # 多采一些
  python -m dlou_crawler --delay 1          # 每次请求间隔1秒（更稳妥）
  python -m dlou_crawler --download-files   # 同时下载附件
        """,
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
        default="DLOUWebsiteCrawler/4.0",
        help="请求标识；请勿伪装成浏览器绕过限制",
    )
    return parser


def _format_duration(seconds: float) -> str:
    """格式化时间，使其更易读。"""
    if seconds < 1:
        return f"{int(seconds * 1000)} 毫秒"
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    minutes = int(seconds // 60)
    seconds %= 60
    if minutes < 60:
        return f"{minutes} 分 {seconds:.1f} 秒"
    hours = int(minutes // 60)
    minutes %= 60
    return f"{hours} 小时 {minutes} 分 {seconds:.1f} 秒"


def main() -> None:
    """解析命令行参数，运行爬虫，并把结果写入 output 目录。"""
    args = build_parser().parse_args()
    
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                   DLOUWebsiteCrawler                          ║")
    print("║              大连海洋大学官网公开信息采集器                     ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    
    if args.pages < 1 or args.max_articles < 1:
        print("❌ 错误：--pages 和 --max-articles 必须大于 0")
        raise SystemExit(1)
    if args.delay < 0 or args.concurrency < 1:
        print("❌ 错误：--delay 不能为负数，--concurrency 不能小于 1")
        raise SystemExit(1)
    
    print(f"📋 采集配置：")
    print(f"   ├─ 每个栏目最多翻 {args.pages} 页")
    print(f"   ├─ 最多采集 {args.max_articles} 篇文章")
    print(f"   ├─ 并发线程数：{args.concurrency}")
    print(f"   ├─ 请求间隔：{'不限速' if args.delay == 0 else f'{args.delay} 秒'}")
    print(f"   ├─ 是否下载附件：{'是' if args.download_files else '否'}")
    print(f"   └─ 结果保存到：{args.output.resolve()}")
    print()
    
    start_time = time.monotonic()
    
    client = HttpClient(args.user_agent, args.delay)
    crawler = DlouCrawler(
        client=client,
        pages_per_source=args.pages,
        max_articles=args.max_articles,
        download_files=args.download_files,
        output_dir=args.output,
        concurrency=args.concurrency,
    )
    
    print("🚀 开始采集...")
    print("────────────────────────────────────────────────────────────────")
    articles = crawler.crawl()
    print("────────────────────────────────────────────────────────────────")
    
    end_time = time.monotonic()
    duration = end_time - start_time
    
    print(f"\n📝 正在保存结果到 {args.output.resolve()} ...")
    write_outputs(args.output, articles, crawler.warnings)
    
    print("\n╔════════════════════════════════════════════════════════════════╗")
    print("║                         采集完成！                             ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    print(f"🎉 共成功采集 {len(articles)} 篇文章")
    print(f"⏱️  总耗时：{_format_duration(duration)}")
    
    if articles:
        avg_time = duration / len(articles)
        print(f"📊 平均每篇文章耗时：{_format_duration(avg_time)}")
    
    if crawler.warnings:
        print(f"\n⚠️  注：有 {len(crawler.warnings)} 条内容因需登录或暂时无法访问而未完整采集")
        print("       详细信息请查看输出文件夹中的「采集报告.txt」")
    
    print(f"\n📂 结果已保存到：{args.output.resolve()}")
    print("\n输出文件说明：")
    print("   ├─ 采集报告.html → 🌟 推荐！浏览器中查看图文报告（支持搜索/折叠）")
    print("   ├─ 文章清单.txt  → 快速浏览所有文章标题和链接")
    print("   ├─ 正文合集.txt  → 逐篇阅读文章完整内容")
    print("   ├─ 采集报告.txt  → 采集统计和警告信息")
    print("   └─ articles.json → 结构化数据（供二次开发）")