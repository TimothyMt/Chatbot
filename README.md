# Shop CSKH Bot

Chatbot chăm sóc khách hàng tiếng Việt cho shop bán quần áo online — hiểu ngữ
nghĩa + ngữ cảnh, tự nạp & phân loại dữ liệu từ Google Sheet, học được từ
nhân viên (có duyệt), không trả lời bậy.

**Nguyên tắc:** mọi thông tin nghiệp vụ là dữ liệu (sheet / câu đã dạy, lưu
Supabase) — không hardcode vào code hay prompt. Chạy được với bất kỳ shop nào.

## Tính năng

- **Ingest tự động**: đưa link Google Sheet (kể cả dạng kịch bản Pancake nhiều
  khối, cột lộn xộn) → tự trích Q&A, gán intent/nhóm, loại nhiễu. Không cần
  khai báo cột. Mỗi lần nạp là một phiên bản, rollback được.
- **Hiểu ngữ cảnh**: viết lại câu cụt ("giá", "nhiêu") theo hội thoại rồi mới
  semantic search (embeddings + pgvector) — không khớp nhầm kiểu so chữ.
- **Vòng học**: câu khó → báo nhóm hỗ trợ → nhân viên reply là trả lời khách
  ngay + vào hàng đợi duyệt (nút ✅/❌) → duyệt xong bot tự trả lời lần sau.
  Lưu bền vững, không mất khi redeploy.
- **An toàn**: ngoài phạm vi → im lặng với khách, chỉ báo nhân sự. Xác nhận
  đơn bằng template cố định — không bịa chi tiết.
- **Ảnh**: gửi ảnh theo intent (bảng size, STK...); ảnh khách gửi lên được
  chuyển nhân sự kèm ngữ cảnh.
- **Đo lường**: log đầy đủ từng lượt; `/stats` ra tỉ lệ trả lời/câu khó/đơn;
  bộ eval chống hồi quy.

## Chạy nhanh

```bash
cp .env.example .env   # điền keys
pip install -r requirements.txt
python scripts/migrate.py       # tạo schema Supabase
python scripts/ingest.py        # nạp sheet lần đầu
uvicorn shopbot.main:app --reload
python scripts/set_webhook.py https://<domain>   # sau khi deploy
```

Test (offline, không cần keys): `pip install -r requirements-dev.txt && pytest`

## Tài liệu

- [docs/architecture.md](docs/architecture.md) — kiến trúc, lý do thiết kế, schema
- [docs/operations.md](docs/operations.md) — vận hành, dạy bot, rollback, sự cố

## Cấu trúc

```
shopbot/
  config.py        # cấu hình hạ tầng (env), persona là config
  db.py            # toàn bộ SQL (Supabase/pgvector)
  llm.py           # mọi lời gọi Claude (routing model rẻ/đắt)
  embeddings.py    # OpenAI embeddings
  ingest/          # sheet -> chunks -> LLM trích Q&A -> embed -> version
  answer.py        # pipeline trả lời (ngữ cảnh -> search -> soạn/câu khó)
  orders.py        # trích field + template xác nhận cố định
  training.py      # vòng học + duyệt
  telegram/        # webhook router, debounce, API
migrations/        # schema SQL
scripts/           # migrate / ingest / set_webhook
eval/              # bộ đo chất lượng
tests/             # unit test offline
```
