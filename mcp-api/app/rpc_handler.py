import json
import traceback
from typing import Any, Dict, List, Optional, Union

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .elasticsearch_client import ElasticsearchClient
from .tools import handle_tool_list, handle_tool_call
from .resources import ReadResourceResult, ResourceContent, handle_resource_list, handle_resource_read

class InitializeResult(BaseModel):
    """
    MCPサーバーの初期化結果を表すPydanticモデル。
    プロトコルバージョン、サーバーの機能、サーバー情報、および指示を含みます。
    """
    protocolVersion: str # プロトコルバージョン
    capabilities: Dict[str, Any] # サーバーの機能 (ServerCapabilitiesオブジェクト)
    serverInfo: Dict[str, str] # サーバーの実装情報 (Implementationオブジェクト)
    instructions: Optional[str] = None # ユーザーへの追加指示

# JSON-RPCのためのPydanticモデル定義
class JsonRpcRequest(BaseModel):
    """
    JSON-RPC 2.0リクエストを表すPydanticモデル。
    """
    jsonrpc: str = "2.0" # JSON-RPCのバージョン
    method: str # 呼び出すメソッド名
    params: Optional[Union[Dict[str, Any], List[Any]]] = None # メソッドのパラメータ
    id: Optional[Union[int, str]] = None # リクエストID (オプション)

class JsonRpcResponse(BaseModel):
    """
    JSON-RPC 2.0レスポンスを表すPydanticモデル。
    """
    jsonrpc: str = "2.0" # JSON-RPCのバージョン
    result: Optional[Any] = None # 成功時の結果
    error: Optional[Dict[str, Any]] = None # エラー情報
    id: Optional[Union[int, str]] = None # リクエストID (オプション)

class JsonRpcError(BaseModel):
    """
    JSON-RPC 2.0エラーを表すPydanticモデル。
    """
    code: int # エラーコード
    message: str # エラーメッセージ
    data: Optional[Any] = None # エラーに関する追加データ (オプション)

async def handle_mcp_request(request: Request, es_client: ElasticsearchClient, app_version: str):
    """
    MCPツールとリソースのためのJSON-RPC 2.0リクエストを処理します。

    Args:
        request (Request): FastAPIのリクエストオブジェクト。
        es_client (ElasticsearchClient): Elasticsearchクライアントインスタンス。
        app_version (str): アプリケーションのバージョン。

    Returns:
        JSONResponse: JSON-RPC 2.0のレスポンス。
    """
    request_id: Optional[Union[int, str]] = None
    try:
        body = await request.json()
        rpc_request = JsonRpcRequest(**body)
        request_id = rpc_request.id

        # JSON-RPCバージョンが"2.0"であることを確認
        if rpc_request.jsonrpc != "2.0":
             return JSONResponse(JsonRpcResponse(id=request_id, error=JsonRpcError(code=-32600, message="Invalid Request: jsonrpc must be '2.0'").dict()).dict(), status_code=400)

        print(f"Received JSON-RPC request: {rpc_request.method} with params: {rpc_request.params}", flush=True)

        # メソッドに応じた処理の分岐
        if rpc_request.method == "initialize":
            # サーバーの初期化リクエスト
            server_capabilities = {
                "resources": {"supported": False, "listChanged": False, "subscribe": False}, # リソースはサポートしない設定
                "tools": {"supported": True, "listChanged": False}, # ツールはサポートする設定
                "prompts": {"supported": False} # プロンプトはサポートしない設定
            }
            server_info = {
                "name": "RAG MCP Server",
                "version": app_version
            }
            initialize_result = InitializeResult(
                protocolVersion="2025-03-26",
                capabilities=server_capabilities,
                serverInfo=server_info,
                instructions="This server provides tools for searching documents and getting document content by ID. Use the 'search' tool to find documents by keyword. Use the 'get_document_by_id' tool to retrieve the full content of a document."
            )
            return JSONResponse(JsonRpcResponse(id=request_id, result=initialize_result.dict()).dict())

        elif rpc_request.method == "initialized":
            # 初期化完了通知 (特に処理は不要)
            return JSONResponse({})

        elif rpc_request.method == "tools/list":
            # ツールリストのリクエスト
            return JSONResponse(JsonRpcResponse(id=request_id, result=handle_tool_list().dict()).dict())

        elif rpc_request.method == "tools/call":
            # ツール呼び出しのリクエスト
            print('Received tools/call request:', rpc_request.params)
            # パラメータの検証
            if not isinstance(rpc_request.params, dict) or "name" not in rpc_request.params or "arguments" not in rpc_request.params:
                return JSONResponse(JsonRpcResponse(id=request_id, error=JsonRpcError(code=-32602, message="Invalid params for tools/call. Expected 'name' and 'arguments'.").dict()).dict(), status_code=400)

            tool_name = rpc_request.params.get("name")
            arguments = rpc_request.params.get("arguments")

            try:
                # ツールの呼び出し
                result = handle_tool_call(es_client, tool_name, arguments)
                return JSONResponse(JsonRpcResponse(id=request_id, result=result).dict())
            except ValueError as e:
                # ツールが見つからない、または引数が不正な場合
                return JSONResponse(JsonRpcResponse(id=request_id, error=JsonRpcError(code=-32601, message=str(e)).dict()).dict(), status_code=404)
            except Exception as e:
                # その他の内部サーバーエラー
                error_message = f"Internal server error during tool call: {str(e)}\n{traceback.format_exc()}"
                print(error_message, flush=True) # エラーメッセージとスタックトレースをログに出力
                return JSONResponse(JsonRpcResponse(id=request_id, error=JsonRpcError(code=-32603, message=error_message).dict()).dict(), status_code=500)

        elif rpc_request.method == "resources/list":
            # リソースリストのリクエスト
            return JSONResponse(JsonRpcResponse(id=request_id, result=handle_resource_list().dict()).dict())

        elif rpc_request.method == "resources/read":
            # リソース読み込みのリクエスト
            # パラメータの検証
            if not isinstance(rpc_request.params, dict) or "uri" not in rpc_request.params:
                return JSONResponse(JsonRpcResponse(id=request_id, error=JsonRpcError(code=-32602, message="Invalid params for resources/read. Expected 'uri'.").dict()).dict(), status_code=400)

            resource_uri = rpc_request.params.get("uri")
            resource_content = handle_resource_read(resource_uri)
            # リソースの内容に基づいてHTTPステータスコードを決定
            return JSONResponse(JsonRpcResponse(id=request_id, result=ReadResourceResult(contents=[resource_content]).dict()).dict(), status_code=200 if not resource_content.isError else (404 if resource_content.error and resource_content.error.get("code") == -32000 else (400 if resource_content.error and resource_content.error.get("code") == -32602 else 500)))

        else:
            # 未知のメソッド
            return JSONResponse(JsonRpcResponse(id=request_id, error=JsonRpcError(code=-32601, message=f"Method '{rpc_request.method}' not found").dict()).dict(), status_code=404)

    except json.JSONDecodeError:
        # JSONパースエラー
        return JSONResponse(JsonRpcResponse(id=None, error=JsonRpcError(code=-32700, message="Parse error").dict()).dict(), status_code=400)
    except Exception as e:
        # その他の予期せぬエラー
        error_message = f"Internal server error: {str(e)}\n{traceback.format_exc()}"
        print(error_message, flush=True) # エラーメッセージとスタックトレースをログに出力
        return JSONResponse(JsonRpcResponse(id=request_id, error=JsonRpcError(code=-32603, message=error_message).dict()).dict(), status_code=500)
