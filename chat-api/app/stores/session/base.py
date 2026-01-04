from abc import ABC, abstractmethod
from typing import Any

class SessionStore(ABC):
    """セッション履歴管理の抽象基底クラス"""

    @abstractmethod
    async def initialize(self) -> None:
        """
        ストアの初期化処理。
        例: DB接続の確立、テーブルやインデックスの作成など。
        """
        pass

    @abstractmethod
    async def load_history(self, session_id: str) -> list[dict[str, Any]]:
        """
        指定されたセッションIDの会話履歴を取得する。
        """
        pass

    @abstractmethod
    async def save_history(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        """
        会話履歴を保存（上書き更新）する。
        """
        pass