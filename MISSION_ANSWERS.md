# Day 14 — Mission Answers

## Part 1 — Localhost vs Production

### Exercise 1.1 — Các vấn đề trong bản develop

Các dòng dưới đây thuộc [develop/app.py](01-localhost-vs-production/develop/app.py).

| Dòng | Vấn đề | Hệ quả khi triển khai |
| --- | --- | --- |
| 17–18 | API key mẫu và chuỗi kết nối chứa mật khẩu được viết thẳng trong mã. | Nếu dùng thông tin thật, người đọc repo hoặc lịch sử Git có thể lấy được thông tin đăng nhập. |
| 33–38 | Mỗi lần gọi, app in câu hỏi, key và toàn bộ câu trả lời. | Người có quyền xem log có thể đọc nội dung người dùng và key. |
| 51 | Server chỉ lắng nghe trên `localhost`. | Reverse proxy ở container khác không kết nối được tới agent qua mạng Docker. |
| 52 | Cổng 8000 được ghi cố định. | Khi nền tảng cấp cổng qua biến `PORT`, lưu lượng có thể tới nhầm cổng. |
| 53 | `reload=True` cho mọi lần khởi động. | Bản triển khai luôn chạy trình theo dõi file và có thể khởi động lại khi mã thay đổi. |
| 25–42 | App có route trang chủ và hỏi đáp nhưng thiếu probe riêng. | Bộ cân bằng tải thiếu tín hiệu để quyết định khi nào agent sẵn sàng nhận request. |

### Exercise 1.2 — Gọi bản develop

Chạy `python app.py` trong `01-localhost-vs-production/develop/`, sau đó gọi endpoint với `question` trên query string. Kết quả của lần chạy CP1:

```console
$ curl -sS -w ' HTTP %{http_code}\n' -X POST 'http://localhost:8000/ask?question=Hello'
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."} HTTP 200
```

Đây là phản hồi từ mock LLM đang chạy trên máy. Cùng lần chạy, cả `GET /health` và `GET /ready` đều trả HTTP 404.

### Exercise 1.3 — So sánh hai bản

| Đặc điểm | Develop | Production | Vì sao quan trọng? |
| --- | --- | --- | --- |
| Cấu hình và secret | Khai báo key và các hằng số trong mã. | `Settings` đọc key, model và giới hạn token từ môi trường. | Có thể đổi cấu hình giữa các lần triển khai và xoay key mà không cần sửa mã. |
| Địa chỉ và cổng | Cố định `localhost:8000`, luôn bật reload. | Đọc `HOST`, `PORT`, `DEBUG`. Mặc định bind `0.0.0.0` và tắt reload. | Nền tảng chọn được cổng, còn proxy có thể truy cập agent qua mạng container. |
| Logging | `print` cả key lẫn nội dung hội thoại. | Handler ghi sự kiện `agent_request`, `agent_response` với độ dài câu hỏi và câu trả lời. | Có thể tìm sự kiện xử lý request mà không đưa key hoặc nguyên văn hội thoại vào log. |
| Health và readiness | Hai probe trả 404. | `/health` báo trạng thái tiến trình. `/ready` dựa vào cờ khởi tạo và trả 503 khi cờ tắt. | Nền tảng có thể kiểm tra tiến trình còn sống và quyết định riêng lúc bắt đầu chuyển traffic. |
| Shutdown | Phần ứng dụng không có bước dọn dẹp riêng. | Uvicorn xử lý việc dừng server. Phần sau `yield` trong `lifespan` hạ cờ readiness và ghi log kết thúc. | Khi thay phiên bản, server cần thời gian hoàn thành request đang xử lý và ứng dụng cần điểm để đóng tài nguyên. |

