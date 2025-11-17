#!/usr/bin/env python3

import asyncio
import httpx
import json

async def test_mcp_server():
    """Test the MCP server with streamable HTTP"""
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        # 初期化リクエスト
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {
                        "listChanged": True
                    },
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        print("Sending initialize request...")
        print(json.dumps(init_request, indent=2))
        
        try:
            response = await client.post(
                base_url,
                json=init_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
            
            print(f"\nResponse Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            if response.content:
                print(f"Response Body: {response.text}")
                
                if response.status_code == 200:
                    # ツール一覧を取得
                    tools_request = {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/list"
                    }
                    
                    print("\nSending tools/list request...")
                    tools_response = await client.post(
                        base_url,
                        json=tools_request,
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json"
                        }
                    )
                    
                    print(f"Tools Response Status: {tools_response.status_code}")
                    if tools_response.content:
                        print(f"Tools Response: {tools_response.text}")
            else:
                print("Empty response body")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_mcp_server())
