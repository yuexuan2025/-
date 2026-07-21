"""把采集结果写成人类易读的文本报告 + HTML 报告 + 机器可读的 JSON。

产出文件（均使用带 BOM 的 UTF-8，Windows 记事本可直接正常查看）：
  · 文章清单.txt  速览：标题、栏目、日期、原文链接
  · 正文合集.txt  精读：每篇文章的完整正文（含元信息）
  · 采集报告.txt  本次采集的概览、文件说明与警告
  · 采集报告.html 浏览器中查看的图文报告（推荐）
  · articles.json 机器可读原始数据（供二次处理）
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import Article

_ENCODING = "utf-8-sig"

_RULE_DOUBLE = "═" * 80
_RULE_SINGLE = "─" * 80
_RULE_THIN = "┄" * 80


def write_outputs(output_dir: Path, articles: list[Article], warnings: list[str]) -> None:
    """把全部采集结果写入 output_dir（目录不存在时自动创建）。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_index(output_dir, articles)
    _write_full_text(output_dir, articles)
    _write_report(output_dir, articles, warnings)
    _write_html_report(output_dir, articles, warnings)
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
        "╔══════════════════════════════════════════════════════════════════════════════════════╗",
        "║                           大连海洋大学官网公开信息 · 文章清单                         ║",
        "╚══════════════════════════════════════════════════════════════════════════════════════╝",
        "",
        f"📅 生成时间：{_local_timestamp()}",
        f"📊 文章总数：{len(articles)} 篇",
    ]
    if groups:
        lines.append(f"📁 栏目分布：{'  |  '.join(f'{cat} {len(items)}篇' for cat, items in groups)}")
    lines.append("")
    lines.append(_RULE_SINGLE)
    lines.append("")
    
    if not articles:
        lines.append("    （本次未采集到任何文章）")
        lines.append("")
    else:
        for cat, items in groups:
            lines.append(f"【{cat}】共 {len(items)} 篇")
            lines.append(_RULE_THIN)
            for index, article in enumerate(items, start=1):
                title_display = article.title if len(article.title) <= 50 else article.title[:49] + "…"
                lines.append(f"  [{index:02d}] {title_display}")
                lines.append(f"     ├─ 日期：{article.published_at or '未识别'}")
                lines.append(f"     └─ 链接：{article.url}")
            lines.append("")
    
    lines.append(_RULE_SINGLE)
    lines.append("")
    lines.append("📖 使用提示：")
    lines.append("   · 按 Ctrl+F 在本文件中搜索标题关键词")
    lines.append("   · 复制链接到浏览器可查看原文")
    lines.append("   · 完整正文请查看「正文合集.txt」")
    
    (output_dir / "文章清单.txt").write_text("\n".join(lines) + "\n", encoding=_ENCODING)


