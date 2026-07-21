import json
import os
from datetime import datetime
from typing import Optional

from .crawler import Article, CATEGORY_GROUPS


def _format_date(date: Optional[datetime]) -> str:
    if not date:
        return "未知日期"
    return date.strftime("%Y-%m-%d")


def generate_html_report(articles: list[Article], output_path: str) -> str:
    if not articles:
        articles = []

    total_count = len(articles)
    generate_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    articles_json = []
    for a in articles:
        articles_json.append({
            "title": a.title,
            "url": a.url,
            "category": a.category,
            "source": a.source,
            "date": _format_date(a.date),
            "content": a.content,
            "images": a.images,
            "attachments": a.attachments,
        })

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>大连海洋大学官网采集报告</title>
<style>
:root {{
  --primary: #2563eb;
  --primary-hover: #1d4ed8;
  --bg: #f8fafc;
  --card: #ffffff;
  --text: #1e293b;
  --text-secondary: #64748b;
  --border: #e2e8f0;
  --success: #10b981;
  --warning: #f59e0b;
}}

* {{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}}

body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue",
    Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
}}

.container {{
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}}

header {{
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  color: white;
  padding: 48px 24px;
  border-radius: 16px;
  margin-bottom: 32px;
  text-align: center;
}}

header h1 {{
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 8px;
}}

header p {{
  opacity: 0.9;
  font-size: 0.95rem;
}}

.stats {{
  display: flex;
  justify-content: center;
  gap: 48px;
  margin-top: 24px;
}}

.stat-item {{
  text-align: center;
}}

.stat-value {{
  font-size: 2rem;
  font-weight: 700;
}}

.stat-label {{
  font-size: 0.85rem;
  opacity: 0.85;
}}

.toolbar {{
  background: var(--card);
  padding: 16px 20px;
  border-radius: 12px;
  margin-bottom: 24px;
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}

.search-box {{
  flex: 1;
  min-width: 200px;
  position: relative;
}}

.search-box input {{
  width: 100%;
  padding: 10px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s;
}}

.search-box input:focus {{
  border-color: var(--primary);
}}

.sort-select {{
  padding: 10px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 0.9rem;
  background: white;
  cursor: pointer;
  outline: none;
}}

.category-tabs {{
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}}

.tab-btn {{
  padding: 10px 20px;
  border: 1px solid var(--border);
  background: var(--card);
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}}

.tab-btn:hover {{
  border-color: var(--primary);
  color: var(--primary);
}}

.tab-btn.active {{
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}}

.category-section {{
  margin-bottom: 32px;
  display: none;
}}

.category-section.active {{
  display: block;
}}

.category-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}}

.category-header h2 {{
  font-size: 1.25rem;
  font-weight: 600;
}}

.article-count {{
  font-size: 0.85rem;
  color: var(--text-secondary);
  background: #f1f5f9;
  padding: 4px 12px;
  border-radius: 20px;
}}

.article-list {{
  background: var(--card);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}

.article-item {{
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background 0.2s;
}}

.article-item:last-child {{
  border-bottom: none;
}}

.article-item:hover {{
  background: #f8fafc;
}}

.article-item-header {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 6px;
}}

.article-title {{
  font-weight: 500;
  color: var(--text);
  flex: 1;
}}

.article-date {{
  font-size: 0.85rem;
  color: var(--text-secondary);
  white-space: nowrap;
}}

.article-meta {{
  font-size: 0.8rem;
  color: var(--text-secondary);
  display: flex;
  gap: 12px;
}}

.article-source {{
  background: #eff6ff;
  color: #2563eb;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
}}

.article-detail {{
  display: none;
  padding: 20px;
  background: #f8fafc;
  border-top: 1px solid var(--border);
}}

.article-detail.active {{
  display: block;
}}

.article-detail h3 {{
  font-size: 1.1rem;
  margin-bottom: 12px;
}}

