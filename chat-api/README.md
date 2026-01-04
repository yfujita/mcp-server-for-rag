# chat-api

## Usage

### OpenAI API KEYの設定

`./openai_token.txt` にトークンを記載する。

### Send User Message

チャットメッセージを送る。
レスポンスはSSE形式でストリーミング。

```
curl -N -X POST http://localhost:8080/chat -H "Content-Type: application/json" -d '{
    "session_id": "test-session-000",
    "message": "質問文など"
}'
```