def _write_full_text(output_dir: Path, articles: list[Article]) -> None:
    """正文合集：开头带按栏目分组的目录，正文按栏目归并、彼此用分隔线区分。"""
    if not articles:
        (output_dir / "正文合集.txt").write_text("（本次未采集到任何文章）\n", encoding=_ENCODING)
        return
    
    groups = _group_by_category(articles)
    
    toc: list[str] = [
        "╔══════════════════════════════════════════════════════════════════════════════════════╗",
        "║                           大连海洋大学官网公开信息 · 正文合集                         ║",
        "╚══════════════════════════════════════════════════════════════════════════════════════╝",
        "",
        "📋 目录（按栏目）",
        _RULE_SINGLE,
    ]
    seen = 0
    for cat, items in groups:
        toc.append(f"")
        toc.append(f"【{cat}】（{len(items)} 篇）")
        for article in items:
            seen += 1
            title_display = article.title if len(article.title) <= 55 else article.title[:54] + "…"
            toc.append(f"  {seen:02d}. {title_display}")
    
    toc.append("")
    toc.append(_RULE_DOUBLE)
    toc.append("")
    toc.append("🔍 阅读提示：")
    toc.append("   · 使用目录可快速定位到感兴趣的文章")
    toc.append("   · 每篇文章之间有分隔线区分")
    toc.append("   · 附件链接可直接复制到浏览器下载")
    toc.append("")
    toc.append(_RULE_DOUBLE)
    toc.append("")
    
    blocks: list[str] = ["\n".join(toc)]
    seen = 0
    
    for cat, items in groups:
        blocks.append(f"\n\n【{cat}】\n{_RULE_SINGLE}\n")
        for article in items:
            seen += 1
            meta_lines = [
                f"╔══════════════════════════════════════════════════════════════════════════════════════╗",
                f"║ [{seen:02d}] {article.title}",
                f"╠══════════════════════════════════════════════════════════════════════════════════════╣",
                f"║ 栏目：{article.category}  │  日期：{article.published_at or '未识别'}",
                f"║ 原文：{article.url}",
                f"╚══════════════════════════════════════════════════════════════════════════════════════╝",
            ]
            if article.attachments:
                meta_lines.append("")
                meta_lines.append("📎 附件列表：")
                for idx, item in enumerate(article.attachments, start=1):
                    meta_lines.append(f"   [{idx}] {item.name}")
                    meta_lines.append(f"      {item.url}")
                    if item.local_path:
                        meta_lines.append(f"      已下载：{item.local_path}")
            
            meta_lines.append("")
            meta_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            meta_lines.append("")
            meta_lines.append(article.content)
            meta_lines.append("")
            meta_lines.append(_RULE_THIN)
            meta_lines.append("")
            
            blocks.append("\n".join(meta_lines))
    
    (output_dir / "正文合集.txt").write_text("\n".join(blocks) + "\n", encoding=_ENCODING)


def _write_report(output_dir: Path, articles: list[Article], warnings: list[str]) -> None:
    """采集报告：本次概览、栏目分布、产出文件说明与警告记录。"""
    groups = _group_by_category(articles)
    
    lines: list[str] = [
        "╔══════════════════════════════════════════════════════════════════════════════════════╗",
        "║                           大连海洋大学官网公开信息 · 采集报告                         ║",
        "╚══════════════════════════════════════════════════════════════════════════════════════╝",
        "",
        f"📅 生成时间：{_local_timestamp()}",
        f"✅ 采集状态：{'成功' if articles else '未获取到文章'}",
        f"📊 文章总数：{len(articles)} 篇",
        f"⚠️  警告/未完整采集：{len(warnings)} 条",
        "",
        _RULE_SINGLE,
        "",
        "📁 本次产出文件说明：",
        "   ├─ 采集报告.html ────────── 🌟推荐！浏览器中查看图文报告（支持搜索/折叠），最直观",
        "   ├─ 文章清单.txt  ────────── 按栏目分组的文章目录（标题/日期/原文链接），便于快速浏览",
        "   ├─ 正文合集.txt  ────────── 每篇文章的完整正文（开头带目录），便于逐篇阅读",
        "   ├─ 采集报告.txt  ────────── 本说明与警告记录，了解采集情况",
        "   └─ articles.json ────────── 机器可读的原始数据（含附件下载地址），供二次开发使用",
    ]
    
    if groups:
        lines.append("")
        lines.append("📈 栏目分布统计：")
        total = len(articles)
        for cat, items in groups:
            percentage = (len(items) / total * 100) if total > 0 else 0
            lines.append(f"   ├─ {cat}：{len(items)} 篇  ({percentage:.1f}%)")
        lines.append(f"   └─ 合计：{total} 篇")
    
    if warnings:
        lines.append("")
        lines.append("⚠️  警告与说明（以下文章未完整采集）：")
        lines.append(_RULE_THIN)
        for idx, warning in enumerate(warnings, start=1):
            lines.append(f"   [{idx}] {warning}")
        lines.append("")
        lines.append("💡 提示：")
        lines.append("   · 需要登录的文章：请通过「原文链接」在学校官网登录后查看")
        lines.append("   · 暂时无法访问的文章：可能是网络问题或页面已删除，请稍后重试")
    else:
        lines.append("")
        lines.append("🎉 本次采集未出现任何警告，所有文章均已完整采集！")
    
    lines.append("")
    lines.append(_RULE_SINGLE)
    lines.append("")
    lines.append("💬 常见问题：")
    lines.append("   Q：打开文件是乱码怎么办？")
    lines.append("   A：文件采用 UTF-8 编码，请使用记事本、VS Code 等支持 UTF-8 的编辑器打开")
    lines.append("")
    lines.append("   Q：为什么有的文章没有正文？")
    lines.append("   A：可能是文章需要登录查看，或网站暂时无法访问，请通过原文链接在官网查看")
    lines.append("")
    lines.append("   Q：如何只采集新文章？")
    lines.append("   A：目前版本会覆盖旧结果。如需保留历史记录，请先复制 output 文件夹并重命名")
    
    (output_dir / "采集报告.txt").write_text("\n".join(lines) + "\n", encoding=_ENCODING)


