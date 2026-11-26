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

## Part 3 — Cloud Deployment

## Part 4 — API Security

## Part 5 — Scaling & Reliability

## Part 6 — Checklist Deliverable

<!-- Dán phần Checklist Deliverable từ lần chạy đầy đủ check_production_ready.py. -->

## AI log

| Câu hỏi đã gửi AI | Gợi ý nhận được | Phần tự sửa và cách tự kiểm tra |
| --- | --- | --- |
| “làm cp1” | Codex đọc hai bản app, chạy thử bằng curl và soạn câu trả lời Exercise 1.1–1.3 từ mã nguồn và kết quả chạy. | Các lần chạy ghi ở Part 1 do Codex thực hiện. Chưa ghi nhận phần tự sửa hoặc kiểm tra lại của học viên. |
