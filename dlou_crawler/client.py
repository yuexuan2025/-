"""HTTP 客户端：请求页面、自动重试、智能重定向。

重定向策略：
- 允许：http→https、站内路径跳转（如 .htm→.psp）
- 拦截：CAS 登录、外站跳转等需要登录或跳出学校域名的重定向
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
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


class _SmartRedirect(HTTPRedirectHandler):
    """智能重定向：允许站内和 https 升级，拦截登录和外站。"""

    max_redirects = 3

    def __init__(self) -> None:
        super().__init__()
        self._count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if self._count >= self.max_redirects:
            return None
        self._count += 1

        old = urlsplit(req.full_url)
        new = urlsplit(urljoin(req.full_url, newurl))

        # 拦截 CAS 登录
        if "cas/login" in new.path or "portal.dlou.edu.cn" in new.netloc:
            return None

        # 允许：同域名或子域名（学校域名内）
        old_host = old.netloc.lower()
        new_host = new.netloc.lower()
        is_same_domain = (
            old_host == new_host
            or (old_host.endswith(".dlou.edu.cn") and new_host.endswith(".dlou.edu.cn"))
            or (not old_host and new_host.endswith(".dlou.edu.cn"))
        )

        # 允许：http→https 升级
        is_https_upgrade = (
            old.scheme == "http"
            and new.scheme == "https"
            and old_host == new_host
        )

        if is_same_domain or is_https_upgrade:
            # 用新的 Request 跟随重定向
            new_req = Request(
                urlunsplit(new),
                headers={"User-Agent": req.get_header("User-Agent")},
                origin_req_host=req.origin_req_host,
            )
            return new_req

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
            self._local.opener = build_opener(_SmartRedirect())
        return self._local.opener

    def get_text(self, url: str) -> str:
        def _fetch(u):
            self._wait()
            request = Request(u, headers={"User-Agent": self.user_agent})
            try:
                response = self._opener.open(request, timeout=self.timeout)
            except HTTPError as error:
                if 300 <= error.code < 400:
                    location = error.headers.get("Location", "")
                    raise FetchError(f"页面重定向被拦截：{u} -> {location}") from error
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