.article-detail-content {{
  font-size: 0.9rem;
  line-height: 1.8;
  color: #334155;
}}

.article-detail-content img {{
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 12px 0;
}}

.article-detail-content a {{
  color: var(--primary);
  text-decoration: none;
}}

.article-detail-content a:hover {{
  text-decoration: underline;
}}

.article-images {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-top: 16px;
}}

.article-images img {{
  width: 100%;
  height: 150px;
  object-fit: cover;
  border-radius: 8px;
  cursor: pointer;
  transition: transform 0.2s;
}}

.article-images img:hover {{
  transform: scale(1.02);
}}

.attachments {{
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}}

.attachments h4 {{
  font-size: 0.9rem;
  margin-bottom: 8px;
  color: var(--text-secondary);
}}

.attachment-list {{
  display: flex;
  flex-direction: column;
  gap: 8px;
}}

.attachment-item {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: white;
  border-radius: 6px;
  font-size: 0.85rem;
}}

.attachment-item a {{
  color: var(--primary);
  text-decoration: none;
}}

.attachment-item a:hover {{
  text-decoration: underline;
}}

footer {{
  text-align: center;
  padding: 24px;
  color: var(--text-secondary);
  font-size: 0.85rem;
}}

.empty-state {{
  text-align: center;
  padding: 60px 20px;
  color: var(--text-secondary);
}}

.empty-state-icon {{
  font-size: 3rem;
  margin-bottom: 16px;
}}

@media (max-width: 640px) {{
  .stats {{
    gap: 24px;
  }}
  .stat-value {{
    font-size: 1.5rem;
  }}
  header h1 {{
    font-size: 1.5rem;
  }}
}}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>大连海洋大学官网采集报告</h1>
    <p>生成时间：{generate_time}</p>
    <div class="stats">
      <div class="stat-item">
        <div class="stat-value">{total_count}</div>
        <div class="stat-label">文章总数</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{len(CATEGORY_GROUPS)}</div>
        <div class="stat-label">栏目分类</div>
      </div>
    </div>
  </header>

  <div class="toolbar">
    <div class="search-box">
      <input type="text" id="searchInput" placeholder="搜索文章标题或内容...">
    </div>
    <select class="sort-select" id="sortSelect">
      <option value="date-desc">按时间倒序</option>
      <option value="date-asc">按时间正序</option>
      <option value="title-asc">按标题 A-Z</option>
      <option value="title-desc">按标题 Z-A</option>
    </select>
  </div>

  <div class="category-tabs" id="categoryTabs">
    <button class="tab-btn active" data-category="all">全部文章</button>
"""

    for group_name, _ in CATEGORY_GROUPS:
        html += f'    <button class="tab-btn" data-category="{group_name}">{group_name}</button>\n'

    html += """  </div>

  <div id="articleContainer"></div>

  <footer>
    <p>DLOUWebsiteCrawler - 大连海洋大学官网采集器 | by:yuexuan</p>
  </footer>
</div>

<script>
const articles = """ + json.dumps(articles_json, ensure_ascii=False) + """;

const categoryGroups = """ + json.dumps(dict(CATEGORY_GROUPS), ensure_ascii=False) + """;

let currentCategory = 'all';
let currentSort = 'date-desc';
let currentSearch = '';

function getFilteredArticles() {
  let filtered = [...articles];

  if (currentCategory !== 'all') {
    const sources = categoryGroups[currentCategory] || [];
    filtered = filtered.filter(a => sources.includes(a.source));
  }

  if (currentSearch) {
    const query = currentSearch.toLowerCase();
    filtered = filtered.filter(a =>
      a.title.toLowerCase().includes(query) ||
      a.content.toLowerCase().includes(query)
    );
  }

  switch (currentSort) {
    case 'date-desc':
      filtered.sort((a, b) => {
        if (a.date === '未知日期' && b.date === '未知日期') return 0;
        if (a.date === '未知日期') return 1;
        if (b.date === '未知日期') return -1;
        return new Date(b.date) - new Date(a.date);
      });
      break;
    case 'date-asc':
      filtered.sort((a, b) => {
        if (a.date === '未知日期' && b.date === '未知日期') return 0;
        if (a.date === '未知日期') return 1;
        if (b.date === '未知日期') return -1;
        return new Date(a.date) - new Date(b.date);
      });
      break;
    case 'title-asc':
      filtered.sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'));
      break;
    case 'title-desc':
      filtered.sort((a, b) => b.title.localeCompare(a.title, 'zh-CN'));
      break;
  }

  return filtered;
}

