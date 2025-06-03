import json
import traceback
from typing import Any, Dict, List, Optional, Union

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from .elasticsearch_client import ElasticsearchClient
from .tools import handle_tool_list, handle_tool_call
from .resources import ReadResourceResult, ResourceContent, handle_resource_list, handle_resource_read

class InitializeResult(BaseModel):
    """
    MCPサーバーの初期化結果を表すPydanticモデル。
    プロトコルバージョン、サーバーの機能、サーバー情報、および指示を含みます。
    """
    protocolVersion: str
    capabilities: Dict[str, Any]
    serverInfo: Dict[str, str]
    instructions: Optional[str] = None

# JSON-RPCのためのPydanticモデル定義
class JsonRpcRequest(BaseModel):
    """
    JSON-RPC 2.0リクエストを表すPydanticモデル。
    """
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Union[Dict[str, Any], List[Any]]] = None
    id: Optional[Union[int, str]] = None

class JsonRpcResponse(BaseModel):
    """
    JSON-RPC 2.0レスポンスを表すPydanticモデル。
    """
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[int, str]] = None

class JsonRpcError(BaseModel):
    """
    JSON-RPC 2.0エラーを表すPydanticモデル。
    """
    code: int
    message: str
    data: Optional[Any] = None

def _create_json_rpc_error_response(
    request_id: Optional[Union[int, str]],
    code: int,
    message: str,
    status_code: int,
    data: Optional[Any] = None
) -> JSONResponse:
    """
    JSON-RPCエラーレスポンスを生成します。
    """
    error_obj = JsonRpcError(code=code, message=message, data=data).model_dump()
    return JSONResponse(JsonRpcResponse(id=request_id, error=error_obj).model_dump(), status_code=status_code)

async def _handle_initialize(request_id: Optional[Union[int, str]], app_version: str) -> JSONResponse:
    """
    'initialize' メソッドのリクエストを処理します。
    """
    server_capabilities = {
        "resources": {"supported": False, "listChanged": False, "subscribe": False},
        "tools": {"supported": True, "listChanged": False},
        "prompts": {"supported": False}
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
    return JSONResponse(JsonRpcResponse(id=request_id, result=initialize_result.model_dump()).model_dump())

async def _handle_tools_list(request_id: Optional[Union[int, str]]) -> JSONResponse:
    """
    'tools/list' メソッドのリクエストを処理します。
    """
    return JSONResponse(JsonRpcResponse(id=request_id, result=handle_tool_list().model_dump()).model_dump())

async def _handle_tools_call(
    request_id: Optional[Union[int, str]],
    params: Optional[Union[Dict[str, Any], List[Any]]],
    es_client: ElasticsearchClient
) -> JSONResponse:
    """
    'tools/call' メソッドのリクエストを処理します。
    """
    if not isinstance(params, dict) or "name" not in params or "arguments" not in params:
        return _create_json_rpc_error_response(request_id, -32602, "Invalid params for tools/call. Expected 'name' and 'arguments'.", 400)

    tool_name = params.get("name")
    arguments = params.get("arguments")

    try:
        result = handle_tool_call(es_client, tool_name, arguments)
        return JSONResponse(JsonRpcResponse(id=request_id, result=result).model_dump())
    except ValueError as e:
        return _create_json_rpc_error_response(request_id, -32601, str(e), 404)
    except Exception as e:
        error_message = f"Internal server error during tool call: {str(e)}\n{traceback.format_exc()}"
        print(error_message, flush=True)
        return _create_json_rpc_error_response(request_id, -32603, error_message, 500)

async def _handle_resources_list(request_id: Optional[Union[int, str]]) -> JSONResponse:
    """
    'resources/list' メソッドのリクエストを処理します。
    """
    return JSONResponse(JsonRpcResponse(id=request_id, result=handle_resource_list().model_dump()).model_dump())

async def _handle_resources_read(
    request_id: Optional[Union[int, str]],
    params: Optional[Union[Dict[str, Any], List[Any]]]
) -> JSONResponse:
    """
    'resources/read' メソッドのリクエストを処理します。
    """
    if not isinstance(params, dict) or "uri" not in params:
        return _create_json_rpc_error_response(request_id, -32602, "Invalid params for resources/read. Expected 'uri'.", 400)

    resource_uri = params.get("uri")
    resource_content = handle_resource_read(resource_uri)

    status_code = 200
    if resource_content.isError:
        if resource_content.error and resource_content.error.get("code") == -32000:
            status_code = 404
        elif resource_content.error and resource_content.error.get("code") == -32602:
            status_code = 400
        else:
            status_code = 500

    return JSONResponse(JsonRpcResponse(id=request_id, result=ReadResourceResult(contents=[resource_content]).model_dump()).model_dump(), status_code=status_code)

async def handle_mcp_request(request: Request, es_client: ElasticsearchClient, app_version: str) -> JSONResponse:
    """
    MCPツールとリソースのためのJSON-RPC 2.0リクエストを処理します。
    """
    request_id: Optional[Union[int, str]] = None
    try:
        body = await request.json()
        rpc_request = JsonRpcRequest(**body)
        request_id = rpc_request.id

        if rpc_request.jsonrpc != "2.0":
            return _create_json_rpc_error_response(request_id, -32600, "Invalid Request: jsonrpc must be '2.0'", 400)

        print(f"Received JSON-RPC request: {rpc_request.method} with params: {rpc_request.params}", flush=True)

        if rpc_request.method == "initialize":
            return await _handle_initialize(request_id, app_version)
        elif rpc_request.method == "initialized":
            return JSONResponse({})
        elif rpc_request.method == "tools/list":
            return await _handle_tools_list(request_id)
        elif rpc_request.method == "tools/call":
            return await _handle_tools_call(request_id, rpc_request.params, es_client)
        elif rpc_request.method == "resources/list":
            return await _handle_resources_list(request_id)
        elif rpc_request.method == "resources/read":
            return await _handle_resources_read(request_id, rpc_request.params)
        else:
            return _create_json_rpc_error_response(request_id, -32601, f"Method '{rpc_request.method}' not found", 404)

    except json.JSONDecodeError:
        return _create_json_rpc_error_response(None, -32700, "Parse error", 400)
    except ValidationError as e:
        return _create_json_rpc_error_response(request_id, -32602, f"Invalid Request params: {e.errors()}", 400)
    except Exception as e:
        error_message = f"Internal server error: {str(e)}\n{traceback.format_exc()}"
        print(error_message, flush=True)
        return _create_json_rpc_error_response(request_id, -32603, error_message, 500)
