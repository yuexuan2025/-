import threading
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit, urljoin, urlunsplit
from urllib.error import URLError, HTTPError


ALLOWED_HOSTS = frozenset({
    "www.dlou.edu.cn", "news.dlou.edu.cn",
    "life.dlou.edu.cn", "hhxy.dlou.edu.cn", "food.dlou.edu.cn",
    "tmgc.dlou.edu.cn", "jixie.dlou.edu.cn", "sea.dlou.edu.cn",
    "xxgc.dlou.edu.cn", "jjgl.dlou.edu.cn", "fxy.dlou.edu.cn",
    "wgy.dlou.edu.cn", "zwhzbx.dlou.edu.cn", "mks.dlou.edu.cn",
    "jxjyxy.dlou.edu.cn", "gzy.dlou.edu.cn", "master.dlou.edu.cn",
    "tyxy.dlou.edu.cn", "jiuye.dlou.edu.cn", "jzszx.dlou.edu.cn",
})


class _SmartRedirect(HTTPRedirectHandler):
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

        if "cas/login" in new.path or "portal.dlou.edu.cn" in new.netloc:
            return None

        old_host = old.netloc.lower()
        new_host = new.netloc.lower()
        is_same_domain = (
            old_host == new_host
            or (old_host.endswith(".dlou.edu.cn") and new_host.endswith(".dlou.edu.cn"))
            or (not old_host and new_host.endswith(".dlou.edu.cn"))
        )

        is_https_upgrade = (
            old.scheme == "http"
            and new.scheme == "https"
            and old_host == new_host
        )

        if is_same_domain or is_https_upgrade:
            new_req = Request(
                urlunsplit(new),
                headers={"User-Agent": req.get_header("User-Agent")},
                origin_req_host=req.origin_req_host,
            )
            return new_req

        return None


class HttpClient:
    def __init__(self, timeout: int = 15) -> None:
        self._timeout = timeout
        self._local = threading.local()

    def _get_opener(self):
        if not hasattr(self._local, "opener"):
            handler = _SmartRedirect()
            self._local.opener = build_opener(handler)
        return self._local.opener

    def get(self, url: str, retries: int = 2) -> str:
        if not url:
            return ""

        parsed = urlsplit(url)
        host = parsed.netloc.lower()
        if not host.endswith(".dlou.edu.cn") and host != "dlou.edu.cn":
            return ""

        opener = self._get_opener()

        for attempt in range(retries + 1):
            try:
                req = Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                                      "Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                    },
                )
                with opener.open(req, timeout=self._timeout) as resp:
                    raw = resp.read()
                    for enc in ("utf-8", "gbk", "gb2312", "iso-8859-1"):
                        try:
                            return raw.decode(enc)
                        except UnicodeDecodeError:
                            continue
                    return raw.decode("utf-8", errors="ignore")
            except (URLError, HTTPError, TimeoutError, OSError):
                continue

        return ""