function renderArticles() {
  const container = document.getElementById('articleContainer');
  const filtered = getFilteredArticles();

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📭</div>
        <p>没有找到匹配的文章</p>
      </div>
    `;
    return;
  }

  if (currentCategory === 'all') {
    let html = '';
    for (const [groupName, sources] of Object.entries(categoryGroups)) {
      const groupArticles = filtered.filter(a => sources.includes(a.source));
      if (groupArticles.length === 0) continue;
      html += renderCategorySection(groupName, groupArticles);
    }
    container.innerHTML = html;
  } else {
    container.innerHTML = renderCategorySection(currentCategory, filtered);
  }

  document.querySelectorAll('.article-item').forEach(item => {
    item.addEventListener('click', () => {
      const detail = item.querySelector('.article-detail');
      detail.classList.toggle('active');
    });
  });
}

function renderCategorySection(name, articleList) {
  let html = `
    <div class="category-section active">
      <div class="category-header">
        <h2>${name}</h2>
        <span class="article-count">${articleList.length} 篇</span>
      </div>
      <div class="article-list">
  `;

  for (const article of articleList) {
    html += `
      <div class="article-item">
        <div class="article-item-header">
          <span class="article-title">${escapeHtml(article.title)}</span>
          <span class="article-date">${article.date}</span>
        </div>
        <div class="article-meta">
          <span class="article-source">${escapeHtml(article.source)}</span>
          <span>${article.images ? article.images.length : 0} 图</span>
          <span>${article.attachments ? article.attachments.length : 0} 附件</span>
        </div>
        <div class="article-detail">
          <h3>${escapeHtml(article.title)}</h3>
          <div class="article-detail-content">
            ${article.content || '<p>暂无内容</p>'}
          </div>
    `;

    if (article.images && article.images.length > 0) {
      html += '<div class="article-images">';
      for (const img of article.images) {
        html += `<img src="${img.src}" alt="${escapeHtml(img.alt || '')}" loading="lazy">`;
      }
      html += '</div>';
    }

    if (article.attachments && article.attachments.length > 0) {
      html += `
        <div class="attachments">
          <h4>附件下载</h4>
          <div class="attachment-list">
      `;
      for (const att of article.attachments) {
        html += `
          <div class="attachment-item">
            <span>📎</span>
            <a href="${att.url}" target="_blank">${escapeHtml(att.name)}</a>
          </div>
        `;
      }
      html += '</div></div>';
    }

    html += `
        </div>
      </div>
    `;
  }

  html += '</div></div>';
  return html;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

document.getElementById('searchInput').addEventListener('input', (e) => {
  currentSearch = e.target.value;
  renderArticles();
});

document.getElementById('sortSelect').addEventListener('change', (e) => {
  currentSort = e.target.value;
  renderArticles();
});

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentCategory = btn.dataset.category;
    renderArticles();
  });
});

renderArticles();
</script>
</body>
</html>
"""

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def save_articles_json(articles: list[Article], output_path: str) -> str:
    data = []
    for a in articles:
        data.append({
            "title": a.title,
            "url": a.url,
            "category": a.category,
            "source": a.source,
            "date": _format_date(a.date),
            "content": a.content,
            "images": a.images,
            "attachments": a.attachments,
        })

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path
