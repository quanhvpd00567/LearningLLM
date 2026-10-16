# Ecommerce chatbot — FastAPI, Ollama và pgvector

Demo đang phát triển từ API chat FastAPI + Ollama. Nền tảng hiện có:

- Chat qua `POST /api/v1/chat`, trả JSON sau khi sinh xong.
- Semantic search qua `POST /api/v1/search`.
- SQLAlchemy 2 Async + asyncpg; quản lý schema bằng Alembic.
- Embedding qua Ollama `qwen3-embedding:0.6b`, vector 1024 chiều.
- PostgreSQL + pgvector, cosine distance và HNSW index.

Hiện đã có catalog, knowledge, jobs, embedding worker và admin site với đăng nhập,
quản lý sản phẩm/biến thể, tài liệu, đồng bộ và settings. Giỏ hàng/đơn hàng và
chatbot RAG/streaming được triển khai sau phần admin. Model chat hiện mặc định `llama3.2:1b`, chưa phải
lựa chọn cuối cùng cho chatbot ecommerce.

## Cấu trúc

```text
app/
├── main.py                  # Lifespan: HTTP clients, engine, session factory
├── api/routes/              # Chat, search, health
├── core/config.py           # Cấu hình môi trường
├── db/
│   ├── session.py           # SQLAlchemy async engine/session
│   └── models.py            # Catalog, knowledge, jobs, DocumentChunk
├── schemas/                 # Request/response validation
├── chatbot/rag/chunking.py   # Chia đoạn và phiên bản pipeline
├── workers/                 # Queue, heartbeat, embedding worker, CLI
└── services/
    ├── ollama.py            # Chat client
    ├── embedding.py         # Embedding client + validation + query instruction
    ├── search.py            # ORM query, pgvector distance, metadata filters
    └── sources.py           # Transactional source writes + embedding jobs
data/seed/ecommerce.json      # 50 sản phẩm + 10 tài liệu demo
migrations/                  # Alembic migrations
scripts/seed_ecommerce.py     # Nguồn ecommerce và jobs
scripts/reindex.py            # Requeue nguồn theo profile hiện tại
scripts/seed_data.py          # Dữ liệu kỹ thuật mẫu cũ
sql/init.sql                 # Schema cũ để tham khảo, không tự chạy nữa
tests/                       # API, embedding và PostgreSQL integration tests
```

Hai thư mục `embedding/` và `reranker/` cũ được giữ để tham khảo, không còn là
service trong Compose. Backend gọi Ollama trực tiếp cho cả chat và embedding.

## Chạy bằng Docker Compose

Lần đầu, copy `.env.example` thành `.env`. Nếu đã có `.env`, bổ sung các biến mới
và giữ cấu hình hiện tại. Đặt `POSTGRES_PASSWORD` trước khi chạy Compose.

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f migrate ollama-init api
```

Compose chạy PostgreSQL và Ollama, job tải hai model, job migration, rồi API.
Lần đầu cần Internet để tải image/model. Model và database được lưu bằng named
volumes. API được bind vào localhost; PostgreSQL/Ollama chỉ truy cập nội bộ.

- Swagger: http://localhost:8000/docs
- Liveness: http://localhost:8000/health

`/health` chỉ xác nhận API đang sống, chưa kiểm tra database/model.
Không dùng `docker compose down -v` nếu cần giữ dữ liệu.

## Chạy backend trực tiếp

Cần Python 3.12, PostgreSQL có extension pgvector và Ollama.
Cấu hình `DATABASE_URL`, `OLLAMA_BASE_URL` theo môi trường thực tế.
Nếu PostgreSQL chạy bằng Compose, có thể chạy lệnh trong container API hoặc
cấu hình cổng localhost riêng cho development.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ollama pull llama3.2:1b
ollama pull qwen3-embedding:0.6b
alembic upgrade head
uvicorn app.main:app --reload
```

`DATABASE_URL` hỗ trợ cả `postgresql://` và `postgresql+asyncpg://`.
Password có ký tự đặc biệt phải được URL-encode khi đưa vào URL; trong Compose
hiện tại nên dùng password URL-safe vì URL được ghép từ POSTGRES_PASSWORD.

