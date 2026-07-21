"""DLOUWebsiteCrawler 图形界面：简洁布局，结果优先，内置HTML报告。

布局：
  ┌─────────────────────────────────────────────┐
  │  顶部标题栏（简洁白底）                        │
  ├──────────────┬──────────────────────────────┤
  │  采集控制     │     运行日志                  │  （上半部分，约 1/4）
  │              │                              │
  ├──────────────┴──────────────────────────────┤
  │                                              │
  │         采集结果（文章浏览 / HTML报告 双视图）   │  （下半部分，约 3/4）
  │                                              │
  └─────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import os
import threading
import time
import webbrowser
from pathlib import Path
from tkinter import (
    Tk, Frame, Label, Entry, Button, Checkbutton, IntVar, StringVar,
    Text, Scrollbar, messagebox, filedialog, Canvas,
    Listbox,
)
from tkinter import ttk

from .cli import _format_duration
from .client import HttpClient
from .crawler import DlouCrawler, CATEGORY_GROUPS
from .output import write_outputs
from .models import Article

try:
    from tkhtmlview import HTMLScrolledText
    _HAS_TKHTMLVIEW = True
except ImportError:
    _HAS_TKHTMLVIEW = False


_CONFIG_FILE = Path.home() / ".dlou_crawler_config.json"
_APP_NAME = "DLOUWebsiteCrawler"


class ModernButton(Button):
    """现代化按钮。"""
    def __init__(self, master, text, command=None, style="primary", **kwargs):
        styles = {
            "primary": {"bg": "#2563eb", "fg": "white", "activebackground": "#1d4ed8",
                        "activeforeground": "white", "relief": "flat", "bd": 0,
                        "font": ("Microsoft YaHei UI", 10, "bold"), "cursor": "hand2",
                        "padx": 18, "pady": 8},
            "secondary": {"bg": "#f1f5f9", "fg": "#475569", "activebackground": "#e2e8f0",
                          "activeforeground": "#334155", "relief": "flat", "bd": 0,
                          "font": ("Microsoft YaHei UI", 10), "cursor": "hand2",
                          "padx": 14, "pady": 8},
            "ghost": {"bg": "#ffffff", "fg": "#2563eb", "activebackground": "#eff6ff",
                      "activeforeground": "#1d4ed8", "relief": "solid", "bd": 1,
                      "font": ("Microsoft YaHei UI", 10), "cursor": "hand2",
                      "padx": 14, "pady": 7},
            "danger": {"bg": "#ef4444", "fg": "white", "activebackground": "#dc2626",
                       "activeforeground": "white", "relief": "flat", "bd": 0,
                       "font": ("Microsoft YaHei UI", 10), "cursor": "hand2",
                       "padx": 14, "pady": 8},
        }
        s = styles.get(style, styles["primary"])
        s.update(kwargs)
        super().__init__(master, text=text, command=command, **s)


class CrawlerGUI:
    """简洁布局：控制+日志在上，结果在下（双视图）。"""

    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("DLOUWebsiteCrawler")
        self.root.geometry("1180x820")
        self.root.minsize(960, 640)
        self.root.configure(bg="#f1f5f9")

        self._running = False
        self._start_time = 0.0
        self._articles: list[Article] = []
        self._warnings: list[str] = []
        self._output_dir = Path("output")
        self._filtered: list[Article] = []
        self._current_group: str | None = None

        # 最优默认参数（用户不用管）
        self._default_pages = 2
        self._default_max_articles = 200
        self._default_concurrency = 20
        self._default_delay = 0.0

        self._setup_ui()
        self._load_config()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_ui(self) -> None:
        """整体布局。"""
        self._build_header()

        body = Frame(self.root, bg="#f1f5f9")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # 上半部分：控制（左） + 日志（右）
        top = Frame(body, bg="#f1f5f9", height=220)
        top.pack(fill="x", pady=(0, 10))
        top.pack_propagate(False)

        left_panel = Frame(top, bg="white", highlightthickness=1,
                           highlightbackground="#e2e8f0", width=340)
        left_panel.pack(side="left", fill="y")
        left_panel.pack_propagate(False)
        self._build_control(left_panel)

        right_panel = Frame(top, bg="white", highlightthickness=1,
                            highlightbackground="#e2e8f0")
        right_panel.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self._build_log(right_panel)

        # 下半部分：采集结果（最重要）
        bottom = Frame(body, bg="white", highlightthickness=1,
                       highlightbackground="#e2e8f0")
        bottom.pack(fill="both", expand=True)
        self._build_results(bottom)

    # ===== 顶部标题栏 =====
    def _build_header(self) -> None:
        header = Frame(self.root, bg="white", height=52,
                       highlightthickness=1, highlightbackground="#e2e8f0")
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        inner = Frame(header, bg="white")
        inner.pack(fill="both", expand=True, padx=18)

        Label(inner, text="DLOUWebsiteCrawler",
              font=("Microsoft YaHei UI", 14, "bold"),
              bg="white", fg="#0f172a").pack(side="left")
        Label(inner, text="  大连海洋大学官网公开信息采集器",
              font=("Microsoft YaHei UI", 10),
              bg="white", fg="#64748b").pack(side="left", padx=(2, 0))

        Label(inner, text="by yuexuan",
              font=("Microsoft YaHei UI", 9),
              bg="white", fg="#94a3b8").pack(side="right", padx=(0, 12))

        self.status_pill = Canvas(inner, width=96, height=26,
                                  bg="white", highlightthickness=0, bd=0)
        self.status_pill.pack(side="right")
        self._draw_pill(self.status_pill, "待采集", "#64748b")

    # ===== 采集控制（左侧，简洁版） =====
    def _build_control(self, parent: Frame) -> None:
        title = Frame(parent, bg="white")
        title.pack(fill="x", padx=14, pady=(10, 2))
        Label(title, text="采集控制", font=("Microsoft YaHei UI", 12, "bold"),
              bg="white", fg="#0f172a").pack(side="left")

        body = Frame(parent, bg="white")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        # 保存路径
        out_frame = Frame(body, bg="white")
        out_frame.pack(fill="x", pady=(6, 0))
        Label(out_frame, text="保存路径", font=("Microsoft YaHei UI", 9),
              bg="white", fg="#64748b").pack(anchor="w")
        out_row = Frame(body, bg="white")
        out_row.pack(fill="x", pady=(3, 0))
        self.output_var = StringVar(value="output")
        Entry(out_row, textvariable=self.output_var, font=("Microsoft YaHei UI", 10),
              relief="solid", bd=1, bg="#f8fafc",
              highlightthickness=1, highlightbackground="#e2e8f0",
              highlightcolor="#2563eb").pack(side="left", fill="x", expand=True)
        ModernButton(out_row, "…", command=self._select_output_dir,
                     style="secondary", padx=8, pady=4).pack(side="left", padx=(6, 0))

        # 下载附件选项
        self.download_files_var = IntVar(value=0)
        Checkbutton(body, text="下载文章附件", variable=self.download_files_var,
                    font=("Microsoft YaHei UI", 10), bg="white", fg="#475569",
                    activebackground="white", selectcolor="white").pack(anchor="w", pady=(10, 0))

        # 主按钮
        btn_frame = Frame(body, bg="white")
        btn_frame.pack(fill="x", pady=(12, 0))

        self.start_btn = ModernButton(btn_frame, "开始采集", command=self._start_crawl, style="primary")
        self.start_btn.pack(fill="x", pady=(0, 6))

        self.stop_btn = ModernButton(btn_frame, "停止采集", command=self._stop_crawl, style="danger")
        self.stop_btn.pack(fill="x")
        self.stop_btn.config(state="disabled")

        # 底部操作
        op_row = Frame(body, bg="white")
        op_row.pack(fill="x", pady=(10, 0))
        ModernButton(op_row, "保存结果", command=self._save_results,
                     style="ghost", padx=10, pady=5).pack(side="left")
        ModernButton(op_row, "打开文件夹", command=self._open_output_dir,
                     style="secondary", padx=10, pady=5).pack(side="left", padx=(6, 0))

    # ===== 运行日志（右侧） =====
    def _build_log(self, parent: Frame) -> None:
        title = Frame(parent, bg="white")
        title.pack(fill="x", padx=14, pady=(10, 2))
        Label(title, text="运行日志", font=("Microsoft YaHei UI", 12, "bold"),
              bg="white", fg="#0f172a").pack(side="left")
        Label(title, text="实时输出", font=("Microsoft YaHei UI", 9),
              bg="white", fg="#94a3b8").pack(side="left", padx=(8, 0))

        body = Frame(parent, bg="white")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        sb = Scrollbar(body)
        sb.pack(side="right", fill="y")

        self.log_text = Text(body, font=("Cascadia Mono", 9),
                             bg="#0b1220", fg="#e2e8f0", wrap="word",
                             yscrollcommand=sb.set, insertbackground="white",
                             relief="flat", bd=0, padx=10, pady=8)
        self.log_text.pack(fill="both", expand=True, side="left")
        sb.config(command=self.log_text.yview)

        self.log_text.tag_configure("success", foreground="#34d399")
        self.log_text.tag_configure("warning", foreground="#fbbf24")
        self.log_text.tag_configure("error", foreground="#f87171")
        self.log_text.tag_configure("info", foreground="#93c5fd")

    # ===== 采集结果（双视图：文章浏览 + HTML报告） =====
    def _build_results(self, parent: Frame) -> None:
        # 标题栏
        header = Frame(parent, bg="white", height=42,
                       highlightthickness=1, highlightbackground="#e2e8f0")
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        header_inner = Frame(header, bg="white")
        header_inner.pack(fill="both", expand=True, padx=14)

        Label(header_inner, text="采集结果", font=("Microsoft YaHei UI", 12, "bold"),
              bg="white", fg="#0f172a").pack(side="left")
        self.results_count = Label(header_inner, text="（点击「开始采集」获取内容）",
                                   font=("Microsoft YaHei UI", 9),
                                   bg="white", fg="#94a3b8")
        self.results_count.pack(side="left", padx=(8, 0))

        # 视图切换按钮
        self.view_tabs = Frame(header_inner, bg="white")
        self.view_tabs.pack(side="right")

        self.btn_view_articles = Button(self.view_tabs, text="📄 文章浏览",
                                        font=("Microsoft YaHei UI", 9, "bold"),
                                        bg="#2563eb", fg="white",
                                        activebackground="#1d4ed8",
                                        activeforeground="white",
                                        relief="flat", bd=0, cursor="hand2",
                                        padx=12, pady=5,
                                        command=self._switch_view_articles)
        self.btn_view_articles.pack(side="left", padx=(0, 2))

        self.btn_view_html = Button(self.view_tabs, text="🌐 HTML 报告",
                                    font=("Microsoft YaHei UI", 9),
                                    bg="#f1f5f9", fg="#475569",
                                    activebackground="#e2e8f0",
                                    activeforeground="#334155",
                                    relief="flat", bd=0, cursor="hand2",
                                    padx=12, pady=5,
                                    command=self._switch_view_html)
        self.btn_view_html.pack(side="left")

        # 空状态
        self.empty_state = Frame(parent, bg="white")
        self.empty_state.pack(fill="both", expand=True)
        self.empty_state.pack_propagate(False)

        empty_inner = Frame(self.empty_state, bg="white")
        empty_inner.pack(pady=60)
        Label(empty_inner, text="📥", font=("Segoe UI Emoji", 42),
              bg="white", fg="#cbd5e1").pack()
        Label(empty_inner, text="暂无采集结果",
              font=("Microsoft YaHei UI", 12, "bold"),
              bg="white", fg="#475569").pack(pady=(10, 4))
        Label(empty_inner, text="点击左上角「开始采集」，结果将显示在这里",
              font=("Microsoft YaHei UI", 10),
              bg="white", fg="#94a3b8").pack()

        # 结果内容容器（初始隐藏）
        self.results_body = Frame(parent, bg="white")

        # === 文章浏览视图 ===
        self.view_articles = Frame(self.results_body, bg="white")
        self._build_articles_view(self.view_articles)

        # === HTML 报告视图 ===
        self.view_html = Frame(self.results_body, bg="white")
        self._build_html_view(self.view_html)

    def _build_articles_view(self, parent: Frame) -> None:
        """文章浏览：三栏（栏目 / 文章列表 / 正文预览）。"""
        # 顶部：分类 Tab + 搜索
        top_bar = Frame(parent, bg="white")
        top_bar.pack(fill="x", padx=14, pady=(8, 6))

        self.group_tabs = Frame(top_bar, bg="white")
        self.group_tabs.pack(side="left")

        search_frame = Frame(top_bar, bg="white")
        search_frame.pack(side="right")
        Label(search_frame, text="🔍", font=("Segoe UI Emoji", 11),
              bg="white").pack(side="left", padx=(0, 4))
        self.search_var = StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        Entry(search_frame, textvariable=self.search_var, width=26,
              font=("Microsoft YaHei UI", 10),
              relief="solid", bd=1, bg="#f8fafc",
              highlightthickness=1, highlightbackground="#e2e8f0",
              highlightcolor="#2563eb").pack(side="left")

        # 三栏主体
        main = Frame(parent, bg="white")
        main.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        # 左：子分类
        cat_frame = Frame(main, bg="#f8fafc", width=150,
                          highlightthickness=1, highlightbackground="#e2e8f0")
        cat_frame.pack(side="left", fill="y")
        cat_frame.pack_propagate(False)

        Label(cat_frame, text="  栏目", font=("Microsoft YaHei UI", 9, "bold"),
              bg="#f1f5f9", fg="#475569", pady=5, anchor="w").pack(fill="x")

        cat_sb = Scrollbar(cat_frame)
        cat_sb.pack(side="right", fill="y")
        self.cat_listbox = Listbox(cat_frame, font=("Microsoft YaHei UI", 10),
                                   bg="#f8fafc", fg="#334155",
                                   selectbackground="#dbeafe",
                                   selectforeground="#1e40af",
                                   relief="flat", bd=0,
                                   yscrollcommand=cat_sb.set,
                                   activestyle="none",
                                   highlightthickness=0)
        self.cat_listbox.pack(fill="both", expand=True, side="left", padx=2, pady=2)
        cat_sb.config(command=self.cat_listbox.yview)
        self.cat_listbox.bind("<<ListboxSelect>>", lambda e: self._on_select_category())

        # 中：文章列表
        list_frame = Frame(main, bg="white", width=340,
                           highlightthickness=1, highlightbackground="#e2e8f0")
        list_frame.pack(side="left", fill="y", padx=(10, 0))
        list_frame.pack_propagate(False)

        Label(list_frame, text="  文章列表", font=("Microsoft YaHei UI", 9, "bold"),
              bg="#f1f5f9", fg="#475569", pady=5, anchor="w").pack(fill="x")

        list_sb = Scrollbar(list_frame)
        list_sb.pack(side="right", fill="y")
        self.article_listbox = Listbox(list_frame, font=("Microsoft YaHei UI", 10),
                                       bg="white", fg="#0f172a",
                                       selectbackground="#dbeafe",
                                       selectforeground="#1e40af",
                                       relief="flat", bd=0,
                                       yscrollcommand=list_sb.set,
                                       activestyle="none",
                                       highlightthickness=0)
        self.article_listbox.pack(fill="both", expand=True, side="left", padx=2, pady=2)
        list_sb.config(command=self.article_listbox.yview)
        self.article_listbox.bind("<<ListboxSelect>>", lambda e: self._on_select_article())

        # 右：正文预览
        reader_frame = Frame(main, bg="white",
                             highlightthickness=1, highlightbackground="#e2e8f0")
        reader_frame.pack(side="left", fill="both", expand=True, padx=(10, 0))

        reader_header = Frame(reader_frame, bg="white")
        reader_header.pack(fill="x", padx=14, pady=(8, 4))
        self.reader_title = Label(reader_header, text="选择文章查看正文",
                                  font=("Microsoft YaHei UI", 12, "bold"),
                                  bg="white", fg="#0f172a", anchor="w", justify="left",
                                  wraplength=400)
        self.reader_title.pack(fill="x")
        self.reader_meta = Label(reader_header, text="",
                                 font=("Microsoft YaHei UI", 9),
                                 bg="white", fg="#64748b", anchor="w")
        self.reader_meta.pack(fill="x", pady=(4, 0))

        reader_body = Frame(reader_frame, bg="white")
        reader_body.pack(fill="both", expand=True, padx=10, pady=(4, 4))

        rsb = Scrollbar(reader_body)
        rsb.pack(side="right", fill="y")

        self.reader_text = Text(reader_body, font=("Microsoft YaHei UI", 11),
                                bg="#ffffff", fg="#1e293b", wrap="word",
                                yscrollcommand=rsb.set, relief="flat", bd=0,
                                spacing3=6, padx=14, pady=10)
        self.reader_text.pack(fill="both", expand=True, side="left")
        rsb.config(command=self.reader_text.yview)

        self.reader_text.tag_configure("h1", font=("Microsoft YaHei UI", 16, "bold"),
                                       foreground="#0f172a", spacing1=8, spacing3=8)
        self.reader_text.tag_configure("h2", font=("Microsoft YaHei UI", 13, "bold"),
                                       foreground="#1e293b", spacing1=6, spacing3=4)
        self.reader_text.tag_configure("meta", font=("Microsoft YaHei UI", 9),
                                       foreground="#64748b")
        self.reader_text.tag_configure("link", foreground="#2563eb", underline=True)
        self.reader_text.tag_configure("quote", foreground="#64748b",
                                       font=("Microsoft YaHei UI", 10, "italic"))
        self.reader_text.tag_configure("attach_bg", background="#f8fafc")

        reader_footer = Frame(reader_frame, bg="white")
        reader_footer.pack(fill="x", padx=14, pady=(0, 8))
        ModernButton(reader_footer, "打开原文链接", command=self._open_current_url,
                     style="ghost", padx=10, pady=5).pack(side="left")

    def _build_html_view(self, parent: Frame) -> None:
        """HTML 报告视图。"""
        if _HAS_TKHTMLVIEW:
            self.html_viewer = HTMLScrolledText(parent, background="white",
                                                 font=("Microsoft YaHei UI", 10))
            self.html_viewer.pack(fill="both", expand=True, padx=0, pady=0)
        else:
            # fallback: 普通文本显示提示
            self.html_viewer = Text(parent, font=("Microsoft YaHei UI", 10),
                                    bg="white", fg="#475569", wrap="word",
                                    relief="flat", padx=20, pady=20)
            self.html_viewer.pack(fill="both", expand=True)
            self.html_viewer.insert("end",
                "HTML 查看组件未就绪\n\n"
                "请点击右上角「浏览器查看 HTML 报告」在浏览器中打开。")
            self.html_viewer.config(state="disabled")

    def _switch_view_articles(self) -> None:
        self.btn_view_articles.config(bg="#2563eb", fg="white",
                                      font=("Microsoft YaHei UI", 9, "bold"))
        self.btn_view_html.config(bg="#f1f5f9", fg="#475569",
                                  font=("Microsoft YaHei UI", 9))
        self.view_html.pack_forget()
        self.view_articles.pack(fill="both", expand=True)

    def _switch_view_html(self) -> None:
        self.btn_view_html.config(bg="#2563eb", fg="white",
                                  font=("Microsoft YaHei UI", 9, "bold"))
        self.btn_view_articles.config(bg="#f1f5f9", fg="#475569",
                                      font=("Microsoft YaHei UI", 9))
        self.view_articles.pack_forget()
        self.view_html.pack(fill="both", expand=True)

        # 加载HTML报告
        self._load_html_report()

    def _load_html_report(self) -> None:
        html_path = Path(self.output_var.get()) / "采集报告.html"
        if not html_path.exists():
            if _HAS_TKHTMLVIEW:
                self.html_viewer.set_html("<h3>暂无HTML报告</h3><p>请先执行采集。</p>")
            return

        try:
            html_content = html_path.read_text(encoding="utf-8", errors="ignore")
            if _HAS_TKHTMLVIEW:
                self.html_viewer.set_html(html_content)
        except Exception as e:
            if _HAS_TKHTMLVIEW:
                self.html_viewer.set_html(f"<h3>加载失败</h3><p>{str(e)}</p>")

    # ===== 分类 / 过滤 / 文章展示 =====
    def _build_group_tabs(self) -> None:
        for w in self.group_tabs.winfo_children():
            w.destroy()

        btn = Button(self.group_tabs, text="全部",
                     font=("Microsoft YaHei UI", 10, "bold"),
                     bg="#2563eb", fg="white",
                     activebackground="#1d4ed8", activeforeground="white",
                     relief="flat", bd=0, cursor="hand2",
                     padx=12, pady=5,
                     command=lambda: self._switch_group(None))
        btn.pack(side="left", padx=(0, 4))

        self._group_buttons: dict[str | None, Button] = {None: btn}

        for group_name, _cats in CATEGORY_GROUPS:
            count = self._count_in_group(group_name)
            if count == 0:
                continue
            b = Button(self.group_tabs, text=f"{group_name} {count}",
                       font=("Microsoft YaHei UI", 10),
                       bg="#f1f5f9", fg="#475569",
                       activebackground="#e2e8f0", activeforeground="#334155",
                       relief="flat", bd=0, cursor="hand2",
                       padx=12, pady=5,
                       command=lambda g=group_name: self._switch_group(g))
            b.pack(side="left", padx=(0, 4))
            self._group_buttons[group_name] = b

    def _count_in_group(self, group_name: str) -> int:
        for name, cats in CATEGORY_GROUPS:
            if name == group_name:
                return sum(1 for a in self._articles if a.category in cats)
        return 0

    def _switch_group(self, group_name: str | None) -> None:
        self._current_group = group_name
        for g, btn in self._group_buttons.items():
            if g == group_name:
                btn.config(bg="#2563eb", fg="white",
                           font=("Microsoft YaHei UI", 10, "bold"))
            else:
                btn.config(bg="#f1f5f9", fg="#475569",
                           font=("Microsoft YaHei UI", 10))
        self._refresh_category_list()
        self._apply_filter()

    def _refresh_category_list(self) -> None:
        self.cat_listbox.delete(0, "end")
        self.cat_listbox.insert(0, "  全部栏目")
        self.cat_listbox.selection_set(0)

        if self._current_group is None:
            seen = set()
            for a in self._articles:
                if a.category not in seen:
                    seen.add(a.category)
                    self.cat_listbox.insert("end", f"  {a.category}")
        else:
            for name, cats in CATEGORY_GROUPS:
                if name == self._current_group:
                    for cat in cats:
                        count = sum(1 for a in self._articles if a.category == cat)
                        if count > 0:
                            self.cat_listbox.insert("end", f"  {cat}")
                    break

    def _on_select_category(self) -> None:
        self._apply_filter()

    def _apply_filter(self) -> None:
        keyword = self.search_var.get().lower() if hasattr(self, 'search_var') else ""

        cat_sel = self.cat_listbox.curselection() if hasattr(self, 'cat_listbox') else []
        selected_cat = None
        if cat_sel and cat_sel[0] > 0:
            selected_cat = self.cat_listbox.get(cat_sel[0]).strip()

        group_cats: set[str] | None = None
        if self._current_group is not None:
            for name, cats in CATEGORY_GROUPS:
                if name == self._current_group:
                    group_cats = set(cats)
                    break

        self._filtered = []
        for a in self._articles:
            if group_cats is not None and a.category not in group_cats:
                continue
            if selected_cat and selected_cat != "全部栏目" and a.category != selected_cat:
                continue
            if keyword and keyword not in a.title.lower():
                continue
            self._filtered.append(a)

        self.article_listbox.delete(0, "end")
        for a in self._filtered:
            date = a.published_at or "  --  "
            short_title = a.title if len(a.title) <= 40 else a.title[:39] + "…"
            self.article_listbox.insert("end", f"  {date}  {short_title}")

        total = len(self._articles)
        shown = len(self._filtered)
        self.results_count.config(text=f"（共 {total} 篇 · 显示 {shown} 篇）")

    def _on_select_article(self) -> None:
        sel = self.article_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._filtered):
            article = self._filtered[idx]
            self._display_article(article)

    def _display_article(self, article: Article) -> None:
        self.reader_title.config(text=article.title)
        self.reader_meta.config(
            text=f"栏目：{article.category}    日期：{article.published_at or '未知'}    原文：{article.url}"
        )
        self.reader_text.delete("1.0", "end")

        self.reader_text.insert("end", article.title + "\n", "h1")
        meta_line = f"\n📅 {article.published_at or '未知'}    📂 {article.category}\n\n"
        self.reader_text.insert("end", meta_line, "meta")
        self.reader_text.insert("end", "─" * 50 + "\n\n", "meta")

        if article.attachments:
            self.reader_text.insert("end", "📎 附件列表：\n", "h2")
            for att in article.attachments:
                self.reader_text.insert("end", f"   • {att.name}\n     ", "attach_bg")
                self.reader_text.insert("end", f"{att.url}\n", "link")
            self.reader_text.insert("end", "\n" + "─" * 50 + "\n\n", "meta")

        content = article.content
        if content:
            paragraphs = [p.strip() for p in content.split("  ") if p.strip()]
            if len(paragraphs) <= 1:
                paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
            for para in paragraphs:
                self.reader_text.insert("end", para + "\n\n")
        else:
            self.reader_text.insert("end", "（正文为空或暂不可用）\n", "quote")

    def _open_current_url(self) -> None:
        sel = self.article_listbox.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一篇文章")
            return
        idx = sel[0]
        if idx < len(self._filtered):
            webbrowser.open(self._filtered[idx].url)

    # ===== 采集逻辑 =====
    def _start_crawl(self) -> None:
        self._running = True
        self._start_time = time.monotonic()
        self._articles = []
        self._warnings = []
        self._output_dir = Path(self.output_var.get())

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.log_text.delete("1.0", "end")
        self._draw_pill(self.status_pill, "采集中", "#f59e0b")

        self._log("开始采集…", "success")
        self._log(f"配置：{self._default_pages} 页/栏目 · 最多 {self._default_max_articles} 篇 · "
                  f"{self._default_concurrency} 线程 · 全速模式", "info")

        thread = threading.Thread(target=self._run_crawler)
        thread.daemon = True
        thread.start()

    def _run_crawler(self) -> None:
        try:
            output_dir = Path(self.output_var.get())
            client = HttpClient("DLOUWebsiteCrawler/2.0", self._default_delay)
            crawler = DlouCrawler(
                client=client,
                pages_per_source=self._default_pages,
                max_articles=self._default_max_articles,
                download_files=self.download_files_var.get() == 1,
                output_dir=output_dir,
                concurrency=self._default_concurrency,
                progress_callback=lambda m: self._log(m, "info"),
            )

            articles = crawler.crawl()
            self._articles = articles
            self._warnings = crawler.warnings

            if self._running:
                self._log("保存结果文件…", "info")
                write_outputs(output_dir, articles, crawler.warnings)

                elapsed = time.monotonic() - self._start_time
                self._draw_pill(self.status_pill, "已完成", "#10b981")

                self._log(f"采集完成！共 {len(articles)} 篇", "success")
                self._log(f"总耗时：{_format_duration(elapsed)}", "success")

                self.root.after(0, self._refresh_results)

        except Exception as e:
            self._log(f"采集失败：{str(e)}", "error")
            messagebox.showerror("采集失败", f"发生错误：{str(e)}")
            self._draw_pill(self.status_pill, "失败", "#ef4444")
        finally:
            self._running = False
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")

    def _stop_crawl(self) -> None:
        self._running = False
        self._log("正在停止…", "warning")
        self._draw_pill(self.status_pill, "停止中", "#64748b")

    def _refresh_results(self) -> None:
        if not self.results_body.winfo_ismapped():
            self.empty_state.pack_forget()
            self.results_body.pack(fill="both", expand=True)
            self.view_articles.pack(fill="both", expand=True)
            self._build_group_tabs()
            self._switch_group(None)
        else:
            self._build_group_tabs()
            self._switch_group(None)
            # 如果当前在HTML视图，刷新一下
            if self.btn_view_html.cget("bg") == "#2563eb":
                self._load_html_report()

    # ===== 辅助 =====
    def _save_results(self) -> None:
        if not self._articles:
            messagebox.showinfo("提示", "还没有采集结果，请先执行采集")
            return
        dest = filedialog.askdirectory(title="选择保存位置")
        if not dest:
            return
        dest_path = Path(dest)
        try:
            write_outputs(dest_path, self._articles, self._warnings)
            messagebox.showinfo("保存成功", f"结果已保存到：\n{dest_path.resolve()}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _log(self, message: str, level: str = "info") -> None:
        tags = {"success": "success", "warning": "warning",
                "error": "error", "info": "info"}
        tag = tags.get(level, "info")

        def append():
            self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n", tag)
            self.log_text.see("end")
        self.root.after(0, append)

    @staticmethod
    def _draw_pill(canvas: Canvas, text: str, color: str) -> None:
        canvas.delete("all")
        w, h = 96, 26
        canvas.create_oval(2, 2, h, h - 2, fill=color, outline=color, width=0)
        canvas.create_rectangle(h // 2, 2, w - h // 2, h - 2, fill=color, outline=color, width=0)
        canvas.create_oval(w - h, 2, w - 2, h - 2, fill=color, outline=color, width=0)
        canvas.create_text(12, h // 2, anchor="w",
                           text=f"● {text}",
                           font=("Microsoft YaHei UI", 9, "bold"),
                           fill="white")

    def _select_output_dir(self) -> None:
        dir_path = filedialog.askdirectory(title="选择保存目录")
        if dir_path:
            self.output_var.set(dir_path)

    def _open_output_dir(self) -> None:
        output_dir = Path(self.output_var.get())
        if output_dir.exists():
            try:
                os.startfile(output_dir)
            except Exception as e:
                messagebox.showerror("错误", f"无法打开文件夹：{str(e)}")
        else:
            messagebox.showinfo("提示", "结果文件夹尚未生成，请先执行采集")

    def _open_html_report(self) -> None:
        html_path = Path(self.output_var.get()) / "采集报告.html"
        if html_path.exists():
            try:
                webbrowser.open(html_path.resolve().as_uri())
            except Exception as e:
                messagebox.showerror("错误", f"无法打开报告：{str(e)}")
        else:
            messagebox.showinfo("提示", "HTML 报告尚未生成，请先执行采集")

    def _save_config(self) -> None:
        config = {
            "output": self.output_var.get(),
            "download_files": self.download_files_var.get(),
        }
        try:
            _CONFIG_FILE.write_text(
                json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def _load_config(self) -> None:
        if not _CONFIG_FILE.exists():
            return
        try:
            config = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            self.output_var.set(config.get("output", "output"))
            self.download_files_var.set(config.get("download_files", 0))
        except Exception:
            pass

    def _on_closing(self) -> None:
        if self._running:
            if messagebox.askyesno("确认退出", "采集正在进行中，确定要退出吗？"):
                self._running = False
                self._save_config()
                self.root.destroy()
        else:
            self._save_config()
            self.root.destroy()


def main() -> None:
    root = Tk()
    try:
        style = ttk.Style()
        style.theme_use("vista")
    except Exception:
        pass

    CrawlerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
