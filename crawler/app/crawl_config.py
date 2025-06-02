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

if __name__ == "__main__":
    # Example usage:
    # Create a dummy config.yaml for testing
    dummy_config_content = """
    start_urls:
      - http://example.com
      - http://another.example.org
    allowed_domains:
      - example.com
      - another.example.org
    target_url_patterns:
      - ".*\\.html$"
    exclude_url_patterns:
      - ".*\\.pdf$"
    max_depth: 3
    delay: 0.5
    user_agent: "MyCustomCrawler/1.0"
    """
    with open("crawler_config.yaml", "w", encoding="utf-8") as f:
        f.write(dummy_config_content)

    config = CrawlerConfig.from_yaml("crawler_config.yaml")
    print(f"Start URLs: {config.start_urls}", flush=True)
    print(f"Allowed Domains: {config.allowed_domains}", flush=True)
    print(f"Target URL Patterns: {config.target_url_patterns}", flush=True)
    print(f"Exclude URL Patterns: {config.exclude_url_patterns}", flush=True)
    print(f"Max Depth: {config.max_depth}", flush=True)
    print(f"Delay: {config.delay}", flush=True)
    print(f"User Agent: {config.user_agent}", flush=True)
