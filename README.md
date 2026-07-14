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
  Sheet cần có 2 cột tiêu đề `question` và `answer` (đổi tên trong `.env` nếu khác).
  Chưa cấu hình sheet thì bot dùng file mẫu `data/qa_sample.csv`.
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
