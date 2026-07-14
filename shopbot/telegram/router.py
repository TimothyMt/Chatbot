"""Định tuyến update Telegram: khách (chat riêng) / nhóm hỗ trợ / nhóm chốt đơn.

- Chat riêng: text -> debounce -> pipeline trả lời; ảnh -> chuyển nhóm hỗ trợ
  kèm ngữ cảnh (bot không tự đoán ảnh).
- Nhóm hỗ trợ: reply vào alert câu khó = trả lời khách + vào hàng đợi duyệt;
  các lệnh /stats /ingest /day /anh; nút ✅/❌ duyệt câu học.
- Nhóm chốt đơn: chỉ nhận thông báo, không xử lý tin.
"""
from __future__ import annotations

import asyncio
import logging

from .. import db, training
from ..answer import Reply, handle_customer_message
from ..config import settings
from ..ingest.run import run_ingest
from . import api
from .debounce import MessageBuffer

logger = logging.getLogger(__name__)

CHANNEL = "telegram"


class Router:
    def __init__(self, shop_id: int) -> None:
        self.shop_id = shop_id
        self.buffer = MessageBuffer(settings.debounce_seconds, self._on_flush)

    # ---------- entry point ----------

    async def handle_update(self, update: dict) -> None:
        update_id = update.get("update_id")
        if update_id is None:
            return
        if not await db.claim_update(CHANNEL, str(update_id)):
            logger.info("Bỏ qua update trùng %s", update_id)
            return

        if "callback_query" in update:
            await self._handle_callback(update["callback_query"])
            return

        msg = update.get("message")
        if not msg:
            return
        chat = msg.get("chat", {})
        chat_id = str(chat.get("id", ""))
        if not chat_id:
            return

        if chat.get("type") == "private":
            await self._handle_customer(chat_id, msg)
        elif chat_id == settings.telegram_support_chat_id:
            await self._handle_support_group(msg)
        # nhóm chốt đơn & nhóm lạ: bỏ qua

    # ---------- khách ----------

    async def _handle_customer(self, chat_id: str, msg: dict) -> None:
        photos = msg.get("photo") or []
        text = msg.get("text") or msg.get("caption") or ""

        if photos:
            await self.buffer.flush_now(chat_id)
            await self._forward_customer_photo(chat_id, msg, text)
            return
        if text.strip():
            self.buffer.add(chat_id, text.strip())

    async def _on_flush(self, chat_id: str, merged_text: str) -> None:
        try:
            conversation_id = await db.get_or_create_conversation(
                self.shop_id, CHANNEL, chat_id
            )
            reply = await handle_customer_message(
                self.shop_id, conversation_id, merged_text
            )
            await self._deliver(chat_id, conversation_id, reply)
        except Exception:
            logger.exception("Xử lý tin của %s lỗi", chat_id)

    async def _deliver(
        self, chat_id: str, conversation_id: int, reply: Reply
    ) -> None:
        for text in reply.texts:
            await api.send_message(chat_id, text)
        for img in reply.images:
            await api.send_photo(
                chat_id, img.get("file_id") or img.get("url") or "",
                img.get("caption") or "",
            )
        if reply.order_alert and settings.telegram_orders_chat_id:
            await api.send_message(settings.telegram_orders_chat_id, reply.order_alert)
        if reply.hard_alert_text and settings.telegram_support_chat_id:
            sent = await api.send_message(
                settings.telegram_support_chat_id, reply.hard_alert_text
            )
            if sent and reply.hard_question_id:
                await db.set_hard_question_alert(
                    reply.hard_question_id, str(sent.get("message_id", ""))
                )

    async def _forward_customer_photo(
        self, chat_id: str, msg: dict, caption: str
    ) -> None:
        """Ảnh khách gửi: không tự đoán — chuyển nhóm hỗ trợ kèm ngữ cảnh."""
        conversation_id = await db.get_or_create_conversation(
            self.shop_id, CHANNEL, chat_id
        )
        file_id = msg["photo"][-1].get("file_id", "")
        await db.log_message(
            conversation_id, "customer", caption or "[ảnh]",
            {"has_photo": True}, {"telegram_file_id": file_id},
        )
        history = await db.recent_messages(conversation_id, 6)
        context = "\n".join(f"[{m['role']}]: {m['content']}" for m in history)
        hard_id = await db.create_hard_question(
            self.shop_id, conversation_id, caption or "[khách gửi ảnh]"
        )
        alert = (
            f"🖼 KHÁCH GỬI ẢNH — câu khó #{hard_id}\n"
            f"Ghi chú của khách: {caption or '(không có)'}\n"
            f"Ngữ cảnh gần nhất:\n{context or '(chưa có)'}\n"
            f"👉 Reply tin này để trả lời khách."
        )
        if settings.telegram_support_chat_id:
            sent = await api.send_message(settings.telegram_support_chat_id, alert)
            if sent:
                await db.set_hard_question_alert(
                    hard_id, str(sent.get("message_id", ""))
                )
            await api.send_photo(
                settings.telegram_support_chat_id, file_id,
                f"Ảnh của câu khó #{hard_id}",
            )

    # ---------- nhóm hỗ trợ ----------

    async def _handle_support_group(self, msg: dict) -> None:
        text = (msg.get("text") or msg.get("caption") or "").strip()
        sender = msg.get("from", {})
        staff = sender.get("username") or str(sender.get("id", ""))
        chat_id = settings.telegram_support_chat_id

        # Lệnh
        if text.startswith("/stats"):
            await self._cmd_stats(chat_id)
            return
        if text.startswith("/ingest"):
            await self._cmd_ingest(chat_id)
            return
        if text.startswith("/day"):
            await self._cmd_teach(chat_id, text, staff)
            return
        if text.startswith("/anh"):
            await self._cmd_image(chat_id, msg, text, staff)
            return

        # Reply vào alert câu khó -> trả lời khách + hàng đợi duyệt
        reply_to = msg.get("reply_to_message")
        if reply_to and text:
            await self._handle_staff_reply(chat_id, reply_to, text, staff)

    async def _handle_staff_reply(
        self, group_id: str, reply_to: dict, text: str, staff: str
    ) -> None:
        alert_id = str(reply_to.get("message_id", ""))
        hard = await db.find_hard_question_by_alert(self.shop_id, alert_id)
        if not hard:
            return  # reply vào tin thường, không phải alert
        target = await db.get_conversation_target(hard["conversation_id"])
        if not target:
            return

        await api.send_message(target["external_user_id"], text)
        await db.log_message(
            hard["conversation_id"], "staff", text, {"via": "support_reply"}
        )
        await db.mark_hard_question_answered(hard["id"])

        teaching_id = await training.submit_teaching(
            self.shop_id, hard["question"], text, staff, hard["conversation_id"]
        )
        await api.send_message(
            group_id,
            training.render_pending_notice(teaching_id, hard["question"], text),
            reply_markup=api.approval_keyboard(teaching_id),
        )

    async def _cmd_stats(self, chat_id: str) -> None:
        s = await db.stats_summary(self.shop_id, days=7)
        answered = s["bot_replies"]
        total = max(s["customer_messages"], 1)
        await api.send_message(
            chat_id,
            "📊 7 ngày qua:\n"
            f"• Tin khách: {s['customer_messages']}\n"
            f"• Bot trả lời: {answered} (~{100 * answered // total}%)\n"
            f"• Câu khó: {s['hard_questions']}\n"
            f"• Chốt đơn: {s['orders']}\n"
            f"• Câu học đã duyệt: {s['taught_approved']} "
            f"(đang chờ duyệt: {s['pending_review']})\n"
            f"• Kho tri thức đang dùng: {s['active_knowledge']} câu",
        )

    async def _cmd_ingest(self, chat_id: str) -> None:
        await api.send_message(chat_id, "⏳ Đang nạp lại Google Sheet...")

        async def _run() -> None:
            try:
                stats = await run_ingest(self.shop_id)
                from ..answer import answer_cache

                answer_cache.clear()
                await api.send_message(
                    chat_id,
                    f"✅ Nạp xong: {stats['entries']} câu Q&A "
                    f"(từ {stats['chunks']} khối, {stats['sheets']} sheet).",
                )
            except Exception as exc:
                logger.exception("Ingest lỗi")
                await api.send_message(chat_id, f"❌ Nạp sheet lỗi: {exc}")

        asyncio.create_task(_run())

    async def _cmd_teach(self, chat_id: str, text: str, staff: str) -> None:
        parsed = training.parse_teach_command(text)
        if not parsed:
            await api.send_message(
                chat_id, "Cú pháp: /day <câu hỏi> | <câu trả lời>"
            )
            return
        q, a = parsed
        teaching_id = await training.submit_teaching(self.shop_id, q, a, staff)
        await api.send_message(
            chat_id,
            training.render_pending_notice(teaching_id, q, a),
            reply_markup=api.approval_keyboard(teaching_id),
        )

    async def _cmd_image(
        self, chat_id: str, msg: dict, text: str, staff: str
    ) -> None:
        """/anh <intent> [chú thích] — gửi kèm ảnh hoặc reply vào một ảnh."""
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            await api.send_message(
                chat_id,
                "Cú pháp: gửi ảnh kèm caption `/anh <intent> [chú thích]`\n"
                "hoặc reply vào ảnh với lệnh đó. Intent trùng với intent trong "
                "kho tri thức (xem cột intent khi ingest), vd: bang_size, thanh_toan.",
            )
            return
        intent = parts[1].strip()
        caption = parts[2].strip() if len(parts) > 2 else ""

        photos = msg.get("photo") or (msg.get("reply_to_message") or {}).get("photo") or []
        if not photos:
            await api.send_message(chat_id, "Không thấy ảnh — gửi ảnh kèm lệnh hoặc reply vào ảnh.")
            return
        file_id = photos[-1].get("file_id", "")
        asset_id = await db.add_image_asset(
            self.shop_id, intent, file_id, caption, staff
        )
        await api.send_message(
            chat_id, f"🖼 Đã lưu ảnh #{asset_id} cho intent `{intent}`."
        )

    # ---------- nút duyệt ----------

    async def _handle_callback(self, callback: dict) -> None:
        data = callback.get("data", "")
        parsed = training.parse_callback(data)
        callback_id = callback.get("id", "")
        if not parsed:
            await api.answer_callback(callback_id)
            return
        action, teaching_id = parsed
        sender = callback.get("from", {})
        staff = sender.get("username") or str(sender.get("id", ""))

        if action == "ok":
            result = await training.approve_teaching(teaching_id, staff)
        else:
            result = await training.reject_teaching(teaching_id, staff)
        await api.answer_callback(callback_id, "Đã xử lý")

        msg = callback.get("message") or {}
        if msg.get("message_id") and msg.get("text"):
            await api.edit_message_text(
                msg["chat"]["id"], msg["message_id"], f"{msg['text']}\n\n{result}"
            )
