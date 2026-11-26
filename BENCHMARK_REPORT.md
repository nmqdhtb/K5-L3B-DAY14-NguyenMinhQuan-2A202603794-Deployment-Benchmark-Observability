# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyễn Minh Quân
**Ngày chạy:** 26/11/2026
**Môi trường:** macOS 26.6, arm64, Python 3.12.2. Ở mục 1–3, agent chạy local bằng Uvicorn với một worker. Mục 4–5 dùng Docker Compose, Nginx và Locust. Dùng mock LLM của bài, v1 ở cổng 8001 và v2 ở cổng 8002. Chi phí trong báo cáo được tính theo token và bảng giá của mock.

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

## 4. Observability stack

### 4.1 Dashboard khi có tải

Locust chạy 30 user, tăng 5 user/giây, qua Nginx trên cổng 8080. Số dưới đây lấy tại một lần truy vấn Prometheus. Ảnh Grafana ở lần refresh kế tiếp hiển thị 16.8 req/s và p95 1.26 giây. Trong cửa sổ một phút của Prometheus với hai replica, p95 của `/ask` là **1521 ms** và trung bình là **345 ms**. p95 được ước lượng từ các bucket histogram; giá trị cao hơn trung bình cho thấy một nhóm request phải đợi lâu hơn. [Dashboard Grafana](screenshots/grafana-dashboard.png)

- **Chia tải:** panel Requests/s theo instance ghi nhận 172.25.0.3:8000 = 8.44, 172.25.0.8:8000 = 8.13 req/s. Chênh lệch nhỏ giữa hai tốc độ cho thấy Nginx chia tải khá đều trong cửa sổ này.
- **Token:** input đạt 1216.9 token/s, output đạt 644.9 token/s. Agent v2 thêm system prompt, câu hỏi và tài liệu truy xuất vào đầu vào; đầu ra chỉ gồm câu trả lời.
- **Scrape:** `GET http://localhost:8080/metrics` trả HTTP 404. Nginx chặn route này ở cổng public; Prometheus khám phá các replica qua DNS và scrape trực tiếp cổng 8000 trong mạng Docker.

### 4.2 Alert và thí nghiệm mô phỏng lỗi

`promtool test rules /p/alert_rules_test.yml` trả `SUCCESS`. Các thời gian bên dưới là số giây từ lúc bắt đầu áp dụng thay đổi tới lần đầu API Prometheus báo firing. Chu kỳ đánh giá 5 giây, các lượt A/B được thăm dò mỗi 2 giây. [Hai alert cùng firing trên Prometheus](screenshots/prometheus-alert-firing.png)

| Thí nghiệm | Quan sát |
|---|---|
| A · `MOCK_ERROR_RATE=0.2` | AgentHighErrorRate firing sau **95.5 s**. Tại lần chụp chung, 20.5% request /ask trả 5xx. Rule yêu cầu trên 5% liên tục trong 1 phút. |
| B · `MOCK_SLOW_RATE=0.3` | AgentHighLatencyP95 firing sau **149.8 s**. p95 tại lần chụp là 1888 ms; rule yêu cầu trên 1 giây liên tục trong 2 phút. |
| C · `LLM_MODEL=mock-llm-large` | Panel cost ước tính 15.21 USD/giờ trên cửa sổ 5 phút tại thời điểm đọc. LLMCostBurnRateHigh firing sau 142.1 s. |
| D · Tạm dừng một trong hai replica | AgentInstanceDown ở trạng thái firing sau 38.3 s. Target còn trong DNS nhưng dừng trả lời scrape. Đã unpause sau phép thử. |
| E · `AGENT_VERSION=v1` | Eval qua Nginx nhận được phản hồi cho cả 23 câu nhưng chỉ 1 câu đúng. Tại thời điểm đo, cả hai replica đều up và Prometheus không có alert đang hoạt động. Các rule hiện có theo dõi lỗi, độ trễ, chi phí và khả dụng. Eval trên golden dataset phát hiện suy giảm chất lượng kể cả khi HTTP vẫn trả 200. |

Trên Grafana, A thể hiện ở panel **Error rate**, B ở **Latency p95**, C ở **Cost burn rate (USD/giờ)** và D ở **Instances up**. Với E, panel **Phiên bản đang chạy** cho biết phiên bản phục vụ, còn điểm eval cho biết chất lượng câu trả lời. [Số liệu Prometheus, thời gian cảnh báo và hai trace gốc](benchmark-results/observability.json)

A và B được bật đồng thời trên cùng tải để quan sát hai alert. Cửa sổ tính cost 5 phút có thể gồm dữ liệu trước khi đổi model. Với D, timeout do Nginx phát sinh được ghi ở proxy/client; counter của agent không đếm được request mà agent chưa hoàn thành.

### 4.3 Từ trace đến log

**Trace chậm.** Trong 75 giây log được khảo sát, đây là request /ask thành công chậm nhất tìm thấy cả trong log lẫn Jaeger. Trace `a0d6475ff868dd049bdb32330a90a562` kéo dài 1965.34 ms. Span gọi model `chat mock-llm-small` chiếm 1686.32 ms (85.8% tổng thời gian). Trong các bước con của agent, lời gọi model chiếm nhiều thời gian nhất. [Ảnh Jaeger](screenshots/jaeger-slow-trace.png)

