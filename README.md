# DLOUWebsiteCrawler

大连海洋大学官网采集器

[![最新版本](https://img.shields.io/github/v/release/yuexuan2025/DLOUWebsiteCrawler?label=最新版本)](https://github.com/yuexuan2025/DLOUWebsiteCrawler/releases)
[![平台](https://img.shields.io/badge/平台-Windows-green)](#)
[![大小](https://img.shields.io/badge/EXE-11MB-orange)](#)
[![语言](https://img.shields.io/badge/语言-Python-blue)](#)
[![许可](https://img.shields.io/badge/许可-MIT-yellow)](#)

---

## 项目简介

快速采集大连海洋大学官网公开信息的工具，支持学校要闻、通知公告、学生发展、各学院动态等 30+ 栏目的并发采集，自动生成 HTML 报告。

---

## 功能特点

- **多栏目采集**：学校要闻、通知公告、学生发展、各学院动态
- **高效并发**：20 线程并发采集，速度快
- **图形界面**：操作简单，开箱即用
- **HTML 报告**：支持搜索、排序、分类筛选
- **图片附件**：自动识别文章中的图片和附件
- **本地安全**：仅访问 dlou.edu.cn 域名，数据保存在本地

---

## 快速开始

1. 从 [Releases](https://github.com/yuexuan2025/DLOUWebsiteCrawler/releases) 下载 `DLOUWebsiteCrawler.exe`
2. 双击运行
3. 点击「开始采集」
4. 查看结果，可在浏览器中打开 HTML 报告

---

## 采集范围

### 学校要闻
学校要闻、综合新闻、校园快讯、媒体报道、校园喜报

### 通知公告
信息公告、学术海大、今日活动、下载专区

### 学生发展
本科生教育、研究生教育、本科生招生、研究生招生、本科生就业、研究生就业、继续教育

### 各学院动态

水产与生命学院 · 海洋科技与环境学院 · 食品科学与工程学院 · 海洋与土木工程学院 · 机械与动力工程学院 · 航海与船舶工程学院 · 信息工程学院 · 经济管理学院 · 海洋法律与人文学院 · 外国语学院 · 中新合作学院 · 马克思主义学院 · 体育与教育学院 · 应用技术学院

---

## 输出文件

采集完成后，`output` 目录下生成：

| 文件 | 说明 |
|------|------|
| 采集报告.html | 交互式 HTML 报告 |
| articles.json | 结构化数据 |

---

## 安全说明

- 仅访问 `dlou.edu.cn` 及其子域名
- 不收集用户个人数据
- 所有文件保存在本地

---

by:yuexuan