def _write_data_json(output_dir: Path, articles: list[Article], warnings: list[str]) -> None:
    """articles.json：供程序二次处理的原始数据，含时区信息的采集时间。"""
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "article_count": len(articles),
        "warnings_count": len(warnings),
        "warnings": warnings,
        "articles": [article.to_dict() for article in articles],
    }
    (output_dir / "articles.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding=_ENCODING
    )


def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符。"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _write_html_report(output_dir: Path, articles: list[Article], warnings: list[str]) -> None:
    """生成精美的 HTML 报告，支持搜索、排序和折叠。"""
    groups = _group_by_category(articles)
    total = len(articles)

    # 文章数据（JSON 格式传给前端）
    articles_data = []
    for idx, article in enumerate(articles, start=1):
        atts = [{"name": a.name, "url": a.url} for a in article.attachments]
        articles_data.append({
            "idx": idx,
            "title": article.title,
            "category": article.category,
            "published_at": article.published_at or "",
            "url": article.url,
            "content": article.content,
            "attachments": atts,
        })
    articles_json = json.dumps(articles_data, ensure_ascii=False)

    # 栏目列表
    categories = sorted(set(a.category for a in articles))
    category_options = "".join(f'<option value="{_escape_html(c)}">{_escape_html(c)}</option>' for c in categories)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DLOUWebsiteCrawler · 采集报告</title>