Ví dụ đối chiếu trực tiếp: [develop/app.py, dòng 52](01-localhost-vs-production/develop/app.py#L52) đặt `port=8000`. [production/config.py, dòng 18](01-localhost-vs-production/production/config.py#L18) đọc `PORT`, rồi [production/app.py, dòng 197](01-localhost-vs-production/production/app.py#L197) truyền giá trị đó cho Uvicorn.

Đã kiểm tra bản production trên `127.0.0.1` với `PORT=8001` và `ENVIRONMENT=development`. Gửi `POST /ask` với JSON `{"question":"Hello"}` nhận HTTP 200. `GET /health` trả HTTP 200 với `status="ok"`, còn `GET /ready` trả HTTP 200 với `{"ready":true}`.

## Part 2 — Docker

### Exercise 2.1 — Đọc Dockerfile develop

1. **Base image** là `python:3.11`. Docker dùng filesystem và Python có sẵn của image này làm nền để cài thư viện và thêm mã agent.
2. **Working directory** là `/app`. Vì vậy `COPY ... .` đặt file vào `/app` và `python app.py` chạy từ thư mục đó.
3. **Thứ tự COPY** quyết định khi nào phải cài lại thư viện. Dockerfile chép `requirements.txt` rồi chạy `pip install` trước khi chép `app.py`. Khi chỉ sửa mã agent, Docker có thể dùng lại layer đã cài thư viện.
4. **CMD và ENTRYPOINT**: `CMD ["python", "app.py"]` cung cấp lệnh mặc định. Ví dụ, `docker run --rm my-agent:develop python --version` thay toàn bộ lệnh mặc định. Nếu image có `ENTRYPOINT` dạng exec, đối số sau tên image sẽ được nối vào entrypoint, thay cho đối số mặc định trong `CMD`.

### Exercise 2.2 — Chạy container develop

Build từ gốc repo để Docker có thể chép cả `utils/mock_llm.py`. Sau khi chạy container, gửi câu hỏi qua query string:

```console
$ docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
$ docker run --rm -d --name k5-day14-cp2-develop -p 127.0.0.1:8000:8000 my-agent:develop
$ curl -fsS -w ' HTTP %{http_code}\n' -X POST 'http://127.0.0.1:8000/ask?question=Hello'
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."} HTTP 200
```

### Exercise 2.3 — Đo kích thước image

Build bản production từ gốc repo bằng `docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .`. Cả hai image được build cho kiến trúc `arm64`.

| Image | Kết quả `docker images my-agent` | Kích thước theo byte từ `docker image inspect` |
| --- | ---: | ---: |
| `my-agent:develop` | 1.67 GB (≈ 1 672 MB) | 1 672 149 312 |
| `my-agent:advanced` | 265 MB | 265 497 305 |

**Bản production nhỏ hơn 84,12%** so với develop, tính theo byte bằng `(1 − 265497305 / 1672149312) × 100`.

Stage `builder` cài `gcc`, `libpq-dev` và các thư viện Python. Stage `runtime` bắt đầu lại từ `python:3.11-slim`, chỉ chép các thư viện đã cài và mã cần để chạy agent. Kích thước giảm nhờ cả hai thay đổi so với develop: dùng base slim và để công cụ biên dịch ở lại builder.

### Exercise 2.4 — Stack Compose và kiểm tra qua Nginx

Trong `02-docker/production/`, tạo file trống bằng `touch .env.local` và chạy `docker compose -p k5-day14-docker up -d --build --wait`. Cả bốn service đã khởi động thành công.

```text
Client → Nginx :80 → agent:8000 (FastAPI, 2 Uvicorn worker)
                       ├── REDIS_URL  → redis:6379  → volume redis_data
                       └── QDRANT_URL → qdrant:6333 → volume qdrant_data
```

Các service phân giải tên qua mạng Compose `internal`. Compose đợi Redis và Qdrant đạt trạng thái healthy trước khi khởi động agent. Hai nhánh dưới là địa chỉ dịch vụ được cấu hình cho agent. Trong bài này, handler `/ask` gọi mock LLM trực tiếp. Client truy cập agent qua Nginx trên cổng 80.

```console
$ curl -fsS -w ' HTTP %{http_code}\n' http://127.0.0.1/health
{"status":"ok","uptime_seconds":19.1,"version":"2.0.0","timestamp":"2026-11-26T08:12:17.725858"} HTTP 200
$ curl -fsS -w ' HTTP %{http_code}\n' -H 'Content-Type: application/json' -d '{"question":"Explain microservices"}' http://127.0.0.1/ask
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."} HTTP 200
```

## Part 3 — Cloud Deployment

### Exercise 3.1–3.2 — Railway và Render

Nền tảng đã chọn cho agent Part 6 là Railway. Trạng thái triển khai và các lệnh kiểm tra nằm trong [DEPLOYMENT.md](DEPLOYMENT.md). Agent đang phục vụ tại [https://agent-production-40ee2863.up.railway.app](https://agent-production-40ee2863.up.railway.app). Bốn phép thử public ngày 26/11/2026 cho kết quả 200, 200, 401 và 200 theo thứ tự trong báo cáo.

| Thành phần | [Railway của Part 6](06-lab-complete/railway.toml) | [Render Blueprint mẫu của Part 3](03-cloud-deployment/render/render.yaml) |
| --- | --- | --- |
| Build và khởi động | `builder = "DOCKERFILE"` dùng Dockerfile trong `06-lab-complete/`. Lệnh khởi động nằm trong image. | Blueprint chọn runtime Python và khai báo riêng lệnh cài thư viện, lệnh chạy Uvicorn. |
| Phạm vi cấu hình | TOML này cấu hình service agent. Redis là service riêng trong project, agent cần tham chiếu URL kết nối của Redis. | Danh sách `services` mô tả cả web và Redis. Web vẫn cần biến kết nối tới Redis. |
| Health check và secret | `healthcheckPath = "/health"`; key của agent được cấp qua biến môi trường của service. | `healthCheckPath: /health`; Blueprint có thể yêu cầu nhập secret bằng `sync: false` hoặc sinh giá trị bằng `generateValue: true`. |

### Exercise 3.3 — Pipeline Cloud Run

1. [Cloud Build](03-cloud-deployment/production-cloud-run/cloudbuild.yaml) cài thư viện và chạy `pytest tests/` trong Python 3.11. Bước test kết thúc bằng `echo` và chưa bật `set -e`, nên lỗi pytest có thể bị che.
2. Bước build tạo image với hai tag `$COMMIT_SHA` và `latest`. Bước push đẩy các tag lên `gcr.io/$PROJECT_ID/ai-agent`.
3. Bước deploy dùng tag của commit để triển khai `ai-agent` lên Cloud Run tại `asia-southeast1`, đặt biến môi trường production và tham chiếu secret qua Secret Manager.
4. [service.yaml](03-cloud-deployment/production-cloud-run/service.yaml) mô tả riêng cấu hình 1–10 instance, concurrency 80, startup probe `/ready` và liveness probe `/health`. Pipeline triển khai bằng các cờ của `gcloud run deploy`.

## Part 4 — API Security

### Exercise 4.1 — API key

Trong [app.py của bản develop](04-api-gateway/develop/app.py), route `POST /ask` khai báo `Depends(verify_api_key)`. FastAPI đọc header `X-API-Key` và kiểm tra trước khi gọi mock LLM. Gửi cùng body `{"question":"Hello"}` ba lần, chỉ thay đổi header, thu được các trích đoạn `curl -i` dưới đây theo thứ tự thiếu key, sai key và đúng key.

```http
HTTP/1.1 401 Unauthorized

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

HTTP/1.1 403 Forbidden

{"detail":"Invalid API key."}

HTTP/1.1 200 OK

{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Để xoay key, cấp key mới cho client qua kênh riêng, cập nhật biến môi trường `AGENT_API_KEY` và phối hợp thời điểm client chuyển key với lần khởi động lại agent. App đọc biến khi nạp module và mỗi tiến trình chỉ chấp nhận một key.

### Exercise 4.2 — JWT

Trên bản production, đăng nhập bằng tài khoản lab `student` tại `POST /auth/token` trả `HTTP/1.1 200 OK` và thời hạn 60 phút. Client gửi access token qua header `Authorization: Bearer <token đã che>`. Server kiểm tra chữ ký HS256 và thời hạn trước khi đọc username và role. Khi dùng token này cho `POST /ask`, request đầu tiên trả HTTP 200 và trường `requests_remaining` bằng 9. [Mã xác thực](04-api-gateway/production/auth.py)

### Exercise 4.3 — Rate limiting

Gửi liên tiếp 20 request `POST /ask` bằng cùng JWT của `student`, với câu hỏi từ `Test 1` đến `Test 20`. Request **1–10 trả 200**, request **11–20 trả 429**. Trích phản hồi `curl -i` của request thứ 11:

```http
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 59

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

[Rate limiter](04-api-gateway/production/rate_limiter.py) giữ thời điểm từng request trong một hàng đợi theo username. Mỗi lần kiểm tra, nó bỏ các mốc cũ hơn 60 giây rồi đếm số còn lại. Hạn mức là 10 request cho user và 100 cho admin trong cùng cửa sổ trượt. Server chọn hạn mức theo role trong JWT đã xác thực. Ở lần đo trên, header `Retry-After` yêu cầu client chờ 59 giây.

### Exercise 4.4 — Cost guard

Trong [cost_guard.py](04-api-gateway/production/cost_guard.py), agent kiểm tra chi phí đã tích lũy trước mỗi lần gọi LLM. Khi người dùng đã tiêu ít nhất 80% ngân sách ngày, guard ghi cảnh báo. Khi đã tiêu đủ 1 USD, request kế tiếp bị chặn với HTTP 402. Nếu tổng chi phí đã đạt ngưỡng 10 USD của dịch vụ, guard trả 503. Sau mỗi câu trả lời, agent ước tính số token đầu vào và đầu ra rồi cộng chi phí theo đơn giá riêng. Bản mẫu giữ các bộ đếm trong RAM.

Với yêu cầu **10 USD/user/tháng** của Exercise 4.4, có thể dùng Redis với khóa theo username và tháng UTC. Trước khi gọi LLM, kiểm tra chi phí đã dùng cộng phần dự trù của request trong cùng một thao tác nguyên tử. Nếu vượt 10 USD thì trả 402, nếu còn đủ thì giữ chỗ phần dự trù. Sau khi có kết quả, đối soát với chi phí thực tế. Khi sang tháng mới, dùng khóa mới và cho khóa cũ hết hạn. Cần cả hai cơ chế vì một vài câu trả lời dài vẫn có thể tiêu hết ngân sách dù số request mỗi phút còn thấp.

## Part 5 — Scaling & Reliability

### Exercise 5.1 — Liveness và readiness

Trên bản develop, `GET /health` trả HTTP 200 với `status="ok"`, còn `GET /ready` trả HTTP 200 với `ready=true`. Liveness giúp nền tảng nhận biết tiến trình còn phản hồi. Readiness giúp bộ cân bằng tải quyết định có chuyển request mới tới instance hay không. Trong [app develop](05-scaling-reliability/develop/app.py), cờ readiness được bật sau bước khởi tạo. Khi cờ tắt, handler của `/ready` trả 503.

### Exercise 5.2 — Graceful shutdown

Chạy `python app.py` trong thư mục develop, gửi `POST /ask?question=Docker`, rồi gửi SIGTERM tới PID của agent sau 0,5 giây khi client vẫn đang chờ. Client nhận đủ câu trả lời với **HTTP 200 sau 3,04 giây** kể từ lúc gửi request. Log ghi `Shutdown complete`, tiếp theo là `Application shutdown complete` và tiến trình thoát với mã **0**. Nhờ thời gian chờ khi dừng, request đang xử lý vẫn trả kết quả cho client.

Kết quả phụ thuộc cách khởi chạy. Trong lần thử riêng dùng `uvicorn app:app`, request cũng trả 200 nhưng tiến trình vẫn chạy sau 10 giây chờ SIGTERM. Kết quả thoát mã 0 ở trên thuộc lệnh `python app.py` trong hướng dẫn lab.

### Exercise 5.3 — Lưu hội thoại trong Redis

Mỗi instance có RAM riêng. Nếu câu hỏi thứ hai đến một instance khác, nó chỉ có thể tiếp tục hội thoại khi đọc được lịch sử của câu thứ nhất. Trong [app production](05-scaling-reliability/production/app.py), client gửi lại cùng `session_id`. Agent đọc và ghi khóa Redis `session:<session_id>`, giữ tối đa 20 tin nhắn và đặt lại TTL 3.600 giây khi ghi. Trong lần chạy dưới đây, `GET /health` xác nhận `storage="redis"` và `redis_connected=true`.

### Exercise 5.4–5.5 — Chạy 3 instance và kiểm tra lịch sử

Chạy trong `05-scaling-reliability/production/`:

```bash
touch .env.local
docker compose -p k5-day14-scaling up -d --build --scale agent=3 --wait
python test_stateless.py
docker compose -p k5-day14-scaling down -v
```

Nginx nhận `POST /chat` qua cổng 8080 và chuyển tới các agent ở cổng nội bộ 8000. Với session `4a21548b-6fef-45d4-baaa-760566ed5f48`, trường `served_by` cho thấy cách phân phối thực tế:

| Instance | Request đã xử lý |
| --- | --- |
| `instance-b441ec` | 1, 4 |
| `instance-447781` | 2, 5 |
| `instance-dcd121` | 3 |

Sau 5 lượt, `GET /chat/{session_id}/history` trả đủ **10 tin nhắn**, gồm 5 câu hỏi và 5 câu trả lời xen kẽ theo đúng thứ tự. Cả 3 instance đã phục vụ cùng một session và đọc chung lịch sử từ Redis. Script giữ cả 3 instance hoạt động trong suốt phép thử.

## Part 6 — Checklist Deliverable

Chạy trong `06-lab-complete/` bằng `.venv/bin/python check_production_ready.py` với Docker. Checker đo image **297 MB**, xác nhận rate limit vẫn có hiệu lực sau khi restart agent và ghi nhận `docker stop` hoàn tất trong **1,5 giây**, exit code **0**.

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

Lần kiểm tra CP8 có thêm URL Railway công khai đạt **12/12 tiêu chí, 42/42 phép kiểm tra**, bao gồm Docker.

## AI log

| Câu hỏi đã gửi AI | Gợi ý nhận được | Phần tự sửa và cách tự kiểm tra |
| --- | --- | --- |
| “làm cp1” | Codex đọc hai bản app, chạy thử bằng curl và soạn câu trả lời Exercise 1.1–1.3 từ mã nguồn và kết quả chạy. | Các lần chạy ghi ở Part 1 do Codex thực hiện. Chưa ghi nhận phần tự sửa hoặc kiểm tra lại của học viên. |
| “hướng dẫn cp2” | Codex đọc Dockerfile và Compose, build hai image, đo kích thước, chạy curl và tổng hợp Exercise 2.1–2.4. | Số đo và phản hồi ở Part 2 do Codex thu trực tiếp trên máy lab. Học viên chưa ghi nhận lần tự kiểm tra. |
| “hướng dẫn cp3” | Codex đọc code Part 4, chạy hai agent local, kiểm tra API key và JWT bằng curl, gửi 20 request rồi giải thích rate limiter và cost guard. | Các phản hồi HTTP trong Part 4 do Codex thu trực tiếp. Học viên chưa ghi nhận lần tự kiểm tra. |
| “hướng dẫn hoàn thiện cp4” | Codex chạy thử các probe, gửi SIGTERM khi có request và chạy test_stateless.py trên 3 instance để soạn Part 5. | Các kết quả đo do Codex thu trực tiếp. Học viên chưa ghi nhận lần tự kiểm tra. |
| “hướng dẫn tôi làm cp5” | Codex triển khai agent Part 6, cấu hình Docker và Railway, dùng Redis để giới hạn request và dự trù chi phí đồng thời. | Codex chạy checker đầy đủ với Docker. |
| “hướng dẫn các bước trong cp6” | Codex so sánh cấu hình, đọc pipeline Cloud Run, triển khai agent và Redis qua Railway CLI rồi lưu ba ảnh minh chứng. |  |
| “hướng dẫn hoàn thiện cp7” | Codex bổ sung histogram, chạy load test và eval, sửa hai mục trong knowledge base và tổng hợp số đo vào báo cáo. | Codex đã khởi động lại v2 và đối chiếu 23 kết quả với baseline. |
| “hướng dẫn cp8” | Codex chạy stack Docker, đối chiếu trace với log, đo thời gian cảnh báo và so sánh benchmark 1 với 3 replica. | Codex đối chiếu kết quả với số liệu gốc và tập hợp minh chứng tại máy để học viên rà soát. |
