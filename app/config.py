"""Cấu hình đọc từ biến môi trường (.env)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-4-8"

    # Nguồn dữ liệu Q&A
    google_sheet_id: str = ""
    google_sheet_gid: str = "0"
    google_sheet_csv_url: str = ""
    qa_csv_path: str = "data/qa_sample.csv"
    qa_question_column: str = "question"
    qa_answer_column: str = "answer"
    # Chế độ đọc theo vị trí cột (0-based) cho sheet nhiều khối Q&A.
    # Ví dụ "2:3,7:8,11:12" = 3 khối, mỗi khối (cột hỏi : cột trả lời).
    # Để trống -> đọc theo tên cột question/answer (2 cột đơn giản).
    qa_column_pairs: str = ""
    qa_skip_rows: int = 0  # số dòng tiêu đề bỏ qua khi dùng chế độ vị trí cột

    # Ngưỡng khớp
    exact_match_threshold: float = 92
    min_match_threshold: float = 45
    top_k: int = 8
    fallback_answer: str = (
        "Xin lỗi, mình chưa có thông tin cho câu hỏi này. "
        "Bạn vui lòng để lại số điện thoại hoặc đợi nhân viên hỗ trợ nhé!"
    )

    # Facebook Messenger
    fb_page_access_token: str = ""
    fb_verify_token: str = "my-verify-token"

    # Zalo OA
    zalo_oa_access_token: str = ""

    # Telegram (dùng để test + kênh thông báo nội bộ)
    telegram_bot_token: str = ""
    telegram_admin_chat_id: str = ""  # chat/group nhận thông báo cho nhân viên

    # Gửi ảnh: file map từ khoá -> ảnh
    images_csv_path: str = "data/images.csv"

    @property
    def sheet_csv_url(self) -> str:
        """Trả về URL CSV export của Google Sheet (nếu có cấu hình)."""
        if self.google_sheet_csv_url:
            return self.google_sheet_csv_url
        if self.google_sheet_id:
            return (
                f"https://docs.google.com/spreadsheets/d/{self.google_sheet_id}"
                f"/export?format=csv&gid={self.google_sheet_gid}"
            )
        return ""

    @property
    def use_ai(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