## API

Chat không lưu hội thoại ở đợt này: client gửi lại lịch sử ở lượt kế tiếp.

```bash
curl http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Giải thích RAG là gì"}]}'
```

Seed mẫu sau khi migration và model sẵn sàng:

```bash
docker compose exec api python -m scripts.seed_data
```

Hoặc chạy local bằng `python -m scripts.seed_data`. Script dùng cấu hình môi
trường và Ollama; chạy lặp sẽ thêm dữ liệu, chưa phải pipeline reindex.
Dữ liệu mẫu hiện là kiến thức kỹ thuật, sẽ được thay bằng ecommerce ở đợt sau.

```bash
curl http://localhost:8000/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"Tìm kiếm ngữ nghĩa là gì?","top_k":5,"filter":{"tenant_id":"tenant_acme","language":"vi","metadata":{"category":"database"}}}'
```

Query embedding có instruction retrieval; document embedding không thêm
instruction. Client kiểm tra số vector, kích thước 1024, giá trị hữu hạn và vector
khác zero. `score = 1 - cosine_distance / 2` nằm trong [0, 1], không phải xác suất.
Bộ lọc tenant hiện giữ hợp đồng API cũ; chưa có xác thực nên không được coi là
cơ chế phân quyền. Đợt auth sẽ lấy danh tính từ phiên đăng nhập.

## Migration và dữ liệu cũ

Migration tự chạy trước API trong Compose. Có thể chạy thủ công:

```bash
alembic upgrade head
alembic check
```

Baseline tiếp nhận bảng hiện có nếu schema tương thích với `sql/init.sql`, giữ
nguyên dữ liệu; volume cũ không cần tạo lại. Downgrade baseline sẽ xóa bảng chunk,
chỉ dùng trên database thử nghiệm hoặc sau khi sao lưu.

Embedding từ service SentenceTransformer cũ không được coi là tương thích với
bản Ollama. Phải tạo lại embedding trước khi dùng query mới với dữ liệu cũ;
không trộn vector của các model/runtime khác nhau. Dùng `scripts.reindex` để tạo
lại vector cho các nguồn đã lưu trong products/knowledge_documents; dữ liệu seed
cũ chỉ có chunk phải được nhập lại thành nguồn hoặc seed lại bằng script cũ.
Đổi model hoặc cách tiền xử lý cũng cần tạo lại tập vector tương ứng.

## Kiểm thử

```bash
python -m pytest -q
```

API chat/health và embedding tests dùng upstream giả lập. Integration test chỉ
chạy khi có TEST_DATABASE_URL trỏ tới database kiểm thử riêng đã migrate:

```bash
DATABASE_URL=postgresql+asyncpg://app:password@localhost:5432/test_db alembic upgrade head
TEST_DATABASE_URL=postgresql+asyncpg://app:password@localhost:5432/test_db python -m pytest -q tests/test_search_integration.py
```

Integration test kiểm tra ranking và bộ lọc thực tế; dữ liệu test được rollback.
Lifespan tạo engine nhưng không bắt buộc kết nối database để chat/health khởi động.
Search cần database sẵn sàng.

| HTTP | Ý nghĩa |
| --- | --- |
| 422 | Request không hợp lệ |
| 502 | Ollama trả lỗi hoặc dữ liệu sai định dạng |
| 503 | Không kết nối được upstream/database |
| 504 | Upstream xử lý quá thời gian chờ |

## Đợt 2: dữ liệu ecommerce và job embedding

Sau khi migrate, tạo dữ liệu cửa hàng giày giả lập:

```bash
docker compose exec api python -m scripts.seed_ecommerce
```

Hoặc local: `python -m scripts.seed_ecommerce`. Seed có 5 danh mục, 50 sản phẩm,
150 biến thể (giá bằng VND), 10 tài liệu FAQ/chính sách. Có sản phẩm hết hàng để
kiểm thử. Sản phẩm/chính sách đều giả lập, không dùng như thông tin cửa hàng thật.
Chạy lại giữ nguyên ID, không tạo bản ghi/job trùng khi nội dung không đổi;
chỉ chạy trên database demo vì script khôi phục giá trị mẫu đã định nghĩa.

