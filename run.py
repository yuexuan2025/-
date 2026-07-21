# -*- coding: utf-8 -*-
"""程序入口：启动图形界面。"""

from tkinter import Tk

from dlou_crawler.gui import CrawlerGUI


def main() -> None:
    root = Tk()
    CrawlerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