Dòng log JSON tương ứng từ container agent là

```json
{"ts":"2026-11-26T09:57:59.059404+00:00","level":"INFO","service":"observable-agent","instance":"ebf8e4e9e9f0","event":"http_request","trace_id":"a0d6475ff868dd049bdb32330a90a562","span_id":"3b23ea4a0ec3325e","request_id":"2a8a7c8f2f47","method":"POST","route":"/ask","status":200,"ms":1964.1}
```

**Trace lỗi.** Trace `2ae2fc7bee6c85fcdab9268ed31a7582` kéo dài 868.59 ms. Span gọi model `chat mock-llm-small` chiếm 849.26 ms (97.8% tổng thời gian). Jaeger ghi event `exception` trong span LLM; agent ghi `llm_error` và trả HTTP 503. [Ảnh Jaeger](screenshots/jaeger-error-trace.png)

Dòng log JSON tương ứng từ container agent là

```json
{"ts":"2026-11-26T09:57:20.069468+00:00","level":"INFO","service":"observable-agent","instance":"456c50df2b50","event":"llm_error","trace_id":"2ae2fc7bee6c85fcdab9268ed31a7582","span_id":"079667999ff6f271","request_id":"6011ed747b43","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling

Hai lượt Locust headless dùng cùng kịch bản, 100 user, ramp 10 user/giây, 2 phút/lượt. Bảng dùng hàng `Aggregated` trong CSV (gồm `/ask` và `/health`), percentile theo mili giây. Mỗi replica agent có giới hạn 0,5 CPU và 256 MB RAM. Máy chạy chung bộ tạo tải và stack giám sát.

| Replica | Request | RPS | p50 | p95 | p99 | Failures | Error rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| [1](benchmark-results/scale_1_stats.csv) | 2689 | 24.10 | 570 | 10000 | 14000 | 346 | 12.87% |
| [3](benchmark-results/scale_3_stats.csv) | 6814 | 57.18 | 200 | 1700 | 3800 | 65 | 0.95% |

Riêng `POST /ask`, lượt 1 replica có 346 lỗi trên 2446 request (14.15%), còn lượt 3 replica có 65 lỗi trên 6229 request (1.04%). Cả hai lượt đều vượt mục tiêu p95 500 ms. Chỉ lượt 3 replica đạt mục tiêu tỷ lệ lỗi ≤ 2%. Khi so sánh với CP7, cần lưu ý Locust tính độ trễ cả phản hồi lỗi, còn load test CP7 tính độ trễ trên phản hồi HTTP 200.

Qua Nginx, throughput tăng **2.37 lần** và p95 giảm **83.0%**. Ở lượt 1 replica, CSV lỗi ghi 320 lần HTTP 504 và 26 lần HTTP 503. Với 3 replica, 65 lỗi đều là HTTP 503. Kết quả phù hợp với việc các replica chia sẻ tải và giảm thời gian xếp hàng. Độ trễ của từng lời gọi mock LLM vẫn góp vào phần đuôi của phân phối. Trong lượt 1 replica, máy cũng mở giao diện truy vết. Đây là một lượt cho mỗi cấu hình trên máy dùng chung, không đủ để quy toàn bộ chênh lệch cho số replica.

Để lặp lại, dùng cùng project Compose `k5-day14-observability`, đặt `--scale agent=1` rồi `--scale agent=3`. Chờ health check và Docker DNS cập nhật trước mỗi lượt. Khi gọi `docker compose run`, thêm `--no-deps` để Locust không khởi tạo lại agent theo số replica mặc định của Compose. Đã kiểm tra số container agent trước và sau mỗi lượt. [Chi tiết lỗi khi chạy 1 replica](benchmark-results/scale_1_failures.csv) · [Chi tiết lỗi khi chạy 3 replica](benchmark-results/scale_3_failures.csv)

## 6. Kết luận

1. Ở CP7, khi tỷ lệ request chậm tăng từ 0 lên 3%, p99 tăng từ 230 lên 1671.8 ms trong khi trung bình chỉ tăng 33.7 ms. Theo dõi percentile giúp nhận ra nhóm người dùng phải chờ lâu.
2. Ở CP8, kết hợp số liệu ở Nginx, agent và trace giúp phân biệt timeout của proxy với lỗi do mock LLM trả về. Chỉ xem metric của agent sẽ bỏ sót một phần lỗi mà client gặp.
3. Hạ tầng vẫn có thể trả HTTP 200 khi nội dung sai. Đo chi phí trên mỗi câu trả lời đúng và chạy eval trước khi phát hành giúp so sánh chi phí với chất lượng thực nhận.

Trong production, nên bổ sung tỷ lệ 5xx và timeout đo tại proxy cùng một phép thử định kỳ đi qua URL public. Theo dõi accuracy trên bộ câu hỏi đã gán nhãn theo phiên bản để cảnh báo suy giảm chất lượng.
