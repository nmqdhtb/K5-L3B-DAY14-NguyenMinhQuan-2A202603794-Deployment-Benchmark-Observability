# Triển khai agent Part 6

**Nền tảng:** Railway. **Thư mục build:** `06-lab-complete/`.

**URL public:** [https://agent-production-40ee2863.up.railway.app](https://agent-production-40ee2863.up.railway.app). [Kiểm tra readiness](https://agent-production-40ee2863.up.railway.app/ready).

Railway báo agent và Redis đều online trong project `day14-agent`, môi trường `production`. Railway CLI triển khai mã từ commit `b46afd2`, dùng Dockerfile của Part 6.

## Biến môi trường đã đặt

| Biến trên service agent | Cách cấp |
| --- | --- |
| `AGENT_API_KEY` | Đặt secret riêng trên Railway. |
| `REDIS_URL` | Tham chiếu biến kết nối của Redis trong cùng project. |
| `PORT` | Đặt `8000`, cùng cổng đích của public domain. |
| `ENVIRONMENT` | Đặt `production`. |

## Kiểm tra trên URL public

Đặt `BASE` bằng URL HTTPS của agent và nạp `AGENT_API_KEY` vào môi trường terminal. Kết quả đo lúc 16:05 ngày 26/11/2026 (GMT+7):

| Request | HTTP |
| --- | ---: |
| GET /health | 200 |
| GET /ready | 200 |
| POST /ask thiếu key | 401 |
| POST /ask có key | 200 |

```bash
BASE=https://agent-production-40ee2863.up.railway.app
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
```

## Ảnh minh chứng

- [Agent và Redis online](screenshots/dashboard.png)
- [Deployment đang chạy](screenshots/running.png)
- [Bốn request trong HTTP logs của Railway](screenshots/test.png)
