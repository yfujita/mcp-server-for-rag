from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Document:
    """
    Elasticsearchに保存されるドキュメントのエンティティ。
    """
    url: str
    title: str
    content: Optional[str]
    content_length: int
    mime_type: str
    timestamp: str

    def to_dict(self):
        """
        ドキュメントエンティティを辞書形式に変換します。
        """
        return asdict(self)
