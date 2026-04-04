# Platform AI Backend - FastAPI

REST API cho bài toán dynamic query extraction và multi-turn slot filling.

## 1. Tổng quan

- Nền tảng: Python + FastAPI
- Có 2 chế độ:
	- Có `OPENAI_URL` + `OPENAI_API_KEY`: gọi LLM để extract slot theo JSON schema
	- Không có env LLM: chat vẫn chạy bằng fallback heuristic (regex + rule-based)
- Session chat cho production ưu tiên Redis, chỉ fallback in-memory khi không có Redis

## 2. Cấu trúc thư mục

```text
app/
	__init__.py
	main.py
	schemas.py
	ai_service.py
	chat_service.py
	session_store.py
requirements.txt
readme.md
```

## 3. Cài đặt

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 4. Cấu hình env

Tạo file `.env`:

```env
OPENAI_URL=https://api.openai.com/v1/responses
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini

# Khuyến nghị production
REDIS_URL=redis://localhost:6379/0
SESSION_TTL_SECONDS=86400
```

Lưu ý:

- Nếu không có `OPENAI_URL`/`OPENAI_API_KEY`:
	- endpoint chat vẫn chạy bằng fallback heuristic
	- endpoint `generate-query-dynamic` sẽ trả lỗi
- Nếu không có `REDIS_URL` hoặc Redis không kết nối được:
	- hệ thống fallback về in-memory (mất session khi restart process)

## 5. Chạy server

```powershell
& ".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 6. API endpoints

- `GET /`
- `GET /health`
- `POST /api/v1/generate-query-dynamic`
- `POST /api/v1/chat/start`
- `POST /api/v1/chat/turn`
- `GET /api/v1/chat/{session_id}`
- `DELETE /api/v1/chat/{session_id}`

`GET /` dùng để expose metadata endpoint của service (name, version, docs, openapi).

## 7. Slot hệ thống

Slot:

- destination
- start_date
- duration_days
- adults
- childs
- budget_min
- budget_max
- start_point
- sort_by
- sort_type
- tags

Required để `completed`:

- destination
- start_date
- duration_days
- adults
- childs
- budget_max
- start_point

## 8. Mô tả nhanh logic chat

1. Tạo session và khởi tạo slots null.
2. Mỗi turn: append history user.
3. Extract slot update (LLM ưu tiên, lỗi thì fallback heuristic).
4. Merge slot update vào slot hiện tại (bỏ qua null).
5. Tính `missing_slots`.
6. Nếu đủ required -> `completed` và trả reply kết thúc.
7. Nếu thiếu -> hỏi tiếp slot đầu tiên còn thiếu.

## 9. Lưu ý production và contract

1. Không dùng in-memory cho production:
	 - Session in-memory sẽ mất khi process restart.
	 - Dùng Redis qua `REDIS_URL` để đảm bảo session bền vững giữa các lần deploy/restart.
2. Chuẩn hóa schema và naming:
	 - Tên trường chuẩn là `duration_days` (không dùng `duration_date`).
	 - Luôn đồng bộ tên trường giữa README, request/response contract và code để tránh sai tích hợp.

## 10. Docker (optimized size)

Project có sẵn:

- `Dockerfile` multi-stage để giảm kích thước image runtime
- `requirements-prod.txt` chỉ chứa dependency chạy production
- `.dockerignore` để giảm build context

Build image:

```powershell
docker build -t platform-ai-backend:latest .
```

Run local container:

```powershell
docker run --rm -p 8000:8000 --env-file .env platform-ai-backend:latest
```

Test nhanh:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health" | ConvertTo-Json -Compress
```

## 11. Chính sách .env

- Commit `.env.example` để chia sẻ danh sách biến môi trường cần dùng.
- Không commit `.env` thật (đã ignore trong `.gitignore`).