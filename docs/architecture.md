# Kiến trúc hệ thống chatbot CSKH

## Nguyên tắc cốt lõi

Hệ thống làm việc ở **tầng hệ thống**: mọi thông tin nghiệp vụ (giá, size,
chính sách, STK...) là **dữ liệu** — nằm trong Google Sheet hoặc câu nhân viên
dạy (đã duyệt), lưu ở Supabase. Code và prompt không chứa dữ liệu nghiệp vụ;
giọng điệu bot (`SHOP_PERSONA`) là config theo shop. Thiết kế chạy được với
bất kỳ shop/sheet nào: đổi shop = đổi biến môi trường + deploy mới (schema đã
có `shop_id` từ đầu).

## Sơ đồ tổng thể

```
Google Sheet (public)                Telegram
      │ /ingest hoặc lệnh nhóm            │ webhook (dedup update_id, trả 200 ngay)
      ▼                                   ▼
┌──── INGEST ────┐              ┌──── ROUTER ─────────────────────────┐
│ tải CSV → grid │              │ chat riêng = khách                  │
│ cắt khối/chunk │              │ nhóm hỗ trợ = câu khó + huấn luyện  │
│ (cấu trúc bất  │              │ nhóm chốt đơn = chỉ nhận thông báo  │
│  khả tri)      │              └───────┬─────────────────────────────┘
│ LLM Haiku trích│                      │ debounce 4s (gộp tin dồn)
│ Q&A + intent   │                      ▼
│ + loại nhiễu   │              ┌──── ANSWER PIPELINE ────────────────┐
│ dedup + embed  │              │ 1 Haiku: viết lại câu theo ngữ cảnh │
└──────┬─────────┘              │   + phân loại (question/order/...)  │
       ▼                        │ 2 embed (OpenAI) → pgvector search  │
┌─── SUPABASE ───┐◄─────────────│ 3 sim < ngưỡng → CÂU KHÓ (im lặng   │
│ knowledge      │              │   với khách, báo nhóm hỗ trợ)       │
│ (sheet+taught, │─────────────►│ 4 Sonnet soạn trả lời CHỈ từ dữ liệu│
│  versioned)    │              │   KHONG_BIET → CÂU KHÓ              │
│ conversations/ │              │ 5 đơn hàng: trích field → template  │
│ messages (log) │              │   CỐ ĐỊNH, không cho LLM soạn       │
│ pending_       │              │ 6 ảnh theo intent; cache câu lặp    │
│ teachings      │              └─────────────────────────────────────┘
│ orders/hard_q/ │
│ image_assets   │        VÒNG HỌC: alert câu khó → nhân viên reply →
│ processed_     │        gửi khách ngay + pending_teaching → nút ✅/❌
│ updates        │        → duyệt = embed + knowledge_entries(taught)
└────────────────┘
```

## Các quyết định thiết kế & lý do

### 1. Ingest không cần khai báo cột
Sheet Pancake lộn xộn (nhiều khối cạnh nhau, cột không chuẩn, lẫn bước kịch
bản/phím tắt/mẫu remind). Parse bằng rule sẽ giòn — thay vào đó:
- Heuristic **cấu-trúc**: tách khối theo cột trống hoàn toàn, cắt cửa sổ dòng
  chồng lấn (kèm header) — không phụ thuộc ngữ nghĩa.
- **LLM (Haiku)** làm phần ngữ nghĩa: nhận diện cặp Q&A, gán intent/category,
  bỏ nhiễu — theo hướng dẫn chung, không theo một sheet cụ thể.
- Đầu ra JSON theo schema (structured outputs) nên không có lỗi parse.

### 2. Versioning tri thức
Mỗi lần nạp là 1 `ingest_run`. Entry mới ghi xong mới `superseded` bản cũ
(cùng transaction) → ingest lỗi không mất dữ liệu; rollback = update status.
Mỗi câu bot trả lời log kèm `used_entry_ids` → truy được "bot nói câu này vì
dữ liệu nào, ai dạy, nạp lúc nào".

