"""HTTP 客户端：负责请求官网页面、自动重试、控制间隔与处理重定向。

仅依赖标准库（urllib）。
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

_T = TypeVar("_T")


class FetchError(RuntimeError):
    """请求失败或页面需要登录时抛出。"""
    pass


def _retry(func: Callable[[str], _T], url: str, retries: int = 2, base_delay: float = 2.0) -> _T:
    """调用 func(url)；遇到超时或网络错误时按指数退避自动重试，仍失败则抛 FetchError。"""
    last_exc = None
    for attempt in range(retries + 1):
        try:
            return func(url)
        except (OSError, TimeoutError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(base_delay * (attempt + 1))
    raise FetchError(f"{url} 在 {retries} 次重试后仍失败：{last_exc}") from last_exc


class _NoRedirect(HTTPRedirectHandler):
    """Do not follow redirects to login systems or other unexpected destinations."""

    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class HttpClient:
    """爬虫用的 HTTP 客户端。

    - 不强制遵守 robots.txt，请求间隔由 ``delay`` 控制（默认 0，即不限速）。
    - 遇到超时/网络错误会自动重试；超时固定 20 秒。
    - 不跟随会跳转到登录页的重定向，避免误采。
    """

    def __init__(self, user_agent: str, delay: float, timeout: int = 20) -> None:
        self.user_agent = user_agent
        self.delay = delay
        self.timeout = timeout
        self._last_request = 0.0
        self._opener = build_opener(_NoRedirect())

    def get_text(self, url: str) -> str:
        """抓取页面并按响应编码返回文本（失败自动重试）。"""
        def _fetch(u):
            response = self._open(u)
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                return response.read().decode(charset, errors="replace")
            finally:
                response.close()

        return _retry(_fetch, url, retries=2, base_delay=2.0)

    def download(self, url: str, destination: Path) -> None:
        """把附件下载到 destination（失败自动重试）。"""
        def _dl(u):
            response = self._open(u)
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("wb") as handle:
                    while chunk := response.read(64 * 1024):
                        handle.write(chunk)
            finally:
                response.close()

        _retry(_dl, url, retries=2, base_delay=2.0)

    def _open(self, url: str):
        """发起一次请求，把重定向到登录页等情况包装成 FetchError。"""
        self._wait()
        request = Request(url, headers={"User-Agent": self.user_agent})
        try:
            return self._opener.open(request, timeout=self.timeout)
        except (HTTPError, URLError, OSError) as error:
            if isinstance(error, HTTPError) and 300 <= error.code < 400:
                location = error.headers.get("Location", "未知地址")
                raise FetchError(f"页面重定向到登录或其他页面，未采集：{url} -> {location}") from error
            raise FetchError(f"无法访问 {url}：{error}") from error

    def _wait(self) -> None:
        """按 delay 控制两次请求之间的最短间隔。"""
        remaining = self.delay - (time.monotonic() - self._last_request)
        if remaining > 0:
            time.sleep(remaining)
        self._last_request = time.monotonic()
