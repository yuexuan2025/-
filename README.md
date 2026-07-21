# <div align="center">🌊 DLOUWebsiteCrawler</div>

<div align="center">

  **大连海洋大学官网采集器**

  [![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python&logoColor=white)](https://www.python.org/)
  [![Platform](https://img.shields.io/badge/平台-Windows-green.svg)](#)
  [![License](https://img.shields.io/badge/许可-MIT-yellow.svg)](#)
  [![Release](https://img.shields.io/github/v/release/yuexuan2025/DLOUWebsiteCrawler?label=最新版本)](https://github.com/yuexuan2025/DLOUWebsiteCrawler/releases)
  [![Size](https://img.shields.io/badge/EXE大小-11MB-orange)](#)

</div>

---

## 📖 项目简介

一个快速采集大连海洋大学官网公开信息的工具。支持学校要闻、通知公告、学生发展、各学院动态等 **30+ 栏目** 的并发采集，自动生成美观的 HTML 报告。

> 仅用于学习和研究目的，请合理使用。

---

## ✨ 功能亮点

| 功能 | 说明 |
|------|------|
| 📰 **多栏目采集** | 覆盖学校要闻、通知公告、学生发展、各学院动态等 30+ 栏目 |
| ⚡ **高效并发** | 20 线程并发采集，速度快 |
| 🎨 **现代界面** | 单页滚动式 GUI，简洁美观 |
| 📊 **HTML 报告** | 交互式报告，支持搜索、排序、分类筛选 |
| 🖼️ **图片识别** | 自动识别文章中的图片和附件 |
| 🔒 **安全可控** | 仅访问 dlou.edu.cn 域名，所有数据保存在本地 |

---

## 🚀 快速开始

### 下载运行

从 [Releases](https://github.com/yuexuan2025/DLOUWebsiteCrawler/releases) 下载最新版 `DLOUWebsiteCrawler.exe`，双击即可运行。

### 操作步骤

```
1️⃣ 启动程序 → 2️⃣ 点击开始采集 → 3️⃣ 查看结果 → 4️⃣ 打开HTML报告
```

---

## 📚 采集范围

### 📰 学校要闻
- 学校要闻、综合新闻、校园快讯、媒体报道、校园喜报

### 📢 通知公告
- 信息公告、学术海大、今日活动、下载专区

### 🎓 学生发展
- 本科生教育、研究生教育、本科生招生、研究生招生
- 本科生就业、研究生就业、继续教育

### 🏫 各学院动态

| 学院 | 学院 | 学院 |
|------|------|------|
| 水产与生命学院 | 海洋科技与环境学院 | 食品科学与工程学院 |
| 海洋与土木工程学院 | 机械与动力工程学院 | 航海与船舶工程学院 |
| 信息工程学院 | 经济管理学院 | 海洋法律与人文学院 |
| 外国语学院 | 中新合作学院 | 马克思主义学院 |
| 体育与教育学院 | 应用技术学院 | - |

---

## 📁 输出文件

采集完成后，`output` 目录下生成：

| 文件 | 格式 | 说明 |
|------|------|------|
| 采集报告.html | HTML | 交互式报告，支持搜索/排序/筛选 |
| articles.json | JSON | 结构化数据，方便二次开发 |

---

## 🛠️ 技术栈

- **语言**：Python 3.x
- **界面**：Tkinter
- **网络**：标准库 HTTP 客户端
- **并发**：线程池 + 智能重定向
- **打包**：PyInstaller 单文件

---

## 📋 安全说明

- ✅ 仅访问 `dlou.edu.cn` 及其子域名
- ✅ 不收集任何用户个人数据
- ✅ 所有输出文件保存在本地
- ✅ 无后台运行、无网络上传

---

<div align="center">

**by:yuexuan**

[⬆️ 回到顶部](#div-center-dlouwebsitecrawler)

</div>
