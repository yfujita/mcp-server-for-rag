import logging
import httpx
import asyncio
from datetime import datetime, timezone
from typing import Any

from .base import SessionStore

logger = logging.getLogger(__name__)

class ElasticsearchSessionStore(SessionStore):
    def __init__(self, es_url: str, index_name: str = "system-chat-sessions"):
        self.es_url = es_url.rstrip("/")
        self.index_name = index_name

    async def initialize(self) -> None:
        await self._wait_for_cluster_ready()

        """インデックスの存在確認と作成"""
        async with httpx.AsyncClient() as client:
            try:
                # HEADリクエストで存在確認
                resp = await client.head(f"{self.es_url}/{self.index_name}")
                if resp.status_code == 404:
                    logger.info(f"Creating index: {self.index_name}")
                    # マッピング定義
                    mapping = {
                        "mappings": {
                            "properties": {
                                "session_id": {"type": "keyword"},
                                "messages": {
                                    "type": "object",
                                    "enabled": False  # 中身は検索不要なのでインデックス化しない
                                },
                                "updated_at": {"type": "date"}
                            }
                        }
                    }
                    await client.put(f"{self.es_url}/{self.index_name}", json=mapping)
                    logger.info(f"Index '{self.index_name}' created successfully.")
                else:
                    logger.info(f"Index '{self.index_name}' already exists.")
            except Exception as e:
                logger.error(f"Failed to initialize Elasticsearch store: {e}")

    async def load_history(self, session_id: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{self.es_url}/{self.index_name}/_doc/{session_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("_source", {}).get("messages", [])
                elif resp.status_code == 404:
                    return []
                else:
                    logger.error(f"Error loading history: {resp.status_code} {resp.text}")
                    return []
            except Exception as e:
                logger.error(f"Exception loading history: {e}")
                return []

    async def save_history(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        doc = {
            "session_id": session_id,
            "messages": messages,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # session_id をドキュメントIDとして保存（上書き）
                resp = await client.put(f"{self.es_url}/{self.index_name}/_doc/{session_id}", json=doc)
                if resp.status_code not in [200, 201]:
                    logger.error(f"Error saving history: {resp.status_code} {resp.text}")
            except Exception as e:
                logger.error(f"Exception saving history: {e}")
    
    async def _wait_for_cluster_ready(self, max_retries: int = 60, interval: int = 2):
        """ElasticsearchのステータスがYellow以上になるまで待機"""
        logger.info(f"Waiting for Elasticsearch at {self.es_url}...")
        
        async with httpx.AsyncClient() as client:
            for i in range(max_retries):
                try:
                    # wait_for_status=yellow: ステータスがyellowになるまでES側で待ってもらう
                    # timeout=10s: ES側での最大待機時間
                    resp = await client.get(
                        f"{self.es_url}/_cluster/health?wait_for_status=yellow&timeout=10s",
                        timeout=15.0  # httpx側のタイムアウト（ES側より少し長くする）
                    )
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        status = data.get("status")
                        logger.info(f"Elasticsearch cluster is ready (status: {status}).")
                        return
                    else:
                        logger.warning(f"Waiting for Elasticsearch... (status code: {resp.status_code})")

                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    # まだ起動中で接続すらできない場合
                    logger.warning(f"Waiting for Elasticsearch connection... ({type(e).__name__})")
                except Exception as e:
                    logger.error(f"Unexpected error while waiting for ES: {e}")

                # リトライ待機
                await asyncio.sleep(interval)
            
            # ループを抜けた＝タイムアウト
            raise Exception("Timed out waiting for Elasticsearch to be ready.")