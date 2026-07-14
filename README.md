# Chatbot chăm sóc khách hàng

Chatbot trả lời khách dựa trên bảng câu hỏi - trả lời (Q&A) có sẵn trên Google Sheets.
Cơ chế **"1+2" kết hợp**:

1. **Khớp câu hỏi (miễn phí, nhanh):** tìm câu gần giống nhất trong sheet bằng thuật toán fuzzy.
   Nếu khớp gần như tuyệt đối → trả thẳng câu trả lời có sẵn.
2. **AI soạn câu trả lời (Claude):** nếu khớp vừa phải, đưa các câu ứng viên cho Claude
   soạn câu trả lời tự nhiên, **chỉ dùng thông tin trong sheet** (không bịa).
3. Nếu không tìm được thông tin phù hợp → trả câu mặc định (mời để lại SĐT / chờ nhân viên).

Kênh hỗ trợ: **Facebook Messenger** và **Zalo OA** (qua webhook), cùng endpoint `/chat` để test.

## Cài đặt

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # rồi mở .env điền cấu hình
```

## Cấu hình `.env`

- **Google Sheet:** mở sheet → Share → *Anyone with the link (Viewer)*, rồi điền `GOOGLE_SHEET_ID`
  (phần giữa `/d/` và `/edit` trong URL) và `GOOGLE_SHEET_GID` (số `gid` của tab).
  - **Sheet 2 cột đơn giản:** đặt tiêu đề `question` / `answer` (đổi tên trong `.env` nếu khác).
  - **Sheet nhiều khối Q&A** (như bảng kịch bản Pancake): đọc theo *vị trí cột* bằng
    `QA_COLUMN_PAIRS` và `QA_SKIP_ROWS`. Ví dụ sheet có 3 khối câu hỏi–trả lời ở các cột
    2-3, 7-8, 11-12 và 2 dòng tiêu đề đầu → đặt `QA_COLUMN_PAIRS=2:3,7:8,11:12` và
    `QA_SKIP_ROWS=2` (số cột tính từ 0).
  Chưa cấu hình sheet thì bot dùng file `data/qa.csv` (hoặc `data/qa_sample.csv`).
- **Claude:** điền `ANTHROPIC_API_KEY` để bật AI soạn câu trả lời. Bỏ trống → bot chỉ
  chạy tầng khớp (trả câu có sẵn), vẫn hoạt động nhưng kém linh hoạt hơn.

## Chạy thử

Test nhanh trong terminal (không cần webhook):

```bash
python cli.py
```

Chạy server:

```bash
uvicorn app.main:app --reload
```

Test bằng API:

```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message":"shop mở cửa lúc mấy giờ vậy?"}'
```

Các endpoint khác: `GET /health`, `POST /reload` (nạp lại sheet ngay).

## Bot Telegram để test (khuyên dùng khi thử nghiệm)

Không cần domain/HTTPS, chạy bằng long-polling:

1. Nhắn **@BotFather** trên Telegram → `/newbot` → lấy token, điền `TELEGRAM_BOT_TOKEN` vào `.env`.
2. Chạy: `python run_telegram.py` rồi nhắn cho bot để test.

## Kênh thông báo cho nhân viên

Bot tự gửi cảnh báo vào một nhóm Telegram khi:
- **Chốt đơn** — khách để lại tin nhắn có số điện thoại + địa chỉ/thông tin đặt hàng.
- **Câu hỏi khó** — bot không tìm được câu trả lời (kể cả bằng ảnh).

Cách lấy id nhóm: tạo 1 nhóm Telegram, thêm bot vào, gửi 1 tin trong nhóm — log của
`run_telegram.py` sẽ in `chat_id`; điền id đó vào `TELEGRAM_ADMIN_CHAT_ID`.

## Gửi ảnh khi khách hỏi

Bot tự gửi ảnh (bảng size, ảnh mẫu, màu, STK/QR…) khi câu hỏi chứa từ khoá tương ứng.
Cấu hình trong `data/images.csv`:

| Cột | Ý nghĩa |
|---|---|
| `keywords` | Các từ khoá cách nhau bởi `\|` (có/không dấu đều nhận) |
| `image_url` | Link ảnh **công khai** của bạn (thay link mẫu `placehold.co`) |
| `caption` | Chú thích gửi kèm ảnh |

> Ảnh mẫu đang dùng link `placehold.co` để demo — **thay bằng link ảnh thật của shop**
> (upload ảnh lên Google Drive/Imgur/hosting và dán link trực tiếp tới file ảnh).

## Kết nối Messenger / Zalo

Server cần chạy trên internet có HTTPS. Khi dev, dùng `ngrok http 8000` để lấy URL công khai.

**Facebook Messenger** (cần Facebook Page + App):
- Webhook URL: `https://<domain>/webhook/messenger`
- Verify Token: đúng với `FB_VERIFY_TOKEN` trong `.env`
- Điền `FB_PAGE_ACCESS_TOKEN`, subscribe field `messages` cho Page.

**Zalo OA** (cần Official Account):
- Webhook URL: `https://<domain>/webhook/zalo`
- Điền `ZALO_OA_ACCESS_TOKEN`.

## Điều chỉnh độ "nhạy"

Trong `.env`:
- `EXACT_MATCH_THRESHOLD` (mặc định 92): điểm ≥ ngưỡng → trả thẳng câu có sẵn.
- `MIN_MATCH_THRESHOLD` (mặc định 45): điểm < ngưỡng → coi như không biết.
- `TOP_K`: số câu ứng viên đưa cho Claude.
