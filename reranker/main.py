from fastapi import FastAPI
from sentence_transformers import CrossEncoder
from pydantic import BaseModel

app = FastAPI()
model = CrossEncoder("Qwen/Qwen3-Reranker-0.6B", trust_remote_code=True)

class RerankRequest(BaseModel):
    query: str
    documents: list[str]
    top_k: int = 5

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/rerank")
def rerank(req: RerankRequest):
    pairs = [[req.query, doc] for doc in req.documents]
    scores = model.predict(pairs).tolist()
    
    ranked = sorted(
        zip(scores, req.documents),
        key=lambda x: x[0],
        reverse=True
    )[:req.top_k]
    
    return {
        "results": [
            {"score": score, "document": doc}
            for score, doc in ranked
        ]
    }