`SourceService` sử dụng transaction do caller quản lý:

```python
async with sessions.begin() as session:
    service = SourceService(session, settings.embedding_model)
    await service.save_product(product_id, ProductInput(...))
```

- Tạo/sửa tên, mô tả, danh mục, thuộc tính hoặc trạng thái nguồn sẽ tạo job.
- Thêm biến thể hoặc đổi options (size/màu) cũng tăng phiên bản sản phẩm.
- Chỉ đổi giá/tồn kho không tăng phiên bản và không tạo job.
- Gửi lại cùng nội dung không tăng phiên bản và không tạo job.
- Nguồn và job được commit/rollback cùng nhau; khóa row để serialize cập nhật.
- Job pending của phiên bản cũ chuyển `superseded`; mỗi nguồn có một phiên bản
  pending mới nhất trong luồng cập nhật thông thường.
- Chunk cũ chuyển `archived` ngay khi nguồn thay đổi, hoặc `deleted` khi tắt nguồn.
- Xóa logic bằng `is_active=False` tạo job `delete_source_embeddings`.

Seed chỉ tạo nguồn và jobs; worker sẽ tạo vector để sản phẩm xuất hiện trong
`/search` với tenant `demo`. Mutation API đã có trong admin và yêu cầu phiên quản trị. Không sửa nguồn trực tiếp bằng SQL vì sẽ bỏ
qua cơ chế versioning/job trong service.

## Đợt 3: embedding worker

Worker dùng chung image backend và chạy riêng trong Compose:

```bash
docker compose up --build -d
docker compose exec api python -m scripts.seed_ecommerce
docker compose logs -f worker
```

Sau khi jobs hoàn tất, tìm sản phẩm qua API:

```bash
curl http://localhost:8000/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"Giày đi bộ đế êm","top_k":5,"filter":{"tenant_id":"demo","metadata":{"source_type":"product"}}}'
```

Chạy local: `python -m app.workers.main`. `--once` xử lý một job đến hạn rồi thoát;
`--drain` xử lý đến khi không còn job đến hạn (không chờ retry được hẹn trong tương lai).

Luồng xử lý:

1. Thu hồi job processing đã quá hạn lease của cùng model/pipeline.
2. Nhận một job bằng `FOR UPDATE SKIP LOCKED`, tăng attempts và cấp token mới.
3. Đọc nguồn/biến thể trong transaction ngắn; đóng transaction trước khi gọi model.
4. Chia nội dung thành đoạn tối đa 1400 ký tự, overlap 160 ký tự, thêm tiêu đề;
   đây là giới hạn ký tự, không phải token. Batch mặc định 8 đoạn.
5. Heartbeat gia hạn lease khi xử lý. Mặc định lease 600 giây, heartbeat mỗi 30 giây.
6. Khóa nguồn rồi job; kiểm tra token và source_version trước khi ghi.
7. Xóa/thay chunks và hoàn tất job trong cùng transaction. Lỗi ghi sẽ rollback cả hai.

Vector sản phẩm chứa mô tả, thuộc tính và biến thể, không chứa giá/tồn kho.
Nguồn tắt hoạt động có job xóa chunks và không gọi model. Nguồn đổi trong lúc
embedding được đánh dấu superseded; worker cũ mất lease không được ghi kết quả.
Hash SHA-256 và unique constraint giúp theo dõi/chặn trùng chunk.

Lỗi tự retry với backoff 5, 10... giây (tối đa 300); mặc định tối đa 3 attempts,
sau đó status=failed. Worker chết sẽ được thu hồi sau khi lease hết hạn; heartbeat
và token bảo vệ khi có nhiều worker. Có thể chạy nhiều replica worker cùng profile.

Reindex tất cả nguồn hiện có, đồng thời retry các job failed của phiên bản hiện tại:

```bash
docker compose exec api python -m scripts.reindex
```

Lệnh này không đổi source_version, không reset job đang processing và giữ chunks
hiện tại cho tới khi thay thế thành công. Không tạo chunks trực tiếp trong script.
Khi đổi model/pipeline, dừng worker profile cũ trước khi chạy worker/reindex mới.
Search chỉ đọc chunks đúng model và PIPELINE_VERSION hiện tại; chunks legacy thiếu
thông tin profile sẽ không được trả về.