<style>
:root {{
    --bg: #f8fafc;
    --surface: #ffffff;
    --surface-hover: #f1f5f9;
    --border: #e2e8f0;
    --text: #0f172a;
    --text-secondary: #64748b;
    --text-tertiary: #94a3b8;
    --primary: #3b82f6;
    --primary-dark: #2563eb;
    --primary-light: #dbeafe;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --purple: #8b5cf6;
    --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
    --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
    --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
    --radius: 12px;
    --radius-sm: 8px;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei",
                 "PingFang SC", "Hiragino Sans GB", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
}}
.container {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 20px 40px;
}}
.hero {{
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: var(--radius);
    padding: 36px 32px;
    margin-bottom: 24px;
    box-shadow: var(--shadow-md);
    position: relative;
    overflow: hidden;
}}
.hero::before {{
    content: "";
    position: absolute;
    top: -50%; right: -20%;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%);
    border-radius: 50%;
}}
.hero h1 {{
    font-size: 26px;
    font-weight: 700;
    margin-bottom: 8px;
    position: relative;
}}
.hero .subtitle {{
    opacity: 0.9;
    font-size: 14px;
    position: relative;
}}
.hero .meta-row {{
    display: flex;
    gap: 24px;
    margin-top: 16px;
    position: relative;
}}
.hero .meta-item {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    opacity: 0.95;
}}
.hero .meta-item .dot {{
    width: 6px; height: 6px;
    border-radius: 50%;
    background: rgba(255,255,255,0.5);
}}
.stats {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
}}
.stat-card {{
    background: var(--surface);
    padding: 20px;
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--border);
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
}}
.stat-card:hover {{
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}}
.stat-card::before {{
    content: "";
    position: absolute;
    top: 0; left: 0;
    width: 4px; height: 100%;
    background: var(--primary);
}}
.stat-card.success::before {{ background: var(--success); }}
.stat-card.warning::before {{ background: var(--warning); }}
.stat-card.purple::before {{ background: var(--purple); }}
.stat-number {{
    font-size: 28px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.2;
    margin-bottom: 4px;
}}
.stat-label {{
    color: var(--text-secondary);
    font-size: 13px;
}}
.toolbar {{
    background: var(--surface);
    border-radius: var(--radius-sm);
    padding: 16px;
    margin-bottom: 20px;
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--border);
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: center;
}}
.search-wrapper {{
    flex: 1;
    min-width: 200px;
    position: relative;
}}
.search-wrapper input {{
    width: 100%;
    padding: 10px 14px 10px 38px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-size: 14px;
    outline: none;
    transition: all 0.2s;
    background: var(--bg);
    color: var(--text);
}}
.search-wrapper input:focus {{
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
    background: var(--surface);
}}
.search-wrapper .icon {{
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-tertiary);
    font-size: 14px;
}}
.sort-group {{
    display: flex;
    gap: 6px;
    align-items: center;
}}
.sort-group label {{
    font-size: 13px;
    color: var(--text-secondary);
}}
.sort-group select {{
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-size: 13px;
    background: var(--bg);
    color: var(--text);
    cursor: pointer;
    outline: none;
    transition: border-color 0.2s;
}}
.sort-group select:focus {{
    border-color: var(--primary);
}}
.filter-group {{
    display: flex;
    gap: 6px;
    align-items: center;
}}
.filter-group label {{
    font-size: 13px;
    color: var(--text-secondary);
}}
.filter-group select {{
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-size: 13px;
    background: var(--bg);
    color: var(--text);
    cursor: pointer;
    outline: none;
    transition: border-color 0.2s;
}}
.filter-group select:focus {{
    border-color: var(--primary);
}}
.warnings {{
    background: #fff1f2;
    border: 1px solid #fecdd3;
    border-radius: var(--radius-sm);
    padding: 16px 20px;
    margin-bottom: 20px;
}}
.warnings h3 {{
    color: #be123c;
    font-size: 14px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.warnings ul {{
    margin-left: 24px;
    color: #9f1239;
    font-size: 13px;
}}
.warnings li {{
    margin-bottom: 4px;
}}
.article-card {{
    background: var(--surface);
    border-radius: var(--radius-sm);
    margin-bottom: 8px;
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--border);
    overflow: hidden;
    transition: all 0.2s ease;
}}
.article-card:hover {{
    box-shadow: var(--shadow);
    border-color: #cbd5e1;
}}
.article-header {{
    padding: 16px 20px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 14px;
    transition: background 0.15s;
    user-select: none;
}}
.article-header:hover {{
    background: var(--surface-hover);
}}
.article-index {{
    background: var(--primary-light);
    color: var(--primary-dark);
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    min-width: 42px;
    text-align: center;
    flex-shrink: 0;
}}
.article-title {{
    flex: 1;
    font-weight: 500;
    font-size: 15px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}
.article-meta {{
    display: flex;
    gap: 12px;
    align-items: center;
    flex-shrink: 0;
}}
.article-category {{
    background: #f0fdf4;
    color: #15803d;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
}}
.article-date {{
    color: var(--text-tertiary);
    font-size: 13px;
    min-width: 85px;
    text-align: right;
}}
.toggle-icon {{
    color: var(--text-tertiary);
    transition: transform 0.25s ease;
    font-size: 12px;
    flex-shrink: 0;
}}
.article-card.expanded .toggle-icon {{
    transform: rotate(180deg);
}}
.article-body {{
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.3s ease;
    padding: 0 20px;
    border-top: 0px solid var(--border);
}}
.article-card.expanded .article-body {{
    max-height: 3000px;
    padding: 0 20px 20px;
    border-top: 1px solid var(--border);
}}
.article-info {{
    padding: 16px 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 14px;
}}
.article-info p {{
    color: var(--text-secondary);
}}
.article-info strong {{
    color: var(--text);
    font-weight: 500;
}}
.article-info a {{
    color: var(--primary);
    text-decoration: none;
    word-break: break-all;
}}
.article-info a:hover {{
    text-decoration: underline;
}}
.attachments {{
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 6px;
    padding: 12px 14px;
    margin-bottom: 16px;
}}
.attachments strong {{
    color: #92400e;
    font-size: 13px;
    display: block;
    margin-bottom: 6px;
}}
.attachments ul {{
    list-style: none;
}}
.attachments li {{
    margin-bottom: 4px;
}}
.attachments a {{
    color: #b45309;
    font-size: 13px;
    text-decoration: none;
}}
.attachments a:hover {{
    text-decoration: underline;
}}
.article-content {{
    white-space: pre-wrap;
    font-size: 14px;
    color: #334155;
    line-height: 1.75;
    border-top: 1px dashed var(--border);
    padding-top: 16px;
    word-wrap: break-word;
}}
.empty {{
    text-align: center;
    padding: 60px 20px;
    color: var(--text-tertiary);
    font-size: 14px;
}}
.footer {{
    text-align: center;
    padding: 32px 20px 0;
    color: var(--text-tertiary);
    font-size: 13px;
}}
@media (max-width: 640px) {{
    .hero {{ padding: 24px 20px; }}
    .hero h1 {{ font-size: 20px; }}
    .article-meta {{ display: none; }}
    .toolbar {{ flex-direction: column; align-items: stretch; }}
    .sort-group, .filter-group {{ justify-content: space-between; }}
    .sort-group select, .filter-group select {{ flex: 1; }}
}}
</style>
</head>
<body>
<div class="container">
    <div class="hero">
        <h1>⚓ DLOUWebsiteCrawler · 采集报告</h1>
        <div class="subtitle">官网公开信息采集结果</div>
        <div class="meta-row">
            <div class="meta-item"><span class="dot"></span>生成时间：{_escape_html(_local_timestamp())}</div>
            <div class="meta-item"><span class="dot"></span>共 {total} 篇文章</div>
        </div>
    </div>

    <div class="stats" id="statsGrid">
        <div class="stat-card">
            <div class="stat-number" id="statTotal">{total}</div>
            <div class="stat-label">文章总数</div>
        </div>
        <div class="stat-card success">
            <div class="stat-number" id="statSuccess">{total}</div>
            <div class="stat-label">成功采集</div>
        </div>
        <div class="stat-card warning">
            <div class="stat-number" id="statWarn">{len(warnings)}</div>
            <div class="stat-label">警告数</div>
        </div>
        <div class="stat-card purple">
            <div class="stat-number" id="statCat">{len(categories)}</div>
            <div class="stat-label">栏目数</div>
        </div>
    </div>

    <div class="toolbar">
        <div class="search-wrapper">
            <span class="icon">🔍</span>
            <input type="text" id="searchInput" placeholder="搜索文章标题...">
        </div>
        <div class="sort-group">
            <label>排序：</label>
            <select id="sortSelect" onchange="renderArticles()">
                <option value="default">默认顺序</option>
                <option value="date_desc">📅 时间（新→旧）</option>
                <option value="date_asc">📅 时间（旧→新）</option>
                <option value="title_asc">🔤 标题（A→Z）</option>
                <option value="title_desc">🔤 标题（Z→A）</option>
                <option value="category_asc">📁 栏目（A→Z）</option>
            </select>
        </div>
        <div class="filter-group">
            <label>栏目：</label>
            <select id="categoryFilter" onchange="renderArticles()">
                <option value="">全部栏目</option>
                {category_options}
            </select>
        </div>
    </div>

    <div id="warningsArea"></div>
    <div id="articleList"></div>

    <div class="footer">
        由 DLOUWebsiteCrawler 生成
    </div>
</div>

<script>
const allArticles = {articles_json};
let currentSort = 'default';
let currentFilter = '';
let currentSearch = '';

function initWarnings() {{
    const warnings = {json.dumps(warnings, ensure_ascii=False)};
    const area = document.getElementById('warningsArea');
    if (warnings.length === 0) {{
        area.innerHTML = '';
        return;
    }}
    let html = '<div class="warnings"><h3>⚠️ 警告信息</h3><ul>';
    warnings.forEach(w => {{ html += '<li>' + escapeHtml(w) + '</li>'; }});
    html += '</ul></div>';
    area.innerHTML = html;
}}

function escapeHtml(str) {{
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}}

function getFilteredArticles() {{
    let result = [...allArticles];

    if (currentSearch) {{
        const kw = currentSearch.toLowerCase();
        result = result.filter(a => a.title.toLowerCase().includes(kw));
    }}

    if (currentFilter) {{
        result = result.filter(a => a.category === currentFilter);
    }}

    switch (currentSort) {{
        case 'date_desc':
            result.sort((a, b) => (b.published_at || '').localeCompare(a.published_at || ''));
            break;
        case 'date_asc':
            result.sort((a, b) => (a.published_at || '').localeCompare(b.published_at || ''));
            break;
        case 'title_asc':
            result.sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'));
            break;
        case 'title_desc':
            result.sort((a, b) => b.title.localeCompare(a.title, 'zh-CN'));
            break;
        case 'category_asc':
            result.sort((a, b) => a.category.localeCompare(b.category, 'zh-CN'));
            break;
    }}
    return result;
}}

function renderArticles() {{
    const list = document.getElementById('articleList');
    const articles = getFilteredArticles();

    if (articles.length === 0) {{
        list.innerHTML = '<div class="empty">没有找到匹配的文章</div>';
        return;
    }}

    let html = '';
    articles.forEach((a, i) => {{
        const attHtml = a.attachments.length > 0
            ? '<div class="attachments"><strong>📎 附件列表</strong><ul>'
              + a.attachments.map(att =>
                  '<li><a href="' + escapeHtml(att.url) + '" target="_blank">'
                  + escapeHtml(att.name) + '</a></li>'
                ).join('')
              + '</ul></div>'
            : '';

        html += `
            <div class="article-card" data-idx="${{a.idx}}">
                <div class="article-header" onclick="toggleArticle(this)">
                    <span class="article-index">${{i+1}}</span>
                    <span class="article-title">${{escapeHtml(a.title)}}</span>
                    <span class="article-meta">
                        <span class="article-category">${{escapeHtml(a.category)}}</span>
                        <span class="article-date">${{escapeHtml(a.published_at || '日期未知')}}</span>
                    </span>
                    <span class="toggle-icon">▼</span>
                </div>
                <div class="article-body">
                    <div class="article-info">
                        <p><strong>栏目：</strong>${{escapeHtml(a.category)}}</p>
                        <p><strong>日期：</strong>${{escapeHtml(a.published_at || '未识别')}}</p>
                        <p><strong>原文链接：</strong><a href="${{escapeHtml(a.url)}}" target="_blank">${{escapeHtml(a.url)}}</a></p>
                    </div>
                    ${{attHtml}}
                    <div class="article-content">${{escapeHtml(a.content)}}</div>
                </div>
            </div>`;
    }});

    list.innerHTML = html;
}}

function toggleArticle(header) {{
    const card = header.parentElement;
    card.classList.toggle('expanded');
}}

document.getElementById('searchInput').addEventListener('input', (e) => {{
    currentSearch = e.target.value.trim();
    renderArticles();
}});

document.getElementById('sortSelect').addEventListener('change', (e) => {{
    currentSort = e.target.value;
    renderArticles();
}});

document.getElementById('categoryFilter').addEventListener('change', (e) => {{
    currentFilter = e.target.value;
    renderArticles();
}});

initWarnings();
renderArticles();
</script>
</body>
</html>"""

    (output_dir / "采集报告.html").write_text(html, encoding=_ENCODING)