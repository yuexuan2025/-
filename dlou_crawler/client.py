"""HTTP 客户端：请求页面、自动重试、控制间隔。"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

_T = TypeVar("_T")


class FetchError(RuntimeError):
    pass


def _retry(func: Callable[[str], _T], url: str, retries: int = 2, base_delay: float = 1.5) -> _T:
    last_exc = None
    for attempt in range(retries + 1):
        try:
            return func(url)
        except (OSError, TimeoutError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(base_delay * (2 ** attempt))
    raise FetchError(f"{url} 在 {retries} 次重试后仍失败：{last_exc}") from last_exc


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class HttpClient:
    def __init__(self, user_agent: str, delay: float, timeout: int = 20) -> None:
        self.user_agent = user_agent
        self.delay = delay
        self.timeout = timeout
        self._last_request = 0.0
        self._wait_lock = threading.Lock()
        self._local = threading.local()

    @property
    def _opener(self):
        if not hasattr(self._local, "opener"):
            self._local.opener = build_opener(_NoRedirect())
        return self._local.opener

    def get_text(self, url: str) -> str:
        def _fetch(u):
            self._wait()
            request = Request(u, headers={"User-Agent": self.user_agent})
            try:
                response = self._opener.open(request, timeout=self.timeout)
            except HTTPError as error:
                if 300 <= error.code < 400:
                    location = error.headers.get("Location", "未知地址")
                    raise FetchError(f"页面重定向：{u} -> {location}") from error
                raise FetchError(f"无法访问 {u}：HTTP {error.code}") from error
            except URLError as error:
                raise FetchError(f"无法访问 {u}：{error.reason}") from error

            charset = response.headers.get_content_charset() or "utf-8"
            try:
                return response.read().decode(charset, errors="replace")
            finally:
                response.close()

        return _retry(_fetch, url, retries=2, base_delay=1.5)

    def download(self, url: str, destination: Path) -> None:
        def _dl(u):
            self._wait()
            request = Request(u, headers={"User-Agent": self.user_agent})
            try:
                response = self._opener.open(request, timeout=self.timeout)
            except (HTTPError, URLError) as error:
                raise FetchError(f"下载失败 {u}：{error}") from error

            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                with destination.open("wb") as handle:
                    while chunk := response.read(64 * 1024):
                        handle.write(chunk)
            finally:
                response.close()

        _retry(_dl, url, retries=2, base_delay=1.5)

    def _wait(self) -> None:
        with self._wait_lock:
            remaining = self.delay - (time.monotonic() - self._last_request)
            if remaining > 0:
                time.sleep(remaining)
            self._last_request = time.monotonic()