from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class TextContent(BaseModel):
    type: str = "text"
    text: str

class ResourceContent(BaseModel):
    uri: str
    mimeType: Optional[str] = None
    text: Optional[str] = None
    blob: Optional[str] = None # base64エンコードされたバイナリデータ用
    isError: Optional[bool] = None
    error: Optional[Dict[str, Any]] = None # ErrorObject

class Resource(BaseModel):
    uri: str
    mimeType: str
    # annotations, examples は今回は省略

class ResourceListResult(BaseModel):
    resources: List[Resource]

class ReadResourceResult(BaseModel):
    contents: List[ResourceContent]

def handle_resource_list() -> ResourceListResult:
    """
    利用可能なリソースをリストします。
    Lists available resources.
    """
    # 現時点では動的にリソースをリストアップする機能はないため、空のリストを返します。
    return ResourceListResult(resources=[])

def handle_resource_read(resource_uri: str) -> ResourceContent:
    """
    リソースの読み込みを処理し、ResourceContentオブジェクトを返します。
    Handles resource read requests and returns a ResourceContent object.
    現在はリソースを提供しないため、エラーを返します。
    """
    return ResourceContent(
        uri=resource_uri,
        isError=True,
        error={"code": -32000, "message": f"Resource '{resource_uri}' not found or not supported."}
    )
