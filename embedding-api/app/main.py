from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from openai import OpenAI
import os

app = FastAPI()

# API Keyは環境変数から取得
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

class EmbedRequest(BaseModel):
    texts: List[str]

class EmbedResponse(BaseModel):
    embeddings: List[List[float]]

@app.post("/embed/text-embedding-3-small", response_model=EmbedResponse)
async def create_embeddings(request: EmbedRequest):
    try:
        # text-embedding-3-small を使用
        response = client.embeddings.create(
            input=request.texts,
            model="text-embedding-3-small"
        )
        # 順序通りにベクトルを抽出
        embeddings = [data.embedding for data in response.data]
        return EmbedResponse(embeddings=embeddings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))