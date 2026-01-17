import json
import logging
from typing import AsyncGenerator

from mcp import ClientSession

from ..clients.llm.factory import llm_client
from ..clients.mcp_client import mcp_client
from ..stores.session.base import SessionStore
# 型判定のためにインポート
from ..clients.llm.base import StreamContentEvent, StreamToolCallEvent

logger = logging.getLogger(__name__)

# システムプロンプト定義
SYSTEM_PROMPT = {
    "role": "system",
    "content": """
        あなたは検索拡張生成（RAG）機能を備えたAIアシスタントです。
        ユーザーの質問に対して、必ず提供されたツールを使用して情報を検索・取得し、その事実に基づいて回答してください。
        自身の知識のみで推測して回答することは避けてください。

        ## 思考と行動のプロセス
        1. **情報探索**: まず `list_indexes` 等で利用可能なインデックスを確認し、適切な対象に対して検索を実行してください。検索結果中のhighlightは部分的なコンテンツなのでそのまま情報源にしないでください。
        2. **詳細確認**: 検索結果から関連性の高いドキュメントを特定し、その内容を取得して詳細を確認してください。
        3. **情報再取得**: まだ情報が不足している場合は、必要に応じてページングやクエリを変えるなどして再度検索を実行してください。
        4. **回答生成**: 収集した情報のみを根拠として回答を作成してください。

        ## 回答のガイドライン
        - **フォーマット**: 回答はMarkdown形式で見やすく整理してください（見出し、箇条書き等を活用）。
        - **正確性**: 検索結果にない情報は「情報が見つかりませんでした」と正直に伝えてください。事実を捏造しないでください。
        - **引用**: 可能であれば、情報の出典（ドキュメント名など）を明記してください。
        """
}

class ChatService:
    def __init__(self, session_store: SessionStore):
        self.session_store = session_store

    async def process_chat(self, session_id: str, user_message: str) -> AsyncGenerator[str, None]:
        # --- セッションIDをクライアントに通知 ---
        yield self._create_sse_event("session_id", {"session_id": session_id})

        # 1. 履歴のロード & ユーザー発話追加
        history = await self.session_store.load_history(session_id)
        if not history:
            history = [SYSTEM_PROMPT]
        
        history.append({"role": "user", "content": user_message})
        await self.session_store.save_history(session_id, history)

        # 最大ループ回数（無限ループ防止）
        MAX_STEPS = 20

        try:
            async with mcp_client.create_client_context() as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    mcp_tools = await mcp_client.get_available_tools(session)
                    llm_tools = llm_client.convert_tools(mcp_tools)

                    # === ReActループ開始 ===
                    for step in range(MAX_STEPS):
                        logger.info(f"Step {step + 1}/{MAX_STEPS}")

                        hybrid_stream = llm_client.create_chat_stream(
                            messages=history,
                            tools=llm_tools
                        )
                        
                        assistant_response_content = ""
                        tool_response_obj = None

                        async for event in hybrid_stream:
                            if event.type == "content":
                                # テキスト生成中
                                content_chunk = event.delta
                                assistant_response_content += content_chunk
                                yield self._create_sse_event("message", {"content": content_chunk})
                            elif event.type == "tool_call":
                                # ツール実行オブジェクト (ストリーム完了時に1回だけ来る)
                                tool_response_obj = event.response

                        # ツール実行が必要だった場合
                        if tool_response_obj:
                            # 1. 履歴に追加 (raw_message)
                            history.append(tool_response_obj.raw_message)

                            # 2. ツール実行ループ
                            # tool_response_obj.tool_calls が None の可能性も考慮して安全にアクセス
                            tool_calls = tool_response_obj.tool_calls or []
                            
                            for tool_call in tool_calls:
                                func_name = tool_call.name
                                func_args = tool_call.arguments
                                
                                # UI通知: ツール実行開始
                                yield self._create_sse_event("status", {
                                    "status": "tool_call", 
                                    "tool": func_name, 
                                    "args": func_args
                                })
                                
                                # ツール実行
                                tool_result_text = await mcp_client.execute_tool(session, func_name, func_args)
                                
                                # 結果を履歴に追加
                                history.append({
                                    "tool_call_id": tool_call.id,
                                    "role": "tool",
                                    "name": func_name,
                                    "content": tool_result_text
                                })
                            
                            # ツール実行後は、continueして再度LLMに「この結果を見てどうする？」と問いかける
                            continue

                        else:
                            # --- ケースB: ツール実行不要（最終回答） ---
                            # 最終回答を履歴に保存して終了
                            if assistant_response_content:
                                history.append({"role": "assistant", "content": assistant_response_content})
                                await self.session_store.save_history(session_id, history)
                            
                            # 回答完了したらループを抜ける
                            break
                    
                    else:
                        # breakされずにループが終わった場合（回数制限到達）
                        logger.warning("Max steps reached.")
                        fallback_msg = "\n(処理ステップ数の上限に達したため、処理を中断しました。)"
                        assistant_response_content += fallback_msg
                        yield self._create_sse_event("message", {"content": fallback_msg})

            yield self._create_sse_event("done", {})

        except Exception as e:
            logger.error(f"Error in chat processing: {e}", exc_info=True)
            yield self._create_sse_event("error", {"error": str(e)})

    def _create_sse_event(self, event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"