Xem trạng thái hàng đợi:

```bash
docker compose exec postgres psql -U app -d semantic_search -c "SELECT status, count(*) FROM jobs GROUP BY status;"
```

Các biến cấu hình mới nằm trong `.env.example`: EMBEDDING_BATCH_SIZE,
EMBEDDING_JOB_POLL_SECONDS, EMBEDDING_JOB_LEASE_SECONDS, EMBEDDING_JOB_RETRY_SECONDS.
Thay chunking/rendering cần tăng PIPELINE_VERSION và reindex; pin phiên bản model
khi cần tái lập kết quả, không thay trọng số dưới cùng profile đã dùng.

## Admin site

Admin UI dùng React + TypeScript + Vite, đóng gói cùng FastAPI trong Docker image.
Truy cập **http://localhost:8000/admin/** sau khi khởi động stack.

Thiết lập trong `.env` trước khi chạy:

```dotenv
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-local-admin-password
ADMIN_COOKIE_SECURE=false
ADMIN_TENANT_ID=demo
```

`ADMIN_PASSWORD` rỗng sẽ tắt quyền truy cập admin, không có mật khẩu mặc định.
Cookie phiên tồn tại tối đa 8 giờ, HttpOnly + SameSite Strict; token chỉ lưu dạng
hash trong database. Bật ADMIN_COOKIE_SECURE=true khi phục vụ qua HTTPS.
Đây là tài khoản quản trị đơn giản cấu hình qua môi trường, chưa có màn quản lý
nhiều tài khoản. Mọi API admin đều yêu cầu phiên đăng nhập; write request kiểm tra
Origin. Migration `0004_admin` bổ sung bảng phiên và cấu hình cửa hàng.

### Các màn quản trị

- **Tổng quan:** số sản phẩm, tài liệu, vector, tồn kho thấp và trạng thái jobs.
- **Sản phẩm:** tìm/lọc/phân trang, tạo/sửa, ẩn sản phẩm; quản lý SKU, size/màu,
  giá, tồn kho và các thuộc tính. Khi lưu, danh sách biến thể được thay bằng danh
  sách trong form; bỏ biến thể khỏi form sẽ xóa biến thể đó.
- **Danh mục:** tạo/sửa tên và slug; thay danh mục sẽ tạo job mới cho sản phẩm
  liên quan để metadata được cập nhật.
- **Kho kiến thức:** tạo/sửa/ẩn tài liệu, FAQ và chính sách.
- **Đồng bộ:** lọc jobs, xem lỗi, retry job failed hiện tại và reindex theo shop.
- **Cài đặt:** tên cửa hàng, email liên hệ, ngưỡng tồn kho thấp và tạm dừng nhận job.
  Job đang chạy vẫn hoàn tất. Model/dimension/pipeline được hiển thị chỉ đọc.

Sửa nội dung đi qua SourceService nên source và job vẫn commit/rollback cùng nhau.
Form sửa sản phẩm/tài liệu gửi expected_version để chặn ghi đè bản sửa mới hơn.
Giá/tồn kho không sinh job mới. Tạm dừng được lưu trong PostgreSQL và worker đọc
trước khi nhận job. Admin hiện quản lý tenant cấu hình bởi ADMIN_TENANT_ID.
Các trường thông tin cửa hàng chưa được dùng để tự sửa nội dung chính sách FAQ.

### Phát triển frontend

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Vite phục vụ ở http://127.0.0.1:5173/admin/, proxy `/api` tới FastAPI cổng 8081.
Chạy API với cấu hình database/admin ở trên:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8081
```

Build frontend để FastAPI phục vụ trực tiếp (khởi động lại API sau lần build đầu):

```bash
npm --prefix frontend run build
```

Frontend chia thành `pages/`, `components/`, `lib/`, `types.ts` và `App.tsx`.
Dockerfile build frontend trong Node stage rồi copy dist vào `app/static/admin`;
không cần chạy Node trong container backend. Endpoint `/` chuyển tới `/admin/`.
