# scripts/seed_data.py
"""
Seed ~60-80 chunks tiếng Việt vào pgvector.
Chạy SAU KHI inference service và postgres đang chạy:
    python scripts/seed_data.py
"""
import asyncio
import uuid
import json
import httpx
import asyncpg

EMBEDDING_URL = "http://embedding:8001"
DATABASE_URL = "postgresql://app:12345678@postgres:5432/semantic_search"

# ─── 5 documents thực tế ───────────────────────────────────────────────────

DOCUMENTS = [
    {
        "title": "Giới thiệu về Vector Database",
        "category": "database",
        "tenant_id": "tenant_acme",
        "content": """
Vector database là hệ thống lưu trữ chuyên biệt được thiết kế để lưu trữ và truy vấn các vector embedding một cách hiệu quả.
Khác với cơ sở dữ liệu quan hệ truyền thống lưu trữ dữ liệu dạng bảng, vector database tổ chức dữ liệu theo không gian đa chiều.

Ứng dụng chính của vector database bao gồm tìm kiếm ngữ nghĩa, hệ thống gợi ý, nhận dạng hình ảnh và xử lý ngôn ngữ tự nhiên.
Các hệ thống phổ biến hiện nay gồm có Pinecone, Weaviate, Qdrant, Milvus và pgvector cho PostgreSQL.

pgvector là extension mã nguồn mở cho PostgreSQL, cho phép lưu trữ vector với số chiều tùy ý.
Extension này hỗ trợ hai loại index chính: IVFFlat phù hợp cho dataset lớn cần tốc độ cao,
và HNSW (Hierarchical Navigable Small World) cho độ chính xác cao hơn với tốc độ truy vấn tốt.

HNSW xây dựng một đồ thị phân cấp các vector, cho phép tìm kiếm láng giềng gần đúng (ANN) với độ phức tạp O(log n).
Tham số m xác định số kết nối mỗi node trong đồ thị, ef_construction ảnh hưởng đến chất lượng đồ thị khi build index.
Giá trị m=16 và ef_construction=64 là cấu hình cân bằng giữa tốc độ và độ chính xác cho hầu hết use case.

Cosine similarity là metric phổ biến nhất cho semantic search vì nó đo góc giữa hai vector, không phụ thuộc vào độ lớn.
Điều này đặc biệt hữu ích khi so sánh các đoạn văn có độ dài khác nhau.
""",
    },
    {
        "title": "Kiến trúc RAG - Retrieval Augmented Generation",
        "category": "llm",
        "tenant_id": "tenant_acme",
        "content": """
RAG (Retrieval Augmented Generation) là kỹ thuật kết hợp tìm kiếm thông tin với mô hình ngôn ngữ lớn để tạo ra câu trả lời chính xác hơn.
Thay vì chỉ dựa vào kiến thức được học trong quá trình huấn luyện, RAG cho phép model truy cập vào nguồn dữ liệu bên ngoài theo thời gian thực.

Pipeline RAG cơ bản gồm ba giai đoạn chính: indexing, retrieval và generation.
Giai đoạn indexing: tài liệu được chia thành các chunk nhỏ, mỗi chunk được chuyển thành vector embedding và lưu vào vector database.
Giai đoạn retrieval: câu hỏi của người dùng được embed, sau đó tìm kiếm các chunk liên quan nhất trong database.
Giai đoạn generation: các chunk liên quan được đưa vào context của LLM cùng với câu hỏi để tạo câu trả lời.

Chunking strategy ảnh hưởng lớn đến chất lượng retrieval. Chunk quá nhỏ mất context, chunk quá lớn làm loãng thông tin.
Kích thước chunk phổ biến là 256-512 token với overlap 10-20% để đảm bảo không mất thông tin ở ranh giới.

Advanced RAG bổ sung thêm các kỹ thuật như query rewriting, hypothetical document embedding (HyDE),
multi-query retrieval, và reranking để cải thiện chất lượng retrieval.
Reranker sử dụng cross-encoder model để đánh giá lại mức độ liên quan của từng candidate chunk với query.

Evaluation RAG thường dùng các metric: faithfulness (câu trả lời có dựa trên context không),
answer relevance (câu trả lời có liên quan đến câu hỏi không), và context precision/recall.
Framework RAGAS là công cụ phổ biến để đánh giá tự động pipeline RAG.
""",
    },
    {
        "title": "Qwen3 - Mô hình ngôn ngữ đa năng của Alibaba",
        "category": "llm",
        "tenant_id": "tenant_beta",
        "content": """
Qwen3 là thế hệ thứ ba của dòng mô hình ngôn ngữ lớn Qwen do Alibaba Cloud phát triển, được phát hành vào năm 2025.
Dòng Qwen3 bao gồm nhiều kích thước từ 0.6B đến 235B tham số, phù hợp với các use case khác nhau từ edge device đến server.

Qwen3-Embedding là mô hình chuyên biệt cho việc tạo vector embedding từ văn bản, hỗ trợ 100+ ngôn ngữ bao gồm tiếng Việt.
Mô hình tạo ra vector 2048 chiều, cao hơn OpenAI text-embedding-ada-002 (1536 chiều), cho phép biểu diễn ngữ nghĩa phong phú hơn.
Qwen3-Embedding đạt điểm cao trên benchmark MTEB (Massive Text Embedding Benchmark) cho nhiều ngôn ngữ châu Á.

Qwen3-Reranker là cross-encoder model được fine-tune để đánh giá mức độ liên quan giữa query và document.
Cross-encoder xử lý cặp (query, document) cùng lúc nên chính xác hơn bi-encoder nhưng chậm hơn, phù hợp cho reranking stage.
Mô hình xuất ra điểm số relevance từ 0 đến 1, cho phép sắp xếp lại danh sách candidate theo mức độ liên quan thực sự.

Ưu điểm của việc dùng Qwen3 thay vì OpenAI embedding là hoàn toàn self-hosted, không tốn chi phí API,
dữ liệu không rời khỏi hệ thống, và có thể fine-tune thêm trên domain cụ thể.
Nhược điểm là cần GPU để chạy hiệu quả, latency cao hơn so với API call khi dùng CPU.
""",
    },
    {
        "title": "FastAPI và Async Python cho AI Services",
        "category": "backend",
        "tenant_id": "tenant_beta",
        "content": """
FastAPI là web framework Python hiện đại được xây dựng trên Starlette và Pydantic, tối ưu cho việc xây dựng API.
Framework hỗ trợ async/await natively, cho phép xử lý nhiều request đồng thời mà không block thread.

Async programming đặc biệt quan trọng trong AI services vì các tác vụ như gọi model inference, truy vấn database,
hay gọi external API đều là I/O bound operations có thể chạy concurrently.

Với asyncpg, kết nối PostgreSQL hoàn toàn async, cho phép xử lý nhiều query database song song.
Connection pooling với asyncpg giảm overhead tạo kết nối mới cho mỗi request, cải thiện throughput đáng kể.

httpx là thư viện HTTP client async cho Python, thay thế requests trong môi trường async.
Sử dụng httpx.AsyncClient với context manager đảm bảo kết nối được đóng đúng cách sau mỗi request.

Pydantic v2 được dùng để validate input/output data với type hints, tự động sinh OpenAPI schema.
BaseModel của Pydantic đảm bảo dữ liệu luôn đúng kiểu trước khi xử lý, giảm runtime errors.

Dependency Injection trong FastAPI cho phép tái sử dụng logic như database connection, authentication,
hay model loading một cách sạch sẽ mà không cần global variables.
Lifespan context manager (thay thế on_event deprecated) quản lý việc khởi tạo và cleanup resources khi app start/stop.
""",
    },
    {
        "title": "Docker và Container hóa ứng dụng AI",
        "category": "devops",
        "tenant_id": "tenant_acme",
        "content": """
Docker cho phép đóng gói ứng dụng cùng tất cả dependencies vào một container độc lập, đảm bảo chạy nhất quán trên mọi môi trường.
Đối với ứng dụng AI, containerization đặc biệt quan trọng vì môi trường Python với nhiều thư viện ML dễ xảy ra conflict.

Multi-stage build trong Dockerfile giúp giảm kích thước image cuối bằng cách tách giai đoạn build và runtime.
Ví dụ: stage đầu install build dependencies và compile, stage thứ hai chỉ copy artifact cần thiết.

Docker Compose orchestrate nhiều service liên quan, định nghĩa network, volume và dependency giữa các container.
Healthcheck trong Compose đảm bảo service chỉ nhận traffic khi thực sự ready, tránh lỗi khi dependent service chưa khởi động xong.

Volume persistence quan trọng cho stateful services như database và model cache.
pgvector data cần được lưu trong named volume để không mất dữ liệu khi restart container.
Model weights của Qwen3 (vài GB) nên được cache trong volume để tránh download lại mỗi lần start.

GPU support trong Docker yêu cầu NVIDIA Container Toolkit và driver phù hợp trên host.
Khi không có GPU, PyTorch tự động fallback về CPU, chậm hơn nhưng vẫn chạy được cho mục đích development.

Resource limits trong Compose (memory, CPU) ngăn container chiếm toàn bộ tài nguyên host,
đặc biệt cần thiết khi chạy nhiều model AI trên cùng một máy.
""",
    },
]

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> list[str]:
    text = " ".join(text.split())  # normalize whitespace
    chunks, start = [], 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if len(chunk) > 60:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

