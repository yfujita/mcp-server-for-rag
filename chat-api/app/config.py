import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # MCPサーバーのURL
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-api:8000/mcp")
    # ESのURL
    ES_URL = os.getenv("ES_URL", "http://elasticsearch:9200")
    # 使用するLLMモデル
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
    # OpenAI APIキー
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# シングルトンインスタンス
config = Config()