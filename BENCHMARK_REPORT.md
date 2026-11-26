# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyễn Minh Quân
**Ngày chạy:** 26/11/2026
**Môi trường:** macOS 26.6, arm64, Python 3.12.2. Agent benchmark chạy local bằng Uvicorn với một worker. Dùng mock LLM của bài, v1 ở cổng 8001 và v2 ở cổng 8002. Chi phí trong báo cáo được tính theo token và bảng giá của mock.

## 1. SLO của agent

| SLI | SLO | Lý do chọn |
|---|---:|---|
| p95 latency của `POST /ask` | ≤ 500 ms | Ngưỡng mặc định của load test cho phép đánh giá thời gian chờ của 95% request thành công. |
| Error rate của `POST /ask` | ≤ 2% | Ngưỡng mặc định cho phép tối đa 6 lỗi trong mỗi lượt 300 request. |
| Accuracy trên golden dataset sau khi sửa | 100% | Mục tiêu CP7 là vượt ngưỡng chấm của cả 23 câu và giữ mọi câu v2 đã làm đúng. |

### Exercise 7.1 — Đọc metrics

Sau một lần gửi câu hỏi `Docker?` (7 ký tự) thành công đến v2, endpoint `/metrics` trả các mẫu sau:

```text
http_requests_total{method="POST",route="/ask",status="200"} 1.0
agent_in_flight_requests 0.0
agent_question_length_chars_count 1.0
agent_question_length_chars_sum 7.0
```

Counter đếm số request đã hoàn thành theo method, route và status. Gauge bằng 0 ở thời điểm scrape vì request đã kết thúc. Histogram mới ghi một lần quan sát với tổng độ dài 7 ký tự, đồng thời phân nhóm độ dài bằng các bucket cố định. Dùng mẫu route và nhãn `unmatched` cho URL lạ giúp giới hạn số chuỗi thời gian. Nếu gắn URL thô vào label, mỗi URL khác nhau có thể tạo thêm một chuỗi cho counter và nhiều chuỗi bucket cho histogram.

## 2. Benchmark hiệu năng (develop, `load_test.py`)

Mỗi lượt gửi 300 request đo sau một request warm-up. Bốn mức concurrency dùng `MOCK_SLOW_RATE=0.03`. Ba lượt thay đổi slow rate cùng dùng concurrency 20 và khởi động lại v2 trước mỗi lượt. Tất cả dùng `MOCK_ERROR_RATE=0.01`. RPS tính trên mọi request, còn latency chỉ tính trên phản hồi HTTP 200. [Các file JSON gốc](06-lab-complete/benchmark-observability/develop/reports/)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.13 | 192.4 | 226.5 | 1686.0 | 1.33% | PASS |
| 10 | 38.95 | 193.7 | 222.1 | 1699.8 | 0.33% | PASS |
| 50 | 110.25 | 195.1 | 262.4 | 1715.3 | 1.33% | PASS |
| 100 | 42.58 | 565.4 | 4750.6 | 5171.4 | 0.33% | FAIL |

Tăng concurrency từ 1 lên 50 cho phép nhiều request cùng chờ mock LLM và đưa throughput từ 4.13 lên 110.25 req/s. Khi tăng tiếp lên 100, throughput giảm xuống 42.58 req/s, còn p95 tăng lên 4750.6 ms. Trong lượt này, client và agent chạy chung máy; số đo cho thấy thời gian chờ tăng, nhưng chưa xác định được thành phần gây nghẽn. Mức 100 vi phạm SLO latency dù tỷ lệ lỗi vẫn dưới 2%.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 192.3 | 218.2 | 230.0 |
| 0.03 (mặc định) | 226.0 | 224.8 | 1671.8 |
| 0.1 | 301.0 | 1687.3 | 1714.7 |

Khi xác suất request chậm tăng từ 0 lên 3%, avg chỉ tăng từ 192.3 lên 226.0 ms, trong khi p99 tăng từ 230.0 lên 1671.8 ms. Khi xác suất tăng lên 10%, p95 cũng tăng đến 1687.3 ms. P99 bộc lộ nhóm ít request phải chờ lâu; p95 cho thấy khi độ trễ đã ảnh hưởng tới nhóm lớn hơn. Chỉ theo dõi avg sẽ bỏ sót cả hai hiện tượng.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 1/23 (4.35%) | 21/23 (91.30%) | 23/23 (100.00%) |
| Avg tokens / câu | 56.8 | 109.0 | 114.2 |
| Tổng cost (USD) | 0.000400 | 0.000760 | 0.000795 |
| Cost / câu đúng (USD) | 0.00039975 | 0.00003619 | 0.00003458 |
| Quality gate | FAIL (≥ 80%) | PASS (≥ 80%) | PASS (100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Thêm tài liệu phân biệt API key và JWT, giải thích cách xác minh chữ ký và thời hạn token. |
| scaling-03 | cpu, memory, custom metrics | Thêm tài liệu về Kubernetes HPA và các chỉ số dùng để điều chỉnh số replica. |

Trên 23 câu, v2 ban đầu tốn nhiều token hơn v1 và có p50 cao hơn (198.0 so với 168.5 ms), nhưng trả lời đúng thêm 20 câu. Sau khi bổ sung hai tài liệu, tổng chi phí mock tăng từ 0.000760 lên 0.000795 USD, còn chi phí mỗi câu đúng giảm từ 0.00003619 xuống 0.00003458 USD. Chi phí trên mỗi câu đúng phản ánh cả tiền đã chi cho những lần trả lời sai.

**Quality gate trong CI.** Với mỗi pull request, cho job khởi động agent v2, chờ `/health` trả 200 rồi chạy lệnh sau từ thư mục develop. Exit code 1 làm job thất bại khi accuracy dưới 85% hoặc bất kỳ câu nào baseline làm đúng chuyển thành sai. Đặt job này làm required status check của nhánh đích để chặn merge khi thất bại. Lần nghiệm thu CP7 dùng ngưỡng cao hơn là 100% và baseline v2 ban đầu.

```bash
python eval/run_eval.py --url http://localhost:8002 --min-accuracy 0.85 --baseline reports/eval_v2_fixed.json
```

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 2 alert cùng đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
