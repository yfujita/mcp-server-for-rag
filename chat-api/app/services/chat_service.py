import json
import logging
from typing import AsyncGenerator

from mcp import ClientSession

from ..clients.llm.factory import llm_client
from ..clients.mcp_client import mcp_client
from ..stores.session.base import SessionStore

logger = logging.getLogger(__name__)

# システムプロンプト定義
SYSTEM_PROMPT = {
    "role": "system",
    "content": """
        あなたはアシスタントです。ユーザーの質問に対して、提供された検索ツールを使用して情報を探し、質問に対して回答してください。
        手順は以下。
          1. インデックスの一覧を取得し、どのインデックスが質問に関連しそうかを判断します。
          2. 関連しそうなインデックスに対して検索を実行し、関連ドキュメントを見つけます。
          3. 関連ドキュメントの内容を取得します。関連しそうだと判断したドキュメントは全て取得して内容を確認してください。
          4. 回答するのに十分な情報が含まれていたら回答を生成。不足している場合は、追加でドキュメント取得や検索を行い、情報を補完します。
        回答は分かりやすく具体的に詳細に行い、必要に応じてサンプルや引用を含めてください。
        """
}

class ChatService:
    def __init__(self, session_store: SessionStore):
        self.session_store = session_store

    async def process_chat(self, session_id: str, user_message: str) -> AsyncGenerator[str, None]:
        
        # 1. 履歴のロード & ユーザー発話追加
        history = await self.session_store.load_history(session_id)
        if not history:
            history = [SYSTEM_PROMPT]
        
        history.append({"role": "user", "content": user_message})
        await self.session_store.save_history(session_id, history)

        assistant_response_content = ""
        
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

                        # 2. LLM推論 (Tool Call判定)
                        # ここで現在のhistory(ツール実行結果含む)を元に次の行動を決定
                        llm_response = await llm_client.create_completion(
                            messages=history,
                            tools=llm_tools
                        )

                        # 思考過程を履歴に追加
                        # (openai_client.pyの修正で raw_message は辞書化されている前提)
                        history.append(llm_response.raw_message)

                        if llm_response.tool_calls:
                            # --- ケースA: ツール実行が必要 ---
                            
                            for tool_call in llm_response.tool_calls:
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
                            
                            # ストリーミング生成
                            stream = llm_client.create_streaming_completion(history)
                            
                            async for content_chunk in stream:
                                assistant_response_content += content_chunk
                                yield self._create_sse_event("message", {"content": content_chunk})
                            
                            # 回答完了したらループを抜ける
                            break
                    
                    else:
                        # breakされずにループが終わった場合（回数制限到達）
                        logger.warning("Max steps reached.")
                        fallback_msg = "\n(処理ステップ数の上限に達したため、処理を中断しました。)"
                        assistant_response_content += fallback_msg
                        yield self._create_sse_event("message", {"content": fallback_msg})

            # 5. 完了後に履歴を更新して保存
            if assistant_response_content:
                history.append({"role": "assistant", "content": assistant_response_content})
                await self.session_store.save_history(session_id, history)
            
            yield self._create_sse_event("done", {})

        except Exception as e:
            logger.error(f"Error in chat processing: {e}", exc_info=True)
            yield self._create_sse_event("error", {"error": str(e)})

    def _create_sse_event(self, event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"