async def embed_batch(texts: list[str]) -> list[list[float]]:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{EMBEDDING_URL}/embed", json={"texts": texts})
        resp.raise_for_status()
        return resp.json()["embeddings"]

async def seed():
    conn = await asyncpg.connect(DATABASE_URL)
    total = 0

    try:
        for doc in DOCUMENTS:
            doc_id = str(uuid.uuid4())
            chunks = chunk_text(doc["content"])
            print(f"\n📄 {doc['title']}  ({len(chunks)} chunks)")

            # Embed theo batch 16
            all_embeddings = []
            for i in range(0, len(chunks), 16):
                batch = chunks[i:i+16]
                embeddings = await embed_batch(batch)
                all_embeddings.extend(embeddings)

            # Insert
            rows = [
                (
                    str(uuid.uuid4()),
                    doc_id,
                    chunk,
                    str(emb),
                    doc["tenant_id"],
                    "vi",
                    json.dumps({
                        "source": doc["title"],
                        "category": doc["category"],
                        "chunk_index": idx,
                    }),
                )
                for idx, (chunk, emb) in enumerate(zip(chunks, all_embeddings))
            ]

            await conn.executemany("""
                INSERT INTO document_chunks
                    (id, document_id, content, embedding, tenant_id, language, metadata)
                VALUES ($1, $2, $3, $4::vector, $5, $6, $7::jsonb)
            """, rows)

            total += len(rows)
            print(f"   ✓ inserted {len(rows)} chunks  tenant={doc['tenant_id']}")

    finally:
        await conn.close()

    print(f"\n Done — {total} chunks total")

if __name__ == "__main__":
    asyncio.run(seed())