# Vận hành & dạy bot

## Cài đặt lần đầu

1. **Supabase**: tạo project (đã có). Lấy connection string
   (Settings → Database → URI) đặt vào `DATABASE_URL`.
2. Điền `.env` theo `.env.example` (Anthropic, OpenAI, Telegram token,
   2 chat_id nhóm, link sheet, persona).
3. Chạy migration:
   ```bash
   pip install -r requirements.txt
   python scripts/migrate.py
   ```
4. Nạp sheet lần đầu:
   ```bash
   python scripts/ingest.py
   ```
5. Deploy Railway (repo này có `Dockerfile` + `Procfile`; set toàn bộ biến
   `.env` vào Railway Variables), rồi đăng ký webhook:
   ```bash
   python scripts/set_webhook.py https://<app>.up.railway.app
   ```
6. Thêm bot vào 2 nhóm Telegram (nhóm chốt đơn + nhóm hỗ trợ). Lấy chat_id
   nhóm: thêm bot @RawDataBot vào nhóm hoặc xem trong log webhook.

## Lệnh trong NHÓM HỖ TRỢ

| Lệnh | Tác dụng |
|---|---|
| `/stats` | Thống kê 7 ngày: tin khách, tỉ lệ trả lời, câu khó, đơn, câu học |
| `/ingest` | Nạp lại Google Sheet (sheet sửa xong gõ lệnh này là cập nhật) |
| `/day <câu hỏi> \| <câu trả lời>` | Dạy trực tiếp 1 câu (vào hàng đợi duyệt) |
| `/anh <intent> [chú thích]` | Gửi ảnh kèm caption này (hoặc reply vào ảnh) để đăng ký ảnh cho intent — vd `/anh bang_size Bảng size váy` |

## Dạy bot qua câu khó (luồng chính)

1. Khách hỏi câu bot không chắc → bot **im lặng với khách** (hoặc gửi câu giữ
   chân nếu đặt `HOLDING_MESSAGE`) và đăng alert `❓ CÂU KHÓ #id` vào nhóm hỗ trợ.
2. Nhân viên **reply trực tiếp vào tin alert** bằng câu trả lời đúng:
   - Câu trả lời được gửi cho khách NGAY.
   - Đồng thời tạo `📚 CÂU HỌC MỚI` kèm 2 nút.
3. Ai đó bấm **✅ Duyệt** → câu học vào kho tri thức, lần sau bot tự trả lời.
   Bấm **❌ Bỏ** → chỉ trả lời khách lần này, bot không học.

> Nên duyệt các câu kiến thức chung (chính sách, phí, size...), bỏ qua câu
> tình huống ("chị chờ em kiểm tra kho").

Khách **gửi ảnh** → bot chuyển ảnh + ngữ cảnh hội thoại vào nhóm hỗ trợ như
một câu khó; nhân viên reply là trả lời khách, và câu trả lời cũng vào hàng
đợi duyệt như trên.

## Cập nhật dữ liệu khi sheet thay đổi

Sửa sheet → gõ `/ingest` trong nhóm hỗ trợ (hoặc `POST /ingest` với header
`X-Admin-Token: <telegram bot token>`). Mỗi lần nạp là một phiên bản
(`ingest_runs`); nạp lỗi thì dữ liệu cũ giữ nguyên.

**Rollback** một lần nạp hỏng (chạy trong SQL editor của Supabase):
```sql
-- xem các lần nạp
select id, status, stats, started_at from ingest_runs order by id desc limit 5;

-- quay về run cũ (vd run 12), tắt run mới (vd run 13)
update knowledge_entries set status='superseded' where ingest_run_id = 13;
update knowledge_entries set status='active'
 where ingest_run_id = 12 and status='superseded';
```

## Chỉnh ngưỡng & giọng điệu

- Bot **bỏ qua quá nhiều** câu đáng lẽ trả lời được → hạ `MIN_SIMILARITY`
  (vd 0.30). Bot **trả lời nhầm** → nâng lên (vd 0.45).
- Đổi giọng điệu: sửa `SHOP_PERSONA` (biến môi trường) — không cần sửa code.
- Sau mỗi lần chỉnh, chạy eval để chắc không hồi quy:
  ```bash
  python eval/run_eval.py eval/questions.yaml
  ```
  (tạo `eval/questions.yaml` từ `eval/questions.example.yaml` với câu hỏi thật).

## Truy vết "vì sao bot trả lời câu này"

```sql
select m.created_at, m.content, m.meta
  from messages m
 where m.role='bot'
 order by m.id desc limit 20;
```
`meta.used_entry_ids` → tra `knowledge_entries` xem nguồn (sheet run nào /
ai dạy, ai duyệt).

## Sự cố thường gặp

| Hiện tượng | Kiểm tra |
|---|---|
| Bot không phản hồi gì | `GET /health`; log Railway; webhook đúng chưa (`getWebhookInfo`) |
| Bot trả lời 2 lần | Không thể do retry (đã dedup) — xem có 2 instance cùng chạy không |
| Ingest ra ít câu | Xem `ingest_runs.stats`; sheet có public không; thử `/ingest` lại |
| Alert không tới nhóm | chat_id nhóm đúng chưa (số âm -100...), bot đã ở trong nhóm chưa |
