"""Xác nhận đơn không bịa: chỉ hiển thị field khách cung cấp."""
from shopbot.orders import (
    missing_required,
    provided_fields,
    render_confirmation,
    render_staff_alert,
)

FIELDS = {
    "phone": "0912345678",
    "name": None,
    "address": "12 Nguyễn Trãi, Hà Nội",
    "product": None,
    "size": "  ",
    "color": None,
    "quantity": None,
    "note": None,
}


def test_provided_fields_drops_null_and_blank():
    got = provided_fields(FIELDS)
    assert got == {"phone": "0912345678", "address": "12 Nguyễn Trãi, Hà Nội"}


def test_confirmation_only_lists_provided():
    text = render_confirmation(FIELDS)
    assert "0912345678" in text
    assert "Nguyễn Trãi" in text
    # Không được hiện field khách chưa nói
    assert "Sản phẩm" not in text
    assert "Size" not in text
    assert "Màu" not in text


def test_confirmation_asks_for_missing_phone():
    fields = {**FIELDS, "phone": None}
    assert missing_required(fields) == ["phone"]
    text = render_confirmation(fields)
    assert "số điện thoại" in text


def test_confirmation_complete_when_required_present():
    text = render_confirmation(FIELDS)
    assert "lên đơn" in text
    assert "số điện thoại" not in text


def test_staff_alert_contains_raw_text_and_missing():
    fields = {**FIELDS, "address": None}
    alert = render_staff_alert(fields, "chốt cho chị nhé 0912345678", "telegram 111")
    assert "CHỐT ĐƠN" in alert
    assert "chốt cho chị nhé" in alert
    assert "địa chỉ" in alert  # cảnh báo thiếu
