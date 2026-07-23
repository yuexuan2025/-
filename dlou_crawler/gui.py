import os
import re
import sys
import threading
import webbrowser
from tkinter import (
    Tk, Frame, Canvas, Scrollbar, Label, Button, Text,
    Listbox, END, BOTH, LEFT, RIGHT, X, Y,
)
from datetime import datetime

from .crawler import Crawler, Article, CATEGORY_GROUPS, SOURCES
from .report import generate_html_report, save_articles_json


def _get_output_dir() -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(os.path.dirname(sys.executable), "output")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


class CrawlerGUI:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("DLOUWebsiteCrawler - 大连海洋大学官网采集器")
        self.root.geometry("1000x700")
        self.root.minsize(900, 600)
        self.root.configure(bg="#f8fafc")

        self.crawler: Crawler | None = None
        self.articles: list[Article] = []
        self._is_running = False
        self._selected_category = "全部"

        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = Frame(self.root, bg="#f8fafc")
        outer.pack(fill="both", expand=True)

        self._canvas = Canvas(outer, bg="#f8fafc", highlightthickness=0, bd=0)
        self._canvas.pack(side="left", fill="both", expand=True)

        vbar = Scrollbar(outer, orient="vertical", command=self._canvas.yview)
        vbar.pack(side="right", fill="y")
        self._canvas.configure(yscrollcommand=vbar.set)

        self._content = Frame(self._canvas, bg="#f8fafc")
        self._content_window = self._canvas.create_window(
            (0, 0), window=self._content, anchor="nw"
        )

        self._content.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            self._on_canvas_resize,
        )
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._build_hero()
        self._build_mid_section()
        self._build_results()

    def _on_canvas_resize(self, event) -> None:
        self._canvas.itemconfigure(self._content_window, width=event.width)
        self._draw_hero_gradient(event.width)

    def _on_mousewheel(self, event) -> None:
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── 顶部标题栏 ──

    def _build_hero(self) -> None:
        self._hero = Canvas(
            self._content, height=140, bg="#f8fafc",
            highlightthickness=0, bd=0,
        )
        self._hero.pack(fill="x", padx=24, pady=(20, 16))

        self._hero.create_text(24, 36, text="DLOUWebsiteCrawler", fill="white",
                               font=("Microsoft YaHei UI", 22, "bold"), anchor="w")
        self._hero.create_text(24, 72, text="大连海洋大学官网采集器", fill="white",
                               font=("Microsoft YaHei UI", 12), anchor="w")
        self._hero.create_text(24, 100, text="快速采集学校要闻、通知公告、学生发展、各学院动态",
                               fill="#e0e7ff",
                               font=("Microsoft YaHei UI", 10), anchor="w")

        self._status_label = Label(self._hero, text="● 就绪", fg="#a7f3d0",
                                   bg="#2563eb", font=("Microsoft YaHei UI", 10, "bold"))
        self._status_label.place(x=24, y=112)

        self._draw_hero_gradient(1000)

    def _draw_hero_gradient(self, width: int) -> None:
        self._hero.delete("gradient")
        w = max(width, 200)
        for i in range(w):
            r = int(37 + (124 - 37) * i / w)
            g = int(99 + (58 - 99) * i / w)
            b = int(235 + (237 - 235) * i / w)
            self._hero.create_line(i, 0, i, 140, fill=f"#{r:02x}{g:02x}{b:02x}", tags="gradient")
        self._hero.tag_lower("gradient")
        self._hero.tag_raise("all")

    # ── 中间区域：左控制 + 右日志 ──

    def _build_mid_section(self) -> None:
        mid = Frame(self._content, bg="#f8fafc")
        mid.pack(fill="x", padx=24, pady=8)

        self._build_control(mid)
        self._build_log(mid)

    def _build_control(self, parent: Frame) -> None:
        card = Frame(parent, bg="white", bd=0, highlightthickness=1,
                     highlightbackground="#e2e8f0")
        card.pack(side="left", fill="both", expand=True, padx=(0, 4))

        header = Frame(card, bg="white")
        header.pack(fill="x", padx=20, pady=(16, 12))

        Label(header, text="采集控制", font=("Microsoft YaHei UI", 14, "bold"),
              bg="white", fg="#1e293b").pack(side="left")

        btn_frame = Frame(header, bg="white")
        btn_frame.pack(side="right")

        self._start_btn = Button(
            btn_frame, text="开始采集", command=self._on_start,
            bg="#2563eb", fg="white", font=("Microsoft YaHei UI", 11, "bold"),
            relief="flat", padx=24, pady=8, cursor="hand2",
            activebackground="#1d4ed8", activeforeground="white",
            disabledforeground="#dbeafe",
        )
        self._start_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = Button(
            btn_frame, text="停止采集", command=self._on_stop,
            bg="#ef4444", fg="white", font=("Microsoft YaHei UI", 11, "bold"),
            relief="flat", padx=24, pady=8, cursor="hand2",
            activebackground="#dc2626", activeforeground="white",
            state="disabled",
            disabledforeground="#fecaca",
        )
        self._stop_btn.pack(side="left")

        info_frame = Frame(card, bg="white")
        info_frame.pack(fill="x", padx=20, pady=(0, 16))

        self._count_label = Label(
            info_frame,
            text=f"栏目数：{len(SOURCES)} 个 | 并发线程：20 | 每栏最大：15 篇",
            bg="white", fg="#64748b", font=("Microsoft YaHei UI", 10),
        )
        self._count_label.pack(side="left")

    def _build_log(self, parent: Frame) -> None:
        card = Frame(parent, bg="white", bd=0, highlightthickness=1,
                     highlightbackground="#e2e8f0")
        card.pack(side="right", fill="both", expand=True, padx=(4, 0))

        header = Frame(card, bg="white")
        header.pack(fill="x", padx=20, pady=(16, 12))

        Label(header, text="运行日志", font=("Microsoft YaHei UI", 14, "bold"),
              bg="white", fg="#1e293b").pack(side="left")

        self._log_text = Text(card, height=8, bg="#f8fafc", fg="#334155",
                              font=("Consolas", 9), relief="flat",
                              padx=12, pady=8, wrap="word")
        self._log_text.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self._log("欢迎使用 DLOUWebsiteCrawler 大连海洋大学官网采集器")
        self._log("点击「开始采集」按钮开始采集官网内容")

    # ── 采集结果区域 ──

    def _build_results(self) -> None:
        self._results_card = Frame(self._content, bg="white", bd=0, highlightthickness=1,
                                   highlightbackground="#e2e8f0")
        self._results_card.pack(fill="both", expand=True, padx=24, pady=(8, 24))

        header = Frame(self._results_card, bg="white")
        header.pack(fill="x", padx=20, pady=(16, 12))

        Label(header, text="采集结果", font=("Microsoft YaHei UI", 14, "bold"),
              bg="white", fg="#1e293b").pack(side="left")

        btn_frame = Frame(header, bg="white")
        btn_frame.pack(side="right")

        self._report_btn = Button(
            btn_frame, text="在浏览器中打开 HTML 报告",
            command=self._on_open_report,
            bg="#2563eb", fg="white", font=("Microsoft YaHei UI", 11, "bold"),
            relief="flat", padx=20, pady=8, cursor="hand2",
            activebackground="#1d4ed8", activeforeground="white",
        )
        self._report_btn.pack(side="left")

        self._empty_frame = Frame(self._results_card, bg="white")
        self._empty_frame.pack(fill="both", expand=True, pady=40)

        Label(self._empty_frame, text="📭", font=("Segoe UI Emoji", 48),
              bg="white", fg="#cbd5e1").pack(pady=(0, 16))
        Label(self._empty_frame, text="暂无采集结果",
              font=("Microsoft YaHei UI", 14, "bold"),
              bg="white", fg="#64748b").pack(pady=(0, 4))
        Label(self._empty_frame, text="点击上方「开始采集」按钮获取官网内容",
              font=("Microsoft YaHei UI", 10),
              bg="white", fg="#94a3b8").pack()

        self._content_frame = Frame(self._results_card, bg="white")

        self._build_tabs()
        self._build_articles_view()

    def _build_tabs(self) -> None:
        self._tabs_frame = Frame(self._content_frame, bg="white")
        self._tabs_frame.pack(fill="x", padx=20, pady=(0, 12))

        self._tab_buttons = []
        categories = ["全部"] + [g[0] for g in CATEGORY_GROUPS]

        for cat in categories:
            btn = Button(
                self._tabs_frame, text=cat,
                command=lambda c=cat: self._on_category_change(c),
                bg="white", fg="#64748b",
                font=("Microsoft YaHei UI", 10),
                relief="flat", padx=14, pady=6, cursor="hand2",
                activebackground="#eff6ff", activeforeground="#2563eb",
            )
            btn.pack(side="left", padx=(0, 4))
            self._tab_buttons.append((btn, cat))

        self._update_tab_style()

    def _build_articles_view(self) -> None:
        paned = Frame(self._content_frame, bg="white")
        paned.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        left = Frame(paned, bg="white")
        left.pack(side="left", fill="both", expand=True)

        Label(left, text="文章列表", font=("Microsoft YaHei UI", 11, "bold"),
              bg="white", fg="#1e293b", anchor="w").pack(fill="x", pady=(0, 8))

        list_frame = Frame(left, bg="#f8fafc", bd=0, highlightthickness=1,
                           highlightbackground="#e2e8f0")
        list_frame.pack(fill="both", expand=True)

        self._article_listbox = Listbox(
            list_frame, bg="white", fg="#334155",
            font=("Microsoft YaHei UI", 9),
            relief="flat", bd=0, highlightthickness=0,
            selectbackground="#eff6ff", selectforeground="#2563eb",
            activestyle="none", exportselection=False,
        )
        self._article_listbox.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        self._article_listbox.bind("<<ListboxSelect>>", self._on_article_select)

        scrollbar = Scrollbar(list_frame, orient="vertical", command=self._article_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self._article_listbox.configure(yscrollcommand=scrollbar.set)

        separator = Frame(paned, bg="#e2e8f0", width=1)
        separator.pack(side="left", fill="y", padx=16)

        right = Frame(paned, bg="white")
        right.pack(side="left", fill="both", expand=True)

        Label(right, text="文章预览", font=("Microsoft YaHei UI", 11, "bold"),
              bg="white", fg="#1e293b", anchor="w").pack(fill="x", pady=(0, 8))

        self._detail_title = Label(right, text="请选择左侧文章查看详情",
                                   font=("Microsoft YaHei UI", 12, "bold"),
                                   bg="white", fg="#1e293b", anchor="w",
                                   wraplength=400, justify="left")
        self._detail_title.pack(fill="x", pady=(0, 8))

        self._detail_meta = Label(right, text="",
                                  font=("Microsoft YaHei UI", 9),
                                  bg="white", fg="#64748b", anchor="w")
        self._detail_meta.pack(fill="x", pady=(0, 12))

        detail_frame = Frame(right, bg="#f8fafc", bd=0, highlightthickness=1,
                             highlightbackground="#e2e8f0")
        detail_frame.pack(fill="both", expand=True)

        self._detail_text = Text(detail_frame, bg="white", fg="#334155",
                                 font=("Microsoft YaHei UI", 9),
                                 relief="flat", wrap="word",
                                 padx=12, pady=8)
        self._detail_text.pack(side="left", fill="both", expand=True, padx=1, pady=1)

        detail_scroll = Scrollbar(detail_frame, orient="vertical",
                                  command=self._detail_text.yview)
        detail_scroll.pack(side="right", fill="y")
        self._detail_text.configure(yscrollcommand=detail_scroll.set)
        self._detail_text.configure(state="disabled")

    # ── 日志 ──

    def _log(self, msg: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_text.insert(END, f"[{timestamp}] {msg}\n")
        self._log_text.see(END)

    # ── 采集控制 ──

    def _on_start(self) -> None:
        if self._is_running:
            return

        self._is_running = True
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._status_label.configure(text="● 采集中", fg="#fbbf24")

        self._log("开始采集...")

        t = threading.Thread(target=self._run_crawler, daemon=True)
        t.start()

    def _on_stop(self) -> None:
        if self.crawler:
            self.crawler.stop()
            self._log("正在停止...")

    def _run_crawler(self) -> None:
        try:
            self.crawler = Crawler(
                max_workers=20,
                max_articles_per_source=15,
                log_callback=self._log,
            )
            self.articles = self.crawler.crawl()
            self.root.after(0, self._on_crawl_done)
        except Exception as e:
            self.root.after(0, lambda: self._log(f"采集异常：{e}"))
            self.root.after(0, self._on_crawl_done)

    def _on_crawl_done(self) -> None:
        self._is_running = False
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_label.configure(text="● 就绪", fg="#a7f3d0")

        if self.articles:
            self._show_results()
            output_dir = _get_output_dir()
            os.makedirs(output_dir, exist_ok=True)
            html_path = os.path.join(output_dir, "采集报告.html")
            json_path = os.path.join(output_dir, "articles.json")
            generate_html_report(self.articles, html_path)
            save_articles_json(self.articles, json_path)
            self._log(f"报告已生成：{html_path}")
        else:
            self._log("未采集到任何文章")

    # ── 结果展示 ──

    def _show_results(self) -> None:
        self._empty_frame.pack_forget()
        self._content_frame.pack(fill="both", expand=True, pady=(0, 16))
        self._refresh_article_list()

    def _refresh_article_list(self) -> None:
        self._article_listbox.delete(0, END)
        filtered = self._get_filtered_articles()
        self._filtered_articles = filtered

        for article in filtered:
            date_str = article.date.strftime("%Y-%m-%d") if article.date else "未知"
            display = f"  {date_str}  {article.title}"
            self._article_listbox.insert(END, display)

    def _get_filtered_articles(self) -> list[Article]:
        if self._selected_category == "全部":
            return list(self.articles)

        for group_name, sources in CATEGORY_GROUPS:
            if group_name == self._selected_category:
                return [a for a in self.articles if a.source in sources]

        return list(self.articles)

    def _on_category_change(self, category: str) -> None:
        self._selected_category = category
        self._update_tab_style()
        self._refresh_article_list()
        self._detail_title.configure(text="请选择左侧文章查看详情")
        self._detail_meta.configure(text="")
        self._detail_text.configure(state="normal")
        self._detail_text.delete("1.0", END)
        self._detail_text.configure(state="disabled")

    def _update_tab_style(self) -> None:
        for btn, cat in self._tab_buttons:
            if cat == self._selected_category:
                btn.configure(bg="#eff6ff", fg="#2563eb",
                              font=("Microsoft YaHei UI", 10, "bold"))
            else:
                btn.configure(bg="white", fg="#64748b",
                              font=("Microsoft YaHei UI", 10))

    def _on_article_select(self, event) -> None:
        selection = self._article_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if not hasattr(self, "_filtered_articles"):
            return
        if idx >= len(self._filtered_articles):
            return

        article = self._filtered_articles[idx]

        self._detail_title.configure(text=article.title)

        date_str = article.date.strftime("%Y-%m-%d") if article.date else "未知日期"
        meta = f"来源：{article.source} | 发布时间：{date_str}"
        if article.images:
            meta += f" | {len(article.images)} 图"
        if article.attachments:
            meta += f" | {len(article.attachments)} 附件"
        self._detail_meta.configure(text=meta)

        self._detail_text.configure(state="normal")
        self._detail_text.delete("1.0", END)

        content = article.content or "暂无正文内容"
        content = re.sub(r"<[^>]+>", "", content)
        content = re.sub(r"&nbsp;", " ", content)
        content = re.sub(r"\s+", "\n\n", content).strip()

        self._detail_text.insert("1.0", content)
        self._detail_text.configure(state="disabled")

    def _on_open_report(self) -> None:
        html_path = os.path.join(_get_output_dir(), "采集报告.html")
        if os.path.exists(html_path):
            webbrowser.open(f"file:///{html_path}")
        else:
            self._log("报告文件不存在，请先采集")
