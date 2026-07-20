"""采集结果的数据模型：文章与附件。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class Attachment:
    """文章中的附件（如 PDF、Word），local_path 为下载后的本地路径。"""

    name: str
    url: str
    local_path: str | None = None


@dataclass(slots=True)
class Article:
    """一篇采集到的文章及其元信息。"""

    title: str
    url: str
    category: str
    published_at: str | None
    content: str
    attachments: list[Attachment] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
