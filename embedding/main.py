from fastapi import FastAPI
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel

app = FastAPI()
model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B", trust_remote_code=True)

class EmbedRequest(BaseModel):
    texts: list[str]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/embed")
def embed(req: EmbedRequest):
    vectors = model.encode(req.texts, normalize_embeddings=True).tolist()
    return {"embeddings": vectors, "dim": len(vectors[0])}