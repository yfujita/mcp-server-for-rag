from pydantic import BaseModel, Field
from typing import List, Optional
import yaml

class CrawlerConfig(BaseModel):
    start_urls: List[str] = Field(..., description="クロールを開始するURLのリスト")
    allowed_domains: List[str] = Field(default_factory=list, description="クロールを許可するドメインのリスト")
    target_url_patterns: List[str] = Field(default_factory=list, description="クロール対象とするURLの正規表現リスト")
    exclude_url_patterns: List[str] = Field(default_factory=list, description="クロールから除外するURLの正規表現リスト")
    max_depth: int = Field(default=5, description="クロールの最大深度")
    delay: float = Field(default=1.0, description="リクエスト間の遅延時間（秒）")
    user_agent: str = Field(default="Mozilla/5.0 (compatible; MyCrawler/1.0)", description="User-Agent文字列")
    es_index: str = Field(..., description="Elasticsearchのインデックス名")
    es_index_description: str = Field(..., description="Elasticsearchインデックスの説明")
    max_documents: Optional[int] = Field(default=None, description="Elasticsearchに追加するドキュメントの最大数")

    @classmethod
    def from_yaml(cls, file_path: str):
        with open(file_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        return cls(**config_data)
