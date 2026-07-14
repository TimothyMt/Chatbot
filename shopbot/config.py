"""Cấu hình hệ thống — CHỈ chứa thông số hạ tầng, không chứa dữ liệu nghiệp vụ.

Mọi giá trị nghiệp vụ (giá, size, chính sách...) nằm trong Google Sheet hoặc
câu nhân viên dạy (bảng knowledge_entries). Giọng điệu bot là config theo shop.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PERSONA = (
    "Bạn là nhân viên chăm sóc khách hàng của một cửa hàng, trả lời bằng tiếng Việt, "
    "thân thiện và lịch sự."
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Hạ tầng bắt buộc
    database_url: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    telegram_bot_token: str = ""

    # 2 nhóm nhân sự riêng: chốt đơn / câu khó + huấn luyện
    telegram_orders_chat_id: str = ""
    telegram_support_chat_id: str = ""
    # Bảo vệ webhook: Telegram gửi kèm header X-Telegram-Bot-Api-Secret-Token
    telegram_webhook_secret: str = ""

    # Nguồn dữ liệu: 1 hoặc nhiều URL Google Sheet (cách nhau dấu phẩy).
    # Chấp nhận cả link edit (tự chuyển thành CSV export) lẫn link export sẵn.
    sheet_urls: str = ""

    # Định danh shop (đa shop = nhiều deploy, mỗi deploy 1 slug)
    shop_slug: str = "default"
    shop_name: str = "Shop"
    # Giọng điệu bot — là DATA (config), không nướng vào code
    shop_persona: str = DEFAULT_PERSONA
    # Câu giữ chân khi gặp câu khó; để trống = im lặng hoàn toàn với khách
    holding_message: str = ""

    # Model routing: rẻ cho phân loại/viết lại/ingest, lớn hơn cho soạn trả lời
    claude_fast_model: str = "claude-haiku-4-5"
    claude_smart_model: str = "claude-sonnet-5"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Ngưỡng tin cậy semantic search (cosine similarity 0..1)
    min_similarity: float = 0.35
    high_similarity: float = 0.75

    # Gộp tin nhắn dồn dập của khách trong N giây thành 1 lượt
    debounce_seconds: float = 4.0
    # Số tin nhắn gần nhất đưa vào ngữ cảnh
    history_limit: int = 10
    # Cache câu trả lời (giây); 0 = tắt
    answer_cache_ttl: int = 600


settings = Settings()
