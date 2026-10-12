# Học LLM với Ollama + FastAPI

Project thực hành Python 3.12: nhận lịch sử hội thoại qua FastAPI, gọi Ollama và trả câu trả lời dạng JSON. Mặc định chạy CPU với `llama3.2:1b`; có thể đổi model qua `.env`.

## Cấu trúc thư mục

```text
.
├── app/
│   ├── main.py              # Khởi tạo FastAPI, quản lý HTTP client bằng lifespan
│   ├── api/
│   │   ├── dependencies.py  # Inject service vào route
│   │   └── routes/
│   │       ├── chat.py      # POST /api/v1/chat
│   │       └── health.py    # GET /health
│   ├── core/config.py       # Đọc cấu hình từ biến môi trường / .env
│   ├── schemas/chat.py      # Kiểm tra request và định dạng response
│   └── services/ollama.py   # Gọi Ollama, xử lý lỗi và timeout
├── tests/test_api.py        # Kiểm thử API với Ollama giả lập
├── .env.example
├── .dockerignore
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```

Luồng xử lý: `client → route → OllamaService → Ollama /api/chat → response`.

## Chạy bằng Docker Compose

Cần Docker Engine và Docker Compose v2. Chạy tại thư mục project:

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f ollama-init api
```

Compose chạy ba service: `ollama` phục vụ model, `ollama-init` tải model rồi kết thúc, `api` chỉ khởi động sau khi tải thành công. Lần đầu cần Internet và dung lượng đĩa để tải image/model; thời gian tải tùy mạng. Model lưu trong volume `ollama_data`, dùng lại sau khi khởi động lại.

- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health (chỉ kiểm tra API đang sống)
- API chỉ được bind vào localhost. Ollama truy cập nội bộ bằng `http://ollama:11434`.

```bash
curl http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"system","content":"Bạn là trợ lý dạy lập trình, trả lời bằng tiếng Việt."},{"role":"user","content":"Giải thích LLM là gì bằng ví dụ đơn giản."}],"temperature":0.7}'
```

API không lưu hội thoại: ở lượt tiếp theo, gửi lại các message trước đó cùng câu hỏi mới. Hiện dùng `stream: false`, trả kết quả khi model sinh xong.

```bash
docker compose down                   # Dừng, giữ model đã tải
docker compose logs --tail=100 api ollama
```

Đổi `OLLAMA_MODEL` trong `.env`, sau đó chạy:

```bash
docker compose up -d --force-recreate ollama-init api
```

`OLLAMA_IMAGE` mặc định dùng `latest` cho môi trường học; đặt tag/digest cố định khi cần triển khai tái lập. Muốn dùng NVIDIA GPU, máy cần NVIDIA Container Toolkit và thêm `gpus: all` vào service `ollama`; cấu hình mặc định không yêu cầu GPU.

## Chạy Python trực tiếp để học/debug

Cần Ollama đang chạy trên máy và Python 3.12. Trên Ubuntu/Debian nếu thiếu `venv`, cài gói `python3-venv` trước.

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ollama pull llama3.2:1b
uvicorn app.main:app --reload
```

Chế độ này dùng `OLLAMA_BASE_URL=http://localhost:11434` trong `.env`. Nếu thay model, dùng tên tương ứng trong lệnh `ollama pull`.

## Kiểm thử

```bash
python -m pytest -q
```

Test không tải model, không cần Ollama thật; kiểm tra request chuyển đến Ollama, response, dữ liệu sai, lỗi upstream, lỗi kết nối và timeout.

## Lỗi thường gặp

| HTTP | Ý nghĩa | Cách xử lý |
| --- | --- | --- |
| 422 | Request không hợp lệ | Kiểm tra role, content và messages trong Swagger |
| 502 | Model chưa tải hoặc Ollama trả lỗi/dữ liệu sai | Xem log Ollama và kết quả ollama-init |
| 503 | Không kết nối được Ollama | Kiểm tra service, OLLAMA_BASE_URL |
| 504 | Model chạy quá thời gian chờ | Tăng OLLAMA_TIMEOUT_SECONDS hoặc dùng model nhỏ hơn |

Gợi ý học tiếp: thêm streaming, embeddings và RAG sau khi hiểu luồng chat hiện tại.

Tài liệu chính thức: [FastAPI Docker](https://fastapi.tiangolo.com/deployment/docker/), [Ollama Chat API](https://docs.ollama.com/api/chat), [Ollama Docker](https://docs.ollama.com/docker).