### 3. Hiểu ngữ nghĩa + ngữ cảnh (thay fuzzy matching)
Lỗi nặng nhất của bản cũ là so chữ: "tiền" trùng 1 từ được ~100 điểm → khớp
sai intent. Bản mới:
- **Viết lại câu theo ngữ cảnh** (Haiku + N lượt hội thoại gần nhất): "nhiêu"
  sau khi nói về váy A → "váy A giá bao nhiêu". Câu cụt hết mơ hồ TRƯỚC khi
  tìm kiếm.
- **Embeddings + pgvector** (cosine): hiểu ngữ nghĩa, không so chữ. Điểm
  similarity liên tục 0..1, hai ngưỡng: `MIN_SIMILARITY` (dưới = câu khó),
  `HIGH_SIMILARITY` (trên = được cache).

### 4. Một bot, hai chế độ (không tách bot training)
Phân biệt tự nhiên theo loại chat: chat riêng = khách; nhóm hỗ trợ = chế độ
huấn luyện. Ưu điểm: 1 token/1 webhook/1 deploy, và luồng dạy nằm đúng chỗ
nhận báo câu khó — nhân viên reply là dạy luôn. Tách 2 bot chỉ cần khi phân
quyền khác nhau (đã quyết bỏ phân quyền).

### 5. Vòng học có duyệt
Reply của nhân viên gửi cho khách NGAY (khách không phải chờ duyệt), nhưng
chỉ vào kho tri thức sau khi bấm ✅ — tránh câu trả lời tình huống ("chị chờ
em check kho") thành kiến thức vĩnh viễn. Lưu Supabase → không mất khi
redeploy Railway.

### 6. Đơn hàng không bịa
LLM chỉ được trích field khách nói (structured output, field thiếu = null);
câu xác nhận do **code render template cố định** — model không soạn văn xác
nhận đơn nên không thể bịa chi tiết.

### 7. Định tuyến model & chi phí
- Haiku ($1/$5 per MTok): viết lại/phân loại (~300 token), trích đơn, ingest.
- Sonnet ($3/$15): chỉ soạn câu trả lời cuối.
- Cache in-memory cho câu hỏi lặp (similarity cao) — 0 LLM call.
- Debounce gộp tin dồn: 3 tin ngắn = 1 lượt xử lý thay vì 3.

### 8. An toàn webhook
- Dedup `update_id` bằng unique constraint (Telegram retry không xử lý 2 lần).
- Trả 200 ngay, xử lý nền (Telegram timeout ngắn).
- `secret_token` webhook chống giả mạo request.

## Schema Supabase

Xem `migrations/001_init.sql` (có comment từng bảng). Tóm tắt:

| Bảng | Vai trò |
|---|---|
| `shops`, `shop_config` | định danh + config theo shop (persona, holding message...) |
| `ingest_runs` | version từng lần nạp sheet |
| `knowledge_entries` | Q&A (sheet/taught) + intent + embedding vector(1536), status lifecycle |
| `pending_teachings` | hàng đợi duyệt câu học (ai dạy, ai duyệt, lúc nào) |
| `conversations`, `messages` | bộ nhớ ngữ cảnh + log đo lường (meta: source, similarity, used_entry_ids, latency) |
| `hard_questions` | câu khó + map alert→khách cho vòng học |
| `orders` | đơn đã trích (chỉ field khách nói) |
| `image_assets` | ảnh theo intent (telegram file_id) |
| `processed_updates` | chống trùng webhook |

## Đo lường & eval

- Mỗi lượt log vào `messages.meta` → lệnh `/stats` trong nhóm hỗ trợ ra tỉ lệ
  trả lời được / câu khó / chốt đơn / câu học.
- `eval/run_eval.py` + file YAML câu hỏi thật: chạy trước & sau khi đổi
  prompt/ngưỡng/model để chống hồi quy (thay cho A/B — đã chốt ngoài phạm vi).

## Mở rộng sau

- Messenger/Zalo: thêm module `channels/` mới dùng lại nguyên pipeline
  (`handle_customer_message` không biết gì về Telegram).
- Đa shop: schema đã sẵn `shop_id`; shop mới = 1 deploy mới với env riêng.
- Vision cho ảnh khách gửi: hiện chuyển nhân sự; sau có thể thêm bước Claude
  vision mô tả ảnh trước khi chuyển.
