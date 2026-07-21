"""启动入口：支持命令行模式和图形化界面模式。"""

import sys

from .cli import main as cli_main


def main() -> None:
    """根据参数选择启动方式：无参数时启动图形化界面，有参数时使用命令行模式。"""
    if len(sys.argv) == 1:
        try:
            from .gui import main as gui_main
            gui_main()
        except ImportError:
            cli_main()
    else:
        cli_main()


if __name__ == "__main__":
    main()