"""把采集结果写成人类易读的文本报告 + 机器可读的 JSON。

产出文件（均使用带 BOM 的 UTF-8，Windows 记事本可直接正常查看）：
  · 文章清单.txt  速览：标题、栏目、日期、原文链接
  · 正文合集.txt  精读：每篇文章的完整正文（含元信息）
  · 采集报告.txt  本次采集的概览、文件说明与警告
  · articles.json 机器可读原始数据（供二次处理）
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import Article

# Windows 记事本默认按本地编码解读 .txt；写入带 BOM 的 UTF-8 可保证中文
# 在所有文本查看器里都正常显示，避免出现“打开是乱码”的情况。
_ENCODING = "utf-8-sig"

# 章节分隔线（72 列，约等于常见文本编辑器的舒适宽度）。
_RULE = "=" * 72
_SUBRULE = "-" * 72


# 历史上曾产出这两个文件名；每次运行前清理，避免新旧文件混在一起。
_LEGACY_NAMES = ("articles.csv", "report.md")


def write_outputs(output_dir: Path, articles: list[Article], warnings: list[str]) -> None:
    """把全部采集结果写入 output_dir（目录不存在时自动创建）。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    for legacy in _LEGACY_NAMES:
        legacy_path = output_dir / legacy
        if legacy_path.exists():
            legacy_path.unlink()
    _write_index(output_dir, articles)
    _write_full_text(output_dir, articles)
    _write_report(output_dir, articles, warnings)
    _write_data_json(output_dir, articles, warnings)


def _local_timestamp() -> str:
    """返回带时区偏移的本地时间，例如 '2026-07-21 02:40:00 (+0800)'。"""
    now = datetime.now().astimezone()
    return now.strftime("%Y-%m-%d %H:%M:%S") + f" ({now.strftime('%z')})"


def _group_by_category(articles: list[Article]) -> list[tuple[str, list[Article]]]:
    """按首次出现顺序把文章归入栏目，返回 [(栏目, [文章...]), ...]。"""
    order: list[str] = []
    buckets: dict[str, list[Article]] = {}
    for article in articles:
        buckets.setdefault(article.category, []).append(article)
        if article.category not in order:
            order.append(article.category)
    return [(cat, buckets[cat]) for cat in order]


def _write_index(output_dir: Path, articles: list[Article]) -> None:
    """文章清单：按栏目分组的一页式目录，方便快速浏览。"""
    groups = _group_by_category(articles)
    lines: list[str] = [
        "大连海洋大学官网公开信息 · 文章清单",
        _RULE,
        f"生成时间：{_local_timestamp()}",
        f"文章总数：{len(articles)}",
    ]
    if groups:
        lines.append("栏目分布：" + "  ·  ".join(f"{cat} {len(items)} 篇" for cat, items in groups))
    lines.append("")
    if not articles:
        lines.append("（本次未采集到任何文章）")
    for cat, items in groups:
        lines.append("")
        lines.append(f"【{cat}】（{len(items)} 篇）")
        lines.append(_SUBRULE)
        for index, article in enumerate(items, start=1):
            lines.append(f"[{index}] {article.title}")
            lines.append(f"    日期：{article.published_at or '未识别'} ｜ 原文：{article.url}")
    (output_dir / "文章清单.txt").write_text("\n".join(lines) + "\n", encoding=_ENCODING)


def _write_full_text(output_dir: Path, articles: list[Article]) -> None:
    """正文合集：开头带按栏目分组的目录，正文按栏目归并、彼此用分隔线区分。"""
    if not articles:
        (output_dir / "正文合集.txt").write_text("（本次未采集到任何文章）\n", encoding=_ENCODING)
        return
    groups = _group_by_category(articles)
    toc: list[str] = ["目录（按栏目）", _SUBRULE]
    seen = 0
    for cat, items in groups:
        toc.append(f"{cat}（{len(items)} 篇）")
        for article in items:
            seen += 1
            toc.append(f"  {seen}. {article.title}")
    blocks: list[str] = ["\n".join(toc), ""]
    seen = 0
    for cat, items in groups:
        blocks.append(_RULE + "\n【" + cat + "】")
        for article in items:
            seen += 1
            meta = [
                f"[{seen}] {article.title}",
                f"栏目：{article.category} ｜ 日期：{article.published_at or '未识别'}",
                f"原文：{article.url}",
            ]
            if article.attachments:
                meta.append("附件：")
                meta.extend(f"  · {item.name} —— {item.url}" for item in article.attachments)
            blocks.append("\n".join(meta) + "\n\n" + article.content)
    (output_dir / "正文合集.txt").write_text("\n\n\n".join(blocks) + "\n", encoding=_ENCODING)


def _write_report(output_dir: Path, articles: list[Article], warnings: list[str]) -> None:
    """采集报告：本次概览、栏目分布、产出文件说明与警告记录。"""
    groups = _group_by_category(articles)
    lines: list[str] = [
        "大连海洋大学官网公开信息采集报告",
        _RULE,
        f"生成时间：{_local_timestamp()}",
        f"采集状态：{'成功' if articles else '未获取到文章'}",
        f"文章总数：{len(articles)}",
        f"警告 / 未完整采集：{len(warnings)} 条",
        "",
        "本次产出文件：",
        "  · 文章清单.txt  —— 按栏目分组的文章目录（标题/日期/原文链接）",
        "  · 正文合集.txt  —— 每篇文章完整正文（开头带目录）",
        "  · 采集报告.txt  —— 本说明与警告记录",
        "  · articles.json —— 机器可读的原始数据（含附件下载地址）",
    ]
    if groups:
        lines.append("")
        lines.append("栏目分布：")
        lines.extend(f"  - {cat}：{len(items)} 篇" for cat, items in groups)
    if warnings:
        lines.extend(["", "警告与说明："])
        lines.extend(f"  - {warning}" for warning in warnings)
    else:
        lines.extend(["", "本次采集未出现警告。"])
    (output_dir / "采集报告.txt").write_text("\n".join(lines) + "\n", encoding=_ENCODING)


def _write_data_json(output_dir: Path, articles: list[Article], warnings: list[str]) -> None:
    """articles.json：供程序二次处理的原始数据，含时区信息的采集时间。"""
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "article_count": len(articles),
        "warnings": warnings,
        "articles": [article.to_dict() for article in articles],
    }
    (output_dir / "articles.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding=_ENCODING
    )
