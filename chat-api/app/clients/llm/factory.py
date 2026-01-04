import logging
from .base import LLMClient
from .openai import OpenAIClient
# from .claude import ClaudeClient  # 将来の実装

logger = logging.getLogger(__name__)

def get_llm_client() -> LLMClient:
    """設定に基づいて適切なLLMクライアントを返す"""
    # ここで環境変数 LLM_PROVIDER などを判定しても良い
    # provider = os.getenv("LLM_PROVIDER", "openai")
    
    # if provider == "claude":
    #     return ClaudeClient()
    
    return OpenAIClient()

# シングルトンとしてエクスポート
llm_client = get_llm_client()